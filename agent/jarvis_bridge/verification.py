from __future__ import annotations

from typing import Any


def build_verification_bundle(
    summary: str,
    *,
    degraded_reasons: list[str] | None = None,
) -> dict[str, Any]:
    bundle: dict[str, Any] = {"summary": summary}
    if degraded_reasons:
        bundle["degraded_reasons"] = degraded_reasons
    return bundle


def allow_writeback(bundle: dict[str, Any] | None) -> bool:
    if not bundle:
        return True
    reasons = bundle.get("degraded_reasons")
    return not (isinstance(reasons, list) and reasons)


def resolve_verification_bundle(
    *,
    controller_payload: dict[str, Any] | None = None,
    configurable: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve verification bundle from known controller lanes."""
    if isinstance(controller_payload, dict):
        bundle = controller_payload.get("verification_bundle")
        if isinstance(bundle, dict):
            return bundle
    if isinstance(configurable, dict):
        bundle = configurable.get("verification_bundle") or configurable.get(
            "jarvis_verification_bundle"
        )
        if isinstance(bundle, dict):
            return bundle
    return None


def writeback_blocked_by_verification(bundle: dict[str, Any] | None) -> bool:
    """Return whether verification state should block writeback."""
    if not bundle:
        return False
    status = bundle.get("status")
    if isinstance(status, str) and status.lower() in {"degraded", "blocked", "hard-stop"}:
        return True
    return not allow_writeback(bundle)
