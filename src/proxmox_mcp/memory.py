"""Persistent memory: environment notes + change log stored in proxmox_memory.md."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parents[3] / "proxmox_memory.md"

# Tools that modify state — these get auto-logged
CHANGE_TOOLS: frozenset[str] = frozenset({
    # VM lifecycle
    "start_vm", "stop_vm", "reboot_vm", "suspend_vm", "resume_vm",
    "set_vm_config", "create_vm", "clone_vm", "migrate_vm", "destroy_vm",
    "resize_vm_disk", "backup_vm",
    # VM snapshots
    "snapshot_vm", "rollback_vm_snapshot", "delete_vm_snapshot",
    # LXC lifecycle
    "start_lxc", "stop_lxc", "reboot_lxc",
    "set_lxc_config", "create_lxc", "clone_lxc", "migrate_lxc", "destroy_lxc",
    "resize_lxc_disk", "backup_lxc",
    # LXC snapshots
    "snapshot_lxc", "rollback_lxc_snapshot", "delete_lxc_snapshot",
    # Node
    "reboot_node", "shutdown_node",
    # Firewall
    "add_firewall_rule", "update_firewall_rule", "delete_firewall_rule",
    "set_firewall_options",
    # Storage
    "delete_storage_content",
    # Pools
    "create_pool", "delete_pool",
    # SSH
    "run_ssh_command",
})

_TEMPLATE = """\
# Proxmox Memory

## Environment Notes
<!-- Claude saves observations about your homelab here -->

## Change Log
<!-- Every modifying action is automatically recorded here -->
"""


def _read() -> str:
    return MEMORY_FILE.read_text(encoding="utf-8") if MEMORY_FILE.exists() else ""


def _write(content: str) -> None:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(content, encoding="utf-8")


def _ensure() -> str:
    content = _read()
    if not content:
        _write(_TEMPLATE)
        return _TEMPLATE
    return content


def load() -> str:
    """Return full memory file content."""
    return _read()


def save_note(note: str) -> str:
    """Append a note to the Environment Notes section."""
    content = _ensure()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n- [{ts}] {note}"
    marker = "## Environment Notes\n"
    if marker in content:
        idx = content.index(marker) + len(marker)
        rest = content[idx:]
        if rest.startswith("<!--"):
            idx += rest.index("-->") + 3
        content = content[:idx] + entry + content[idx:]
    else:
        content += f"\n## Environment Notes\n{entry}"
    _write(content)
    return "Note saved."


def log_change(tool_name: str, params: dict, result: str) -> None:
    """Auto-append to the Change Log. No-op for read-only tools."""
    if tool_name not in CHANGE_TOOLS:
        return
    content = _ensure()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params_str = json.dumps({k: v for k, v in params.items()}, default=str)
    entry = (
        f"\n### {ts} — `{tool_name}`\n"
        f"- **Params:** `{params_str}`\n"
        f"- **Result:** {result[:300].replace(chr(10), ' ')}\n"
    )
    marker = "## Change Log\n"
    if marker in content:
        idx = content.index(marker) + len(marker)
        rest = content[idx:]
        if rest.startswith("<!--"):
            idx += rest.index("-->") + 3
        content = content[:idx] + entry + content[idx:]
    else:
        content += f"\n## Change Log\n{entry}"
    _write(content)
