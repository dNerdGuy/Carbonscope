# CarbonScope — Deployment Guide

> Production deployment guide for the CarbonScope platform (FastAPI backend + Next.js frontend).

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Database Setup](#database-setup)
- [Backend Deployment](#backend-deployment)
- [Frontend Deployment](#frontend-deployment)
- [Nginx Reverse Proxy](#nginx-reverse-proxy)
- [Docker Deployment](#docker-deployment)
- [Bittensor Subnet Setup](#bittensor-subnet-setup)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Scaling](#scaling)
- [Backup & Recovery](#backup--recovery)
- [Pre-Launch Checklist](#pre-launch-checklist)

---

## Prerequisites

| Requirement   | Version  | Purpose                                       |
| :------------ | :------- | :-------------------------------------------- |
| Python        | 3.10+    | Backend runtime                               |
| Node.js       | 18+      | Frontend build & runtime                      |
| PostgreSQL    | 15+      | Production database (asyncpg driver)          |
| Nginx         | 1.24+    | Reverse proxy with TLS termination            |
| Bittensor SDK | ≥ 10.1.0 | Subnet communication (if using subnet mode)   |
| Redis         | 7+       | Optional — caching and rate limiting at scale |

---

## Environment Variables

Create a `.env` file (never commit this) or configure via your orchestration tool.

### Required

```bash
ENV=production
DATABASE_URL=postgresql+asyncpg://carbonscope:SECRET@db-host:5432/carbonscope
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
ALLOWED_ORIGINS=https://app.example.com
```

### Optional

````bash
# ── CORS / Cookies ──────────────────────────────────────
COOKIE_DOMAIN=.example.com
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
TRUST_PROXY=true                    # Set true behind reverse proxy

# ── Logging ─────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_JSON=true                       # Structured JSON logs for aggregation

# ── Rate Limiting ───────────────────────────────────────
RATE_LIMIT_AUTH=10/minute
RATE_LIMIT_DEFAULT=60/minute

# ── JWT ─────────────────────────────────────────────────
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── Database observability ─────────────────────────────
DB_SLOW_QUERY_MS=500               # Warn when query duration exceeds threshold

# ── Bittensor (subnet mode) ────────────────────────────
ESTIMATION_MODE=subnet              # or "local" for built-in engine
BT_NETWORK=finney
BT_NETUID=<your-subnet-uid>
BT_WALLET_NAME=api_client
BT_WALLET_HOTKEY=default
BT_QUERY_TIMEOUT=30.0

# ── Email (SMTP) ───────────────────────────────────────
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=<smtp-password>
EMAIL_FROM=noreply@example.com
REQUIRE_SMTP_IN_PRODUCTION=false   # true = fail fast if SMTP vars are missing

# ── LLM (optional AI features) ─────────────────────────
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
# ── Stripe (optional billing integration) ────────────
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Production Safety Checks

The application **refuses to start** in production if:

- `SECRET_KEY` is the default value or shorter than 32 characters
- `SECRET_KEY` has fewer than 10 unique characters
- `DATABASE_URL` contains `sqlite` (PostgreSQL required in production)
- `REQUIRE_SMTP_IN_PRODUCTION=true` and SMTP credentials are incomplete

---

## Database Setup

### Create the Database

```bash
createdb carbonscope
````

### Run Alembic Migrations

```bash
cd /path/to/carbonscope
alembic upgrade head
```

This applies all schema migrations in order. The application skips `create_all()` in production mode — always use Alembic.

### Migration Commands Reference

```bash
alembic upgrade head                                # Apply all pending
alembic downgrade -1                                # Rollback one revision
alembic current                                     # Show current revision
alembic history                                     # Show migration history
alembic revision --autogenerate -m "description"    # Generate new migration
```

---

## Backend Deployment

### Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run with Uvicorn

```bash
uvicorn api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

### Systemd Service

Create `/etc/systemd/system/carbonscope-api.service`:

```ini
[Unit]
Description=CarbonScope API
After=network.target postgresql.service

[Service]
User=carbonscope
WorkingDirectory=/opt/carbonscope
EnvironmentFile=/opt/carbonscope/.env
ExecStart=/opt/carbonscope/.venv/bin/uvicorn api.main:app \
  --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable carbonscope-api
sudo systemctl start carbonscope-api
sudo journalctl -u carbonscope-api -f    # View logs
```

---

## Frontend Deployment

### Build

```bash
cd frontend
npm ci
npm run build
```

The build produces a standalone output at `.next/standalone/`.

### Run

```bash
npm start -- -p 3000
```

Set `BACKEND_URL` if the API is on a different host (defaults to `http://localhost:8000`). The Next.js config rewrites `/api/*` requests to the backend.

### Systemd Service

Create `/etc/systemd/system/carbonscope-frontend.service`:

```ini
[Unit]
Description=CarbonScope Frontend
After=network.target

[Service]
User=carbonscope
WorkingDirectory=/opt/carbonscope/frontend
Environment=NODE_ENV=production
Environment=BACKEND_URL=http://127.0.0.1:8000
ExecStart=/usr/bin/node .next/standalone/server.js
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### PM2 Alternative

```bash
npm install -g pm2
cd frontend
pm2 start .next/standalone/server.js --name carbonscope-frontend
pm2 save
pm2 startup
```

---

## Nginx Reverse Proxy

### TLS with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d app.example.com
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name app.example.com;

    ssl_certificate     /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;

    # Security headers (supplement FastAPI middleware)
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # File upload limit (questionnaire documents)
        client_max_body_size 10M;
    }

    # Health check (no auth)
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    # Metrics (restrict to internal)
    location /metrics {
        proxy_pass http://127.0.0.1:8000/metrics;
        allow 127.0.0.1;
        deny all;
    }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name app.example.com;
    return 301 https://$host$request_uri;
}
```

Set `TRUST_PROXY=true` in `.env` so the backend honors `X-Forwarded-For` headers for rate limiting.

---

## Docker Deployment

### Development

```bash
docker compose up --build -d
curl http://localhost:8000/health
```

The development stack uses SQLite with volume persistence.

### Production

```bash
# Configure environment
cp .env.example .env     # Edit with production values
export POSTGRES_PASSWORD=$(openssl rand -hex 16)

# Start the stack
docker compose -f docker-compose.prod.yml up --build -d
```

The production stack includes:

| Service      | Image              | Resources      | Notes                                 |
| :----------- | :----------------- | :------------- | :------------------------------------ |
| **db**       | PostgreSQL 16      | 512 MB / 1 CPU | Persistent volume, health check       |
| **backend**  | Python 3.12-slim   | 1 GB / 2 CPUs  | Non-root `appuser`, no-new-privileges |
| **frontend** | Node 20 standalone | 512 MB / 1 CPU | Depends on backend health             |

### Dockerfile Overview

The multi-stage Dockerfile produces two targets:

1. **`backend`** — Python 3.12-slim with `requirements.txt` deps, runs as non-root `appuser` (UID 1000)
2. **`frontend`** — Three stages: install deps → build → standalone runtime. Runs as built-in `node` user

### Custom Docker Build

```bash
# Backend only
docker build --target backend -t carbonscope-api .

# Frontend only
docker build --target frontend -t carbonscope-frontend .
```

---

## Bittensor Subnet Setup

Skip this section if using `ESTIMATION_MODE=local`.

### 1. Create Wallets

```bash
btcli wallet create --wallet.name api_client --wallet.hotkey default
```

### 2. Register on Subnet

```bash
btcli subnet register \
  --wallet.name api_client \
  --wallet.hotkey default \
  --netuid <YOUR_SUBNET_UID> \
  --subtensor.network finney
```

### 3. Configure

```bash
ESTIMATION_MODE=subnet
BT_NETWORK=finney
BT_NETUID=<YOUR_SUBNET_UID>
BT_WALLET_NAME=api_client
BT_WALLET_HOTKEY=default
BT_QUERY_TIMEOUT=30.0
```

### Running Miners & Validators

```bash
./scripts/run_miner.sh          # Starts Axon server (port 8091)
./scripts/run_validator.sh      # Starts Dendrite client
```

All scripts accept environment variables: `NETUID`, `WALLET_NAME`, `HOTKEY`, `SUBTENSOR_NETWORK`, `AXON_PORT`.

---

## Monitoring & Health Checks

### Endpoints

| Endpoint   | Auth | Purpose                                         |
| :--------- | :--: | :---------------------------------------------- |
| `/health`  |  No  | DB connectivity, email config, Bittensor status |
| `/metrics` |  No  | Uptime (seconds), total request count, version  |

### External Monitoring

Set up an external monitor (UptimeRobot, Datadog, Prometheus) to poll `/health` every 60 seconds. Alert on non-`200` responses.

### Log Aggregation

When `LOG_JSON=true` (automatic in production), logs are emitted as structured JSON — pipe to your log aggregator:

- **ELK Stack** — Filebeat → Logstash → Elasticsearch
- **Grafana Loki** — Promtail → Loki → Grafana
- **AWS CloudWatch** — CloudWatch agent or Docker log driver

### Key Log Fields

| Field         | Description             |
| :------------ | :---------------------- |
| `request_id`  | Unique request trace ID |
| `method`      | HTTP method             |
| `path`        | Request path            |
| `status`      | Response status code    |
| `duration_ms` | Request duration        |

---

## Scaling

### Horizontal Scaling (Backend)

```bash
# Increase Uvicorn workers
uvicorn api.main:app --workers 8

# Or run multiple containers behind a load balancer
docker compose -f docker-compose.prod.yml up --scale backend=4
```

### Database Connection Pooling

For high-traffic deployments, use PgBouncer or a managed connection pooler:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@pgbouncer:6432/carbonscope
```

### Frontend CDN

For static assets, deploy the Next.js standalone server behind a CDN (CloudFront, Cloudflare) with appropriate cache headers.

---

## Backup & Recovery

Detailed operational procedure: see `BACKUP_RESTORE_RUNBOOK.md`.

### PostgreSQL Backups

```bash
# Full backup
pg_dump -h localhost -U carbonscope -d carbonscope -F c -f backup_$(date +%Y%m%d).dump

# Restore
pg_restore -h localhost -U carbonscope -d carbonscope backup_20240115.dump
```

### Automated Backups (cron)

```cron
0 2 * * * pg_dump -h localhost -U carbonscope -d carbonscope -F c -f /backups/carbonscope_$(date +\%Y\%m\%d).dump
0 3 * * 0 find /backups -name "*.dump" -mtime +30 -delete
```

---

## Pre-Launch Checklist

- [ ] `ENV=production` is set
- [ ] `SECRET_KEY` is a 64+ character random hex string with high entropy
- [ ] `DATABASE_URL` points to PostgreSQL (not SQLite)
- [ ] `alembic upgrade head` has been run successfully
- [ ] `ALLOWED_ORIGINS` is set to the exact frontend domain
- [ ] TLS is configured with valid certificates
- [ ] `TRUST_PROXY=true` is set (if behind Nginx/load balancer)
- [ ] SMTP credentials are configured for password reset emails
- [ ] Bittensor wallet is registered (if using subnet mode)
- [ ] `/health` returns `{"status": "ok"}`
- [ ] Rate limits are tuned for expected traffic
- [ ] Log aggregation is configured
- [ ] Backups are scheduled for PostgreSQL
- [ ] Monitoring/alerting is set up for `/health` endpoint
- [ ] `client_max_body_size` is set in Nginx (≥ 10M for file uploads)
- [ ] Firewall rules restrict direct access to ports 8000/3000 (only Nginx exposed)

---

## CI/CD Pipeline

The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) with 5 jobs:

| Job          | Description                                                |
| :----------- | :--------------------------------------------------------- |
| **test**     | Backend tests on Python 3.11 + 3.12 matrix (`pytest`)      |
| **lint**     | Ruff linting (`ruff check . --select E,F,W --ignore E501`) |
| **frontend** | Frontend test suite (`vitest`)                             |
| **security** | `pip-audit` + `bandit` security scans                      |
| **docker**   | Docker image build verification                            |

The pipeline runs on pushes to `main` and on all pull requests.

---

## Kubernetes Deployment Runbook

### Prerequisites

- Kubernetes 1.28+ cluster with `kubectl` configured
- NGINX Ingress Controller installed
- cert-manager for automatic TLS (recommended)
- Container images published to `ghcr.io/carbonscope/carbonscope`

### Initial Deployment

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Edit secrets with real base64-encoded values
#    echo -n "your-secret-value" | base64
vim k8s/secrets.yaml
kubectl apply -f k8s/secrets.yaml

# 3. Apply config + infrastructure
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/resource-quota.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 4. Wait for data stores
kubectl -n carbonscope wait --for=condition=ready pod -l app=postgres --timeout=120s
kubectl -n carbonscope wait --for=condition=ready pod -l app=redis --timeout=60s

# 5. Deploy application + policies
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/pdb.yaml
kubectl apply -f k8s/network-policy.yaml
kubectl apply -f k8s/ingress.yaml
```

### Rolling Update

```bash
# Update image tag and apply
kubectl -n carbonscope set image deployment/backend backend=ghcr.io/carbonscope/carbonscope:v0.17.0
kubectl -n carbonscope rollout status deployment/backend

# Rollback if needed
kubectl -n carbonscope rollout undo deployment/backend
```

### Monitoring

```bash
# Pod status
kubectl -n carbonscope get pods -o wide

# HPA status (current vs desired replicas)
kubectl -n carbonscope get hpa

# Resource usage
kubectl -n carbonscope top pods

# Logs
kubectl -n carbonscope logs deploy/backend -f --tail=100
kubectl -n carbonscope logs deploy/frontend -f --tail=100

# Check resource quota consumption
kubectl -n carbonscope describe resourcequota carbonscope-quota
```

### Database Maintenance

```bash
# Manual migration
kubectl -n carbonscope exec deploy/backend -- alembic upgrade head

# Database shell
kubectl -n carbonscope exec -it deploy/postgres -- psql -U carbonscope

# Backup (pipe to local file)
kubectl -n carbonscope exec deploy/postgres -- pg_dump -U carbonscope carbonscope > backup.sql
```

### Troubleshooting

| Symptom                  | Check                                                                                          |
| :----------------------- | :--------------------------------------------------------------------------------------------- |
| Pods in CrashLoopBackOff | `kubectl -n carbonscope describe pod <name>` + `kubectl -n carbonscope logs <name> --previous` |
| 503 from Ingress         | Verify readiness probe: `kubectl -n carbonscope get endpoints backend`                         |
| HPA not scaling          | Check metrics-server: `kubectl -n kube-system get pods -l k8s-app=metrics-server`              |
| Network timeouts         | Verify NetworkPolicy: `kubectl -n carbonscope get networkpolicy`                               |
