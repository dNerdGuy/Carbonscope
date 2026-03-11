#!/usr/bin/env bash
# Run CarbonScope miner
set -euo pipefail

NETUID="${NETUID:-1}"
WALLET_NAME="${WALLET_NAME:-miner}"
HOTKEY="${HOTKEY:-default}"
SUBTENSOR_NETWORK="${SUBTENSOR_NETWORK:-test}"
AXON_PORT="${AXON_PORT:-8091}"

echo "=== Starting CarbonScope Miner ==="
echo "Network:  $SUBTENSOR_NETWORK"
echo "NetUID:   $NETUID"
echo "Port:     $AXON_PORT"

python -m neurons.miner \
    --netuid "$NETUID" \
    --wallet.name "$WALLET_NAME" \
    --wallet.hotkey "$HOTKEY" \
    --subtensor.network "$SUBTENSOR_NETWORK" \
    --axon.port "$AXON_PORT" \
    "$@"
