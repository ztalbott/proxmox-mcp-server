"""Proxmox MCP Server — exposes Proxmox VE management tools to Claude."""
from __future__ import annotations
import json
import os
from typing import Any

from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load .env from project root regardless of working directory, BEFORE importing
# submodules — so any module-level environment reads (e.g. memory paths) see it.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from .proxmox import ProxmoxClient  # noqa: E402
from . import memory  # noqa: E402

mcp = FastMCP(
    "proxmox",
    instructions="""You are a Proxmox VE homelab assistant with full API and SSH access.

At the START of every conversation, always call get_memory() first to load context
about this homelab before doing anything else.

As you work, call save_note() whenever you learn something small and standalone
worth remembering:
- Node names, IPs, hardware specs
- What each VM/LXC is for and who uses it
- Storage pool layout and purposes
- Network topology, VLANs, bridges
- Services running and where
- Naming conventions used
- Any quirks or important config details

For recurring structured documents you regenerate over time — especially a full
homelab audit/snapshot — use update_note(heading, note) INSTEAD of save_note().
Pass the same heading each time (e.g. "# Homelab Environment — Full Audit") and
update_note will replace the previous version in place rather than stacking a new
duplicate copy alongside it. This keeps memory lean — never re-save a full audit
with save_note().

After completing any significant task, save a note summarizing what was done.

Always describe destructive actions (stop, delete, rollback, destroy) and confirm
with the user before executing them."""
)

# ── Client (lazy singleton) ────────────────────────────────────────────────────

_pve: ProxmoxClient | None = None


def _get_pve() -> ProxmoxClient:
    global _pve
    if _pve is None:
        _pve = ProxmoxClient(
            host=os.environ["PROXMOX_HOST"],
            token_id=os.environ["PROXMOX_TOKEN_ID"],
            token_secret=os.environ["PROXMOX_TOKEN_SECRET"],
            verify_ssl=os.getenv("VERIFY_SSL", "true").lower() not in ("false", "0", "no"),
        )
    return _pve


def _fmt(obj: Any) -> str:
    if isinstance(obj, (dict, list)):
        return json.dumps(obj, indent=2, default=str)
    return str(obj) if obj is not None else "OK"


def _run(tool_name: str, fn, *args, **kwargs) -> str:
    """Call fn, log the change, return formatted result."""
    result = _fmt(fn(*args, **kwargs))
    memory.log_change(tool_name, kwargs, result)
    return result


# ── Cluster / Nodes ────────────────────────────────────────────────────────────

@mcp.tool()
def get_proxmox_version() -> str:
    """Get Proxmox VE version and API version info."""
    return _fmt(_get_pve().get_version())


@mcp.tool()
def get_cluster_status() -> str:
    """Get overall cluster health, quorum, and node membership."""
    return _fmt(_get_pve().get_cluster_status())


@mcp.tool()
def list_nodes() -> str:
    """List all Proxmox nodes in the cluster with online/offline status."""
    return _fmt(_get_pve().list_nodes())


@mcp.tool()
def get_node_status(node: str) -> str:
    """Get detailed CPU, RAM, disk, and load stats for a specific node."""
    return _fmt(_get_pve().get_node_status(node))


@mcp.tool()
def reboot_node(node: str) -> str:
    """Reboot a Proxmox node.
    ⚠️ DESTRUCTIVE — all VMs/containers on this node will be interrupted. Confirm first."""
    return _run("reboot_node", _get_pve().reboot_node, node)


@mcp.tool()
def shutdown_node(node: str) -> str:
    """Shut down a Proxmox node.
    ⚠️ DESTRUCTIVE — all VMs/containers on this node will stop. Confirm first."""
    return _run("shutdown_node", _get_pve().shutdown_node, node)


@mcp.tool()
def list_cluster_resources(resource_type: str = "") -> str:
    """List all cluster resources. resource_type: vm, lxc, storage, node (empty = all)."""
    return _fmt(_get_pve().list_cluster_resources(resource_type or None))


