from typing import Any


def redact_finding_evidence(result: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(result)
    for key in ("findings", "ai_findings"):
        redacted[key] = [
            {**finding, "evidence": None}
            for finding in result.get(key, [])
        ]
    return redacted
