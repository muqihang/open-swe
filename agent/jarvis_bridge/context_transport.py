from __future__ import annotations

import json
import re
from typing import Any

from .contracts import (
    JARVIS_BY_REFERENCE_BLOCK_TYPE,
    JARVIS_BY_REFERENCE_KEY,
    JARVIS_CONTEXT_ROOT_KEY,
    JARVIS_CONTROLLER_CLOSE_TAG,
    JARVIS_CONTROLLER_CONTEXT_BLOCK_TYPE,
    JARVIS_CONTROLLER_CONTEXT_KEY,
    JARVIS_CONTROLLER_OPEN_TAG,
)


def is_controller_payload(payload: dict[str, Any]) -> bool:
    root = payload.get(JARVIS_CONTEXT_ROOT_KEY)
    return isinstance(root, dict) and JARVIS_CONTROLLER_CONTEXT_KEY in root


def wrap_controller_payload(context: dict[str, Any]) -> dict[str, Any]:
    return {JARVIS_CONTEXT_ROOT_KEY: {JARVIS_CONTROLLER_CONTEXT_KEY: context}}


def _extract_controller_context(payload: dict[str, Any]) -> dict[str, Any]:
    root = payload.get(JARVIS_CONTEXT_ROOT_KEY, {})
    if isinstance(root, dict):
        context = root.get(JARVIS_CONTROLLER_CONTEXT_KEY, {})
        if isinstance(context, dict):
            return context
    return {}


def build_controller_blocks(context: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    by_reference = context.get(JARVIS_BY_REFERENCE_KEY)
    if isinstance(by_reference, list) and by_reference:
        blocks.append({"type": JARVIS_BY_REFERENCE_BLOCK_TYPE, "refs": by_reference})
    other_context = {key: value for key, value in context.items() if key != JARVIS_BY_REFERENCE_KEY}
    if other_context:
        blocks.append({"type": JARVIS_CONTROLLER_CONTEXT_BLOCK_TYPE, "context": other_context})
    return blocks


def build_controller_text_block(context: dict[str, Any]) -> dict[str, str]:
    """Build a tagged text block that preserves controller payload in messages."""
    return {
        "type": "text",
        "text": (
            f"{JARVIS_CONTROLLER_OPEN_TAG}\n"
            f"{json.dumps(context, ensure_ascii=False, sort_keys=True)}\n"
            f"{JARVIS_CONTROLLER_CLOSE_TAG}"
        ),
    }


def build_controller_message(context: dict[str, Any]) -> dict[str, Any]:
    return {"role": "user", "content": build_controller_blocks(context)}


def extract_controller_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if is_controller_payload(payload):
        return build_controller_blocks(_extract_controller_context(payload))
    if JARVIS_BY_REFERENCE_KEY in payload or payload.get(JARVIS_CONTEXT_ROOT_KEY):
        if isinstance(payload, dict):
            return build_controller_blocks(payload)
    return []


def attach_controller_payload(
    content: str | list[dict[str, Any]] | None,
    payload: dict[str, Any] | None,
) -> str | list[dict[str, Any]]:
    """Attach a controller payload block to user content."""
    if payload is None:
        return content or ""

    controller_block = build_controller_text_block(payload)
    if isinstance(content, list):
        return [*content, controller_block]
    if isinstance(content, str):
        if not content:
            return [controller_block]
        return [{"type": "text", "text": content}, controller_block]
    return [controller_block]


def _extract_controller_payload_from_text(text: str) -> dict[str, Any] | None:
    pattern = re.compile(
        rf"{re.escape(JARVIS_CONTROLLER_OPEN_TAG)}\s*(.*?)\s*{re.escape(JARVIS_CONTROLLER_CLOSE_TAG)}",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_controller_payload_from_messages(messages: list[Any]) -> dict[str, Any] | None:
    """Extract the latest tagged controller payload from messages."""
    for message in reversed(messages):
        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = getattr(message, "content", "")

        if isinstance(content, str):
            payload = _extract_controller_payload_from_text(content)
            if payload:
                return payload
            continue

        if isinstance(content, list):
            extracted_from_blocks: dict[str, Any] = {}
            for block in reversed(content):
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == JARVIS_CONTROLLER_CONTEXT_BLOCK_TYPE:
                    context = block.get("context")
                    if isinstance(context, dict):
                        extracted_from_blocks.update(context)
                        continue
                if block_type == JARVIS_BY_REFERENCE_BLOCK_TYPE:
                    refs = block.get("refs")
                    if isinstance(refs, list):
                        extracted_from_blocks[JARVIS_BY_REFERENCE_KEY] = refs
                        continue
                text = block.get("text")
                if isinstance(text, str):
                    payload = _extract_controller_payload_from_text(text)
                    if payload:
                        return payload
            if extracted_from_blocks:
                return extracted_from_blocks
    return None


def build_run_create_payload(
    *,
    thread_id: str,
    message_content: str | list[dict[str, Any]],
    configurable: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    branch_name: str | None = None,
    controller_payload: dict[str, Any] | None = None,
    multitask_strategy: str | None = None,
) -> dict[str, Any]:
    """Build a canonical `runs.create` payload."""
    effective_metadata = dict(metadata or {})
    if branch_name and "branch_name" not in effective_metadata:
        effective_metadata["branch_name"] = branch_name

    payload: dict[str, Any] = {
        "thread_id": thread_id,
        "assistant_id": "agent",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": attach_controller_payload(message_content, controller_payload),
                }
            ]
        },
        "config": {
            "configurable": configurable,
            "metadata": effective_metadata,
        },
        "if_not_exists": "create",
    }
    if multitask_strategy:
        payload["multitask_strategy"] = multitask_strategy
    return payload
