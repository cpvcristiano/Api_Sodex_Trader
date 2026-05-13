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
    if meta:
        print(meta[0].keys())
        for symbol in meta:
            if 'SOL' in str(symbol):
                print(symbol)
except Exception as e:
    print(f"Error: {e}")
