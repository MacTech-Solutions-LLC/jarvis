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
        lines.append(f"MACTECH SUITE — LIVE OPS BRIEFING (generated {self.generated_at})")

        s = self.status
        lines.append("")
        lines.append("Overview:")
        lines.append(f"  Registered active apps: {s.get('totalApps', 'unknown')}")
        by_health = s.get("byHealth") or {}
        if by_health:
            health_str = ", ".join(f"{k}={v}" for k, v in by_health.items())
            lines.append(f"  Health breakdown: {health_str}")
        lines.append(f"  Open risk flags: {s.get('openRiskCount', 0)}")
        lines.append(f"  Critical/high risks: {s.get('criticalRiskCount', 0)}")
        if s.get("appsMissingHealthUrl"):
            lines.append(f"  Apps with no health endpoint: {s.get('appsMissingHealthUrl')}")
        if s.get("lastReconciliationAt"):
            lines.append(
                f"  Last reconciliation: {s.get('lastReconciliationAt')}"
                f" ({s.get('lastReconciliationOutcome') or 'unknown'})"
            )

        lines.append("")
        lines.append("Apps:")
        for app in self.apps[:max_apps]:
            health = app.get("health") or {}
            health_str = health.get("status", "unknown")
            if health.get("latencyMs") is not None:
                health_str += f" ({health['latencyMs']}ms)"
            bits = [
                f"  - {app.get('name')} [{app.get('appKey')}]",
                f"health={health_str}",
                f"criticality={app.get('criticality')}",
                f"lifecycle={app.get('lifecycle')}",
            ]
            if app.get("repoFullName"):
                bits.append(f"repo={app['repoFullName']}")
            if app.get("publicUrl"):
                bits.append(f"url={app['publicUrl']}")
            lines.append(" | ".join(bits))
            for risk in app.get("openRisks") or []:
                lines.append(
                    f"      risk: [{risk.get('severity')}] "
                    f"{risk.get('category')} — {risk.get('title')}"
                )

        if self.deployments:
            lines.append("")
            lines.append("Deployments (Railway):")
            for dep in self.deployments:
                latest = dep.get("latest") or {}
                bits = [
                    f"  - {dep.get('serviceName') or 'unknown'}"
                    f" ({dep.get('projectName') or 'unknown'}/"
                    f"{dep.get('environmentName') or 'unknown'})",
                ]
                if dep.get("appKey"):
                    bits.append(f"app={dep['appKey']}")
                if latest.get("status"):
                    bits.append(f"status={latest['status']}")
                if latest.get("branch"):
                    bits.append(f"branch={latest['branch']}")
                if latest.get("commitSha"):
                    bits.append(f"commit={latest['commitSha']}")
                if latest.get("driftStatus") and latest["driftStatus"] != "unknown":
                    drift = latest["driftStatus"]
                    if latest.get("commitsBehind"):
                        drift += f" ({latest['commitsBehind']} behind)"
                    bits.append(f"drift={drift}")
                lines.append(" | ".join(bits))

        return "\n".join(lines)


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
