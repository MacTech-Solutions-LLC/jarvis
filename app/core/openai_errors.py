"""Turn OpenAI HTTP errors into messages an operator can act on.

Shared by the chat provider and the voice module because they fail the
same way. The case that matters: OpenAI returns 429 both for genuine
rate limiting and for an account that has run out of credit. Those
demand opposite responses — wait, versus go fix billing — and the raw
"429 Too Many Requests" points at the wrong one.
"""

from __future__ import annotations

import httpx

BILLING_URL = "platform.openai.com/settings/organization/billing"


class OpenAIError(RuntimeError):
    """An OpenAI call failed, carrying a message worth showing an operator."""


def explain_openai_failure(response: httpx.Response) -> str:
    """Describe a non-200 OpenAI response in terms of what to do next."""
    try:
        error = response.json().get("error", {})
    except Exception:
        error = {}

    code = error.get("code") or ""
    message = error.get("message") or response.text[:200]

    if code == "insufficient_quota":
        return (
            "The OpenAI account has no remaining quota. Add credit or raise the "
            f"billing limit at {BILLING_URL}, then try again."
        )
    if response.status_code == 401:
        return "OpenAI rejected the API key (401). Check OPENAI_API_KEY."
    if response.status_code == 429:
        return f"OpenAI is rate limiting requests. {message}"
    return f"OpenAI request failed (HTTP {response.status_code}). {message}"


def raise_for_openai_status(response: httpx.Response) -> None:
    """Raise OpenAIError with an actionable message on any non-200."""
    if response.status_code != 200:
        raise OpenAIError(explain_openai_failure(response))
