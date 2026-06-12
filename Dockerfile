# Containerized Proxmox MCP server (HTTP transport).
#
# Build:  docker build -t proxmox-mcp .
# Run:    docker run -d --name proxmox-mcp \
#           -p 8000:8000 \
#           --env-file .env \
#           -e MCP_TRANSPORT=streamable-http \
#           -e PROXMOX_MEMORY_FILE=/data/proxmox_memory.md \
#           -v proxmox_mcp_data:/data \
#           -v /path/to/id_rsa:/keys/id_rsa:ro \
#           -e PROXMOX_SSH_KEY=/keys/id_rsa \
#           proxmox-mcp
#
# Notes:
#  - Mount the memory file on a named volume so it persists across rebuilds.
#  - Mount the SSH private key read-only; never bake keys into the image.
#  - MCP_AUTH_TOKEN must be set (via --env-file/.env) for HTTP mode to start.

FROM python:3.12-slim

# Avoid interactive prompts; keep Python output unbuffered for clean logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

WORKDIR /app

# Install dependencies first (better layer caching), then the package.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Default memory location inside the container — override via PROXMOX_MEMORY_FILE.
ENV PROXMOX_MEMORY_FILE=/data/proxmox_memory.md
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "proxmox_mcp.server"]
