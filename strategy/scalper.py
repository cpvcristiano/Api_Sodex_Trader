"""
Scalping bot - BTC-USD - Geracao de volume para airdrop SOSO
=============================================================
Regras:
  - Apenas BTC-USD (perps)
  - 25% da margem disponivel por operacao
  - Alavancagem maxima do BTC na Sodex: 25x (max permitido)
  - Uma posicao de cada vez
  - Roda 24h por dia
  - Analisa preco ~30s (ritmo 1-min chart) antes de cada entrada
  - TP: $0.50 fixo | SL: $0.10 fixo | R:R = 5:1
  - Break-even win rate: ~20% | EV @ 40% win: ~+$0.12/trade
  - Com conta de $12: SL = ~0.12% de movimento | TP = ~0.62%
"""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Optional

import requests

from sodex import (
    OrderModifier,
    OrderSide,
    OrderType,
    PositionSide,
    SodexClient,
    StopType,
    TimeInForce,
    TriggerType,
)
from strategy.tracker import Trade, VolumeTracker

log = logging.getLogger("scalper")

TICK  = 1        # BTC tickSize
STEP  = 0.00001  # BTC stepSize
MIN_NOTIONAL = 10.0


# ─── Configuracoes ────────────────────────────────────────────────────────────

@dataclass
class ScalpConfig:
    symbol_name: str   = "BTC-USD"
    symbol_id: int     = 1

    # Sizing
    margin_pct: float  = 0.25   # 25% da margem disponivel por trade
    leverage: int      = 25     # max permitido na Sodex para BTC

    # TP / SL em dólares fixos
    tp_usd: float      = 2.00   # lucro alvo por trade em USD
    sl_usd: float      = 0.50   # perda maxima por trade em USD

    # Analise pos-trade (coleta N amostras de preco antes de entrar)
    analysis_secs: float  = 20.0   # tempo de observacao de preco
    analysis_samples: int = 8      # quantas leituras coletar

    # Timeouts
    entry_timeout_s: float    = 25.0   # max esperando fill da entrada
    position_timeout_s: float = 180.0  # max na posicao antes de fechar a mkt

    # Intervalo entre chamadas de polling (segundos)
    poll_s: float = 2.0

    # Protecoes
    min_margin_usd: float    = 1.0   # nao opera se margem < $1
    max_daily_loss_usd: float = 3.0  # para o dia se perder mais que $3

    # Meta semanal de volume
    weekly_target_usd: float = 100_000.0

    # Dias ativos (None = todos os dias)
    active_weekdays: Optional[list] = None

    # Horario de encerramento diario (hora UTC, None = sem limite)
    # Ex: 23 = para as 23:00 UTC = 20:00 horario de Brasilia (BRT = UTC-3)
    stop_hour_utc: Optional[int] = None

    # Taxas reais da Sodex
    maker_fee_pct: float = 0.00012   # 0.012% — ordens LIMIT (entrada e TP)
    taker_fee_pct: float = 0.00050   # 0.050% — ordens MARKET (SL, BE, saida manual)


# ─── Bot principal ────────────────────────────────────────────────────────────

