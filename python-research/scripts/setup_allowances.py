#!/usr/bin/env python3
"""
Setup Allowances - Approve USDC.e spending for Polymarket trading
Run this before placing any trades.

Usage:
    python scripts/setup_allowances.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()


def main():
    """Set up token allowances for Polymarket trading"""
    try:
        from py_clob_client.client import ClobClient
    except ImportError:
        print("Error: py-clob-client not installed")
        print("Run: pip install py-clob-client")
        sys.exit(1)

    private_key = os.getenv("POLYGON_WALLET_PRIVATE_KEY")
    wallet_address = os.getenv("WALLET_ADDRESS")
    clob_url = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")

    if not private_key or not wallet_address:
        print("Error: POLYGON_WALLET_PRIVATE_KEY and WALLET_ADDRESS must be set")
        sys.exit(1)

    print("=" * 60)
    print("POLYMARKET ALLOWANCE SETUP")
    print("=" * 60)
    print(f"Wallet: {wallet_address}")
    print(f"CLOB URL: {clob_url}")
    print()

    # Initialize client
    client = ClobClient(
        clob_url,
        key=private_key,
        chain_id=137,  # Polygon mainnet
        funder=wallet_address,
    )

    # Check and set allowances
    print("Setting up allowances...")

    try:
        # This sets up the necessary allowances for trading
        # The exact method depends on the py-clob-client version
        client.set_allowances()
        print("✅ Allowances set successfully!")
    except Exception as e:
        print(f"❌ Failed to set allowances: {e}")
        print("\nYou may need to manually approve USDC.e spending on Polygon.")
        sys.exit(1)

    print()
    print("You can now run the trading bot.")


if __name__ == "__main__":
    main()
