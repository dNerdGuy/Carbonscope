#!/usr/bin/env bash
# Register CarbonScope miner on testnet
set -euo pipefail

NETUID="${NETUID:-1}"
WALLET_NAME="${WALLET_NAME:-miner}"
HOTKEY="${HOTKEY:-default}"
SUBTENSOR_NETWORK="${SUBTENSOR_NETWORK:-test}"

echo "=== CarbonScope Subnet Registration ==="
echo "Network:  $SUBTENSOR_NETWORK"
echo "NetUID:   $NETUID"
echo "Wallet:   $WALLET_NAME"
echo "Hotkey:   $HOTKEY"
echo ""

# Create wallet if it doesn't exist
btcli wallet create --wallet.name "$WALLET_NAME" --wallet.hotkey "$HOTKEY" --no_prompt 2>/dev/null || true

# Get testnet TAO from faucet (testnet only)
if [ "$SUBTENSOR_NETWORK" = "test" ]; then
    echo "Requesting testnet TAO from faucet..."
    btcli wallet faucet --wallet.name "$WALLET_NAME" --subtensor.network "$SUBTENSOR_NETWORK" --no_prompt || true
fi

# Register on subnet
echo "Registering on subnet $NETUID..."
btcli subnet register \
    --wallet.name "$WALLET_NAME" \
    --wallet.hotkey "$HOTKEY" \
    --netuid "$NETUID" \
    --subtensor.network "$SUBTENSOR_NETWORK" \
    --no_prompt

echo "Registration complete."
