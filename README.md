# proxmox-mcp-server

MCP server that gives Claude direct control of your Proxmox VE homelab — VMs, containers,
snapshots, backups, firewall, storage, networking, tasks, pools, and SSH shell access.
Works with the Claude desktop app using your subscription (no API credits needed).

It runs in two modes from the **same codebase**, selected by `MCP_TRANSPORT` in `.env`:

| Mode | `MCP_TRANSPORT` | Use case |
|---|---|---|
| **Local** | `stdio` (default) | Claude desktop spawns the process on your PC. Only runs while the app is open. |
| **Service** | `streamable-http` | A persistent, always-on network service (e.g. on a Proxmox LXC), reachable by networked MCP clients. Requires a bearer token. |

---

## Requirements

- Python 3.11+
- A Proxmox VE host reachable from where the server runs
- A Proxmox API token with **Privilege Separation unchecked**

---

## Mode A — Local on your PC (stdio)

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

## Mode B — Persistent service on a Proxmox LXC (HTTP)

Runs the server as an always-on systemd service so it works even when your PC is off,
and can be reached by networked MCP clients.

> ⚠️ **Security:** in HTTP mode this server is a network endpoint that can run **arbitrary
> root shell commands** on your Proxmox host (`run_ssh_command`). It therefore **refuses to
> start without `MCP_AUTH_TOKEN` set**, and rejects any request lacking a matching
> `Authorization: Bearer <token>` header. Keep it on a trusted/LAN or Tailscale network —
> do not expose the port directly to the public internet.

**1. On the LXC (Debian/Ubuntu), clone and install:**

This repo is **private**, so cloning needs a read-only [deploy key](https://docs.github.com/en/developer-guide/managing-deploy-keys):
```bash
sudo apt update && sudo apt install -y python3-venv git
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519_github -N "" -C "lxc107-deploy-key"
cat /root/.ssh/id_ed25519_github.pub   # add this as a read-only Deploy Key on the GitHub repo
```
Add the printed key via **GitHub repo → Settings → Deploy keys → Add deploy key** (read-only is
fine), or with the CLI: `gh repo deploy-key add /root/.ssh/id_ed25519_github.pub --title lxc107 --repo tail412/proxmox-mcp-server`

Then point SSH at GitHub with that key and clone:
```bash
cat >> /root/.ssh/config <<'EOF'
Host github.com
  IdentityFile /root/.ssh/id_ed25519_github
  IdentitiesOnly yes
EOF
sudo git clone git@github.com:tail412/proxmox-mcp-server.git /opt/proxmox-homelab
cd /opt/proxmox-homelab
git checkout lxc-migration   # or master, once merged
python3 -m venv .venv
.venv/bin/pip install .
cp .env.example .env
```

**2. Give the LXC its own SSH access to the Proxmox host** (separate key from your PC):
```bash
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
ssh-copy-id -i /root/.ssh/id_ed25519.pub root@192.168.1.100   # the pve host
```

**3. Edit `.env`** for service mode:
```
PROXMOX_HOST=192.168.1.100
PROXMOX_TOKEN_ID=root@pam!mcp-token
PROXMOX_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VERIFY_SSL=false
PROXMOX_SSH_USER=root
PROXMOX_SSH_KEY=/root/.ssh/id_ed25519

MCP_TRANSPORT=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_AUTH_TOKEN=          # generate: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
MCP_REQUIRE_AUTH=true

# Allow the LXC's LAN IP through the SDK's DNS-rebinding Host-header check.
# Without this, requests with `Host: <lxc-ip>:8000` get HTTP 421.
MCP_ALLOWED_HOSTS=192.168.1.107:*

PROXMOX_MEMORY_FILE=/opt/proxmox-homelab/proxmox_memory.md
```

**4. Migrate existing memory** (optional) — copy the `proxmox_memory.md` built on your PC to
the path above so the homelab's accumulated knowledge carries over:
```bash
scp proxmox_memory.md root@192.168.1.107:/opt/proxmox-homelab/proxmox_memory.md
```

**5. Install the systemd service:**
```bash
sudo cp deploy/proxmox-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now proxmox-mcp.service
journalctl -u proxmox-mcp.service -f
```

**6. (Away-from-home access)** To reach it from `claude.ai` / the mobile app — which connect
via Anthropic's cloud, not your LAN — expose just this service with
[Tailscale Funnel](https://tailscale.com/kb/1223/funnel). Plain Tailscale is enough for a
desktop client on your own tailnet.

**Docker alternative:** a `Dockerfile` and `.dockerignore` are included — see the header
comments in `Dockerfile` for build/run commands.

### Connect Claude Desktop to the LXC service

The desktop app only speaks stdio to local connectors, so bridge it to the remote HTTP
server with [`mcp-remote`](https://www.npmjs.com/package/mcp-remote):

```bash
npm install -g mcp-remote
```

Then add a second entry to `claude_desktop_config.json` alongside (or instead of) the
local `proxmox` entry from Mode A:

```json
{
  "mcpServers": {
    "proxmox-lxc": {
      "command": "node",
      "args": [
        "/path/to/global/node_modules/mcp-remote/dist/proxy.js",
        "http://192.168.1.107:8000/mcp",
        "--header", "Authorization: Bearer <your MCP_AUTH_TOKEN>",
        "--allow-http"
      ]
    }
  }
}
```

> **Windows note:** use the full path to `node.exe` (e.g.
> `C:\Program Files\nodejs\node.exe`) as `command`, not `npx`/`npx.cmd` — the `.cmd` shim
> runs through `cmd.exe`, which breaks on the space in "Program Files" and the bridge
> fails immediately with "Server disconnected". Find the global `mcp-remote` install path
> with `npm root -g`.
>
> **Windows config file location:** if Claude Desktop was installed via the Microsoft
> Store / winget (an MSIX package), `%APPDATA%\Claude\claude_desktop_config.json` is a
> virtualized path that Explorer can't see. The real file is at
> `%LOCALAPPDATA%\Packages\<ClaudePackageName>\LocalCache\Roaming\Claude\claude_desktop_config.json`.
> Fully quit the app (it's not in the system tray by default) before editing, since it
> rewrites the file on exit.

Restart the app — you should now have both a `proxmox` (local PC) and `proxmox-lxc`
(always-on LXC) connector available.

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
| Memory | `save_note`, `update_note`, `get_memory` — persistent homelab knowledge across sessions (`update_note` replaces a previous note with the same heading instead of duplicating it — used for recurring docs like full audits) |

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
