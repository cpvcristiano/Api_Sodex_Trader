"""
Sodex API credentials and configuration.

IMPORTANT: In production, load these from environment variables or a secrets manager.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Master EVM wallet address — used in account query paths (/accounts/{userAddress}/...)
WALLET_ADDRESS = os.getenv("SODEX_WALLET")

# API key: EVM address derived from the API private key (registered sub-key on Sodex)
# Used for signing requests; the address is NOT sent directly as the X-API-Key header.
API_KEY = os.getenv("SODEX_API_KEY")

# Name of the API key as shown in the Sodex UI (Settings → API Keys → Name column).
# This is what the server expects in the X-API-Key header.
API_KEY_NAME = os.getenv("SODEX_API_KEY_NAME", "SODEX_API_KEY")

# ECDSA private key corresponding to API_KEY — used for EIP-712 signing
PRIVATE_KEY = os.getenv("SODEX_PRIVATE_KEY")

# Set to True to use testnet instead of mainnet
USE_TESTNET = os.getenv("SODEX_TESTNET", "false").lower() == "true"

if not WALLET_ADDRESS or not API_KEY or not PRIVATE_KEY:
    print("WARNING: Missing environment variables for Sodex API. Please check your .env file.")
