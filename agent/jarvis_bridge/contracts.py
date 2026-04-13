JARVIS_CONTEXT_ROOT_KEY = "jarvis"
JARVIS_CONTROLLER_CONTEXT_KEY = "controller_context"
JARVIS_BY_REFERENCE_KEY = "by_reference"
JARVIS_CONTROLLER_OPEN_TAG = "<jarvis-controller>"
JARVIS_CONTROLLER_CLOSE_TAG = "</jarvis-controller>"

JARVIS_CONTROLLER_CONTEXT_BLOCK_TYPE = "jarvis.controller_context"
JARVIS_BY_REFERENCE_BLOCK_TYPE = "jarvis.by_reference"

JARVIS_RUN_ARTIFACTS_KEY = "run_artifacts"
JARVIS_LATEST_SLOTS_KEY = "latest_slots"
JARVIS_LATEST_HANDOFF_KEY = "latest_handoff"
JARVIS_LATEST_REPAIR_BUNDLE_KEY = "latest_repair_bundle"
JARVIS_TASK_SUMMARY_KEY = "task_summary"

TOOL_SURFACE_KB_PLUS_REPO = "kb_plus_repo"
TOOL_SURFACE_KB_PLUS_REPO_PLUS_NET = "kb_plus_repo_plus_net"

JARVIS_BY_REFERENCE_SURFACE_KEYS = (
    "repo_rules_pack",
    "verification_bundle",
    "run_artifacts",
    "escalation_semantics",
    "rule_attachment_summary",
)

JARVIS_CANONICAL_SLOT_KEYS = (
    JARVIS_LATEST_HANDOFF_KEY,
    JARVIS_LATEST_REPAIR_BUNDLE_KEY,
)

DEFAULT_TOOL_SURFACE_LAYER = TOOL_SURFACE_KB_PLUS_REPO
UPGRADED_TOOL_SURFACE_LAYER = TOOL_SURFACE_KB_PLUS_REPO_PLUS_NET


def resolve_tool_surface_layer(configurable: dict[str, object]) -> str:
    """Resolve the requested tool surface layer."""
    requested = configurable.get("tool_surface_layer")
    if requested in {TOOL_SURFACE_KB_PLUS_REPO, TOOL_SURFACE_KB_PLUS_REPO_PLUS_NET}:
        return str(requested)
    return DEFAULT_TOOL_SURFACE_LAYER
