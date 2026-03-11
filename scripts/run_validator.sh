#!/usr/bin/env bash
# Run CarbonScope validator
set -euo pipefail

NETUID="${NETUID:-1}"
WALLET_NAME="${WALLET_NAME:-validator}"
HOTKEY="${HOTKEY:-default}"
SUBTENSOR_NETWORK="${SUBTENSOR_NETWORK:-test}"

echo "=== Starting CarbonScope Validator ==="
echo "Network:  $SUBTENSOR_NETWORK"
echo "NetUID:   $NETUID"

python -m neurons.validator \
    --netuid "$NETUID" \
    --wallet.name "$WALLET_NAME" \
    --wallet.hotkey "$HOTKEY" \
    --subtensor.network "$SUBTENSOR_NETWORK" \
    --query_interval 60 \
    --query_timeout 30 \
    "$@"
