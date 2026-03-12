# ── Backend (FastAPI) ────────────────────────────────────────────────
FROM python:3.12-slim AS backend

WORKDIR /app

# Install system deps for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY alembic/ alembic/
COPY alembic.ini .
COPY carbonscope/ carbonscope/

# Create data directory and non-root user
RUN useradd -r -s /usr/sbin/nologin -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ── Frontend (Next.js) ──────────────────────────────────────────────
FROM node:20-alpine AS frontend-deps

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts

FROM node:20-alpine AS frontend-build

WORKDIR /app
COPY --from=frontend-deps /app/node_modules ./node_modules
COPY frontend/ .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS frontend

WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=frontend-build /app/.next/standalone ./
COPY --from=frontend-build /app/.next/static ./.next/static
COPY --from=frontend-build /app/public ./public

USER node

EXPOSE 3000

CMD ["node", "server.js"]
