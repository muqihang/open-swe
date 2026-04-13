from __future__ import annotations

from typing import Any

from .contracts import (
    JARVIS_LATEST_HANDOFF_KEY,
    JARVIS_LATEST_REPAIR_BUNDLE_KEY,
    JARVIS_LATEST_SLOTS_KEY,
    JARVIS_RUN_ARTIFACTS_KEY,
    JARVIS_TASK_SUMMARY_KEY,
)


def _build_latest_slots(
    latest_handoff: dict[str, Any] | None,
    latest_repair_bundle: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_slots: dict[str, Any] = {}
    if latest_handoff is not None:
        latest_slots[JARVIS_LATEST_HANDOFF_KEY] = latest_handoff
    if latest_repair_bundle is not None:
        latest_slots[JARVIS_LATEST_REPAIR_BUNDLE_KEY] = latest_repair_bundle
    return latest_slots


def build_canonical_receipt(
    *,
    latest_handoff: dict[str, Any] | None = None,
    latest_repair_bundle: dict[str, Any] | None = None,
    task_summary: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    latest_slots = _build_latest_slots(latest_handoff, latest_repair_bundle)
    if latest_slots:
        payload[JARVIS_RUN_ARTIFACTS_KEY] = {JARVIS_LATEST_SLOTS_KEY: latest_slots}
    if task_summary:
        payload[JARVIS_TASK_SUMMARY_KEY] = task_summary
    return payload


def build_writeback_receipt(
    *,
    branch_name: str,
    status: str,
    pr_url: str | None = None,
    pr_existing: bool | None = None,
    task_summary: Any | None = None,
) -> dict[str, Any]:
    """Build a canonical writeback receipt."""
    latest_handoff: dict[str, Any] = {
        "status": status,
        "branch_name": branch_name,
    }
    latest_repair_bundle: dict[str, Any] = {
        "status": status,
        "branch_name": branch_name,
    }
    if pr_url:
        latest_handoff["pr_url"] = pr_url
        latest_repair_bundle["pr_url"] = pr_url
    if pr_existing is not None:
        latest_repair_bundle["pr_existing"] = pr_existing

    return build_canonical_receipt(
        latest_handoff=latest_handoff,
        latest_repair_bundle=latest_repair_bundle,
        task_summary=task_summary,
    )


def apply_canonical_receipt(
    payload: dict[str, Any],
    *,
    latest_handoff: dict[str, Any] | None = None,
    latest_repair_bundle: dict[str, Any] | None = None,
    task_summary: str | None = None,
) -> dict[str, Any]:
    updated = dict(payload)
    receipt = build_canonical_receipt(
        latest_handoff=latest_handoff,
        latest_repair_bundle=latest_repair_bundle,
        task_summary=task_summary,
    )
    if not receipt:
        return updated

    run_artifacts = receipt.get(JARVIS_RUN_ARTIFACTS_KEY)
    if isinstance(run_artifacts, dict):
        existing = updated.get(JARVIS_RUN_ARTIFACTS_KEY)
        merged = dict(existing) if isinstance(existing, dict) else {}
        incoming_slots = run_artifacts.get(JARVIS_LATEST_SLOTS_KEY)
        if isinstance(incoming_slots, dict):
            current_slots = merged.get(JARVIS_LATEST_SLOTS_KEY)
            merged_slots = dict(current_slots) if isinstance(current_slots, dict) else {}
            merged_slots.update(incoming_slots)
            merged[JARVIS_LATEST_SLOTS_KEY] = merged_slots
        updated[JARVIS_RUN_ARTIFACTS_KEY] = merged

    if JARVIS_TASK_SUMMARY_KEY in receipt:
        updated[JARVIS_TASK_SUMMARY_KEY] = receipt[JARVIS_TASK_SUMMARY_KEY]

    return updated


def resolve_task_summary(
    controller_payload: dict[str, Any] | None = None,
    configurable: dict[str, Any] | None = None,
) -> Any | None:
    """Resolve task summary from controller payload or config."""
    if isinstance(controller_payload, dict) and JARVIS_TASK_SUMMARY_KEY in controller_payload:
        return controller_payload[JARVIS_TASK_SUMMARY_KEY]
    if isinstance(configurable, dict) and JARVIS_TASK_SUMMARY_KEY in configurable:
        return configurable[JARVIS_TASK_SUMMARY_KEY]
    return None
