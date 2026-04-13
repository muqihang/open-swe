from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agent.jarvis_bridge.context_transport import build_controller_message
from agent.middleware.open_pr import open_pr_if_needed


def _build_controller_payload(*, verification_status: str) -> dict[str, object]:
    return {
        "verification_bundle": {
            "status": verification_status,
            "degraded_reasons": ["tests_not_run"] if verification_status == "degraded" else [],
        },
        "run_artifacts": {
            "latest_slots": {
                "latest_handoff": {"path": "reports/handoff.json"},
                "latest_repair_bundle": {"path": "reports/repair.json"},
            }
        },
        "task_summary": {
            "summary": "preserve controller handoff",
            "next_actor": "open_swe_coding_worker",
            "unresolved": ["wait for verification green"],
        },
    }


def _build_config(*, branch_name: str = "feature/jarvis-sync") -> dict[str, object]:
    return {
        "configurable": {
            "thread_id": "thread-123",
            "repo": {"owner": "langchain-ai", "name": "open-swe"},
        },
        "metadata": {"branch_name": branch_name},
    }


def _build_pr_request() -> dict[str, object]:
    return {
        "name": "commit_and_open_pr",
        "content": {
            "title": "feat: preserve receipts [closes OPS-1]",
            "body": "## Description\nKeep canonical continuity.\n\n## Test Plan\n- [ ] Verify degraded writeback blocks cleanly",
            "commit_message": "preserve continuity on completion",
        },
    }


def test_open_pr_middleware_blocks_writeback_when_verification_is_degraded(monkeypatch) -> None:
    monkeypatch.setattr("agent.middleware.open_pr.get_config", lambda: _build_config())
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

    async def fake_get_installation_token() -> str:
        return "installation-token"

    async def fake_get_sandbox_backend(_thread_id: str) -> object:
        return object()

    async def fake_resolve_repo_dir(_sandbox_backend: object, _repo_name: str) -> str:
        return "/tmp/open-swe"

    monkeypatch.setattr(
        "agent.middleware.open_pr.get_github_app_installation_token",
        fake_get_installation_token,
    )
    monkeypatch.setattr("agent.middleware.open_pr.get_sandbox_backend", fake_get_sandbox_backend)
    monkeypatch.setattr("agent.middleware.open_pr.aresolve_repo_dir", fake_resolve_repo_dir)
    monkeypatch.setattr(
        "agent.middleware.open_pr.git_has_uncommitted_changes",
        lambda *_args: True,
    )
    monkeypatch.setattr("agent.middleware.open_pr.git_fetch_origin", lambda *_args: None)
    monkeypatch.setattr(
        "agent.middleware.open_pr.git_has_unpushed_commits",
        lambda *_args: False,
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("writeback should stop before git mutation")

    monkeypatch.setattr("agent.middleware.open_pr.git_current_branch", fail_if_called)
    monkeypatch.setattr("agent.middleware.open_pr.git_checkout_existing_branch", fail_if_called)
    monkeypatch.setattr("agent.middleware.open_pr.git_checkout_branch", fail_if_called)
    monkeypatch.setattr("agent.middleware.open_pr.git_config_user", fail_if_called)
    monkeypatch.setattr("agent.middleware.open_pr.git_add_all", fail_if_called)
    monkeypatch.setattr("agent.middleware.open_pr.git_commit", fail_if_called)
    monkeypatch.setattr("agent.middleware.open_pr.git_push", fail_if_called)

    async def fail_pr_creation(**_kwargs):
        raise AssertionError("writeback should stop before PR creation")

    monkeypatch.setattr("agent.middleware.open_pr.create_github_pr", fail_pr_creation)

    result = asyncio.run(
        open_pr_if_needed.aafter_agent(
            state={
                "messages": [
                    build_controller_message(
                        _build_controller_payload(verification_status="degraded")
                    ),
                    _build_pr_request(),
                ]
            },
            runtime=SimpleNamespace(),
        )
    )

    assert result == {
        "run_artifacts": {
            "latest_slots": {
                "latest_handoff": {
                    "status": "blocked_by_verification",
                    "branch_name": "feature/jarvis-sync",
                },
                "latest_repair_bundle": {
                    "status": "blocked_by_verification",
                    "branch_name": "feature/jarvis-sync",
                },
            }
        },
        "task_summary": {
            "summary": "preserve controller handoff",
            "next_actor": "open_swe_coding_worker",
            "unresolved": ["wait for verification green"],
        },
    }


def test_open_pr_middleware_returns_canonical_receipt_on_pr_safe_completion(monkeypatch) -> None:
    monkeypatch.setattr("agent.middleware.open_pr.get_config", lambda: _build_config())
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

    async def fake_get_installation_token() -> str:
        return "installation-token"

    async def fake_get_sandbox_backend(_thread_id: str) -> object:
        return object()

    async def fake_resolve_repo_dir(_sandbox_backend: object, _repo_name: str) -> str:
        return "/tmp/open-swe"

    async def fake_get_default_branch(*_args, **_kwargs) -> str:
        return "main"

    async def fake_create_pr(**_kwargs):
        return ("https://example.invalid/pull/123", 123, False)

    monkeypatch.setattr(
        "agent.middleware.open_pr.get_github_app_installation_token",
        fake_get_installation_token,
    )
    monkeypatch.setattr("agent.middleware.open_pr.get_sandbox_backend", fake_get_sandbox_backend)
    monkeypatch.setattr("agent.middleware.open_pr.aresolve_repo_dir", fake_resolve_repo_dir)
    monkeypatch.setattr(
        "agent.middleware.open_pr.git_has_uncommitted_changes",
        lambda *_args: True,
    )
    monkeypatch.setattr("agent.middleware.open_pr.git_fetch_origin", lambda *_args: None)
    monkeypatch.setattr(
        "agent.middleware.open_pr.git_has_unpushed_commits",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        "agent.middleware.open_pr.git_current_branch",
        lambda *_args: "feature/jarvis-sync",
    )
    monkeypatch.setattr("agent.middleware.open_pr.git_config_user", lambda *_args: None)
    monkeypatch.setattr("agent.middleware.open_pr.git_add_all", lambda *_args: None)
    monkeypatch.setattr(
        "agent.middleware.open_pr.git_commit",
        lambda *_args: SimpleNamespace(exit_code=0, output=""),
    )
    monkeypatch.setattr(
        "agent.middleware.open_pr.git_push",
        lambda *_args: SimpleNamespace(exit_code=0, output=""),
    )
    monkeypatch.setattr(
        "agent.middleware.open_pr.get_github_default_branch",
        fake_get_default_branch,
    )
    monkeypatch.setattr("agent.middleware.open_pr.create_github_pr", fake_create_pr)

    result = asyncio.run(
        open_pr_if_needed.aafter_agent(
            state={
                "messages": [
                    build_controller_message(_build_controller_payload(verification_status="pass")),
                    _build_pr_request(),
                ]
            },
            runtime=SimpleNamespace(),
        )
    )

    assert result == {
        "run_artifacts": {
            "latest_slots": {
                "latest_handoff": {
                    "status": "pr_created",
                    "branch_name": "feature/jarvis-sync",
                    "pr_url": "https://example.invalid/pull/123",
                },
                "latest_repair_bundle": {
                    "status": "pr_created",
                    "branch_name": "feature/jarvis-sync",
                    "pr_url": "https://example.invalid/pull/123",
                    "pr_existing": False,
                },
            }
        },
        "task_summary": {
            "summary": "preserve controller handoff",
            "next_actor": "open_swe_coding_worker",
            "unresolved": ["wait for verification green"],
        },
    }
