"""
Sodex REST API client.

Mainnet endpoints:
  Spot:  https://mainnet-gw.sodex.dev/api/v1/spot
  Perps: https://mainnet-gw.sodex.dev/api/v1/perps

Testnet endpoints:
  Spot:  https://testnet-gw.sodex.dev/api/v1/spot
  Perps: https://testnet-gw.sodex.dev/api/v1/perps
"""
import time
from typing import Any, Optional

import requests

from .models import (
    MarginMode,
    OrderModifier,
    OrderSide,
    OrderType,
    PositionSide,
    StopType,
    TimeInForce,
    TransferAssetType,
    TriggerType,
)
from .signing import sign_action


class NetworkConfig:
    MAINNET_SPOT = "https://mainnet-gw.sodex.dev/api/v1/spot"
    MAINNET_PERPS = "https://mainnet-gw.sodex.dev/api/v1/perps"
    TESTNET_SPOT = "https://testnet-gw.sodex.dev/api/v1/spot"
    TESTNET_PERPS = "https://testnet-gw.sodex.dev/api/v1/perps"

    MAINNET_CHAIN_ID = 286623
    TESTNET_CHAIN_ID = 138565


class SodexClient:
    """
    Sodex REST API client with EIP-712 request signing.

    Args:
        api_key:      EVM address of the registered API sub-key, e.g. "0xD7D626..."
        private_key:  ECDSA private key for signing, e.g. "0x664876..."
        api_key_name: Name of the API key as registered in the Sodex UI (e.g. "SODEX_API_KEY").
                      Sent in the X-API-Key header.  The server looks up the key by name,
                      not by address.
        wallet_address: Master wallet address used in account query paths.
        testnet:      Use testnet endpoints when True (default False = mainnet)
    """

    def __init__(
        self,
        api_key: str,
        private_key: str,
        api_key_name: str = "SODEX_API_KEY",
        wallet_address: str = None,
        testnet: bool = False,
    ):
        self.api_key = api_key
        self.private_key = private_key
        # X-API-Key header must be the key NAME (e.g. "SODEX_API_KEY"), not the address.
        self.api_key_name = api_key_name
        # Master wallet address used in account query paths.
        # Falls back to api_key if not provided (single-key setup).
        self.wallet_address = wallet_address or api_key
        self.testnet = testnet

        if testnet:
            self.spot_url = NetworkConfig.TESTNET_SPOT
            self.perps_url = NetworkConfig.TESTNET_PERPS
            self.chain_id = NetworkConfig.TESTNET_CHAIN_ID
        else:
            self.spot_url = NetworkConfig.MAINNET_SPOT
            self.perps_url = NetworkConfig.MAINNET_PERPS
            self.chain_id = NetworkConfig.MAINNET_CHAIN_ID

        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _nonce(self) -> int:
        """Return current Unix timestamp in milliseconds as nonce."""
        return int(time.time() * 1000)

    def _signed_headers(self, domain_name: str, action_type: str, params: dict) -> dict:
        """Build authentication headers for a signed request."""
        nonce = self._nonce()
        signature = sign_action(
            private_key=self.private_key,
            domain_name=domain_name,
            chain_id=self.chain_id,
            action_type=action_type,
            params=params,
            nonce=nonce,
        )
        return {
            "X-API-Key": self.api_key_name,   # key NAME, not address
            "X-API-Sign": signature,
            "X-API-Nonce": str(nonce),
        }

    def _get(self, base_url: str, path: str, query: dict = None) -> Any:
        """Perform an unauthenticated GET request."""
        resp = self.session.get(base_url + path, params=query, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"API error {data['code']}: {data.get('error')}")
        return data.get("data")

    def _post(
        self,
        base_url: str,
        path: str,
        domain_name: str,
        action_type: str,
        params: dict,
    ) -> Any:
        """Perform a signed POST request."""
        headers = self._signed_headers(domain_name, action_type, params)
        resp = self.session.post(
            base_url + path, json=params, headers=headers, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"API error {data['code']}: {data.get('error')}")
        return data.get("data")

    def _delete(
        self,
        base_url: str,
        path: str,
        domain_name: str,
        action_type: str,
        params: dict,
    ) -> Any:
        """Perform a signed DELETE request."""
        headers = self._signed_headers(domain_name, action_type, params)
        resp = self.session.delete(
            base_url + path, json=params, headers=headers, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"API error {data['code']}: {data.get('error')}")
        return data.get("data")

    # =========================================================================
    # MARKET DATA — SPOT
    # =========================================================================

    def spot_symbols(self) -> Any:
        """Return all tradeable spot symbols."""
        return self._get(self.spot_url, "/markets/symbols")

    def spot_coins(self) -> Any:
        """Return all spot coins/assets."""
        return self._get(self.spot_url, "/markets/coins")

    def spot_tickers(self) -> Any:
        """Return 24h price statistics for all spot symbols."""
        return self._get(self.spot_url, "/markets/tickers")

    def spot_mini_tickers(self) -> Any:
        """Return abbreviated 24h statistics for all spot symbols."""
        return self._get(self.spot_url, "/markets/miniTickers")

    def spot_book_tickers(self) -> Any:
        """Return best bid/ask for all spot symbols."""
        return self._get(self.spot_url, "/markets/bookTickers")

    def spot_orderbook(self, symbol: str, level: int = 25) -> Any:
        """
        Return spot order book depth for a symbol.
        level: 10 | 25 | 100 | 500 | 1000
        """
        return self._get(
            self.spot_url,
            f"/markets/{symbol}/orderbook",
            {"level": level},
        )

    def spot_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> Any:
        """
        Return spot candlestick data.
        interval: 1m|5m|15m|30m|1h|4h|8h|12h|1D|3D|1W|1M
        """
        return self._get(
            self.spot_url,
            f"/markets/{symbol}/klines",
            {"interval": interval, "limit": limit},
        )

    def spot_trades(self, symbol: str, limit: int = 50) -> Any:
        """Return recent public trades for a spot symbol."""
        return self._get(
            self.spot_url,
            f"/markets/{symbol}/trades",
            {"limit": limit},
        )

    # =========================================================================
    # ACCOUNT DATA — SPOT  (uses EVM address in path)
    # =========================================================================

    def spot_balances(self, user_address: str = None) -> Any:
        """Return spot balances. Defaults to own address."""
        addr = user_address or self.wallet_address
        return self._get(self.spot_url, f"/accounts/{addr}/balances")

    def spot_open_orders(self, user_address: str = None, symbol: str = None) -> Any:
        """Return open spot orders."""
        addr = user_address or self.wallet_address
        query = {}
        if symbol:
            query["symbol"] = symbol
        return self._get(self.spot_url, f"/accounts/{addr}/orders", query)

    def spot_order_history(
        self, user_address: str = None, symbol: str = None, limit: int = 100
    ) -> Any:
        """Return spot order history."""
        addr = user_address or self.wallet_address
        query = {"limit": limit}
        if symbol:
            query["symbol"] = symbol
        return self._get(self.spot_url, f"/accounts/{addr}/orders/history", query)

    def spot_trade_history(
        self, user_address: str = None, symbol: str = None, limit: int = 100
    ) -> Any:
        """Return spot trade history."""
        addr = user_address or self.wallet_address
        query = {"limit": limit}
        if symbol:
            query["symbol"] = symbol
        return self._get(self.spot_url, f"/accounts/{addr}/trades", query)

    def spot_account_state(self, user_address: str = None) -> Any:
        """Return comprehensive spot account state (frontend use)."""
        addr = user_address or self.wallet_address
        return self._get(self.spot_url, f"/accounts/{addr}/state")

    def spot_api_keys(self, user_address: str = None) -> Any:
        """Return registered API keys for the account."""
        addr = user_address or self.wallet_address
        return self._get(self.spot_url, f"/accounts/{addr}/api-keys")

    def spot_fee_rate(self, user_address: str = None) -> Any:
        """Return spot maker/taker fee rates."""
        addr = user_address or self.wallet_address
        return self._get(self.spot_url, f"/accounts/{addr}/fee-rate")

    # =========================================================================
    # TRADING — SPOT (SIGNED)
    # =========================================================================

    def spot_place_orders(
        self,
        account_id: int,
        orders: list[dict],
    ) -> Any:
        """
        Place one or more spot orders in a batch.

        Each order dict must contain (in this field order):
            symbolID    (int)
            clOrdID     (str, 1-36 alphanumeric)
            side        (int: 1=BUY, 2=SELL)
            type        (int: 1=LIMIT, 2=MARKET)
            timeInForce (int: 1=GTC, 3=IOC, 4=GTX)
            price       (str, optional)
            quantity    (str, optional)
            funds       (str, optional — market buy only)
        """
        params = {"accountID": account_id, "orders": orders}
        return self._post(self.spot_url, "/trade/orders/batch", "spot", "newOrder", params)

    def spot_new_order(
        self,
        account_id: int,
        symbol_id: int,
        cl_ord_id: str,
        side: OrderSide,
        order_type: OrderType,
        time_in_force: TimeInForce,
        price: Optional[str] = None,
        quantity: Optional[str] = None,
        funds: Optional[str] = None,
    ) -> Any:
        """
        Convenience wrapper to place a single spot order.

        Args:
            account_id: Numeric account ID (uint64) — find it via spot_account_state()
            symbol_id: Symbol numeric ID — find it via spot_symbols()
            cl_ord_id: Client order ID (1-36 alphanumeric, e.g. "buy-001")
            side: OrderSide.BUY or OrderSide.SELL
            order_type: OrderType.LIMIT or OrderType.MARKET
            time_in_force: TimeInForce.GTC, .IOC, or .GTX
            price: Limit price as decimal string, e.g. "50000.5"
            quantity: Quantity as decimal string, e.g. "0.001"
            funds: Quote amount for market buy (alternative to quantity)
        """
        order: dict = {
            "symbolID": symbol_id,
            "clOrdID": cl_ord_id,
            "side": int(side),
            "type": int(order_type),
            "timeInForce": int(time_in_force),
        }
        if price is not None:
            order["price"] = price
        if quantity is not None:
            order["quantity"] = quantity
        if funds is not None:
            order["funds"] = funds

        return self.spot_place_orders(account_id, [order])

    def spot_cancel_orders(self, account_id: int, cancels: list[dict]) -> Any:
        """
        Cancel one or more spot orders.

        Each cancel dict must contain:
            symbolID    (int)
            clOrdID     (str)
            orderID     (int, optional)
            origClOrdID (str, optional)
        """
        params = {"accountID": account_id, "cancels": cancels}
        return self._delete(
            self.spot_url, "/trade/orders/batch", "spot", "cancelOrder", params
        )

    def spot_cancel_order(
        self,
        account_id: int,
        symbol_id: int,
        cl_ord_id: str,
        order_id: Optional[int] = None,
    ) -> Any:
        """Convenience wrapper to cancel a single spot order."""
        cancel: dict = {"symbolID": symbol_id, "clOrdID": cl_ord_id}
        if order_id is not None:
            cancel["orderID"] = order_id
        return self.spot_cancel_orders(account_id, [cancel])

    def spot_schedule_cancel(self, account_id: int, symbol_id: int) -> Any:
        """Schedule cancel-all for a spot symbol."""
        params = {"accountID": account_id, "symbolID": symbol_id}
        return self._post(
            self.spot_url, "/trade/orders/schedule-cancel", "spot", "scheduleCancel", params
        )

    # =========================================================================
    # MARKET DATA — PERPS
    # =========================================================================

    def perps_symbols(self) -> Any:
        """Return all tradeable perps symbols."""
        return self._get(self.perps_url, "/markets/symbols")

    def perps_coins(self) -> Any:
        """Return all perps coins/assets."""
        return self._get(self.perps_url, "/markets/coins")

    def perps_tickers(self) -> Any:
        """Return 24h statistics for all perps symbols."""
        return self._get(self.perps_url, "/markets/tickers")

    def perps_mini_tickers(self) -> Any:
        """Return abbreviated 24h statistics for all perps symbols."""
        return self._get(self.perps_url, "/markets/miniTickers")

    def perps_mark_prices(self) -> Any:
        """Return mark price data for all perps symbols."""
        return self._get(self.perps_url, "/markets/mark-prices")

    def perps_book_tickers(self) -> Any:
        """Return best bid/ask for all perps symbols."""
        return self._get(self.perps_url, "/markets/bookTickers")

    def perps_orderbook(self, symbol: str, level: int = 25) -> Any:
        """Return perps order book depth. level: 10|25|100|500|1000."""
        return self._get(
            self.perps_url,
            f"/markets/{symbol}/orderbook",
            {"level": level},
        )

    def perps_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> Any:
        """
        Return perps candlestick data.
        interval: 1m|5m|15m|30m|1h|4h|1D|1W|1M
        """
        return self._get(
            self.perps_url,
            f"/markets/{symbol}/klines",
            {"interval": interval, "limit": limit},
        )

    def perps_trades(self, symbol: str, limit: int = 50) -> Any:
        """Return recent public trades for a perps symbol."""
        return self._get(
            self.perps_url,
            f"/markets/{symbol}/trades",
            {"limit": limit},
        )

    # =========================================================================
    # ACCOUNT DATA — PERPS
    # =========================================================================

    def perps_balances(self, user_address: str = None) -> Any:
        """Return perps balances."""
        addr = user_address or self.wallet_address
        return self._get(self.perps_url, f"/accounts/{addr}/balances")

    def perps_positions(self, user_address: str = None, symbol: str = None) -> Any:
        """Return open perps positions."""
        addr = user_address or self.wallet_address
        query = {}
        if symbol:
            query["symbol"] = symbol
        return self._get(self.perps_url, f"/accounts/{addr}/positions", query)

    def perps_open_orders(self, user_address: str = None, symbol: str = None) -> Any:
        """Return open perps orders."""
        addr = user_address or self.wallet_address
        query = {}
        if symbol:
            query["symbol"] = symbol
        return self._get(self.perps_url, f"/accounts/{addr}/orders", query)

    def perps_account_state(self, user_address: str = None) -> Any:
        """Return comprehensive perps account state."""
        addr = user_address or self.wallet_address
        return self._get(self.perps_url, f"/accounts/{addr}/state")

    def perps_order_history(
        self, user_address: str = None, symbol: str = None, limit: int = 100
    ) -> Any:
        """Return perps order history."""
        addr = user_address or self.wallet_address
        query = {"limit": limit}
        if symbol:
            query["symbol"] = symbol
        return self._get(self.perps_url, f"/accounts/{addr}/orders/history", query)

    def perps_position_history(self, user_address: str = None, limit: int = 100) -> Any:
        """Return closed perps positions."""
        addr = user_address or self.wallet_address
        return self._get(
            self.perps_url, f"/accounts/{addr}/positions/history", {"limit": limit}
        )

    def perps_trade_history(
        self, user_address: str = None, symbol: str = None, limit: int = 100
    ) -> Any:
        """Return perps trade history."""
        addr = user_address or self.wallet_address
        query = {"limit": limit}
        if symbol:
            query["symbol"] = symbol
        return self._get(self.perps_url, f"/accounts/{addr}/trades", query)

    def perps_fundings(self, user_address: str = None, limit: int = 100) -> Any:
        """Return funding payment history."""
        addr = user_address or self.wallet_address
        return self._get(
            self.perps_url, f"/accounts/{addr}/fundings", {"limit": limit}
        )

    def perps_fee_rate(self, user_address: str = None) -> Any:
        """Return perps maker/taker fee rates."""
        addr = user_address or self.wallet_address
        return self._get(self.perps_url, f"/accounts/{addr}/fee-rate")

    # =========================================================================
    # TRADING — PERPS (SIGNED)
    # =========================================================================

    def perps_place_orders(
        self,
        account_id: int,
        symbol_id: int,
        orders: list[dict],
    ) -> Any:
        """
        Place one or more perps orders.

        Each order dict must contain:
            clOrdID     (str, 1-36 alphanumeric)
            modifier    (int: 1=NORMAL, 2=STOP, 3=BRACKET, 4=ATTACHED_STOP)
            side        (int: 1=BUY, 2=SELL)
            type        (int: 1=LIMIT, 2=MARKET)
            timeInForce (int: 1=GTC, 3=IOC, 4=GTX)
            reduceOnly  (bool)
            positionSide (int: 1=BOTH — only BOTH supported currently)
            price       (str, optional)
            quantity    (str, optional)
            stopPrice   (str, optional)
            stopType    (int, optional)
            triggerType (int, optional)
        """
        params = {"accountID": account_id, "symbolID": symbol_id, "orders": orders}
        return self._post(self.perps_url, "/trade/orders", "futures", "newOrder", params)

    def perps_new_order(
        self,
        account_id: int,
        symbol_id: int,
        cl_ord_id: str,
        side: OrderSide,
        order_type: OrderType,
        time_in_force: TimeInForce,
        reduce_only: bool = False,
        modifier: OrderModifier = OrderModifier.NORMAL,
        position_side: PositionSide = PositionSide.BOTH,
        price: Optional[str] = None,
        quantity: Optional[str] = None,
        stop_price: Optional[str] = None,
        stop_type: Optional[StopType] = None,
        trigger_type: Optional[TriggerType] = None,
    ) -> Any:
        """Convenience wrapper to place a single perps order."""
        # Field order MUST match Go RawOrder struct definition exactly.
        # Omitempty fields (price, quantity, funds, stopPrice, stopType, triggerType)
        # must come BEFORE the non-optional fields (reduceOnly, positionSide).
        order: dict = {}
        order["clOrdID"] = cl_ord_id
        order["modifier"] = int(modifier)
        order["side"] = int(side)
        order["type"] = int(order_type)
        order["timeInForce"] = int(time_in_force)
        if price is not None:
            order["price"] = price
        if quantity is not None:
            order["quantity"] = quantity
        # funds omitempty — not used in perps but kept for completeness
        if stop_price is not None:
            order["stopPrice"] = stop_price
        if stop_type is not None:
            order["stopType"] = int(stop_type)
        if trigger_type is not None:
            order["triggerType"] = int(trigger_type)
        order["reduceOnly"] = reduce_only       # always present (no omitempty)
        order["positionSide"] = int(position_side)  # always present (no omitempty)

        return self.perps_place_orders(account_id, symbol_id, [order])

    def perps_cancel_orders(
        self, account_id: int, cancels: list[dict]
    ) -> Any:
        """
        Cancel one or more perps orders.

        Each cancel dict must contain:
            symbolID (int)
            orderID  (int, optional)
            clOrdID  (str, optional)
        """
        params = {"accountID": account_id, "cancels": cancels}
        return self._delete(
            self.perps_url, "/trade/orders", "futures", "cancelOrder", params
        )

    def perps_cancel_order(
        self,
        account_id: int,
        symbol_id: int,
        cl_ord_id: Optional[str] = None,
        order_id: Optional[int] = None,
    ) -> Any:
        """Convenience wrapper to cancel a single perps order."""
        cancel: dict = {"symbolID": symbol_id}
        if order_id is not None:
            cancel["orderID"] = order_id
        if cl_ord_id is not None:
            cancel["clOrdID"] = cl_ord_id
        return self.perps_cancel_orders(account_id, [cancel])

    def perps_update_leverage(
        self,
        account_id: int,
        symbol_id: int,
        leverage: int,
        margin_mode: MarginMode,
    ) -> Any:
        """Update leverage and margin mode for a perps symbol."""
        params = {
            "accountID": account_id,
            "symbolID": symbol_id,
            "leverage": leverage,
            "marginMode": int(margin_mode),
        }
        return self._post(
            self.perps_url, "/trade/leverage", "futures", "updateLeverage", params
        )

    def perps_update_margin(
        self,
        account_id: int,
        symbol_id: int,
        amount: str,
    ) -> Any:
        """
        Add or remove isolated margin for a perps position.
        Use positive amount to add, negative to remove (e.g. "-10.5").
        """
        params = {
            "accountID": account_id,
            "symbolID": symbol_id,
            "amount": amount,
        }
        return self._post(
            self.perps_url, "/trade/margin", "futures", "updateMargin", params
        )

    def perps_schedule_cancel(self, account_id: int, symbol_id: int) -> Any:
        """Schedule cancel-all for a perps symbol."""
        params = {"accountID": account_id, "symbolID": symbol_id}
        return self._post(
            self.perps_url,
            "/trade/orders/schedule-cancel",
            "futures",
            "scheduleCancel",
            params,
        )

    # =========================================================================
    # TRANSFERS (SIGNED)
    # =========================================================================

    def transfer_spot(
        self,
        transfer_id: int,
        from_account_id: int,
        to_account_id: int,
        coin_id: int,
        amount: str,
        transfer_type: TransferAssetType,
    ) -> Any:
        """Transfer assets via the spot API (deposit/withdraw/internal)."""
        params = {
            "id": transfer_id,
            "fromAccountID": from_account_id,
            "toAccountID": to_account_id,
            "coinID": coin_id,
            "amount": amount,
            "type": int(transfer_type),
        }
        return self._post(
            self.spot_url, "/accounts/transfers", "spot", "transferAsset", params
        )

    def transfer_perps(
        self,
        transfer_id: int,
        from_account_id: int,
        to_account_id: int,
        coin_id: int,
        amount: str,
        transfer_type: TransferAssetType,
    ) -> Any:
        """Transfer assets via the perps API."""
        params = {
            "id": transfer_id,
            "fromAccountID": from_account_id,
            "toAccountID": to_account_id,
            "coinID": coin_id,
            "amount": amount,
            "type": int(transfer_type),
        }
        return self._post(
            self.perps_url, "/accounts/transfers", "futures", "transferAsset", params
        )