@mcp.tool()
def list_storage(node: str = "") -> str:
    """List storage pools. Pass node name to filter, or leave empty for all."""
    return _fmt(_get_pve().list_storage(node or None))


@mcp.tool()
def list_storage_content(node: str, storage: str, content_type: str = "") -> str:
    """List contents of a storage pool. content_type: backup, iso, vztmpl, images (empty = all)."""
    return _fmt(_get_pve().list_storage_content(node, storage, content_type or None))


@mcp.tool()
def delete_storage_content(node: str, storage: str, volume: str) -> str:
    """Delete a file/volume from storage (e.g. an ISO or backup).
    ⚠️ DESTRUCTIVE — use list_storage_content first to confirm the volume ID."""
    result = _fmt(_get_pve().delete_storage_content(node, storage, volume))
    memory.log_change("delete_storage_content", {"node": node, "storage": storage, "volume": volume}, result)
    return result


@mcp.tool()
def list_networks(node: str) -> str:
    """List all network interfaces and bridges configured on a node."""
    return _fmt(_get_pve().list_networks(node))


@mcp.tool()
def list_tasks(node: str, limit: int = 50) -> str:
    """List recent tasks on a node (backups, migrations, etc). limit: max results."""
    return _fmt(_get_pve().list_tasks(node, limit))


@mcp.tool()
def get_task_status(node: str, upid: str) -> str:
    """Get status of a specific task by its UPID (returned by long-running operations)."""
    return _fmt(_get_pve().get_task_status(node, upid))


@mcp.tool()
def get_task_log(node: str, upid: str) -> str:
    """Get the full log output of a task by its UPID."""
    return _fmt(_get_pve().get_task_log(node, upid))


@mcp.tool()
def list_pools() -> str:
    """List all resource pools."""
    return _fmt(_get_pve().list_pools())


@mcp.tool()
def get_pool(poolid: str) -> str:
    """Get members and details of a resource pool."""
    return _fmt(_get_pve().get_pool(poolid))


@mcp.tool()
def create_pool(poolid: str, comment: str = "") -> str:
    """Create a new resource pool."""
    result = _fmt(_get_pve().create_pool(poolid, comment))
    memory.log_change("create_pool", {"poolid": poolid, "comment": comment}, result)
    return result


@mcp.tool()
def delete_pool(poolid: str) -> str:
    """Delete a resource pool.
    ⚠️ DESTRUCTIVE — pool must be empty first."""
    result = _fmt(_get_pve().delete_pool(poolid))
    memory.log_change("delete_pool", {"poolid": poolid}, result)
    return result


@mcp.tool()
def list_users() -> str:
    """List all Proxmox user accounts and their realms."""
    return _fmt(_get_pve().list_users())


# ── VMs ────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_vms(node: str = "") -> str:
    """List all QEMU/KVM VMs. Optionally filter by node name."""
    return _fmt(_get_pve().list_vms(node or None))


@mcp.tool()
def get_vm_status(node: str, vmid: int) -> str:
    """Get running status, CPU usage, RAM, uptime for a VM."""
    return _fmt(_get_pve().get_vm_status(node, vmid))


@mcp.tool()
def get_vm_config(node: str, vmid: int) -> str:
    """Get full configuration (cores, memory, disks, network) for a VM."""
    return _fmt(_get_pve().get_vm_config(node, vmid))


@mcp.tool()
def start_vm(node: str, vmid: int) -> str:
    """Start a stopped or paused VM."""
    return _run("start_vm", _get_pve().start_vm, node, vmid)


@mcp.tool()
def stop_vm(node: str, vmid: int, force: bool = False) -> str:
    """Stop a VM. force=False is graceful ACPI shutdown; force=True is hard power-off.
    ⚠️ DESTRUCTIVE — describe the impact and confirm with the user first."""
    return _run("stop_vm", _get_pve().stop_vm, node=node, vmid=vmid, force=force)


