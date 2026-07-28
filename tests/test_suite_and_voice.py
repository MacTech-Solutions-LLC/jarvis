"""Tests for the Suite briefing client and the Jarvis voice.

Neither test hits the network. The briefing test feeds a payload shaped
like the Suite's real response through the renderer; the voice tests
cover the markdown stripping that decides what actually gets spoken.
"""

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.openai_errors import explain_openai_failure
from app.media.voice import _strip_for_speech
from app.suite.client import SuiteBriefing, SuiteClient, SuiteUnavailable


SAMPLE_PAYLOAD = {
    "ok": True,
    "generatedAt": "2026-07-27T12:00:00.000Z",
    "status": {
        "totalApps": 3,
        "byHealth": {"healthy": 2, "down": 1},
        "openRiskCount": 2,
        "criticalRiskCount": 1,
        "appsMissingHealthUrl": 1,
        "lastReconciliationAt": "2026-07-27T11:55:00.000Z",
        "lastReconciliationOutcome": "ok",
    },
    "apps": [
        {
            "appKey": "quality",
            "name": "MacTech Quality (QMS)",
            "category": "compliance",
            "criticality": "high",
            "lifecycle": "production",
            "publicUrl": "https://quality.mactechsolutionsllc.com",
            "repoFullName": "MacTech-Solutions-LLC/QMS",
            "health": {
                "status": "healthy",
                "statusCode": 200,
                "latencyMs": 142,
                "checkedAt": "2026-07-27T11:55:00.000Z",
            },
            "openRisks": [],
        },
        {
            "appKey": "jarvis",
            "name": "Jarvis",
            "category": "other",
            "criticality": "medium",
            "lifecycle": "production",
            "publicUrl": "https://jarvis-production-7dc3.up.railway.app",
            "repoFullName": "MacTech-Solutions-LLC/jarvis",
            "health": {
                "status": "down",
                "statusCode": 503,
                "latencyMs": None,
                "checkedAt": "2026-07-27T11:55:00.000Z",
            },
            "openRisks": [
                {
                    "category": "availability",
                    "severity": "critical",
                    "title": "Health endpoint unreachable",
                }
            ],
        },
    ],
    "deployments": [
        {
            "appKey": "jarvis",
            "projectName": "jarvis",
            "serviceName": "jarvis",
            "environmentName": "production",
            "publicDomain": "jarvis-production-7dc3.up.railway.app",
            "latest": {
                "status": "success",
                "branch": "main",
                "commitSha": "0266be6",
                "driftStatus": "behind",
                "commitsBehind": 2,
                "checkedAt": "2026-07-27T11:55:00.000Z",
            },
            "lastSuccessfulCheckAt": "2026-07-27T11:55:00.000Z",
        }
    ],
}


def test_briefing_parses_payload():
    briefing = SuiteBriefing.from_payload(SAMPLE_PAYLOAD)
    assert briefing.generated_at == "2026-07-27T12:00:00.000Z"
    assert len(briefing.apps) == 2
    assert len(briefing.deployments) == 1


def test_unhealthy_apps_and_risk_count():
    briefing = SuiteBriefing.from_payload(SAMPLE_PAYLOAD)
    unhealthy = briefing.unhealthy_apps
    assert [a["appKey"] for a in unhealthy] == ["jarvis"]
    assert briefing.risk_count == 1


def test_prompt_context_includes_the_facts_a_reply_would_cite():
    context = SuiteBriefing.from_payload(SAMPLE_PAYLOAD).to_prompt_context()
    # Names and keys so the model can refer to apps the way the operator does.
    assert "MacTech Quality (QMS)" in context
    assert "[jarvis]" in context
    # Health, risk, and drift are the three things worth asking about.
    assert "health=down" in context
    assert "critical" in context
    assert "drift=behind (2 behind)" in context


def test_prompt_context_caps_app_count():
    payload = dict(SAMPLE_PAYLOAD)
    payload["apps"] = SAMPLE_PAYLOAD["apps"] * 30
    context = SuiteBriefing.from_payload(payload).to_prompt_context(max_apps=5)
    assert context.count("  - ") <= 5 + len(SAMPLE_PAYLOAD["deployments"])


def test_client_without_token_refuses_to_fetch():
    client = SuiteClient(base_url="https://example.invalid", token=None)
    assert not client.configured
    with pytest.raises(SuiteUnavailable):
        client.fetch()


def test_strip_for_speech_drops_code_fences():
    spoken = _strip_for_speech("Run this:\n```bash\nrailway up --detach\n```\nDone.")
    assert "railway up" not in spoken
    assert "code omitted" in spoken
    assert "Done." in spoken


def _response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        json=payload,
        request=httpx.Request("POST", "https://api.openai.com/v1/audio/speech"),
    )


def test_quota_exhaustion_is_not_reported_as_rate_limiting():
    # OpenAI returns 429 for both "slow down" and "you have no money".
    # Only the second is actionable, and conflating them sends an
    # operator off to wait for a limit that will never clear.
    message = explain_openai_failure(
        _response(429, {"error": {"code": "insufficient_quota", "message": "quota"}})
    )
    assert "no remaining quota" in message
    assert "billing" in message


def test_real_rate_limiting_still_reads_as_rate_limiting():
    message = explain_openai_failure(
        _response(429, {"error": {"code": "rate_limit_exceeded", "message": "slow down"}})
    )
    assert "rate limiting" in message


def test_bad_key_is_named_as_a_key_problem():
    message = explain_openai_failure(
        _response(401, {"error": {"code": "invalid_api_key", "message": "nope"}})
    )
    assert "OPENAI_API_KEY" in message


def test_strip_for_speech_removes_markdown_scaffolding():
    spoken = _strip_for_speech(
        "## Status\n\n- **QMS** is healthy\n- See [the console](https://example.com)"
    )
    assert "##" not in spoken
    assert "**" not in spoken
    assert "https://example.com" not in spoken
    assert "the console" in spoken
    assert "QMS is healthy" in spoken
