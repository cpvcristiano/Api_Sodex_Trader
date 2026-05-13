import logging
import requests
from typing import Optional, Tuple
from sodex import SodexClient, OrderSide
from .base import BaseStrategy

log = logging.getLogger("strategy.hybrid_smc")

class HybridSMCStrategy(BaseStrategy):
    """
    Estratégia Híbrida combinando EMA 9/17, SMC (Smart Money Concepts) 
    e Market Intelligence da Binance.
    """

    def __init__(self, client: SodexClient, config):
        self.client = client
        self.cfg = config

    def _mark_price(self) -> float:
        marks = self.client.perps_mark_prices()
        for m in marks:
            if m["symbol"] == self.cfg.symbol_name:
                return float(m["markPrice"])
        raise RuntimeError(f"Mark price nao encontrado para {self.cfg.symbol_name}")

    def _get_binance_symbol(self) -> str:
        # Converte SOL-USD -> SOLUSDT
        return self.cfg.symbol_name.replace("-USD", "USDT")

    def _ema_signals(self, interval: str = "1m") -> dict:
        out = {"direction": None, "ema9": 0.0, "ema17": 0.0,
               "price": 0.0, "prev_ema9": 0.0, "prev_ema17": 0.0,
               "cross_bull": False, "cross_bear": False, "ok": False}
        try:
            limit = 30 if interval == "1m" else 40
            r = requests.get(
                "https://fapi.binance.com/fapi/v1/klines",
                params={"symbol": self._get_binance_symbol(), "interval": interval, "limit": limit},
                timeout=5,
            )
            closes = [float(c[4]) for c in r.json()]

            def ema(data, period):
                k = 2 / (period + 1)
                res = [data[0]]
                for p in data[1:]:
                    res.append(p * k + res[-1] * (1 - k))
                return res

            e9  = ema(closes, 9)
            e17 = ema(closes, 17)

            price      = closes[-1]
            ema9_now   = e9[-1];   ema9_prev  = e9[-2]
            ema17_now  = e17[-1];  ema17_prev = e17[-2]

            cross_bull = ema9_prev <= ema17_prev and ema9_now > ema17_now
            cross_bear = ema9_prev >= ema17_prev and ema9_now < ema17_now

            direction = None
            if price > ema9_now and ema9_now > ema17_now:
                direction = OrderSide.BUY
            elif price < ema9_now and ema9_now < ema17_now:
                direction = OrderSide.SELL

            out.update({
                "direction": direction, "ema9": ema9_now, "ema17": ema17_now,
                "prev_ema9": ema9_prev, "prev_ema17": ema17_prev,
                "price": price, "cross_bull": cross_bull, "cross_bear": cross_bear,
                "ok": True,
            })
        except Exception as e:
            log.warning(f"[EMA-{interval}] {e}")
        return out

    def _smc_signals(self, interval: str = "5m") -> dict:
        out = {
            "ok": False, "zone": None, "zone_pct": 0.0,
            "ob_bull": None, "ob_bear": None, "fvg_bull": None, "fvg_bear": None,
            "structure": None, "swing_high": 0.0, "swing_low": 0.0, "price": 0.0,
        }
        try:
            r = requests.get(
                "https://fapi.binance.com/fapi/v1/klines",
                params={"symbol": self._get_binance_symbol(), "interval": interval, "limit": 100},
                timeout=5,
            )
            candles = r.json()
            opens  = [float(c[1]) for c in candles]
            highs  = [float(c[2]) for c in candles]
            lows   = [float(c[3]) for c in candles]
            closes = [float(c[4]) for c in candles]
            n = len(candles)
            price = closes[-1]

            lb = min(96, n)
            swing_high = max(highs[-lb:])
            swing_low  = min(lows[-lb:])
            rng = swing_high - swing_low

            amplitude_pct = rng / price * 100
            if amplitude_pct < 0.8:
                out.update({"ok": True, "price": price, "zone": "EQUI", "zone_pct": 50.0,
                            "swing_high": swing_high, "swing_low": swing_low})
                return out

            zone_pct = (price - swing_low) / rng * 100
            if zone_pct <= 25: zone = "DISCOUNT"
            elif zone_pct >= 75: zone = "PREMIUM"
            else: zone = "EQUI"

            structure = None
            if n >= 15:
                seg = [(max(highs[i:i+5]), min(lows[i:i+5])) for i in range(n - 15, n, 5)]
                if len(seg) == 3:
                    (h1, l1), (h2, l2), (h3, l3) = seg
                    if h3 > h2 and l3 > l2: structure = "BULLISH"
                    elif h3 < h2 and l3 < l2: structure = "BEARISH"

            ob_bull = ob_bear = fvg_bull = fvg_bear = None
            for i in range(n - 3, max(n - 25, 1), -1):
                if closes[i] < opens[i] and closes[i+1] > opens[i+1]:
                    lo, hi = min(opens[i], closes[i]), max(opens[i], closes[i])
                    if price > lo and ob_bull is None: ob_bull = (lo, hi)
                if closes[i] > opens[i] and closes[i+1] < opens[i+1]:
                    lo, hi = min(opens[i], closes[i]), max(opens[i], closes[i])
                    if price < hi and ob_bear is None: ob_bear = (lo, hi)
            
            for i in range(n - 2, 0, -1):
                if i + 1 < n and highs[i - 1] < lows[i + 1]:
                    if fvg_bull is None and price > highs[i - 1]: fvg_bull = (highs[i - 1], lows[i + 1])
                if i + 1 < n and lows[i - 1] > highs[i + 1]:
                    if fvg_bear is None and price < lows[i - 1]: fvg_bear = (highs[i + 1], lows[i - 1])

            out.update({
                "ok": True, "zone": zone, "zone_pct": round(zone_pct, 1),
                "ob_bull": ob_bull, "ob_bear": ob_bear, "fvg_bull": fvg_bull, "fvg_bear": fvg_bear,
                "structure": structure, "swing_high": swing_high, "swing_low": swing_low, "price": price,
            })
        except Exception as e:
            log.warning(f"[SMC-{interval}] {e}")
        return out

    def analyze(self, market_data: dict) -> Tuple[Optional[OrderSide], float]:
        # ── Sinal 5min ────────────────────────────────────────────────────────
        sig5 = self._ema_signals("5m")
        if not sig5["ok"]:
            return None, self._mark_price()

        trend = sig5["direction"]
        t5_label = "LONG" if trend == OrderSide.BUY else "SHORT" if trend == OrderSide.SELL else "LATERAL"
        sep5 = abs(sig5["ema9"] - sig5["ema17"]) / sig5["price"] * 100
        log.info(f"[5min] EMA: {t5_label} | Price={sig5['price']:,.2f} | Sep={sep5:.3f}%")

        if trend is None:
            return None, sig5["price"]

        if sep5 < 0.01:
            log.info(f"[EMA-FLAT] Separacao {sep5:.3f}% < 0.01% — bloqueado")
            return None, sig5["price"]

        # ── Filtro 1H: so opera se tendencia maior confirma ───────────────────
        sig1h = self._ema_signals("1h")
        if sig1h["ok"]:
            trend1h = sig1h["direction"]
            t1h = "LONG" if trend1h == OrderSide.BUY else "SHORT" if trend1h == OrderSide.SELL else "LATERAL"
            sep1h = abs(sig1h["ema9"] - sig1h["ema17"]) / sig1h["price"] * 100
            log.info(f"[1H]   EMA: {t1h} | EMA9={sig1h['ema9']:,.0f} EMA17={sig1h['ema17']:,.0f} | Sep={sep1h:.3f}%")

            if trend1h != trend:
                motivo = "LATERAL no 1H" if trend1h is None else f"1H={t1h} oposto ao 5min={t5_label}"
                log.info(f"[1H FILTER] BLOQUEOU — {motivo}")
                return None, sig5["price"]

            log.info(f"[1H FILTER] CONFIRMOU — 5min={t5_label} alinhado com 1H={t1h}")
        else:
            log.warning("[1H FILTER] Dados indisponiveis — prosseguindo sem filtro 1H")

        # ── Filtro SMC ─────────────────────────────────────────────────────────
        smc = self._smc_signals("5m")
        if smc["ok"]:
            log.info(f"[SMC] Zona: {smc['zone']} ({smc['zone_pct']}%) | Struct: {smc['structure']}")
            if trend == OrderSide.BUY and smc["zone"] == "PREMIUM" and smc["structure"] == "BEARISH" and smc["ob_bear"]:
                log.info("[SMC] LONG bloqueado: PREMIUM + BEARISH + OB bearish confirmados")
                return None, sig5["price"]
            if trend == OrderSide.SELL and smc["zone"] == "DISCOUNT" and smc["structure"] == "BULLISH" and smc["ob_bull"]:
                log.info("[SMC] SHORT bloqueado: DISCOUNT + BULLISH + OB bullish confirmados")
                return None, sig5["price"]

        log.info(f"[ALINHADO] 5min + 1H confirmados -> Operando {t5_label}")
        return trend, sig5["price"]

    def get_tp_sl(self, fill_price: float, qty: float, notional: float) -> Tuple[float, float]:
        tp_move = self.cfg.tp_usd / qty
        sl_move = self.cfg.sl_usd / qty
        return tp_move, sl_move

    def check_exit(self, side: OrderSide, current_data: dict) -> bool:
        sig = self._ema_signals("1m")
        if not sig["ok"]:
            return False
        return (side == OrderSide.BUY and sig["cross_bear"]) or \
               (side == OrderSide.SELL and sig["cross_bull"])
