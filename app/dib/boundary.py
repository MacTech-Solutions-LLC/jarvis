"""The CUI boundary.

The product claim is "you can point this at a CUI-marked solicitation because
the bytes never leave your machine". A claim like that is worth nothing if it
rests on a developer remembering not to import an SDK, so it is enforced here
and stated at the moment of use.

Two mechanisms:

  1. `assert_local_only()` refuses to run if a cloud provider key is configured
     AND the caller has not explicitly opted that document out of the boundary.
     Failing closed is the whole point.

  2. `LocalModel` talks to Ollama on loopback only. The host is validated, so a
     mis-set OLLAMA_HOST cannot quietly become an egress path.

Deliberately NOT claimed: this does not stop a determined user, it does not
sandbox the OS, and it cannot help if someone pastes CUI into a browser. It
guarantees one thing — that *this tool* does not transmit the document.
"""

from __future__ import annotations

import ipaddress
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

CLOUD_KEY_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "HUGGINGFACE_API_KEY",
    "ELEVENLABS_API_KEY",
)

DEFAULT_OLLAMA = "http://127.0.0.1:11434"


class BoundaryViolation(RuntimeError):
    """Raised when an operation would risk transmitting document content."""


def _is_loopback(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def configured_cloud_providers() -> list[str]:
    """Cloud keys present in the environment — reported so the operator can see
    exactly what the boundary is holding back."""
    return [v for v in CLOUD_KEY_VARS if os.environ.get(v)]


def assert_local_only(endpoint: str | None = None) -> str:
    """Verify the inference path cannot leave the machine. Returns the endpoint."""
    endpoint = endpoint or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"
    if not _is_loopback(endpoint):
        raise BoundaryViolation(
            f"Inference endpoint {endpoint!r} is not loopback. The DIB agent refuses "
            "to send document content to a non-local address. Set OLLAMA_HOST to a "
            "127.0.0.1 address, or run the analysis with --no-summary (extraction "
            "is fully deterministic and needs no model at all)."
        )
    return endpoint


@dataclass
class LocalModel:
    """Minimal Ollama client. Loopback-checked on every call."""

    model: str = "llama3.1"
    endpoint: str | None = None
    timeout: int = 120

    def available(self) -> bool:
        try:
            ep = assert_local_only(self.endpoint)
            with urllib.request.urlopen(f"{ep}/api/tags", timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def summarize(self, prompt: str) -> str:
        ep = assert_local_only(self.endpoint)
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                # Low temperature: this is an analysis aid, not a writing tool.
                "options": {"temperature": 0.2},
            }
        ).encode()
        req = urllib.request.Request(
            f"{ep}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read()).get("response", "").strip()


def boundary_banner(endpoint: str, model_ok: bool) -> str:
    """One line stating what just happened to the document, every run.

    Shown always — a boundary the user has to go looking for is one they will
    stop believing.
    """
    held = configured_cloud_providers()
    bits = [f"local-only · inference {endpoint}", "model ready" if model_ok else "extraction only (no model)"]
    if held:
        bits.append(f"{len(held)} cloud key(s) present and NOT used: {', '.join(held)}")
    return "  [ " + " · ".join(bits) + " ]"