@mcp.tool()
def reboot_vm(node: str, vmid: int) -> str:
    """Reboot a running VM gracefully via ACPI."""
    return _run("reboot_vm", _get_pve().reboot_vm, node, vmid)


@mcp.tool()
def suspend_vm(node: str, vmid: int) -> str:
    """Suspend (pause) a running VM — saves state to RAM."""
    return _run("suspend_vm", _get_pve().suspend_vm, node, vmid)


@mcp.tool()
def resume_vm(node: str, vmid: int) -> str:
    """Resume a suspended VM."""
    return _run("resume_vm", _get_pve().resume_vm, node, vmid)


@mcp.tool()
def set_vm_config(node: str, vmid: int, cores: int = 0, memory: int = 0,
                  net0: str = "", boot: str = "", description: str = "",
                  onboot: int = -1, tags: str = "", pool: str = "") -> str:
    """Update VM configuration. Only pass fields you want to change (0/empty = skip).
    tags: comma-separated list. onboot: 1=start at boot, 0=don't."""
    config: dict[str, Any] = {}
    if cores > 0: config["cores"] = cores
    if memory > 0: config["memory"] = memory
    if net0: config["net0"] = net0
    if boot: config["boot"] = boot
    if description: config["description"] = description
    if onboot >= 0: config["onboot"] = onboot
    if tags: config["tags"] = tags
    if pool: config["pool"] = pool
    if not config:
        return "No fields provided — nothing to change."
    result = _fmt(_get_pve().set_vm_config(node, vmid, **config))
    memory.log_change("set_vm_config", {"node": node, "vmid": vmid, **config}, result)
    return result


@mcp.tool()
def create_vm(node: str, vmid: int, name: str,
              cores: int = 1, memory_mb: int = 512) -> str:
    """Create a new blank VM."""
    return _run("create_vm", lambda: _get_pve().create_vm(
        node, vmid, name, cores=cores, memory=memory_mb
    ))


@mcp.tool()
def clone_vm(node: str, vmid: int, newid: int,
             name: str = "", full: bool = True, target_node: str = "") -> str:
    """Clone a VM. full=True makes an independent copy; full=False is a linked clone."""
    return _run("clone_vm", lambda: _get_pve().clone_vm(
        node, vmid, newid,
        name=name or None,
        full=full,
        target_node=target_node or None
    ))


@mcp.tool()
def migrate_vm(node: str, vmid: int, target_node: str, online: bool = True) -> str:
    """Migrate a VM to another node. online=True allows live migration while running.
    ⚠️ May cause brief downtime if offline migration."""
    return _run("migrate_vm", lambda: _get_pve().migrate_vm(
        node, vmid, target_node, online=online
    ))


@mcp.tool()
def destroy_vm(node: str, vmid: int) -> str:
    """Permanently DELETE a VM and all its disks. Irreversible.
    ⚠️ DESTRUCTIVE — always describe what will be deleted and confirm with the user first."""
    return _run("destroy_vm", _get_pve().destroy_vm, node, vmid)


@mcp.tool()
def resize_vm_disk(node: str, vmid: int, disk: str, size: str) -> str:
    """Resize a VM disk. size: '+10G' to grow by 10 GB, or '50G' to set absolute size.
    Example disk names: scsi0, virtio0, ide0. Shrinking is not supported."""
    return _run("resize_vm_disk", lambda: _get_pve().resize_vm_disk(node, vmid, disk, size))


@mcp.tool()
def backup_vm(node: str, vmid: int, storage: str,
              mode: str = "snapshot", compress: str = "zstd") -> str:
    """Trigger a backup of a VM. mode: snapshot, suspend, stop. compress: zstd, lzo, gzip.
    Returns a task UPID — use get_task_status to monitor progress."""
    return _run("backup_vm", lambda: _get_pve().backup_vm(
        node, vmid, storage, mode=mode, compress=compress
    ))


