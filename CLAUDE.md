# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

MCP server exposing Proxmox VE management as ~55 tools Claude can call from any Claude
session — no separate agent app, no API credits. Uses your Claude subscription via the
Claude desktop app.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env        # fill in credentials
```

Required `.env`: `PROXMOX_HOST`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET`
Optional: `PROXMOX_SSH_HOST`, `PROXMOX_SSH_USER`, `PROXMOX_SSH_KEY` or `PROXMOX_SSH_PASSWORD`

**API token must have Privilege Separation unchecked.**

### Transport / deployment env

- `MCP_TRANSPORT` — `stdio` (default, local PC), `streamable-http`, or `sse`
- `MCP_HOST` / `MCP_PORT` — bind address for HTTP modes (default `0.0.0.0:8000`)
- `MCP_AUTH_TOKEN` — bearer token; **required** in HTTP modes (server refuses to start
  without it unless `MCP_REQUIRE_AUTH=false` for isolated testing)
- `MCP_ALLOWED_HOSTS` — comma-separated Host-header allowlist for the SDK's DNS-rebinding
  protection (e.g. `192.168.1.107:*`). Empty disables the check (bearer auth still applies).
- `PROXMOX_MEMORY_FILE` — override the memory file location (portability for LXC/container)

## Architecture

```
src/proxmox_mcp/
├── server.py    FastMCP server — all tool defs + transport selection (main()) + HTTP auth
├── proxmox.py   ProxmoxClient — proxmoxer wrapper for every API call
└── memory.py    Reads/writes the memory file (save_note, update_note, log_change)
deploy/
└── proxmox-mcp.service   systemd unit for running as an HTTP service on an LXC
Dockerfile       containerized HTTP deployment
```

`proxmox_memory.md` lives at project root by default (override via `PROXMOX_MEMORY_FILE`),
gitignored, persists across sessions. The path resolves lazily at call time (`memory_file()`),
so the env override applies regardless of import order.

## Adding tools

1. Add method to `ProxmoxClient` in `proxmox.py`
2. Add `@mcp.tool()` function in `server.py`
3. If it modifies state, add tool name to `CHANGE_TOOLS` in `memory.py`

## Key notes

- Uses `FastMCP` — tool docstrings become the descriptions Claude sees
- SSH runs as root — mark destructive commands clearly in docstrings
- stdio transport (default) for Claude desktop app; HTTP modes for the LXC service
- HTTP modes are bearer-token authenticated and fail-safe (no token → won't start)
- `load_dotenv()` runs before submodule imports so module-level env reads work
- systemd deploys must use `EnvironmentFile=` in the unit (see `deploy/proxmox-mcp.service`) —
  without it `.env` vars don't reach the process and it silently falls back to stdio
- `_run()` helper in server.py calls the method AND logs to memory
- Read-only tools use `_fmt()` directly, no logging
- The memory file is gitignored (incl. backups) — never commit homelab data

## Connecting to Claude desktop

`%APPDATA%\Claude\claude_desktop_config.json` (Windows) or
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

On Windows use `.venv\Scripts\python.exe` and backslashes in the paths.
