# proxmox-mcp-server

MCP server that gives Claude direct control of your Proxmox VE homelab — VMs, containers,
snapshots, backups, firewall, storage, networking, tasks, pools, and SSH shell access.
Works with the Claude desktop app using your subscription (no API credits needed).

---

## Requirements

- Python 3.11+
- A Proxmox VE host reachable from your machine
- A Proxmox API token with **Privilege Separation unchecked**

---

## Quick Setup

Clone the repo and run these commands from the project directory:

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env
notepad .env
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
nano .env
```

Fill in `.env`:
```
PROXMOX_HOST=192.168.1.x
PROXMOX_TOKEN_ID=root@pam!mcp-token
PROXMOX_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VERIFY_SSL=false
PROXMOX_SSH_USER=root
PROXMOX_SSH_KEY=/path/to/.ssh/id_rsa
```

> **Important:** The Proxmox API token must be created with **Privilege Separation unchecked**.

---

## Connect to Claude Desktop App

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "/path/to/proxmox-mcp-server/.venv/bin/python",
      "args": ["-m", "proxmox_mcp.server"],
      "cwd": "/path/to/proxmox-mcp-server"
    }
  }
}
```

On Windows use the `.venv\Scripts\python.exe` path and backslashes.

Restart the Claude app. You can now say things like:
- *"List my VMs"*
- *"Show me the status of node pve1"*
- *"Take a snapshot of VM 101 called before-update"*
- *"What's running on my homelab?"*

---

## Tools

| Category | Tools |
|---|---|
| Cluster | `get_proxmox_version`, `get_cluster_status`, `list_nodes`, `get_node_status`, `reboot_node`⚠️, `shutdown_node`⚠️ |
| Resources | `list_cluster_resources`, `list_tasks`, `get_task_status`, `get_task_log` |
| Storage | `list_storage`, `list_storage_content`, `delete_storage_content`⚠️ |
| Network | `list_networks` |
| Pools | `list_pools`, `get_pool`, `create_pool`, `delete_pool`⚠️ |
| Users | `list_users` |
| VMs | `list_vms`, `get_vm_status`, `get_vm_config`, `start_vm`, `stop_vm`⚠️, `reboot_vm`, `suspend_vm`, `resume_vm`, `set_vm_config`, `create_vm`, `clone_vm`, `migrate_vm`, `destroy_vm`⚠️, `resize_vm_disk`, `backup_vm` |
| VM Snapshots | `list_vm_snapshots`, `snapshot_vm`, `rollback_vm_snapshot`⚠️, `delete_vm_snapshot`⚠️ |
| LXC | `list_lxc`, `get_lxc_status`, `get_lxc_config`, `start_lxc`, `stop_lxc`⚠️, `reboot_lxc`, `set_lxc_config`, `create_lxc`, `clone_lxc`, `migrate_lxc`, `destroy_lxc`⚠️, `resize_lxc_disk`, `backup_lxc` |
| LXC Snapshots | `list_lxc_snapshots`, `snapshot_lxc`, `rollback_lxc_snapshot`⚠️, `delete_lxc_snapshot`⚠️ |
| Firewall | `list_firewall_rules`, `get_firewall_options`, `set_firewall_options`, `add_firewall_rule`, `update_firewall_rule`, `delete_firewall_rule`⚠️, `list_firewall_ipsets`, `list_firewall_aliases` |
| SSH | `run_ssh_command` — run any shell command on the host as root |
| Memory | `save_note`, `get_memory` — persistent homelab knowledge across sessions |

⚠️ = destructive — Claude will describe and ask you to confirm before executing.

---

## How Data Flows

```
You (Claude chat)
      │  natural language
      ▼
Claude (LLM)
      │  decides which tool to call + parameters
      ▼
MCP Protocol (stdio)
      │  JSON tool call
      ▼
proxmox_mcp/server.py  (running on your PC)
      │
      ├─► Proxmox REST API (HTTPS)  ──► Proxmox VE
      │                                   returns JSON
      │
      └─► SSH (paramiko)  ──────────────► Proxmox host shell
                                          returns stdout/stderr
      │
      ▼
Result returned to Claude via MCP
      │
      ▼
Claude summarizes / acts on the result
      │
      ▼
You see the response
```

**Memory** (`proxmox_memory.md`): Claude writes notes and a change log to this file
at the project root. It's gitignored and persists between sessions.
