from __future__ import annotations

from agent.jarvis_bridge.receipts import build_writeback_receipt, resolve_task_summary
from agent.jarvis_bridge.verification import (
    resolve_verification_bundle,
    writeback_blocked_by_verification,
)


def test_build_writeback_receipt_uses_canonical_keys() -> None:
    receipt = build_writeback_receipt(
        branch_name="feature/jarvis-sync",
        status="pr_created",
        pr_url="https://github.com/langchain-ai/open-swe/pull/123",
        pr_existing=False,
        task_summary={"summary": "controller handoff ready"},
    )

    assert receipt["run_artifacts"]["latest_slots"]["latest_handoff"] == {
        "status": "pr_created",
        "branch_name": "feature/jarvis-sync",
        "pr_url": "https://github.com/langchain-ai/open-swe/pull/123",
    }
    assert receipt["run_artifacts"]["latest_slots"]["latest_repair_bundle"] == {
        "status": "pr_created",
        "branch_name": "feature/jarvis-sync",
        "pr_url": "https://github.com/langchain-ai/open-swe/pull/123",
        "pr_existing": False,
    }
    assert receipt["task_summary"] == {"summary": "controller handoff ready"}


def test_verification_bundle_blocks_writeback_when_degraded() -> None:
    bundle = resolve_verification_bundle(
        controller_payload={
            "verification_bundle": {
                "status": "degraded",
                "degraded_reasons": ["tests_not_run"],
            }
        }
    )

    assert bundle == {
        "status": "degraded",
        "degraded_reasons": ["tests_not_run"],
    }
    assert writeback_blocked_by_verification(bundle) is True


def test_task_summary_prefers_controller_payload() -> None:
    task_summary = resolve_task_summary(
        controller_payload={"task_summary": {"summary": "use controller summary"}},
        configurable={"task_summary": {"summary": "use config summary"}},
    )

    assert task_summary == {"summary": "use controller summary"}
