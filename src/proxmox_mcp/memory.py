"""Persistent memory: environment notes + change log stored in proxmox_memory.md."""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path(__file__).resolve().parents[2] / "proxmox_memory.md"

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


_BULLET_RE = re.compile(r"^- \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] ", re.MULTILINE)


def update_note(heading: str, note: str) -> str:
    """Save a note in Environment Notes, replacing any existing note that starts
    with the same `heading` instead of appending a new copy alongside it.

    Use this for recurring structured documents (e.g. a "Full Audit" that gets
    re-saved as the homelab evolves) so re-saving updates the entry in place
    rather than letting duplicates pile up.
    """
    content = _ensure()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"- [{ts}] {note}"

    marker = "## Environment Notes\n"
    if marker not in content:
        content += f"\n## Environment Notes\n\n{new_entry}\n"
        _write(content)
        return "Note saved (section created)."

    start = content.index(marker) + len(marker)
    rest = content[start:]
    if rest.lstrip().startswith("<!--"):
        start += rest.index("-->") + 3

    end_marker = "\n## Change Log"
    rel_end = content.find(end_marker, start)
    section_end = rel_end if rel_end != -1 else len(content)
    section = content[start:section_end]

    heading_re = re.compile(
        r"^- \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}\] " + re.escape(heading),
        re.MULTILINE,
    )

    # Collect every existing entry whose heading matches (self-heals if duplicates
    # already piled up), so they all get collapsed into the one fresh entry.
    spans: list[tuple[int, int]] = []
    for m in heading_re.finditer(section):
        next_bullet = _BULLET_RE.search(section, m.end())
        entry_end = next_bullet.start() if next_bullet else len(section)
        spans.append((m.start(), entry_end))

    if spans:
        first_start = spans[0][0]
        new_section = section[:first_start] + new_entry + "\n"
        prev_end = spans[0][1]
        for s, e in spans[1:]:
            new_section += section[prev_end:s]
            prev_end = e
        new_section += section[prev_end:]
        n = len(spans)
        msg = (
            "Note updated (replaced previous version with the same heading)."
            if n == 1
            else f"Note updated (collapsed {n} duplicate entries with this heading into one)."
        )
    else:
        sep = "" if section.endswith("\n\n") else ("\n" if section.endswith("\n") else "\n\n")
        new_section = section + sep + new_entry + "\n"
        msg = "Note saved (no existing entry with this heading — added new)."

    content = content[:start] + new_section + content[section_end:]
    _write(content)
    return msg


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