@mcp.tool()
def list_vm_snapshots(node: str, vmid: int) -> str:
    """List all snapshots for a VM."""
    return _fmt(_get_pve().list_vm_snapshots(node, vmid))


@mcp.tool()
def snapshot_vm(node: str, vmid: int, snapname: str,
                description: str = "", include_ram: bool = False) -> str:
    """Take a snapshot of a VM. include_ram=True saves memory state (VM stays online)."""
    return _run("snapshot_vm", lambda: _get_pve().snapshot_vm(
        node, vmid, snapname,
        description=description or None,
        vmstate=include_ram
    ))


@mcp.tool()
def rollback_vm_snapshot(node: str, vmid: int, snapname: str) -> str:
    """Roll a VM back to a snapshot. All changes since the snapshot will be lost.
    ⚠️ DESTRUCTIVE — confirm with the user first."""
    return _run("rollback_vm_snapshot", _get_pve().rollback_vm_snapshot, node, vmid, snapname)


@mcp.tool()
def delete_vm_snapshot(node: str, vmid: int, snapname: str) -> str:
    """Delete a VM snapshot.
    ⚠️ DESTRUCTIVE — confirm with the user first."""
    return _run("delete_vm_snapshot", _get_pve().delete_vm_snapshot, node, vmid, snapname)


# ── LXC ───────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_lxc(node: str = "") -> str:
    """List all LXC containers. Optionally filter by node."""
    return _fmt(_get_pve().list_lxc(node or None))


@mcp.tool()
def get_lxc_status(node: str, vmid: int) -> str:
    """Get running status, CPU, RAM, and uptime for an LXC container."""
    return _fmt(_get_pve().get_lxc_status(node, vmid))


@mcp.tool()
def get_lxc_config(node: str, vmid: int) -> str:
    """Get full configuration for an LXC container."""
    return _fmt(_get_pve().get_lxc_config(node, vmid))


@mcp.tool()
def start_lxc(node: str, vmid: int) -> str:
    """Start a stopped LXC container."""
    return _run("start_lxc", _get_pve().start_lxc, node, vmid)


@mcp.tool()
def stop_lxc(node: str, vmid: int, force: bool = False) -> str:
    """Stop an LXC container. force=False is graceful; force=True is immediate kill.
    ⚠️ DESTRUCTIVE — confirm with the user first."""
    return _run("stop_lxc", _get_pve().stop_lxc, node=node, vmid=vmid, force=force)


@mcp.tool()
def reboot_lxc(node: str, vmid: int) -> str:
    """Reboot a running LXC container."""
    return _run("reboot_lxc", _get_pve().reboot_lxc, node, vmid)


@mcp.tool()
def set_lxc_config(node: str, vmid: int, cores: int = 0, memory: int = 0,
                   hostname: str = "", onboot: int = -1,
                   description: str = "", tags: str = "") -> str:
    """Update LXC container config. Only pass fields you want to change."""
    config: dict[str, Any] = {}
    if cores > 0: config["cores"] = cores
    if memory > 0: config["memory"] = memory
    if hostname: config["hostname"] = hostname
    if onboot >= 0: config["onboot"] = onboot
    if description: config["description"] = description
    if tags: config["tags"] = tags
    if not config:
        return "No fields provided — nothing to change."
    result = _fmt(_get_pve().set_lxc_config(node, vmid, **config))
    memory.log_change("set_lxc_config", {"node": node, "vmid": vmid, **config}, result)
    return result


@mcp.tool()
def create_lxc(node: str, vmid: int, ostemplate: str, hostname: str = "",
               cores: int = 1, memory_mb: int = 512) -> str:
    """Create a new LXC container from a template.
    ostemplate example: local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"""
    return _run("create_lxc", lambda: _get_pve().create_lxc(
        node, vmid, ostemplate,
        hostname=hostname or None,
        cores=cores,
        memory=memory_mb
    ))


