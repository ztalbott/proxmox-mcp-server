# proxmox-mcp-server

> **MCP server that gives Claude AI natural-language control of a Proxmox VE homelab.**
> Manage VMs, LXC containers, snapshots, backups, firewall rules, storage, and run arbitrary
> shell commands — all through conversation, with no API credits required.

Built as a real homelab project: deployed as a persistent systemd service inside a Proxmox
LXC container, bridged to the Claude desktop app via HTTP with bearer-token auth.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **MCP framework** | [FastMCP](https://github.com/jlowin/fastmcp) (`mcp` SDK) |
| **HTTP server** | Uvicorn + Starlette (ASGI) |
| **Proxmox API** | [proxmoxer](https://github.com/proxmoxer/proxmoxer) (REST) |
| **SSH** | paramiko |
| **Transport** | stdio (local) · streamable-HTTP · SSE |
| **Auth** | Bearer token via HMAC-safe `compare_digest` middleware |
| **Deployment** | systemd service · Docker · LXC container |
| **Config** | python-dotenv, env-selectable transport and paths |

---

## What It Does

67 tools across every major Proxmox API surface area — exposed to Claude as callable
functions via the [Model Context Protocol](https://modelcontextprotocol.io/):

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
| Memory | `save_note`, `update_note`, `get_memory` — persistent homelab knowledge across sessions |

⚠️ = destructive — Claude describes the action and asks for confirmation before executing.

---

## Architecture

The server runs in two modes from the **same codebase**, selected by `MCP_TRANSPORT` in `.env`:

| Mode | `MCP_TRANSPORT` | Use case |
|---|---|---|
| **Local** | `stdio` (default) | Claude desktop spawns the process on your PC. Zero network exposure. |
| **Service** | `streamable-http` | Persistent always-on HTTP service (e.g. a Proxmox LXC), reachable by any networked MCP client. Requires bearer token. |

```
You (Claude chat)
      │  natural language
      ▼
Claude (LLM)
      │  decides which tool to call + parameters
      ▼
MCP Protocol  (stdio or HTTP+bearer)
      │
      ▼
proxmox_mcp/server.py
      │
      ├─► Proxmox REST API (HTTPS)  ──► Proxmox VE host
      │                                   returns JSON
      │
      └─► SSH / paramiko  ─────────────► Proxmox host shell
                                          returns stdout / stderr
      │
      ▼
Result returned to Claude → shown in chat
```

**Persistent memory:** Claude writes structured notes and a self-pruning change log to
`proxmox_memory.md` (gitignored). The path is env-configurable for portability between
local and server deployments. `update_note()` does an in-place replace so recurring
documents (e.g. a full homelab audit) never accumulate duplicates.

**Security model:** HTTP mode refuses to start without `MCP_AUTH_TOKEN`. Every request
is checked against the token via `hmac.compare_digest` (constant-time, timing-attack safe).
DNS-rebinding protection is configurable via `MCP_ALLOWED_HOSTS`. Secrets live only in
`.env` (gitignored); `.env.example` is committed with placeholder values.

---

## Requirements

- Python 3.11+
- A Proxmox VE host reachable from where the server runs
- A Proxmox API token with **Privilege Separation unchecked**

---

## Mode A — Local on your PC (stdio)

```powershell
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env
notepad .env
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
nano .env
```

Minimum `.env`:
```
PROXMOX_HOST=192.168.1.x
PROXMOX_TOKEN_ID=root@pam!mcp-token
PROXMOX_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VERIFY_SSL=false
PROXMOX_SSH_USER=root
PROXMOX_SSH_KEY=/path/to/.ssh/id_rsa
```

### Connect to Claude Desktop

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

On Windows use `.venv\Scripts\python.exe` and backslashes. Restart Claude — you can now say
things like *"List my VMs"*, *"Snapshot VM 101 called before-update"*, or *"What's running on
my homelab?"*

> **Windows MSIX note:** if Claude Desktop was installed via the Store/winget, the config file
> is virtualized. The real path is
> `%LOCALAPPDATA%\Packages\<ClaudePackageName>\LocalCache\Roaming\Claude\claude_desktop_config.json`.

---

## Mode B — Persistent service on a Proxmox LXC (HTTP)

Runs as a systemd service so it works even when your PC is off.

> ⚠️ **Security:** HTTP mode exposes `run_ssh_command`, which runs arbitrary root shell
> commands on your Proxmox host. The server **refuses to start without `MCP_AUTH_TOKEN`**,
> and rejects any request without a matching `Authorization: Bearer` header. Keep it on a
> trusted LAN or Tailscale network — do not expose directly to the public internet.

**1. Clone and install on the LXC:**
```bash
sudo apt update && sudo apt install -y python3-venv git
# For a private fork, generate a deploy key and add it to GitHub first:
#   ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519_github -N ""
#   gh repo deploy-key add /root/.ssh/id_ed25519_github.pub --title lxc --repo <you>/proxmox-mcp-server
git clone https://github.com/tail412/proxmox-mcp-server.git /opt/proxmox-homelab
cd /opt/proxmox-homelab
python3 -m venv .venv
.venv/bin/pip install .
cp .env.example .env
```

**2. Give the LXC its own SSH key for the Proxmox host:**
```bash
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
ssh-copy-id -i /root/.ssh/id_ed25519.pub root@<proxmox-host-ip>
```

**3. Edit `.env` for service mode:**
```
PROXMOX_HOST=192.168.1.x
PROXMOX_TOKEN_ID=root@pam!mcp-token
PROXMOX_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VERIFY_SSL=false
PROXMOX_SSH_USER=root
PROXMOX_SSH_KEY=/root/.ssh/id_ed25519

MCP_TRANSPORT=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_AUTH_TOKEN=          # python3 -c "import secrets; print(secrets.token_urlsafe(32))"
MCP_REQUIRE_AUTH=true

# Allow the LXC's LAN IP through the SDK's DNS-rebinding Host-header check
MCP_ALLOWED_HOSTS=192.168.1.x:*

PROXMOX_MEMORY_FILE=/opt/proxmox-homelab/proxmox_memory.md
```

**4. Install the systemd service:**
```bash
sudo cp deploy/proxmox-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now proxmox-mcp.service
journalctl -u proxmox-mcp.service -f
```

**5. (Optional) Migrate existing memory** from your PC:
```bash
scp proxmox_memory.md root@<lxc-ip>:/opt/proxmox-homelab/proxmox_memory.md
```

**6. (Away-from-home access)** Expose with
[Tailscale Funnel](https://tailscale.com/kb/1223/funnel) for a public HTTPS endpoint
(required for `claude.ai` / the mobile app, which connect via Anthropic's cloud).

**Docker alternative:** `Dockerfile` and `.dockerignore` are included.

### Connect Claude Desktop to the LXC service

Bridge the desktop app to the remote HTTP server with [`mcp-remote`](https://www.npmjs.com/package/mcp-remote):

```bash
npm install -g mcp-remote
```

```json
{
  "mcpServers": {
    "proxmox-lxc": {
      "command": "node",
      "args": [
        "/path/to/global/node_modules/mcp-remote/dist/proxy.js",
        "http://<lxc-ip>:8000/mcp",
        "--header", "Authorization: Bearer <your MCP_AUTH_TOKEN>",
        "--allow-http"
      ]
    }
  }
}
```

> **Windows:** use the full path to `node.exe` (e.g. `C:\Program Files\nodejs\node.exe`)
> as `command` — `.cmd` shims run through `cmd.exe` and break on the space in "Program Files".
> Find the `mcp-remote` path with `npm root -g`.

---

## Project Structure

```
src/proxmox_mcp/
├── server.py    FastMCP server — all tool definitions, transport dispatch, HTTP auth middleware
├── proxmox.py   ProxmoxClient — proxmoxer wrapper for every API call
└── memory.py    Persistent notes: save_note, update_note, log_change, _prune_changelog
deploy/
└── proxmox-mcp.service   systemd unit (EnvironmentFile= ensures .env vars reach the process)
Dockerfile               containerized HTTP deployment
.env.example             all config options documented with safe placeholder values
```

---

## License

MIT
