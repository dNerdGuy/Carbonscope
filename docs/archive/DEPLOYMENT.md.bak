# CarbonScope — Deployment Guide

This guide covers deploying the CarbonScope platform (FastAPI backend + Next.js frontend) to a production environment.

---

## Prerequisites

- **Python 3.12+** (tested with 3.14)
- **Node.js 20+** (for the Next.js frontend)
- **PostgreSQL 15+** (asyncpg driver)
- **Nginx** or another reverse proxy with TLS termination
- (Optional) **Redis** for caching / rate limiting at scale

---

## 1. Environment Variables

Create a `.env` file (never commit this) or configure via your orchestration tool:

```bash
# ── Required ────────────────────────────────────────────
ENV=production
DATABASE_URL=postgresql+asyncpg://carbonscope:SECRET@db-host:5432/carbonscope
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# ── CORS / Frontend ────────────────────────────────────
ALLOWED_ORIGINS=https://app.example.com
COOKIE_DOMAIN=.example.com

# ── Logging ─────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_JSON=true          # structured JSON logs for aggregation

# ── Rate Limiting ───────────────────────────────────────
RATE_LIMIT_AUTH=10/minute
RATE_LIMIT_DEFAULT=60/minute

# ── Bittensor (if using subnet mode) ───────────────────
ESTIMATION_MODE=subnet   # or "local" for fallback
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
```

### Production Safety Checks

The application **refuses to start** in production if:

- `SECRET_KEY` is the default value or shorter than 32 characters
- `DATABASE_URL` contains `sqlite` (PostgreSQL required)

---

## 2. Database Setup

### Create the database

```bash
createdb carbonscope
```

### Run Alembic migrations

```bash
cd /path/to/carbonscope
alembic upgrade head
```

This applies all schema migrations in order. Never use `create_all()` in production; the app skips it when `ENV=production`.

---

## 3. Backend Deployment

### Install dependencies

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

For systemd, create `/etc/systemd/system/carbonscope-api.service`:

```ini
[Unit]
Description=CarbonScope API
After=network.target postgresql.service

[Service]
User=carbonscope
WorkingDirectory=/opt/carbonscope
EnvironmentFile=/opt/carbonscope/.env
ExecStart=/opt/carbonscope/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 4. Frontend Deployment

### Build

```bash
cd frontend
npm ci
npm run build
```

### Run

```bash
npm start -- -p 3000
```

Or use a process manager (PM2, systemd) to keep the Next.js server running. Set `NEXT_PUBLIC_API_URL` if the API is on a different host.

---

## 5. Nginx Reverse Proxy (TLS)

```nginx
server {
    listen 443 ssl http2;
    server_name app.example.com;

    ssl_certificate     /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;

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
    }

    # Health check (no auth)
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}

server {
    listen 80;
    server_name app.example.com;
    return 301 https://$host$request_uri;
}
```

---

## 6. Docker Deployment

```bash
docker build -t carbonscope .
docker run -d \
  --name carbonscope \
  --env-file .env \
  -p 8000:8000 \
  carbonscope
```

The Dockerfile runs as a non-root `appuser` for security.

---

## 7. Monitoring & Health

| Endpoint   | Purpose                                 |
| ---------- | --------------------------------------- |
| `/health`  | DB connectivity, email/Bittensor config |
| `/metrics` | Uptime, total request count, version    |

Set up external monitoring (e.g., UptimeRobot, Datadog) to poll `/health` every 60s.

Logs are emitted as structured JSON when `LOG_JSON=true` — pipe to your log aggregator (ELK, Loki, CloudWatch).

---

## 8. Pre-Launch Checklist

- [ ] `ENV=production` is set
- [ ] `SECRET_KEY` is a 64+ character random hex string
- [ ] `DATABASE_URL` points to PostgreSQL (not SQLite)
- [ ] `alembic upgrade head` has been run
- [ ] `ALLOWED_ORIGINS` is set to the frontend domain
- [ ] TLS is configured (HSTS header is automatic over HTTPS)
- [ ] SMTP credentials are configured for password reset emails
- [ ] Bittensor wallet is configured (if using subnet mode)
- [ ] `/health` returns `{"status": "ok"}`
- [ ] Log aggregation is configured
- [ ] Backups are scheduled for the PostgreSQL database