@mcp.tool()
def clone_lxc(node: str, vmid: int, newid: int,
              hostname: str = "", full: bool = True) -> str:
    """Clone an LXC container to a new ID."""
    return _run("clone_lxc", lambda: _get_pve().clone_lxc(
        node, vmid, newid,
        hostname=hostname or None,
        full=full
    ))


@mcp.tool()
def migrate_lxc(node: str, vmid: int, target_node: str, restart: bool = True) -> str:
    """Migrate an LXC container to another node.
    restart=True stops, migrates, then restarts the container."""
    return _run("migrate_lxc", lambda: _get_pve().migrate_lxc(
        node, vmid, target_node, restart=restart
    ))


@mcp.tool()
def destroy_lxc(node: str, vmid: int) -> str:
    """Permanently DELETE an LXC container. Irreversible.
    ⚠️ DESTRUCTIVE — confirm with the user first."""
    return _run("destroy_lxc", _get_pve().destroy_lxc, node, vmid)


@mcp.tool()
def resize_lxc_disk(node: str, vmid: int, disk: str, size: str) -> str:
    """Resize an LXC disk. size: '+10G' to grow, or '50G' absolute.
    Example disk: rootfs, mp0. Shrinking is not supported."""
    return _run("resize_lxc_disk", lambda: _get_pve().resize_lxc_disk(node, vmid, disk, size))


@mcp.tool()
def backup_lxc(node: str, vmid: int, storage: str,
               mode: str = "snapshot", compress: str = "zstd") -> str:
    """Trigger a backup of an LXC container. Returns a task UPID."""
    return _run("backup_lxc", lambda: _get_pve().backup_lxc(
        node, vmid, storage, mode=mode, compress=compress
    ))


@mcp.tool()
def list_lxc_snapshots(node: str, vmid: int) -> str:
    """List snapshots for an LXC container."""
    return _fmt(_get_pve().list_lxc_snapshots(node, vmid))


@mcp.tool()
def snapshot_lxc(node: str, vmid: int, snapname: str, description: str = "") -> str:
    """Take a snapshot of an LXC container."""
    return _run("snapshot_lxc", lambda: _get_pve().snapshot_lxc(
        node, vmid, snapname, description=description or None
    ))


@mcp.tool()
def rollback_lxc_snapshot(node: str, vmid: int, snapname: str) -> str:
    """Roll an LXC container back to a snapshot. Current state will be lost.
    ⚠️ DESTRUCTIVE — confirm with the user first."""
    return _run("rollback_lxc_snapshot", _get_pve().rollback_lxc_snapshot, node, vmid, snapname)


@mcp.tool()
def delete_lxc_snapshot(node: str, vmid: int, snapname: str) -> str:
    """Delete an LXC snapshot.
    ⚠️ DESTRUCTIVE — confirm with the user first."""
    return _run("delete_lxc_snapshot", _get_pve().delete_lxc_snapshot, node, vmid, snapname)


# ── Firewall ──────────────────────────────────────────────────────────────────

@mcp.tool()
def list_firewall_rules(scope: str = "datacenter", node: str = "", vmid: int = 0) -> str:
    """List firewall rules. scope: datacenter, node, vm, lxc.
    Pass node and vmid when scope is vm or lxc."""
    return _fmt(_get_pve().list_firewall_rules(scope, node or None, vmid or None))


@mcp.tool()
def get_firewall_options(scope: str = "datacenter", node: str = "", vmid: int = 0) -> str:
    """Get firewall enable/policy settings for a scope."""
    return _fmt(_get_pve().get_firewall_options(scope, node or None, vmid or None))


@mcp.tool()
def set_firewall_options(scope: str = "datacenter", node: str = "", vmid: int = 0,
                         enable: int = -1, policy_in: str = "",
                         policy_out: str = "") -> str:
    """Set firewall enable/policy for a scope. enable: 1=on, 0=off.
    policy_in/policy_out: ACCEPT, DROP, REJECT."""
    opts: dict[str, Any] = {}
    if enable >= 0: opts["enable"] = enable
    if policy_in: opts["policy_in"] = policy_in
    if policy_out: opts["policy_out"] = policy_out
    if not opts:
        return "No options provided."
    result = _fmt(_get_pve().set_firewall_options(scope, node or None, vmid or None, **opts))
    memory.log_change("set_firewall_options", {"scope": scope, **opts}, result)
    return result


