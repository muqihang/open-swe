from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agent import webapp
from agent.jarvis_bridge.context_transport import (
    build_controller_message,
    build_run_create_payload,
    extract_controller_payload_from_messages,
)
from agent.middleware.check_message_queue import _build_blocks_from_payload
from agent.middleware.open_pr import open_pr_if_needed


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
        "escalation_semantics": {"verdict": "repairable"},
        "rule_attachment_summary": {"rule_attachments_loaded": ["AGENTS.md"]},
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


def test_open_pr_middleware_returns_canonical_receipt_when_installation_token_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "agent.middleware.open_pr.get_config",
        lambda: {
            "configurable": {
                "thread_id": "thread-123",
                "repo": {"owner": "langchain-ai", "name": "open-swe"},
            },
            "metadata": {"branch_name": "feature/jarvis-sync"},
        },
    )
    monkeypatch.setattr("agent.middleware.open_pr.get_github_token", lambda: "token")
    monkeypatch.setattr(
        "agent.middleware.open_pr.resolve_triggering_user_identity",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "agent.middleware.open_pr.add_pr_collaboration_note",
        lambda body, _identity: body,
    )
    monkeypatch.setattr(
        "agent.middleware.open_pr.add_user_coauthor_trailer",
        lambda message, _identity: message,
    )

    async def fake_get_installation_token() -> None:
        return None

    monkeypatch.setattr(
        "agent.middleware.open_pr.get_github_app_installation_token",
        fake_get_installation_token,
    )

    result = asyncio.run(
        open_pr_if_needed.aafter_agent(
            state={
                "messages": [
                    build_controller_message(
                        {
                            "task_summary": {"summary": "preserve controller handoff"},
                            "run_artifacts": {
                                "latest_slots": {
                                    "latest_handoff": {"path": "reports/handoff.json"},
                                    "latest_repair_bundle": {"path": "reports/repair.json"},
                                }
                            },
                        }
                    ),
                    {
                        "name": "commit_and_open_pr",
                        "content": {
                            "title": "feat: preserve receipts [closes OPS-1]",
                            "body": "## Description\nKeep canonical continuity.\n\n## Test Plan\n- [ ] Verify degraded writeback blocks cleanly",
                            "commit_message": "preserve continuity on failure",
                        },
                    },
                ]
            },
            runtime=SimpleNamespace(),
        )
    )

    assert result == {
        "run_artifacts": {
            "latest_slots": {
                "latest_handoff": {
                    "status": "missing_installation_token",
                    "branch_name": "feature/jarvis-sync",
                },
                "latest_repair_bundle": {
                    "status": "missing_installation_token",
                    "branch_name": "feature/jarvis-sync",
                },
            }
        },
        "task_summary": {"summary": "preserve controller handoff"},
    }


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
