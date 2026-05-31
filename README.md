# Infra Manager

An internal infrastructure management and provisioning platform for Proxmox VE clusters. Runs on the same private network as the cluster — nothing is exposed to the internet.

## What It Does

- **Provision VMs and LXC containers** on any Proxmox cluster node from a web dashboard
- **Manage cluster firewall rules** (cluster, node, and per-VM/CT scope) via the Proxmox SDN API
- **Manage DNS entries** via Proxmox SDN DNS
- **Deploy Docker services** to managed VMs/containers through the Proxmox exec API (no SSH required)
- **Reverse proxy** all deployed services via a built-in nginx instance with HTTP and TCP stream support
- **Plugin system** — install self-contained applications (e.g. backup-manager) by providing a repo URL; the platform manages their Docker lifecycle and integrates with their capabilities (e.g. image allowlists)
- **Multi-tenant** — each tenant gets their own Proxmox SDN VNet and firewall isolation zone

## Architecture

```
[Browser] → [Frontend :3333] → [Backend API :8080]
                                        │
                               [Proxmox API :8006]
                                        │
                              Proxmox Cluster Nodes
                              (VM/LXC/firewall/DNS)

[Backend/Worker] → [nginx] → deployed services (HTTP/TCP proxy)

[Worker] → [Plugin containers] → integration endpoints (/platform/*)
```

**Services:**

| Service | Role |
|---|---|
| `frontend` | Next.js 15 + Mantine UI dashboard |
| `backend` | FastAPI — CRUD, auth, orchestration |
| `worker` | Celery — async provisioning, plugin install, nginx reload |
| `scheduler` | Celery Beat — cluster sync, plugin health checks, log cleanup |
| `nginx` | Reverse proxy for deployed services |
| `rabbitmq` | Task broker |
| `app_db` | PostgreSQL — app state, logs |

## First Run

1. Copy `.env.example` to `.env` and fill in credentials.
2. Start all services:
   ```bash
   docker compose up -d
   ```
3. Open `http://localhost:3333` — you will be redirected to the setup wizard.
4. In the wizard: enter the Proxmox VE API URL, select the version (7.x or 8.x), and provide an API token (`root@pam!infra-manager` or similar). The platform will validate the connection.
5. Register an admin account. The first registered user is automatically admin.

## Proxmox Prerequisites

Before deploying:

- **Proxmox SDN** must be enabled and at least one zone configured. The platform provisions tenant VNets inside this zone.
- **API token** must exist with sufficient permissions: `VM.Allocate`, `VM.Config.*`, `SDN.*`, `Firewall.*`, `Sys.Audit`.
- For **Docker provisioning on QEMU VMs**: `qemu-guest-agent` must be installed and running inside the VM.
- For **Docker provisioning on LXC containers**: no extra setup — uses the Proxmox LXC exec endpoint directly.

## Plugin System

Plugins are self-contained applications installed by providing a Git repo URL. The platform:
1. Clones the repo into `/plugins/{name}/`
2. Reads `infra-plugin.yaml` from the repo root
3. Runs the plugin's Docker Compose stack
4. Integrates with the plugin via its `/platform/*` endpoints

### Plugin Manifest (`infra-plugin.yaml`)

```yaml
name: backup-manager
version: "1.0"
description: "Multi-source backup management"
compose_file: docker-compose.yaml
env_vars:
  - DATABASE_URL
  - SECRET_KEY
  - RABBITMQ_URL
integration:
  base_path: /platform
  capabilities:
    - name: image_allowlist
      endpoint: /platform/images
    - name: health
      endpoint: /platform/health
```

### Integrating an Existing App as a Plugin

Add a lightweight router to the app under `/platform`:

```python
# src/api/platform_integration.py
from fastapi import APIRouter

platform_router = APIRouter(prefix="/platform")

@platform_router.get("/health")
def health():
    return {"status": "ok", "version": "1.0"}

@platform_router.get("/images")
def allowed_images():
    return {
        "images": [
            {"name": "postgres", "tags": ["15", "16", "17"], "description": "PostgreSQL"},
        ]
    }
```

The app remains fully self-contained. The integration router is purely additive.

## Docker Image Allowlist

Docker services can only be deployed if their image appears in the allowlist. The allowlist is the **union** of:
- Capabilities returned by installed plugins with `image_allowlist` capability
- Platform-local overrides (admin-managed via `/ui/settings/images`)

If a plugin is temporarily unreachable, the platform falls back to its last cached response.

## Ports

| Service | Host Port |
|---|---|
| Frontend | 3333 |
| Backend API | 8080 |
| Nginx (deployed services) | 80, 443 |
| RabbitMQ management | 15672 |
| PostgreSQL | 5678 |

## Environment Variables

See `.env.example` for all required variables. Key ones:

| Variable | Description |
|---|---|
| `SECRET_KEY` | AES-GCM encryption key for stored credentials |
| `DATABASE_URL` | PostgreSQL connection string |
| `CELERY_BROKER_URL` | RabbitMQ URL |
| `NEXT_PUBLIC_BACKEND_URL` | Backend URL as seen from the browser |
| `DOCKER_GID` | Host Docker group ID (for socket access in worker) |
| `PLUGINS_BASE_DIR` | Path where plugin repos are cloned (default: `/plugins`) |

## Development

### Backend

```bash
cd backend
uv sync
uv run uvicorn src.services.main:app --host 0.0.0.0 --port 8000 --reload
uv run celery -A src.services.worker worker --loglevel=info
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

### Frontend

```bash
cd frontend
yarn install
yarn dev
```