@mcp.tool()
def add_firewall_rule(action: str, rule_type: str, scope: str = "datacenter",
                      node: str = "", vmid: int = 0, proto: str = "",
                      dport: str = "", sport: str = "", source: str = "",
                      dest: str = "", comment: str = "",
                      enable: int = 1) -> str:
    """Add a firewall rule.
    action: ACCEPT, DROP, REJECT. rule_type: in, out.
    proto: tcp, udp, icmp. dport/sport: port or range (e.g. 80, 8000:9000).
    source/dest: IP, CIDR, or alias."""
    kwargs: dict[str, Any] = {"enable": enable}
    if proto: kwargs["proto"] = proto
    if dport: kwargs["dport"] = dport
    if sport: kwargs["sport"] = sport
    if source: kwargs["source"] = source
    if dest: kwargs["dest"] = dest
    if comment: kwargs["comment"] = comment
    result = _fmt(_get_pve().add_firewall_rule(
        action, rule_type, scope, node or None, vmid or None, **kwargs
    ))
    memory.log_change("add_firewall_rule", {
        "action": action, "rule_type": rule_type, "scope": scope, **kwargs
    }, result)
    return result


@mcp.tool()
def update_firewall_rule(pos: int, scope: str = "datacenter", node: str = "", vmid: int = 0,
                         action: str = "", enable: int = -1, comment: str = "") -> str:
    """Update an existing firewall rule by position. Use list_firewall_rules to find pos."""
    kwargs: dict[str, Any] = {}
    if action: kwargs["action"] = action
    if enable >= 0: kwargs["enable"] = enable
    if comment: kwargs["comment"] = comment
    if not kwargs:
        return "No fields provided."
    result = _fmt(_get_pve().update_firewall_rule(pos, scope, node or None, vmid or None, **kwargs))
    memory.log_change("update_firewall_rule", {"pos": pos, "scope": scope, **kwargs}, result)
    return result


@mcp.tool()
def delete_firewall_rule(pos: int, scope: str = "datacenter",
                         node: str = "", vmid: int = 0) -> str:
    """Delete a firewall rule by position index.
    ⚠️ DESTRUCTIVE — use list_firewall_rules first to confirm the correct position."""
    result = _fmt(_get_pve().delete_firewall_rule(pos, scope, node or None, vmid or None))
    memory.log_change("delete_firewall_rule", {"pos": pos, "scope": scope}, result)
    return result


@mcp.tool()
def list_firewall_ipsets(scope: str = "datacenter", node: str = "", vmid: int = 0) -> str:
    """List IP sets (named groups of IPs) for a firewall scope."""
    return _fmt(_get_pve().list_firewall_ipsets(scope, node or None, vmid or None))


@mcp.tool()
def list_firewall_aliases(scope: str = "datacenter", node: str = "", vmid: int = 0) -> str:
    """List firewall aliases (named IP/CIDR references) for a scope."""
    return _fmt(_get_pve().list_firewall_aliases(scope, node or None, vmid or None))


# ── SSH ────────────────────────────────────────────────────────────────────────

@mcp.tool()
def run_ssh_command(command: str, timeout: int = 30) -> str:
    """Run any shell command directly on the Proxmox host via SSH.
    Use for anything not covered by the API: disk checks, logs, package installs,
    services, network diagnostics, file edits, cron jobs, etc.
    ⚠️ Runs as root — describe what the command does before executing it."""
    import paramiko
    host = os.environ.get("PROXMOX_SSH_HOST") or os.environ.get("PROXMOX_HOST")
    user = os.environ.get("PROXMOX_SSH_USER", "root")
    key_path = os.environ.get("PROXMOX_SSH_KEY", "")
    password = os.environ.get("PROXMOX_SSH_PASSWORD", "")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if key_path:
            client.connect(host, username=user, key_filename=key_path, timeout=10)
        else:
            client.connect(host, username=user, password=password, timeout=10)
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        result = out + ("\n[stderr]\n" + err if err else "")
        memory.log_change("run_ssh_command", {"command": command}, result[:300])
        return result or "(no output)"
    finally:
        client.close()


