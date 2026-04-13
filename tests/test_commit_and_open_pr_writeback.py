from __future__ import annotations

import importlib
from types import SimpleNamespace


def _build_config(
    *,
    verification_status: str,
    branch_name: str = "feature/jarvis-sync",
) -> dict[str, object]:
    return {
        "configurable": {
            "thread_id": "thread-123",
            "repo": {"owner": "langchain-ai", "name": "open-swe"},
            "task_summary": {
                "summary": "preserve controller handoff",
                "next_actor": "open_swe_coding_worker",
                "unresolved": ["wait for verification green"],
            },
            "verification_bundle": {
                "status": verification_status,
                "degraded_reasons": ["tests_not_run"] if verification_status == "degraded" else [],
            },
        },
        "metadata": {"branch_name": branch_name},
    }


def test_commit_and_open_pr_blocks_writeback_when_verification_is_degraded(monkeypatch) -> None:
    commit_tool_module = importlib.import_module("agent.tools.commit_and_open_pr")

    monkeypatch.setattr(
        commit_tool_module,
        "get_config",
        lambda: _build_config(verification_status="degraded"),
    )
    monkeypatch.setattr(commit_tool_module, "get_sandbox_backend_sync", lambda _thread_id: object())
    monkeypatch.setattr(commit_tool_module, "resolve_repo_dir", lambda *_args: "/tmp/open-swe")
    monkeypatch.setattr(commit_tool_module, "get_github_token", lambda: "token")
    monkeypatch.setattr(
        commit_tool_module,
        "resolve_triggering_user_identity",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        commit_tool_module,
        "add_pr_collaboration_note",
        lambda body, _identity: body,
    )
    monkeypatch.setattr(
        commit_tool_module,
        "git_has_uncommitted_changes",
        lambda *_args: True,
    )
    monkeypatch.setattr(commit_tool_module, "git_fetch_origin", lambda *_args: None)
    monkeypatch.setattr(commit_tool_module, "git_has_unpushed_commits", lambda *_args: False)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("writeback should stop before git mutation")

    monkeypatch.setattr(commit_tool_module, "git_current_branch", fail_if_called)
    monkeypatch.setattr(commit_tool_module, "git_checkout_existing_branch", fail_if_called)
    monkeypatch.setattr(commit_tool_module, "git_checkout_branch", fail_if_called)
    monkeypatch.setattr(commit_tool_module, "git_config_user", fail_if_called)
    monkeypatch.setattr(commit_tool_module, "git_add_all", fail_if_called)
    monkeypatch.setattr(commit_tool_module, "git_commit", fail_if_called)
    monkeypatch.setattr(commit_tool_module, "git_push", fail_if_called)

    result = commit_tool_module.commit_and_open_pr(
        title="feat: preserve receipts [closes OPS-1]",
        body="## Description\nKeep canonical continuity.\n\n## Test Plan\n- [ ] Verify blocked writeback returns receipts",
    )

    assert result == {
        "success": False,
        "error": "Writeback blocked by verification bundle",
        "pr_url": None,
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


def test_commit_and_open_pr_returns_canonical_receipt_on_pr_safe_completion(monkeypatch) -> None:
    commit_tool_module = importlib.import_module("agent.tools.commit_and_open_pr")

    monkeypatch.setattr(
        commit_tool_module,
        "get_config",
        lambda: _build_config(verification_status="pass"),
    )
    monkeypatch.setattr(commit_tool_module, "get_sandbox_backend_sync", lambda _thread_id: object())
    monkeypatch.setattr(commit_tool_module, "resolve_repo_dir", lambda *_args: "/tmp/open-swe")
    monkeypatch.setattr(commit_tool_module, "get_github_token", lambda: "token")
    monkeypatch.setattr(
        commit_tool_module,
        "resolve_triggering_user_identity",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        commit_tool_module,
        "add_pr_collaboration_note",
        lambda body, _identity: body,
    )
    monkeypatch.setattr(
        commit_tool_module,
        "add_user_coauthor_trailer",
        lambda message, _identity: message,
    )
    monkeypatch.setattr(
        commit_tool_module,
        "git_has_uncommitted_changes",
        lambda *_args: True,
    )
    monkeypatch.setattr(commit_tool_module, "git_fetch_origin", lambda *_args: None)
    monkeypatch.setattr(commit_tool_module, "git_has_unpushed_commits", lambda *_args: False)
    monkeypatch.setattr(commit_tool_module, "git_current_branch", lambda *_args: "feature/jarvis-sync")
    monkeypatch.setattr(commit_tool_module, "git_config_user", lambda *_args: None)
    monkeypatch.setattr(commit_tool_module, "git_add_all", lambda *_args: None)
    monkeypatch.setattr(
        commit_tool_module,
        "git_commit",
        lambda *_args: SimpleNamespace(exit_code=0, output=""),
    )
    monkeypatch.setattr(
        commit_tool_module,
        "git_push",
        lambda *_args: SimpleNamespace(exit_code=0, output=""),
    )

    async def fake_get_installation_token() -> str:
        return "installation-token"

    async def fake_get_default_branch(*_args, **_kwargs) -> str:
        return "main"

    async def fake_create_pr(**_kwargs):
        return ("https://example.invalid/pull/123", 123, False)

    monkeypatch.setattr(
        commit_tool_module,
        "get_github_app_installation_token",
        fake_get_installation_token,
    )
    monkeypatch.setattr(
        commit_tool_module,
        "get_github_default_branch",
        fake_get_default_branch,
    )
    monkeypatch.setattr(commit_tool_module, "create_github_pr", fake_create_pr)

    result = commit_tool_module.commit_and_open_pr(
        title="feat: preserve receipts [closes OPS-1]",
        body="## Description\nKeep canonical continuity.\n\n## Test Plan\n- [ ] Verify PR-safe completion keeps canonical receipts",
        commit_message="preserve continuity on completion",
    )

    assert result == {
        "success": True,
        "error": None,
        "pr_url": "https://example.invalid/pull/123",
        "pr_existing": False,
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
