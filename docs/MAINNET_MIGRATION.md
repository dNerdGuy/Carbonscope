# Bittensor Mainnet Migration Runbook

> Last updated: 2025  
> Audience: DevOps / Platform team  
> Estimated downtime: 0 (rolling migration)

---

## Prerequisites

| Requirement | Check |
|---|---|
| **Funded mainnet coldkey** with sufficient TAO for registration | `btcli wallet balance --wallet.name <NAME> --subtensor.network finney` |
| **Registered hotkey** on the target subnet | `btcli subnet register --netuid <UID> --wallet.name <NAME> --subtensor.network finney` |
| **Kubernetes cluster** with secrets provisioned (see `k8s/external-secrets.yaml`) | `kubectl get secrets -n carbonscope` |
| **Database migrations** applied (Alembic) | `alembic upgrade head` |
| **Monitoring** in place (Prometheus + Grafana dashboard from `k8s/grafana-dashboard.json`) | `/health/detail` returns all-green |

---

## Step 1 — Create & Fund Mainnet Wallets

```bash
# Create coldkey (store mnemonic securely!)
btcli wallet create --wallet.name carbonscope_mainnet

# Create hotkeys for miner and validator
btcli wallet create --wallet.name carbonscope_mainnet --wallet.hotkey miner
btcli wallet create --wallet.name carbonscope_mainnet --wallet.hotkey validator

# Fund the coldkey with TAO (transfer or exchange)
btcli wallet balance --wallet.name carbonscope_mainnet --subtensor.network finney
```

> **Security**: Never commit mnemonics or keyfiles to version control. Use the external-secrets operator (`k8s/external-secrets.yaml`) or a hardware wallet for production.

---

## Step 2 — Register on Mainnet Subnet

```bash
# Register miner hotkey
btcli subnet register \
  --netuid <TARGET_NETUID> \
  --wallet.name carbonscope_mainnet \
  --wallet.hotkey miner \
  --subtensor.network finney

# Register validator hotkey
btcli subnet register \
  --netuid <TARGET_NETUID> \
  --wallet.name carbonscope_mainnet \
  --wallet.hotkey validator \
  --subtensor.network finney

# Verify registration
btcli subnet metagraph --netuid <TARGET_NETUID> --subtensor.network finney
```

---

## Step 3 — Update Environment Configuration

### 3a. Kubernetes ConfigMap

Edit `k8s/configmap.yaml`:

```yaml
data:
  ESTIMATION_MODE: "subnet"        # ← change from "local" to "subnet"
  BT_NETWORK: "finney"             # ← already set, verify
  BT_NETUID: "<TARGET_NETUID>"     # ← update to your subnet UID
  BT_WALLET_NAME: "carbonscope_mainnet"
  BT_WALLET_HOTKEY: "default"
  BT_QUERY_TIMEOUT: "30.0"
```

Apply:

```bash
kubectl apply -f k8s/configmap.yaml -n carbonscope
```

### 3b. Kubernetes Secrets

Ensure wallet keyfiles are available in the pod via external secrets or mounted volumes:

```bash
# Verify secrets exist
kubectl get secret bittensor-wallet -n carbonscope -o jsonpath='{.data}' | jq keys
```

### 3c. Docker Compose (if applicable)

Add to `docker-compose.prod.yml` backend service:

```yaml
environment:
  ESTIMATION_MODE: subnet
  BT_NETWORK: finney
  BT_NETUID: "<TARGET_NETUID>"
  BT_WALLET_NAME: carbonscope_mainnet
  BT_WALLET_HOTKEY: default
  BT_QUERY_TIMEOUT: "30.0"
```

---

## Step 4 — Deploy Neurons

### Miner

```bash
# Option A: Shell script
NETUID=<TARGET_NETUID> \
SUBTENSOR_NETWORK=finney \
WALLET_NAME=carbonscope_mainnet \
HOTKEY=miner \
./scripts/run_miner.sh

# Option B: Direct
python neurons/miner.py \
  --netuid <TARGET_NETUID> \
  --subtensor.network finney \
  --wallet.name carbonscope_mainnet \
  --wallet.hotkey miner
```

### Validator

```bash
NETUID=<TARGET_NETUID> \
SUBTENSOR_NETWORK=finney \
WALLET_NAME=carbonscope_mainnet \
HOTKEY=validator \
./scripts/run_validator.sh
```

---

## Step 5 — Switch API to Subnet Mode (Rolling)

1. **Canary**: Update one API replica to `ESTIMATION_MODE=subnet` and monitor for 15 minutes.

   ```bash
   kubectl set env deployment/carbonscope-api ESTIMATION_MODE=subnet -n carbonscope
   ```

2. **Verify**: Hit `/health/detail` and confirm `bittensor` status is `"connected"`:

   ```bash
   curl -s https://api.carbonscope.io/health/detail | jq '.bittensor'
   ```

3. **Full rollout**: If canary is healthy, the rolling update will propagate to all replicas.

---

## Step 6 — Post-Migration Verification

| Check | Command / URL |
|---|---|
| Health endpoint | `GET /health/detail` → all services `"ok"` |
| Carbon estimation via subnet | `POST /api/v1/carbon/estimate` with test payload → response includes `miner_scores` |
| Metagraph connectivity | `btcli subnet metagraph --netuid <UID> --subtensor.network finney` |
| Grafana dashboard | Verify `carbonscope_requests_total` counter increments |
| Audit log | `GET /api/v1/audit/` → recent estimation entries present |
| Error rate | `carbonscope_errors_total` should not spike |

---

## Rollback Procedure

If mainnet introduces regressions, revert to local estimation:

```bash
# Immediate: switch back to local mode
kubectl set env deployment/carbonscope-api ESTIMATION_MODE=local -n carbonscope

# Verify health
curl -s https://api.carbonscope.io/health | jq '.status'
```

The `local` estimation engine uses the built-in `carbonscope/scoring.py` and emission factors — no external dependencies. All existing reports and data remain unaffected.

---

## Monitoring Alerts

Set up the following Prometheus alerts during and after migration:

```yaml
# High error rate after migration
- alert: CarbonScopeSubnetErrors
  expr: rate(carbonscope_errors_total[5m]) > 0.1
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Elevated error rate after mainnet migration"

# Subnet query latency
- alert: CarbonScopeHighLatency
  expr: histogram_quantile(0.95, rate(carbonscope_http_request_duration_seconds_bucket[5m])) > 30
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "P95 latency exceeds 30s — possible subnet connectivity issue"
```

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| `bittensor: "unavailable"` in health | Wallet not found in pod | Mount wallet keyfiles or fix secret reference |
| `ConnectionRefusedError` to subtensor | Wrong network or firewall | Verify `BT_NETWORK=finney` and outbound port 9944 is open |
| `NotRegisteredError` | Hotkey not registered on subnet | Run `btcli subnet register` with correct netuid |
| Estimation returns `null` | No active miners responding | Check metagraph for active miners; verify miner axon is reachable |
| High latency (>30s) | Network congestion or slow miners | Increase `BT_QUERY_TIMEOUT`; validator circuit breaker will skip slow miners |
