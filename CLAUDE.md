# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

MCP server exposing Proxmox VE management as ~55 tools Claude can call from any Claude
session — no separate agent app, no API credits. Uses your Claude subscription via the
Claude desktop app.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env   # fill in credentials
```

Required `.env`: `PROXMOX_HOST`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET`
Optional: `PROXMOX_SSH_HOST`, `PROXMOX_SSH_USER`, `PROXMOX_SSH_KEY` or `PROXMOX_SSH_PASSWORD`

**API token must have Privilege Separation unchecked.**

## Architecture

```
src/proxmox_mcp/
├── server.py    FastMCP server — all ~55 tool definitions
├── proxmox.py   ProxmoxClient — proxmoxer wrapper for every API call
└── memory.py    Reads/writes proxmox_memory.md (save_note + log_change)
```

`proxmox_memory.md` lives at project root, gitignored, persists across sessions.

## Adding tools

1. Add method to `ProxmoxClient` in `proxmox.py`
2. Add `@mcp.tool()` function in `server.py`
3. If it modifies state, add tool name to `CHANGE_TOOLS` in `memory.py`

## Key notes

- Uses `FastMCP` — tool docstrings become the descriptions Claude sees
- SSH runs as root — mark destructive commands clearly in docstrings
- stdio transport (default) for Claude desktop app compatibility
- `_run()` helper in server.py calls the method AND logs to memory
- Read-only tools use `_fmt()` directly, no logging
- `proxmox_memory.md` is gitignored — never commit it

## Connecting to Claude desktop

`%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "proxmox": {
      "command": "C:\\Claude Projects\\proxmox-mcp-server\\.venv\\Scripts\\python.exe",
      "args": ["-m", "proxmox_mcp.server"],
      "cwd": "C:\\Claude Projects\\proxmox-mcp-server"
    }
  }
}
```
