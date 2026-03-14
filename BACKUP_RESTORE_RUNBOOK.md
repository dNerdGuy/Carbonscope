# Backup and Restore Runbook

This runbook defines the operational procedure for backup creation, restore validation, and recovery drills for CarbonScope.

## Goals

- Ensure recoverability for PostgreSQL data.
- Standardize restore execution for local Docker and Kubernetes deployments.
- Record measurable recovery objectives.

## Recovery Targets

- RTO target: 60 minutes
- RPO target: 24 hours (daily backup schedule)

## Backup Sources

- Docker/local: manual `pg_dump` or cron-based dump.
- Kubernetes: `k8s/cronjob-backup.yaml` creates compressed dump artifacts.

## Restore Procedure (Docker Compose)

1. Identify the backup artifact to restore.
2. Stop backend writes during restore window.
3. Restore database from dump.

```bash
# Example restore for gzip SQL dump
gunzip -c backup_YYYYMMDD.sql.gz | docker exec -i carbonscope-db-1 psql -U carbonscope carbonscope
```

4. Run migration check:

```bash
alembic upgrade head
```

5. Run smoke checks:

```bash
curl -s http://localhost:8000/health
pytest -q tests/test_auth_api.py -k login
```

## Restore Procedure (Kubernetes)

1. Pick a backup file from backup storage/PVC.
2. Scale API workload down to prevent writes:

```bash
kubectl -n carbonscope scale deploy/backend --replicas=0
```

3. Restore dump into PostgreSQL pod/service.

```bash
# Example SQL restore from local machine
cat backup.sql | kubectl -n carbonscope exec -i deploy/postgres -- psql -U carbonscope carbonscope
```

4. Re-apply schema migrations:

```bash
kubectl -n carbonscope exec deploy/backend -- alembic upgrade head
```

5. Scale backend up and run smoke checks:

```bash
kubectl -n carbonscope scale deploy/backend --replicas=2
kubectl -n carbonscope rollout status deploy/backend
kubectl -n carbonscope get pods
```

6. Validate application behavior (auth, report read, billing balance).

## Post-Restore Verification Checklist

- Health endpoint returns ok.
- Auth login succeeds.
- Latest reports are queryable.
- Credit balance endpoint responds for a known company.
- No migration drift (`alembic current` equals expected head).

## Drill Cadence

- Run restore drill weekly in non-production.
- Record:
  - backup artifact used
  - restore start and end timestamp
  - achieved RTO and observed data currency (RPO)
  - failures and corrective actions

## Failure Escalation

- If restore exceeds 60 minutes, escalate to incident channel and declare degradation.
- If data loss exceeds 24 hours, escalate to incident commander and security/compliance stakeholders.
