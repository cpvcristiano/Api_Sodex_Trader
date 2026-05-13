import os
from config import API_KEY, API_KEY_NAME, PRIVATE_KEY, WALLET_ADDRESS
from sodex import SodexClient

client = SodexClient(
    api_key=API_KEY,
    private_key=PRIVATE_KEY,
    api_key_name=API_KEY_NAME,
    wallet_address=WALLET_ADDRESS,
    testnet=False,
)

try:
    meta = client.perps_symbols()
    sol = [s for s in meta if 'SOL' in s['name']][0]
    print(f"PRICE_PRECISION: {sol.get('pricePrecision')}")
    print(f"QTY_PRECISION: {sol.get('quantityPrecision')}")
    print(f"TICK_SIZE: {sol.get('tickSize')}")
    print(f"STEP_SIZE: {sol.get('stepSize')}")
except Exception as e:
    print(f"Error: {e}")
