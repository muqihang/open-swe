from __future__ import annotations

import asyncio

from agent import webapp
from agent.jarvis_bridge.context_transport import (
    build_controller_message,
    build_run_create_payload,
    extract_controller_payload_from_messages,
)
from agent.middleware.check_message_queue import _build_blocks_from_payload


def test_build_run_create_payload_preserves_controller_first_mapping() -> None:
    controller_payload = {
        "context_pack": {"current_truth_refs": ["docs/current-state.md"]},
        "repo_rules_pack": {"repo_rules_digest": "digest-123"},
        "verification_bundle": {"status": "pass"},
        "run_artifacts": {
            "latest_slots": {
                "latest_handoff": {"path": "reports/handoff.json"},
                "latest_repair_bundle": {"path": "reports/repair.json"},
            }
        },
        "task_summary": {"summary": "controller handoff"},
    }
    payload = build_run_create_payload(
        thread_id="thread-123",
        message_content="Apply the queued repair bundle.",
        configurable={
            "repo": {"owner": "langchain-ai", "name": "open-swe"},
            "source": "controller",
            "user_email": "controller@example.com",
            "github_login": "controller-bot",
            "github_user_id": 42,
        },
        metadata={"LANGSMITH_AGENT_VERSION": "test-version"},
        branch_name="feature/jarvis-sync",
        controller_payload=controller_payload,
    )

    assert payload["thread_id"] == "thread-123"
    assert payload["assistant_id"] == "agent"
    assert payload["config"]["configurable"]["repo"] == {
        "owner": "langchain-ai",
        "name": "open-swe",
    }
    assert payload["config"]["configurable"]["source"] == "controller"
    assert payload["config"]["configurable"]["user_email"] == "controller@example.com"
    assert payload["config"]["configurable"]["github_login"] == "controller-bot"
    assert payload["config"]["metadata"]["branch_name"] == "feature/jarvis-sync"

    content = payload["input"]["messages"][0]["content"]
    assert isinstance(content, list)
    assert content[0]["text"] == "Apply the queued repair bundle."
    extracted = extract_controller_payload_from_messages(payload["input"]["messages"])
    assert extracted == controller_payload


def test_queue_payload_builder_preserves_structured_jarvis_payload() -> None:
    blocks = asyncio.run(
        _build_blocks_from_payload(
            {
                "text": "Please continue from the latest handoff.",
                "controller_payload": {
                    "run_artifacts": {
                        "latest_slots": {
                            "latest_handoff": {"path": "reports/handoff.json"},
                            "latest_repair_bundle": {"path": "reports/repair.json"},
                        }
                    },
                    "task_summary": {"summary": "continue from handoff"},
                },
            }
        )
    )

    assert len(blocks) == 2
    assert blocks[0]["text"] == "Please continue from the latest handoff."
    extracted = extract_controller_payload_from_messages([{"role": "user", "content": blocks}])
    assert extracted == {
        "run_artifacts": {
            "latest_slots": {
                "latest_handoff": {"path": "reports/handoff.json"},
                "latest_repair_bundle": {"path": "reports/repair.json"},
            }
        },
        "task_summary": {"summary": "continue from handoff"},
    }


def test_extract_controller_payload_from_custom_blocks() -> None:
    payload = {
        "verification_bundle": {"status": "degraded", "degraded_reasons": ["tests_not_run"]},
        "task_summary": {"summary": "controller handoff"},
    }

    extracted = extract_controller_payload_from_messages([build_controller_message(payload)])

    assert extracted == payload


def test_process_controller_invocation_uses_real_run_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_is_thread_active(thread_id: str) -> bool:
        assert thread_id == "thread-123"
        return False

    async def fake_create_agent_run(**kwargs):
        captured.update(kwargs)
        return {"run_id": "run-123"}

    monkeypatch.setattr(webapp, "is_thread_active", fake_is_thread_active)
    monkeypatch.setattr(webapp, "_create_agent_run", fake_create_agent_run)

    result = asyncio.run(
        webapp.process_controller_invocation(
            {
                "thread_id": "thread-123",
                "repo": {"owner": "langchain-ai", "name": "open-swe"},
                "source": "controller",
                "user_email": "controller@example.com",
                "github_login": "controller-bot",
                "github_user_id": 42,
                "branch_name": "feature/jarvis-sync",
                "message_content": "Apply the repair bundle.",
                "controller_payload": {
                    "context_pack": {"current_truth_refs": ["docs/current-state.md"]},
                    "verification_bundle": {"status": "pass"},
                    "task_summary": {"summary": "controller handoff"},
                },
            }
        )
    )

    assert result == {"status": "started", "thread_id": "thread-123", "run_id": "run-123"}
    assert captured["branch_name"] == "feature/jarvis-sync"
    assert captured["controller_payload"] == {
        "context_pack": {"current_truth_refs": ["docs/current-state.md"]},
        "verification_bundle": {"status": "pass"},
        "task_summary": {"summary": "controller handoff"},
    }
    assert captured["configurable"] == {
        "repo": {"owner": "langchain-ai", "name": "open-swe"},
        "source": "controller",
        "user_email": "controller@example.com",
        "github_login": "controller-bot",
        "github_user_id": 42,
    }


def test_trigger_or_queue_run_forwards_branch_name_to_real_run_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_is_thread_active(thread_id: str) -> bool:
        assert thread_id == "thread-123"
        return False

    async def fake_create_agent_run(**kwargs):
        captured.update(kwargs)
        return {"run_id": "run-123"}

    monkeypatch.setattr(webapp, "is_thread_active", fake_is_thread_active)
    monkeypatch.setattr(webapp, "_create_agent_run", fake_create_agent_run)

    asyncio.run(
        webapp._trigger_or_queue_run(
            "thread-123",
            "Please address the PR feedback.",
            github_login="reviewer",
            github_user_id=7,
            repo_config={"owner": "langchain-ai", "name": "open-swe"},
            pr_number=123,
            branch_name="feature/pr-123",
        )
    )

    assert captured["branch_name"] == "feature/pr-123"
    assert captured["configurable"] == {
        "source": "github",
        "github_login": "reviewer",
        "github_user_id": 7,
        "repo": {"owner": "langchain-ai", "name": "open-swe"},
        "pr_number": 123,
    }
