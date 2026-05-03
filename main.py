"""
Sodex API — connection test and usage examples.

Run: python main.py
"""
import json

from config import API_KEY, API_KEY_NAME, PRIVATE_KEY, WALLET_ADDRESS, USE_TESTNET
from sodex import SodexClient


def print_result(label: str, data) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    if isinstance(data, list):
        print(f"  [{len(data)} items]")
        if data:
            print(json.dumps(data[0], indent=2, default=str))
            if len(data) > 1:
                print(f"  ... and {len(data)-1} more")
    else:
        print(json.dumps(data, indent=2, default=str))


def main():
    net = "TESTNET" if USE_TESTNET else "MAINNET"
    print(f"\nConnecting to Sodex {net}...")
    print(f"Wallet  : {WALLET_ADDRESS}")
    print(f"API Key : {API_KEY}")

    client = SodexClient(
        api_key=API_KEY,
        private_key=PRIVATE_KEY,
        api_key_name=API_KEY_NAME,
        wallet_address=WALLET_ADDRESS,
        testnet=USE_TESTNET,
    )

    # ------------------------------------------------------------------
    # 1. Spot symbols
    # ------------------------------------------------------------------
    print("\n[1] Fetching spot symbols...")
    try:
        symbols = client.spot_symbols()
        print_result("Spot Symbols", symbols)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # 2. Spot tickers
    # ------------------------------------------------------------------
    print("\n[2] Fetching spot tickers...")
    try:
        tickers = client.spot_tickers()
        print_result("Spot Tickers", tickers)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # 3. Perps symbols
    # ------------------------------------------------------------------
    print("\n[3] Fetching perps symbols...")
    try:
        perps_syms = client.perps_symbols()
        print_result("Perps Symbols", perps_syms)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # 4. Perps mark prices
    # ------------------------------------------------------------------
    print("\n[4] Fetching perps mark prices...")
    try:
        marks = client.perps_mark_prices()
        print_result("Perps Mark Prices", marks)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # 5. Account balances (uses own API key address)
    # ------------------------------------------------------------------
    print("\n[5] Fetching spot balances...")
    try:
        balances = client.spot_balances()
        print_result("Spot Balances", balances)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # 6. Spot open orders
    # ------------------------------------------------------------------
    print("\n[6] Fetching spot open orders...")
    try:
        orders = client.spot_open_orders()
        print_result("Spot Open Orders", orders)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # 7. Perps account state
    # ------------------------------------------------------------------
    print("\n[7] Fetching perps account state...")
    try:
        state = client.perps_account_state()
        print_result("Perps Account State", state)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # 8. Fee rate
    # ------------------------------------------------------------------
    print("\n[8] Fetching spot fee rate...")
    try:
        fee = client.spot_fee_rate()
        print_result("Spot Fee Rate", fee)
    except Exception as e:
        print(f"  ERROR: {e}")

    # ------------------------------------------------------------------
    # PLACE ORDER EXAMPLE (disabled by default)
    # Uncomment to test. Import enums at the top when enabling.
    #   from sodex import OrderSide, OrderType, TimeInForce
    #
    # ACCOUNT_ID = 0  # <-- set your numeric account ID (from account state)
    # SYMBOL_ID  = 1  # <-- get from spot_symbols()
    #
    # result = client.spot_new_order(
    #     account_id=ACCOUNT_ID,
    #     symbol_id=SYMBOL_ID,
    #     cl_ord_id="buy-001",
    #     side=OrderSide.BUY,
    #     order_type=OrderType.LIMIT,
    #     time_in_force=TimeInForce.GTC,
    #     price="1.00",
    #     quantity="1.00",
    # )
    # print_result("New Order Result", result)
    # ------------------------------------------------------------------

    print("\nDone.")


if __name__ == "__main__":
    main()
