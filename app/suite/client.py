"""Client for the MacTech Suite command-center briefing.

The Suite exposes GET /api/command-center/briefing — a read-only,
token-authenticated snapshot of every registered app: health, open
risks, and Railway deployment state. This module fetches it and renders
it down to a compact text block that fits comfortably in an LLM context
window, so Jarvis can answer questions about the suite from live data
instead of guessing.

Configuration (environment):
    SUITE_BASE_URL              e.g. https://www.suite.mactechsolutionsllc.com
    SUITE_AGENT_BRIEFING_TOKEN  bearer token matching the Suite's value
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = "https://www.suite.mactechsolutionsllc.com"

# The briefing is rebuilt from the database on every request, but the
# underlying data only changes when the sync cron runs (every 5 min).
# Cache locally so a chat turn that mentions the suite three times
# doesn't make three round trips.
CACHE_TTL_SECONDS = 120


class SuiteUnavailable(RuntimeError):
    """Raised when the briefing cannot be fetched or is not configured."""


@dataclass
class SuiteBriefing:
    """A parsed briefing plus the helpers that turn it into prompt text."""

    generated_at: str
    status: dict[str, Any]
    apps: list[dict[str, Any]] = field(default_factory=list)
    deployments: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SuiteBriefing":
        return cls(
            generated_at=payload.get("generatedAt", ""),
            status=payload.get("status") or {},
            apps=payload.get("apps") or [],
            deployments=payload.get("deployments") or [],
        )

    # ── Summary helpers ───────────────────────────────────────────────

    @property
    def unhealthy_apps(self) -> list[dict[str, Any]]:
        return [
            a
            for a in self.apps
            if (a.get("health") or {}).get("status") in {"down", "degraded"}
        ]

    @property
    def risk_count(self) -> int:
        return sum(len(a.get("openRisks") or []) for a in self.apps)

    def to_prompt_context(self, max_apps: int = 40) -> str:
        """Render the briefing as the context block handed to the model.

        Deliberately terse and factual. Every line is something the
        Suite actually measured — no derived or estimated numbers, so
        the assistant can quote figures without inventing them.
        """
        lines: list[str] = []
        s = self.status

        by_health = s.get("byHealth") or {}
        health_str = " ".join(f"{k}={v}" for k, v in by_health.items() if v)
        lines.append(f"MACTECH SUITE — LIVE OPS ({_short_time(self.generated_at)})")
        lines.append(
            f"{s.get('totalApps', '?')} active apps ({health_str}); "
            f"{s.get('openRiskCount', 0)} open risks, "
            f"{s.get('criticalRiskCount', 0)} critical/high"
        )
        if s.get("lastReconciliationAt"):
            lines.append(
                f"Reconciled {_short_time(s['lastReconciliationAt'])}"
                f" ({s.get('lastReconciliationOutcome') or 'unknown'})."
                " Repos are MacTech-Solutions-LLC/* unless shown otherwise."
            )

        # Apps split by whether they need a decision. Anything unhealthy
        # or carrying a risk gets full detail — that is what gets asked
        # about. The healthy remainder collapses to a name list: naming
        # them proves they exist and are fine, which is all a reply needs.
        flagged = [a for a in self.apps if _needs_attention(a)]
        clean = [a for a in self.apps if not _needs_attention(a)]

        if flagged:
            lines.append("")
            lines.append("NEEDS ATTENTION:")
            for app in flagged[:max_apps]:
                health = app.get("health") or {}
                bits = [
                    f"- {app.get('name')} [{app.get('appKey')}]",
                    health.get("status", "unknown"),
                    str(app.get("criticality")),
                ]
                if app.get("lifecycle") and app["lifecycle"] != "production":
                    bits.append(str(app["lifecycle"]))
                if app.get("repoFullName"):
                    bits.append(_short_repo(app["repoFullName"]))
                lines.append(" | ".join(bits))
                for risk in app.get("openRisks") or []:
                    title = _trim_prefix(risk.get("title") or "", app.get("name") or "")
                    lines.append(
                        f"    [{risk.get('severity')}] {risk.get('category')} — {title}"
                    )

        if clean:
            lines.append("")
            lines.append(
                f"HEALTHY, NO RISKS ({len(clean)}): "
                + ", ".join(a.get("appKey", "?") for a in clean)
            )

        # Deployments: a service that deployed successfully and is in
        # sync tells you nothing you would ask about. Print the
        # exceptions and count the rest.
        if self.deployments:
            odd = [d for d in self.deployments if _deploy_is_notable(d)]
            lines.append("")
            if odd:
                lines.append("DEPLOYMENTS — NOTABLE:")
                for dep in odd:
                    latest = dep.get("latest") or {}
                    bits = [f"- {dep.get('serviceName') or '?'}"]
                    if dep.get("appKey"):
                        bits.append(f"app={dep['appKey']}")
                    if latest.get("status"):
                        bits.append(str(latest["status"]))
                    if latest.get("commitSha"):
                        bits.append(f"{latest.get('branch') or '?'} {latest['commitSha']}")
                    drift = latest.get("driftStatus")
                    if drift and drift not in {"unknown", "in_sync"}:
                        behind = latest.get("commitsBehind")
                        bits.append(f"{drift}{f' by {behind}' if behind else ''}")
                    lines.append(" | ".join(bits))
            rest = len(self.deployments) - len(odd)
            if rest > 0:
                lines.append(
                    f"{rest} other services: latest deploy succeeded, no drift flagged."
                )

        return "\n".join(lines)


def _needs_attention(app: dict[str, Any]) -> bool:
    return bool(
        (app.get("health") or {}).get("status") in {"down", "degraded"}
        or app.get("openRisks")
    )


# Drift values that mean production actually diverges from the repo.
# "unknown" is excluded deliberately: it means the comparison could not
# be computed, which is not something to act on, and printing ~5 such
# rows costs tokens while telling the model nothing.
REAL_DRIFT = {"behind", "ahead", "diverged"}


def _deploy_is_notable(dep: dict[str, Any]) -> bool:
    """True when a deploy failed, is missing, or genuinely drifted."""
    latest = dep.get("latest")
    if not latest:
        return True
    if latest.get("status") != "success":
        return True
    return latest.get("driftStatus") in REAL_DRIFT


def _short_time(timestamp: str) -> str:
    """2026-07-28T06:20:23.990Z -> 07-28 06:20Z. Seconds never matter here."""
    if not timestamp or len(timestamp) < 16:
        return timestamp or "unknown"
    return f"{timestamp[5:10]} {timestamp[11:16]}Z"


def _short_repo(full_name: str) -> str:
    """Drop the org prefix that is identical across ~20 of the repos."""
    prefix = "MacTech-Solutions-LLC/"
    return full_name[len(prefix):] if full_name.startswith(prefix) else full_name


def _trim_prefix(title: str, app_name: str) -> str:
    """Risk titles repeat the app name already printed on the line above."""
    if app_name and title.startswith(app_name):
        trimmed = title[len(app_name):].lstrip(" -—:")
        if trimmed:
            return trimmed[0].upper() + trimmed[1:]
    return title


class SuiteClient:
    """Fetches (and briefly caches) the Suite ops briefing."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 20.0,
    ):
        self.base_url = (base_url or os.getenv("SUITE_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.token = token or os.getenv("SUITE_AGENT_BRIEFING_TOKEN")
        self.timeout = timeout
        self._cache: Optional[SuiteBriefing] = None
        self._cache_at: float = 0.0

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def fetch(self, force: bool = False) -> SuiteBriefing:
        """Return the briefing, using the local cache when it is fresh."""
        if not self.configured:
            raise SuiteUnavailable(
                "SUITE_AGENT_BRIEFING_TOKEN is not set — Jarvis cannot reach the Suite."
            )

        now = time.monotonic()
        if not force and self._cache and (now - self._cache_at) < CACHE_TTL_SECONDS:
            return self._cache

        url = f"{self.base_url}/api/command-center/briefing"
        try:
            response = httpx.get(
                url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise SuiteUnavailable(f"Could not reach the Suite at {url}: {exc}") from exc

        if response.status_code == 401:
            raise SuiteUnavailable(
                "Suite rejected the briefing token (401). Check that "
                "SUITE_AGENT_BRIEFING_TOKEN matches the Suite's value."
            )
        if response.status_code == 503:
            raise SuiteUnavailable(
                "Suite has no briefing token configured (503). Set "
                "SUITE_AGENT_BRIEFING_TOKEN on the Suite service."
            )
        if response.status_code != 200:
            raise SuiteUnavailable(
                f"Suite briefing returned HTTP {response.status_code}."
            )

        payload = response.json()
        if not payload.get("ok"):
            raise SuiteUnavailable(
                f"Suite briefing error: {payload.get('error', 'unknown')}"
            )

        briefing = SuiteBriefing.from_payload(payload)
        self._cache = briefing
        self._cache_at = now
        return briefing