# ── Memory ────────────────────────────────────────────────────────────────────

@mcp.tool()
def save_note(note: str) -> str:
    """Save a persistent note about this homelab to memory.
    Use whenever you learn something worth remembering across sessions:
    node names/IPs, VM purposes, storage layout, credentials hints, naming conventions,
    network topology, important service locations."""
    return memory.save_note(note)


@mcp.tool()
def update_note(heading: str, note: str) -> str:
    """Save or update a long-form/structured note in memory, replacing any existing
    note that starts with the same heading instead of stacking a duplicate copy.

    Use this (NOT save_note) for recurring documents you regenerate over time —
    e.g. a full homelab audit titled "# Homelab Environment — Full Audit". Pass the
    exact heading text the note starts with, and the full new note content (including
    that heading as its first line). If a previous note with that heading exists it
    is replaced in place; otherwise the note is added fresh.

    heading: the exact leading text identifying this note, e.g. "# Homelab Environment — Full Audit"
    note: the complete new note content (markdown), starting with `heading`
    """
    return memory.update_note(heading, note)


@mcp.tool()
def get_memory() -> str:
    """Read all persistent memory about this homelab.
    Call this at the start of every session to recall previously learned context."""
    content = memory.load()
    return content if content.strip() else "No memory yet — this is the first session."


# ── Entry point ───────────────────────────────────────────────────────────────

_HTTP_TRANSPORTS = {"streamable-http", "sse"}


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _run_http(transport: str) -> None:
    """Run an HTTP transport (streamable-http or sse) behind a required bearer token.

    Fail-safe: refuses to start if MCP_AUTH_TOKEN is unset, so a network-exposed
    server (which gives root SSH access via run_ssh_command) can never come up
    unauthenticated. Set MCP_REQUIRE_AUTH=false only for trusted, isolated testing.
    """
    import hmac

    import uvicorn
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    host = os.getenv("MCP_HOST", "0.0.0.0").strip()
    port = int(os.getenv("MCP_PORT", "8000"))
    token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    require_auth = _bool_env("MCP_REQUIRE_AUTH", True)

    if require_auth and not token:
        raise SystemExit(
            "Refusing to start: MCP_AUTH_TOKEN is empty but transport is "
            f"'{transport}'. This server exposes root SSH access — set a strong "
            "MCP_AUTH_TOKEN in your .env, or set MCP_REQUIRE_AUTH=false only for "
            "isolated local testing."
        )

    mcp.settings.host = host
    mcp.settings.port = port

    app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()

    if token:
        expected = f"Bearer {token}"

        class BearerAuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                provided = request.headers.get("authorization", "")
                # constant-time compare to avoid leaking the token via timing
                if not hmac.compare_digest(provided, expected):
                    return JSONResponse({"error": "unauthorized"}, status_code=401)
                return await call_next(request)

        app.add_middleware(BearerAuthMiddleware)

    auth_state = "bearer-token auth ON" if token else "AUTH DISABLED (testing)"
    print(f"[proxmox-mcp] {transport} on http://{host}:{port}  ({auth_state})")
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport in _HTTP_TRANSPORTS:
        _run_http(transport)
    elif transport in ("stdio", ""):
        mcp.run()  # local PC / Claude desktop — stdio, no network exposure
    else:
        raise SystemExit(
            f"Unknown MCP_TRANSPORT={transport!r}. "
            "Use 'stdio' (default), 'streamable-http', or 'sse'."
        )


if __name__ == "__main__":
    main()
