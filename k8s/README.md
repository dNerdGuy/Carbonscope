# CarbonScope Kubernetes Deployment

## Prerequisites

- Kubernetes 1.28+
- kubectl configured for your cluster
- NGINX Ingress Controller installed
- cert-manager (for TLS) — optional but recommended

## Quick Start

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Configure secrets using a local untracked file
cp k8s/secrets.local.example.yaml k8s/secrets.local.yaml
vi k8s/secrets.local.yaml
kubectl apply -f k8s/secrets.local.yaml

# Alternative: use External Secrets Operator (recommended for production)
# Install operator: https://external-secrets.io/latest/introduction/getting-started/
# Then apply: kubectl apply -f k8s/external-secrets.yaml

# Alternative: apply tracked template only in ephemeral/dev contexts
# vi k8s/secrets.yaml
# kubectl apply -f k8s/secrets.yaml

# 3. Apply ConfigMap
kubectl apply -f k8s/configmap.yaml

# 4. Deploy data stores
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml

# 5. Wait for data stores to be ready
kubectl -n carbonscope wait --for=condition=ready pod -l app=postgres --timeout=120s
kubectl -n carbonscope wait --for=condition=ready pod -l app=redis --timeout=60s

# 6. Deploy application
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml

# 7. Expose via Ingress (edit host in ingress.yaml first)
kubectl apply -f k8s/ingress.yaml
```

## Apply All at Once

```bash
kubectl apply -f k8s/
```

## Verify Deployment

```bash
kubectl -n carbonscope get pods
kubectl -n carbonscope get services
kubectl -n carbonscope get ingress
```

## Scaling

Autoscaling is handled by HorizontalPodAutoscalers defined in `hpa.yaml`:

- **Backend**: 2–8 replicas, scales on CPU (70%) and memory (80%)
- **Frontend**: 2–4 replicas, scales on CPU (70%)
- **Redis**: 1–3 replicas, scales on memory (75%) and CPU (70%)

```bash
# Check HPA status
kubectl -n carbonscope get hpa

# Manual override
kubectl -n carbonscope scale deployment backend --replicas=4
```

## High Availability

- **PodDisruptionBudgets** (`pdb.yaml`): Ensure at least 1 pod stays available during node drains
- **NetworkPolicies** (`network-policy.yaml`): Deny-by-default ingress, allow only required traffic
- **ResourceQuota** (`resource-quota.yaml`): Caps namespace at 8 CPU / 8Gi RAM requests, 16 CPU / 16Gi RAM limits, 30 pods, 5 PVCs

### Resource Quota Details

The namespace-level quota prevents runaway resource consumption:

| Resource | Limit |
|---|---|
| CPU requests | 8 cores |
| Memory requests | 8 Gi |
| CPU limits | 16 cores |
| Memory limits | 16 Gi |
| Pods | 30 |
| PVCs | 5 |

To check current usage:

```bash
kubectl -n carbonscope describe resourcequota carbonscope-quota
```

## Database Migrations

Migrations run automatically via the backend init container on each deploy.
To run manually:

```bash
kubectl -n carbonscope exec deploy/backend -- alembic upgrade head
```

## Monitoring

```bash
# View logs
kubectl -n carbonscope logs deploy/backend -f
kubectl -n carbonscope logs deploy/frontend -f

# Check resource usage
kubectl -n carbonscope top pods
```

### Prometheus (optional)

If the [Prometheus Operator](https://prometheus-operator.dev/) is installed in your cluster:

```bash
kubectl apply -f k8s/monitoring.yaml
```

This creates a **ServiceMonitor** (scrapes `/metrics` every 30 s) and **PrometheusRule** alerts for high error rate, high latency, pod crash loops, and backup failures.

## Automated Backups

A CronJob runs `pg_dump` at 02:00 UTC daily and stores compressed backups in a 20 Gi PVC. Backups older than 30 days are pruned automatically.

```bash
kubectl apply -f k8s/cronjob-backup.yaml

# Check backup history
kubectl -n carbonscope get jobs -l component=backup
```

## Customization

- **Domain**: Edit `host` in [ingress.yaml](ingress.yaml)
- **Replicas**: Edit `spec.replicas` in backend/frontend deployments
- **Resources**: Adjust `resources.requests/limits` per workload
- **Storage**: Modify PVC sizes in postgres.yaml and redis.yaml
- **TLS**: The Ingress uses cert-manager with Let's Encrypt by default