class ScalpingBot:

    def __init__(self, client: SodexClient, account_id: int, config: ScalpConfig = None):
        self.client     = client
        self.account_id = account_id
        self.cfg        = config or ScalpConfig()
        self.tracker    = VolumeTracker(self.cfg.weekly_target_usd)
        self._running   = False
        self._last_side: Optional[OrderSide] = None   # lado do ultimo trade

    # ── Preco ────────────────────────────────────────────────────────────────

    def _mark_price(self) -> float:
        marks = self.client.perps_mark_prices()
        for m in marks:
            if m["symbol"] == self.cfg.symbol_name:
                return float(m["markPrice"])
        raise RuntimeError(f"Mark price nao encontrado para {self.cfg.symbol_name}")

    def _px(self, price: float) -> str:
        """Formata preco no tick size do BTC (inteiro)."""
        return str(int(price))

    def _qty(self, notional: float, price: float) -> str:
        """Calcula e formata quantidade respeitando stepSize (sem trailing zeros)."""
        raw = notional / price
        dec = Decimal(str(raw)).quantize(Decimal("0.00001"), rounding=ROUND_DOWN)
        return format(dec.normalize(), "f")  # "0.00110" -> "0.0011"

    # ── Conta ────────────────────────────────────────────────────────────────

    def _available_margin(self) -> float:
        """Retorna margem disponivel em USD."""
        try:
            state = self.client.perps_account_state()
            return float(state.get("am", 0))
        except Exception as e:
            log.warning(f"[MARGIN] {e}")
            return 0.0

    def _get_position(self) -> Optional[dict]:
        """Retorna posicao aberta em BTC-USD, ou None."""
        try:
            state = self.client.perps_account_state()
            if not state:
                return None
            for p in (state.get("P") or []):
                if p.get("s") == self.cfg.symbol_name and float(p.get("sz", 0)) != 0:
                    return p
        except Exception as e:
            log.warning(f"[POS] {e}")
        return None

    def _open_orders(self) -> list:
        """Retorna lista de ordens abertas em BTC-USD (via account state)."""
        try:
            state = self.client.perps_account_state()
            orders = (state.get("O") or []) if state else []
            return [o for o in orders if o.get("s") == self.cfg.symbol_name]
        except Exception as e:
            log.warning(f"[ORDERS] {e}")
            return []

    # ── Binance Market Intelligence ──────────────────────────────────────────

    def _binance_signals(self) -> dict:
        """
        Busca 3 sinais de mercado da Binance (API pública, sem autenticação):
          cvd          : delta de volume (+ = pressão compradora, - = vendedora)
          ls_ratio     : long/short ratio (> 1 = mais longs no mercado)
          funding_rate : taxa de financiamento (+ = longs pagam shorts)
        """
        out = {"cvd": 0.0, "ls_ratio": 1.0, "funding": 0.0, "ok": False}
        try:
            # CVD — últimos 100 aggTrades
            r = requests.get(
                "https://fapi.binance.com/fapi/v1/aggTrades",
                params={"symbol": "BTCUSDT", "limit": 100},
                timeout=4,
            )
            trades = r.json()
            buy_vol  = sum(float(t["q"]) for t in trades if not t["m"])
            sell_vol = sum(float(t["q"]) for t in trades if t["m"])
            out["cvd"] = buy_vol - sell_vol

            # Long/Short ratio (5m)
            r2 = requests.get(
                "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                params={"symbol": "BTCUSDT", "period": "5m", "limit": 1},
                timeout=4,
            )
            out["ls_ratio"] = float(r2.json()[0]["longShortRatio"])

            # Funding rate
            r3 = requests.get(
                "https://fapi.binance.com/fapi/v1/premiumIndex",
                params={"symbol": "BTCUSDT"},
                timeout=4,
            )
            out["funding"] = float(r3.json()["lastFundingRate"])
            out["ok"] = True
        except Exception as e:
            log.warning(f"[BINANCE] {e}")
        return out

    # ── Tape Reading (Order Book Imbalance) ─────────────────────────────────

    def _book_imbalance(self, levels: int = 5) -> float:
        """
        Calcula imbalance do order book: (bid_vol - ask_vol) / (bid_vol + ask_vol)
        Resultado em [-1, +1]:
          > 0  => pressao compradora (bids dominam)
          < 0  => pressao vendedora (asks dominam)
          ~0   => equilibrado
        """
        try:
            book = self.client.perps_orderbook(self.cfg.symbol_name, level=10)
            bids = book.get("bids", [])[:levels]
            asks = book.get("asks", [])[:levels]
            bid_vol = sum(float(b[1]) for b in bids)
            ask_vol = sum(float(a[1]) for a in asks)
            total = bid_vol + ask_vol
            if total == 0:
                return 0.0
            return (bid_vol - ask_vol) / total
        except Exception as e:
            log.warning(f"[BOOK] {e}")
            return 0.0

    # ── Analise tecnica EMA 9/17 (hibrido 5min + 1min) ──────────────────────

    def _ema_signals(self, interval: str = "1m") -> dict:
        """
        Calcula sinais EMA 9/17 para o intervalo informado (Binance Futures).
        Retorna direction, ema9, ema17, price, cross_bull, cross_bear.
        """
        out = {"direction": None, "ema9": 0.0, "ema17": 0.0,
               "price": 0.0, "prev_ema9": 0.0, "prev_ema17": 0.0,
               "cross_bull": False, "cross_bear": False, "ok": False}
        try:
            limit = 30 if interval == "1m" else 40
            r = requests.get(
                "https://fapi.binance.com/fapi/v1/klines",
                params={"symbol": "BTCUSDT", "interval": interval, "limit": limit},
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

    def _check_ema_exit(self, side: OrderSide) -> bool:
        """Retorna True se houve cruzamento inverso das EMAs no 1min (sinal de saida)."""
        sig = self._ema_signals("1m")
        if not sig["ok"]:
            return False
        return (side == OrderSide.BUY and sig["cross_bear"]) or \
               (side == OrderSide.SELL and sig["cross_bull"])

    # ── SMC (Smart Money Concepts) ───────────────────────────────────────────

    def _smc_signals(self, interval: str = "5m") -> dict:
        """
        Analisa SMC no grafico informado:
          zone      : DISCOUNT / EQUI / PREMIUM (posicao do preco no swing range)
          ob_bull   : (low, high) do Order Block bullish mais recente
          ob_bear   : (low, high) do Order Block bearish mais recente
          fvg_bull  : (low, high) do FVG bullish ativo mais recente
          fvg_bear  : (low, high) do FVG bearish ativo mais recente
          structure : BULLISH / BEARISH / None (analise de HH/HL vs LH/LL)
        """
        out = {
            "ok": False,
            "zone": None,
            "zone_pct": 0.0,
            "ob_bull": None,
            "ob_bear": None,
            "fvg_bull": None,
            "fvg_bear": None,
            "structure": None,
            "swing_high": 0.0,
            "swing_low": 0.0,
            "price": 0.0,
        }
        try:
            r = requests.get(
                "https://fapi.binance.com/fapi/v1/klines",
                params={"symbol": "BTCUSDT", "interval": interval, "limit": 50},
                timeout=5,
            )
            candles = r.json()
            opens  = [float(c[1]) for c in candles]
            highs  = [float(c[2]) for c in candles]
            lows   = [float(c[3]) for c in candles]
            closes = [float(c[4]) for c in candles]
            n = len(candles)
            price = closes[-1]

            # ── Swing range (ultimas 20 velas) ────────────────────────────
            lb = min(20, n)
            swing_high = max(highs[-lb:])
            swing_low  = min(lows[-lb:])
            rng = swing_high - swing_low

            if rng < 1.0:
                out.update({"ok": True, "price": price, "zone": "EQUI", "zone_pct": 50.0,
                            "swing_high": swing_high, "swing_low": swing_low})
                return out

            # ── Premium / Discount / Equilibrio ──────────────────────────
            # Thresholds relaxados (cenario 3): 45/55 ao inves de 40/60
            # LONG aceito ate 55% do range | SHORT aceito a partir de 45%
            zone_pct = (price - swing_low) / rng * 100
            if zone_pct <= 45:
                zone = "DISCOUNT"
            elif zone_pct >= 55:
                zone = "PREMIUM"
            else:
                zone = "EQUI"

            # ── Market structure (HH+HL = bullish | LH+LL = bearish) ─────
            structure = None
            if n >= 15:
                seg = [
                    (max(highs[i:i+5]), min(lows[i:i+5]))
                    for i in range(n - 15, n, 5)
                ]  # 3 segmentos de 5 velas
                if len(seg) == 3:
                    (h1, l1), (h2, l2), (h3, l3) = seg
                    if h3 > h2 and l3 > l2:
                        structure = "BULLISH"
                    elif h3 < h2 and l3 < l2:
                        structure = "BEARISH"

            # ── Order Blocks ──────────────────────────────────────────────
            ob_bull = None
            ob_bear = None
            for i in range(n - 3, max(n - 25, 1), -1):
                # Bullish OB: vela DOWN seguida de 2+ velas UP (demanda)
                if closes[i] < opens[i] and closes[i+1] > opens[i+1]:
                    ob_lo = min(opens[i], closes[i])
                    ob_hi = max(opens[i], closes[i])
                    if price > ob_lo and ob_bull is None:
                        ob_bull = (ob_lo, ob_hi)
                # Bearish OB: vela UP seguida de 2+ velas DOWN (oferta)
                if closes[i] > opens[i] and closes[i+1] < opens[i+1]:
                    ob_lo = min(opens[i], closes[i])
                    ob_hi = max(opens[i], closes[i])
                    if price < ob_hi and ob_bear is None:
                        ob_bear = (ob_lo, ob_hi)
                if ob_bull and ob_bear:
                    break

            # ── Fair Value Gaps ───────────────────────────────────────────
            fvg_bull = None
            fvg_bear = None
            for i in range(n - 2, 0, -1):
                # Bullish FVG: high[i-1] < low[i+1] — gap de alta (zona de suporte)
                if i + 1 < n and highs[i - 1] < lows[i + 1]:
                    if fvg_bull is None and price > highs[i - 1]:
                        fvg_bull = (highs[i - 1], lows[i + 1])
                # Bearish FVG: low[i-1] > high[i+1] — gap de baixa (zona de resistencia)
                if i + 1 < n and lows[i - 1] > highs[i + 1]:
                    if fvg_bear is None and price < lows[i - 1]:
                        fvg_bear = (highs[i + 1], lows[i - 1])
                if fvg_bull and fvg_bear:
                    break

            out.update({
                "ok": True,
                "zone": zone,
                "zone_pct": round(zone_pct, 1),
                "ob_bull": ob_bull,
                "ob_bear": ob_bear,
                "fvg_bull": fvg_bull,
                "fvg_bear": fvg_bear,
                "structure": structure,
                "swing_high": swing_high,
                "swing_low": swing_low,
                "price": price,
            })
        except Exception as e:
            log.warning(f"[SMC-{interval}] {e}")
        return out

    # ── Analise de entrada (HIBRIDO 5min + 1min + SMC) ───────────────────────

    def _analyze_entry(self) -> tuple[Optional[OrderSide], float]:
        """
        Estrategia hibrida EMA 9/17 + SMC:
          Passo 1 — Grafico 5min: define a TENDENCIA macro
          Passo 2 — Grafico 1min: confirma o MOMENTO de entrada
          Passo 3 — SMC 5min   : confirma a ZONA de mercado
                    LONG apenas em DISCOUNT (preco nos 40% inferiores do range)
                    SHORT apenas em PREMIUM (preco nos 40% superiores do range)
                    EQUI aceito somente se ha Order Block confirmado
        """
        # ── Passo 1: tendencia no 5min ───────────────────────────────────────
        sig5 = self._ema_signals("5m")
        trend = sig5["direction"]

        if not sig5["ok"]:
            try:
                return None, self._mark_price()
            except Exception:
                return None, 0.0

        t5_label = "LONG" if trend == OrderSide.BUY else "SHORT" if trend == OrderSide.SELL else "LATERAL"
        log.info(
            f"[5min] EMA9={sig5['ema9']:,.1f}  EMA17={sig5['ema17']:,.1f}  "
            f"preco={sig5['price']:,.1f}  -> {t5_label}"
        )

        if trend is None:
            log.info("[HIBRIDO] 5min lateral — sem tendencia clara, aguardando")
            try:
                return None, self._mark_price()
            except Exception:
                return None, sig5["price"]

        # ── Passo 2: confirmacao no 1min ─────────────────────────────────────
        sig1 = self._ema_signals("1m")

        if not sig1["ok"]:
            return None, sig5["price"]

        t1_label = "LONG" if sig1["direction"] == OrderSide.BUY else \
                   "SHORT" if sig1["direction"] == OrderSide.SELL else "LATERAL"
        log.info(
            f"[1min] EMA9={sig1['ema9']:,.1f}  EMA17={sig1['ema17']:,.1f}  "
            f"preco={sig1['price']:,.1f}  -> {t1_label}"
        )

        if sig1["direction"] != trend:
            log.info(
                f"[HIBRIDO] 1min ({t1_label}) nao confirma 5min ({t5_label}) — aguardando alinhamento"
            )
            return None, sig1["price"]

        # ── Passo 3: confirmacao SMC (zona de preco) ─────────────────────────
        smc = self._smc_signals("5m")
        if smc["ok"]:
            zone      = smc["zone"]
            zone_pct  = smc["zone_pct"]
            structure = smc["structure"]
            ob_bull   = smc["ob_bull"]
            ob_bear   = smc["ob_bear"]
            fvg_bull  = smc["fvg_bull"]
            fvg_bear  = smc["fvg_bear"]

            ob_bull_str = f"[{ob_bull[0]:.0f}-{ob_bull[1]:.0f}]" if ob_bull else "N/A"
            ob_bear_str = f"[{ob_bear[0]:.0f}-{ob_bear[1]:.0f}]" if ob_bear else "N/A"
            fvg_b_str   = f"[{fvg_bull[0]:.0f}-{fvg_bull[1]:.0f}]" if fvg_bull else "N/A"
            fvg_s_str   = f"[{fvg_bear[0]:.0f}-{fvg_bear[1]:.0f}]" if fvg_bear else "N/A"
            log.info(
                f"[SMC] zona={zone}({zone_pct}%) struct={structure} "
                f"range=[{smc['swing_low']:.0f}-{smc['swing_high']:.0f}] "
                f"OB_bull={ob_bull_str} OB_bear={ob_bear_str} "
                f"FVG_bull={fvg_b_str} FVG_bear={fvg_s_str}"
            )

            smc_ok = False
            smc_reason = ""

            if trend == OrderSide.BUY:
                if zone == "DISCOUNT":
                    smc_ok = True
                    smc_reason = f"DISCOUNT({zone_pct}%)"
                    if ob_bull:
                        smc_reason += f" + OB_bull{ob_bull_str}"
                    elif fvg_bull:
                        smc_reason += f" + FVG_bull{fvg_b_str}"
                elif zone == "EQUI" and ob_bull:
                    # Aceita EQUI apenas com OB de demanda confirmado
                    smc_ok = True
                    smc_reason = f"EQUI + OB_bull{ob_bull_str}"
                else:
                    log.info(f"[SMC] LONG bloqueado: zona {zone}({zone_pct}%) sem confluencia de demanda")

            elif trend == OrderSide.SELL:
                if zone == "PREMIUM":
                    smc_ok = True
                    smc_reason = f"PREMIUM({zone_pct}%)"
                    if ob_bear:
                        smc_reason += f" + OB_bear{ob_bear_str}"
                    elif fvg_bear:
                        smc_reason += f" + FVG_bear{fvg_s_str}"
                elif zone == "EQUI" and ob_bear:
                    smc_ok = True
                    smc_reason = f"EQUI + OB_bear{ob_bear_str}"
                else:
                    log.info(f"[SMC] SHORT bloqueado: zona {zone}({zone_pct}%) sem confluencia de oferta")

            if not smc_ok:
                return None, sig1["price"]

            log.info(f"[SMC] Confluencia OK: {smc_reason}")

        log.info(f"[HIBRIDO+SMC] 5min + 1min + SMC alinhados -> {t5_label} CONFIRMADO — entrando")
        return trend, sig1["price"]

    # ── Sizing dinamico ──────────────────────────────────────────────────────

    def _calc_trade_size(self, price: float) -> tuple[str, float]:
        """
        Calcula notional e quantidade com base em 25% da margem disponivel.
        Retorna (qty_str, notional_usd).
        """
        margin_avail = self._available_margin()
        margin_use   = margin_avail * self.cfg.margin_pct
        notional     = margin_use * self.cfg.leverage

        # Garantir minimo
        if notional < MIN_NOTIONAL:
            log.warning(
                f"[SIZE] Margem insuficiente: disponivel=${margin_avail:.4f} "
                f"uso={margin_use:.4f} notional=${notional:.2f} < ${MIN_NOTIONAL}"
            )
            return "0", 0.0

        qty = self._qty(notional, price)
        actual_notional = float(qty) * price

        log.info(
            f"[SIZE] Margem disponivel=${margin_avail:.4f} "
            f"| Usando 25%=${margin_use:.4f} "
            f"| 25x => notional=${actual_notional:.2f} "
            f"| qty={qty} BTC"
        )
        return qty, actual_notional

    # ── Ordens ───────────────────────────────────────────────────────────────

    def _clid(self, prefix: str) -> str:
        return f"{prefix}{int(time.time())}{uuid.uuid4().hex[:4]}"

    def _place_entry(self, side: OrderSide, price: float, qty: str) -> Optional[str]:
        """Coloca ordem LIMIT de entrada. Retorna clOrdID ou None."""
        if side == OrderSide.BUY:
            entry_px = self._px(price - TICK)  # 1 tick abaixo para fill mais rapido
        else:
            entry_px = self._px(price + TICK)

        cl = self._clid("E")
        # Field order MUST match Go RawOrder struct (optional omitempty fields
        # before non-optional reduceOnly / positionSide).
        order = {}
        order["clOrdID"] = cl
        order["modifier"] = int(OrderModifier.NORMAL)
        order["side"] = int(side)
        order["type"] = int(OrderType.LIMIT)
        order["timeInForce"] = int(TimeInForce.GTC)
        order["price"] = entry_px
        order["quantity"] = qty
        order["reduceOnly"] = False
        order["positionSide"] = int(PositionSide.BOTH)
        try:
            self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [order])
            log.info(f"[ENTRY] {side.name} {qty} BTC @ limit {entry_px} (id={cl})")
            return cl
        except Exception as e:
            log.error(f"[ENTRY] Falha: {e}")
            return None

    def _cancel(self, cl: str) -> None:
        try:
            self.client.perps_cancel_order(
                account_id=self.account_id,
                symbol_id=self.cfg.symbol_id,
                cl_ord_id=cl,
            )
        except Exception:
            pass

    def _wait_fill(self, entry_cl: str) -> Optional[float]:
        """Aguarda fill da entrada. Retorna preco de fill ou None."""
        deadline = time.time() + self.cfg.entry_timeout_s
        while time.time() < deadline:
            time.sleep(self.cfg.poll_s)
            open_cls = {o.get("c") for o in self._open_orders()}
            if entry_cl not in open_cls:
                pos = self._get_position()
                if pos:
                    fill = float(pos.get("ep", 0))
                    log.info(f"[FILL] Entrada confirmada @ ${fill:,.2f}")
                    return fill
                return None  # cancelada sem posicao
        # Timeout — cancela a parte nao preenchida da ordem
        log.warning("[FILL] Timeout - cancelando entrada")
        self._cancel(entry_cl)
        # Verificar se houve partial fill (posicao aberta sem fill confirmado)
        pos = self._get_position()
        if pos:
            fill = float(pos.get("ep", 0))
            log.warning(f"[FILL] Partial fill detectado @ ${fill:,.2f} - continuando com TP/SL")
            return fill
        return None

    def _place_tp_sl(
        self, side: OrderSide, fill: float, qty: str
    ) -> tuple[Optional[str], Optional[str]]:
        """Coloca TP (limit) e SL (stop market) com alvos fixos em USD."""
        close_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY

        qty_f    = float(qty)
        tp_move  = self.cfg.tp_usd / qty_f   # variacao de preco para $tp_usd de lucro
        sl_move  = self.cfg.sl_usd / qty_f   # variacao de preco para $sl_usd de perda

        if side == OrderSide.BUY:
            tp_px = self._px(fill + tp_move)
            sl_px = self._px(fill - sl_move)
        else:
            tp_px = self._px(fill - tp_move)
            sl_px = self._px(fill + sl_move)

        tp_cl = self._clid("T")
        sl_cl = self._clid("S")

        tp_order = {}
        tp_order["clOrdID"] = tp_cl
        tp_order["modifier"] = int(OrderModifier.NORMAL)
        tp_order["side"] = int(close_side)
        tp_order["type"] = int(OrderType.LIMIT)
        tp_order["timeInForce"] = int(TimeInForce.GTC)
        tp_order["price"] = tp_px
        tp_order["quantity"] = qty
        tp_order["reduceOnly"] = True
        tp_order["positionSide"] = int(PositionSide.BOTH)

        # SL order — MARKET garante fill mesmo com gap de preco
        # Field order MUST match Go RawOrder struct: quantity before stopPrice.
        sl_order = {}
        sl_order["clOrdID"] = sl_cl
        sl_order["modifier"] = int(OrderModifier.STOP)
        sl_order["side"] = int(close_side)
        sl_order["type"] = int(OrderType.MARKET)
        sl_order["timeInForce"] = int(TimeInForce.IOC)
        sl_order["quantity"] = qty           # pos 7 in Go struct (before stopPrice)
        sl_order["stopPrice"] = sl_px        # pos 9
        sl_order["stopType"] = int(StopType.STOP_LOSS)
        sl_order["triggerType"] = int(TriggerType.MARK_PRICE)
        sl_order["reduceOnly"] = True
        sl_order["positionSide"] = int(PositionSide.BOTH)

        try:
            self.client.perps_place_orders(
                self.account_id, self.cfg.symbol_id, [tp_order, sl_order]
            )
            tp_pct = tp_move / fill * 100
            sl_pct = sl_move / fill * 100
            log.info(
                f"[TP/SL] TP={tp_px} (+${self.cfg.tp_usd:.2f} / {tp_pct:.3f}%)  "
                f"SL={sl_px} (-${self.cfg.sl_usd:.2f} / {sl_pct:.3f}%)  "
                f"lado={close_side.name}"
            )
            return tp_cl, sl_cl
        except Exception as e:
            log.error(f"[TP/SL] Falha: {e}")
            return None, None

    def _market_close(self, side: OrderSide, qty: str, tp_cl: Optional[str], sl_cl: Optional[str]) -> None:
        """Fecha posicao a mercado e cancela ordens abertas."""
        close_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        cl = self._clid("M")
        order = {}
        order["clOrdID"] = cl
        order["modifier"] = int(OrderModifier.NORMAL)
        order["side"] = int(close_side)
        order["type"] = int(OrderType.MARKET)
        order["timeInForce"] = int(TimeInForce.IOC)
        order["quantity"] = qty
        order["reduceOnly"] = True
        order["positionSide"] = int(PositionSide.BOTH)
        try:
            self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [order])
        except Exception as e:
            log.error(f"[MKTCLOSE] {e}")
        if tp_cl:
            self._cancel(tp_cl)
        if sl_cl:
            self._cancel(sl_cl)

    def _place_be_stop(self, side: OrderSide, fill: float, qty: str) -> Optional[str]:
        """
        Coloca stop-market no preco de entrada (breakeven).
        Cancela o SL original antes de chamar este metodo.
        """
        close_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        be_px = self._px(fill)
        cl = self._clid("B")
        order = {}
        order["clOrdID"] = cl
        order["modifier"] = int(OrderModifier.STOP)
        order["side"] = int(close_side)
        order["type"] = int(OrderType.MARKET)
        order["timeInForce"] = int(TimeInForce.IOC)
        order["quantity"] = qty
        order["stopPrice"] = be_px
        order["stopType"] = int(StopType.STOP_LOSS)
        order["triggerType"] = int(TriggerType.MARK_PRICE)
        order["reduceOnly"] = True
        order["positionSide"] = int(PositionSide.BOTH)
        try:
            self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [order])
            log.info(f"[BE] Stop breakeven colocado @ ${be_px} (id={cl})")
            return cl
        except Exception as e:
            log.error(f"[BE] Falha ao colocar BE stop: {e}")
            return None

    def _wait_close(
        self,
        tp_cl: Optional[str],
        sl_cl: Optional[str],
        fill: float,
        side: OrderSide,
        qty: str,
    ) -> tuple[str, float]:
        """
        Monitora a posicao ate fechar via TP, SL ou regras dinamicas:

          1. Preco atinge 50% do alvo  -> move SL para breakeven (entrada)
             A partir dai aguarda indefinidamente ate TP ou BE stop.
          2. Posicao negativa por 90s  -> fecha a mercado (MANUAL)
          3. Hard timeout (5 min)      -> fecha a mercado (failsafe)

        Retorna (resultado, preco_saida).
        """
        deadline = time.time() + self.cfg.position_timeout_s

        qty_f   = float(qty)
        tp_move = self.cfg.tp_usd / qty_f
        sl_move = self.cfg.sl_usd / qty_f
        half_tp = tp_move * 0.5   # 50% do alvo TP

        breakeven_set  = False
        negative_since: Optional[float] = None

        while time.time() < deadline:
            time.sleep(self.cfg.poll_s)

            pos = self._get_position()
            if pos is None:
                # Posicao fechou — descobrir qual ordem executou
                open_cls = {o.get("c") for o in self._open_orders()}

                if tp_cl and tp_cl not in open_cls:
                    result_px = (fill + tp_move) if side == OrderSide.BUY else (fill - tp_move)
                    if sl_cl and sl_cl in open_cls:
                        self._cancel(sl_cl)
                    log.info(f"[CLOSE] TAKE PROFIT @ ~${result_px:,.2f}")
                    return "TP", result_px

                if sl_cl and sl_cl not in open_cls:
                    if breakeven_set:
                        result_px = fill
                        log.info(f"[CLOSE] BREAKEVEN @ ~${result_px:,.2f}")
                        return "BE", result_px
                    result_px = (fill - sl_move) if side == OrderSide.BUY else (fill + sl_move)
                    if tp_cl and tp_cl in open_cls:
                        self._cancel(tp_cl)
                    log.info(f"[CLOSE] STOP LOSS @ ~${result_px:,.2f}")
                    return "SL", result_px

                px = self._mark_price()
                log.info(f"[CLOSE] Fechado (outro motivo) @ ${px:,.2f}")
                return "MANUAL", px

            # ── Verificar preco atual para logica dinamica ───────────────────
            try:
                mark = self._mark_price()
            except Exception:
                continue

            if side == OrderSide.BUY:
                pnl_raw      = (mark - fill) * qty_f
                reached_half = mark >= fill + half_tp
            else:
                pnl_raw      = (fill - mark) * qty_f
                reached_half = mark <= fill - half_tp

            # 1. Mover SL para breakeven ao atingir 50% do TP
            if reached_half and not breakeven_set:
                log.info(
                    f"[BE] 50% do alvo atingido — mark=${mark:,.0f} | "
                    f"pnl=${pnl_raw:+.4f} | movendo SL para entrada @ ${fill:,.0f}"
                )
                if sl_cl:
                    self._cancel(sl_cl)
                sl_cl = self._place_be_stop(side, fill, qty)
                breakeven_set = True
                negative_since = None  # reseta contador

            # 2. Saida antecipada: cruzamento inverso das EMAs
            if not breakeven_set and self._check_ema_exit(side):
                log.info(f"[EMA-EXIT] Cruzamento inverso detectado — fechando posicao (mark=${mark:,.0f})")
                self._market_close(side, qty, tp_cl, sl_cl)
                return "MANUAL", mark

            # 3. Fechar se negativo por mais de 90s (nao se breakeven ativo)
            if not breakeven_set:
                if pnl_raw < 0:
                    if negative_since is None:
                        negative_since = time.time()
                        log.info(f"[MONIT] Posicao negativa ${pnl_raw:+.4f} — contagem 90s iniciada")
                    elif time.time() - negative_since >= 90:
                        log.warning(
                            f"[EXIT] Negativo por 90s — zerando posicao "
                            f"(mark=${mark:,.2f} pnl=${pnl_raw:+.4f})"
                        )
                        self._market_close(side, qty, tp_cl, sl_cl)
                        return "MANUAL", mark
                else:
                    if negative_since is not None:
                        log.info(f"[MONIT] Posicao voltou ao positivo ${pnl_raw:+.4f} — reset contador")
                    negative_since = None

        # Hard timeout (failsafe — nao deve ocorrer normalmente)
        log.warning("[CLOSE] Hard timeout — fechando a mercado")
        mark = self._mark_price()
        self._market_close(side, qty, tp_cl, sl_cl)
        return "MANUAL", mark

    # ── Logica do dia ────────────────────────────────────────────────────────

    def _daily_loss(self) -> float:
        today = datetime.now(timezone.utc).date()
        losses = [t.pnl for t in self.tracker.trades
                  if t.timestamp.date() == today and t.pnl < 0]
        return -sum(losses)

    def _is_active_day(self) -> bool:
        if self.cfg.active_weekdays is None:
            return True
        return datetime.now(timezone.utc).weekday() in self.cfg.active_weekdays

    def _is_active_hour(self) -> bool:
        """Retorna False se estiver apos o horario de encerramento diario."""
        if self.cfg.stop_hour_utc is None:
            return True
        return datetime.now(timezone.utc).hour < self.cfg.stop_hour_utc

    # ── Loop principal ───────────────────────────────────────────────────────

    def run(self) -> None:
        log.info("=" * 58)
        log.info("  SODEX BTC SCALPER - 24H AIRDROP BOT")
        log.info(f"  Par       : {self.cfg.symbol_name}")
        log.info(f"  Sizing    : {int(self.cfg.margin_pct*100)}% margem x {self.cfg.leverage}x leverage")
        log.info(f"  TP / SL   : ${self.cfg.tp_usd:.2f} / ${self.cfg.sl_usd:.2f} (fixo em USD)")
        log.info(f"  Meta vol  : ${self.cfg.weekly_target_usd:,.0f}")
        log.info("=" * 58)

        self._running = True

        while self._running:
            try:
                # ── Checks de operacao ────────────────────────────
                if not self._is_active_day():
                    log.info("[PAUSE] Dia inativo - aguardando meia-noite UTC...")
                    time.sleep(60)
                    continue

                if not self._is_active_hour():
                    now_utc = datetime.now(timezone.utc)
                    log.info(
                        f"[PAUSA NOTURNA] {now_utc.strftime('%H:%M UTC')} — "
                        f"encerrado as {self.cfg.stop_hour_utc:02d}:00 UTC (20:00 BRT). "
                        f"Retomando amanha."
                    )
                    time.sleep(300)
                    continue

                if self.tracker.total_volume >= self.cfg.weekly_target_usd:
                    log.info("[DONE] Meta de volume semanal atingida!")
                    self.tracker.print_dashboard()
                    self._running = False
                    break

                daily_loss = self._daily_loss()
                if daily_loss >= self.cfg.max_daily_loss_usd:
                    log.warning(
                        f"[PAUSA DIA] Perda diaria ${daily_loss:.4f} >= limite ${self.cfg.max_daily_loss_usd} "
                        f"| Retomando em 5 min..."
                    )
                    time.sleep(300)
                    continue

                # ── Verificar posicao existente ───────────────────
                existing = self._get_position()
                if existing:
                    sz  = float(existing.get("sz", 0))
                    ep  = float(existing.get("ep", 0))
                    lev = existing.get("l", "?")
                    log.info(
                        f"[WAIT] Posicao aberta: {'LONG' if sz > 0 else 'SHORT'} "
                        f"{abs(sz)} BTC @ ${ep:,.0f} (lev={lev}x) - aguardando fechar..."
                    )
                    time.sleep(10)
                    continue

                # ── Analise de preco e decisao de entrada ─────────
                direction, current_price = self._analyze_entry()

                if direction is None or current_price == 0:
                    time.sleep(5)
                    continue

                # ── Sizing ────────────────────────────────────────
                qty, notional = self._calc_trade_size(current_price)
                if notional < MIN_NOTIONAL:
                    log.warning(f"[SKIP] Notional ${notional:.2f} < minimo ${MIN_NOTIONAL}")
                    time.sleep(30)
                    continue

                n = len(self.tracker.trades) + 1
                log.info(
                    f"\n{'='*58}\n"
                    f"  TRADE #{n} | {direction.name} {qty} BTC @ ~${current_price:,.2f}\n"
                    f"  Volume acumulado: ${self.tracker.total_volume:,.2f} / ${self.cfg.weekly_target_usd:,.0f}\n"
                    f"{'='*58}"
                )

                ts_start = time.time()
                self._last_side = direction

                # ── Colocar entrada ───────────────────────────────
                entry_cl = self._place_entry(direction, current_price, qty)
                if not entry_cl:
                    time.sleep(5)
                    continue

                # ── Aguardar fill ─────────────────────────────────
                fill_px = self._wait_fill(entry_cl)
                if not fill_px:
                    time.sleep(5)
                    continue

                # ── Colocar TP + SL ───────────────────────────────
                tp_cl, sl_cl = self._place_tp_sl(direction, fill_px, qty)

                # ── Monitorar ate fechar ──────────────────────────
                result, exit_px = self._wait_close(tp_cl, sl_cl, fill_px, direction, qty)

                # ── Calcular PnL ──────────────────────────────────
                qty_f = float(qty)
                notional_f = qty_f * fill_px
                raw_pnl = (
                    (exit_px - fill_px) * qty_f
                    if direction == OrderSide.BUY
                    else (fill_px - exit_px) * qty_f
                )
                # Entrada sempre LIMIT (maker). Saida depende do tipo:
                #   TP  -> LIMIT (maker)
                #   SL / BE / MANUAL -> MARKET (taker)
                fee_entry = notional_f * self.cfg.maker_fee_pct
                if result == "TP":
                    fee_exit = notional_f * self.cfg.maker_fee_pct
                else:
                    fee_exit = notional_f * self.cfg.taker_fee_pct
                fees    = fee_entry + fee_exit
                net_pnl = raw_pnl - fees
                dur_s   = time.time() - ts_start

                trade = Trade(
                    id=entry_cl,
                    symbol=self.cfg.symbol_name,
                    side=direction.name,
                    entry_price=fill_px,
                    exit_price=exit_px,
                    quantity=qty_f,
                    notional=notional_f,
                    pnl=net_pnl,
                    fees=fees,
                    duration_s=dur_s,
                    result=result,
                )
                self.tracker.add_trade(trade)

                log.info(
                    f"[RESULT] {result} | "
                    f"entry=${fill_px:,.2f} exit=${exit_px:,.2f} | "
                    f"PnL={net_pnl:+.6f} USD | "
                    f"vol+=${notional_f*2:,.2f} | "
                    f"dur={dur_s:.0f}s"
                )

                # Dashboard a cada 10 trades
                if len(self.tracker.trades) % 10 == 0:
                    self.tracker.print_dashboard()

            except KeyboardInterrupt:
                log.info("\n[STOP] Bot parado pelo usuario.")
                break
            except Exception as e:
                log.error(f"[ERROR] {e}", exc_info=True)
                time.sleep(10)

        self._running = False
        self.tracker.print_dashboard()
        log.info("[BOT] Encerrado.")

    def stop(self) -> None:
        self._running = False
