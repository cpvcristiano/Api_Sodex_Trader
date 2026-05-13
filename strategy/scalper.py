import logging
import time
import uuid
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Optional, List

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
from strategy.base import BaseStrategy

log = logging.getLogger("engine")

TICK = 1
STEP = 0.00001
MIN_NOTIONAL = 10.0

@dataclass
class ScalpConfig:
    symbol_name: str = "BTC-USD"
    symbol_id: int = 1
    margin_pct: float = 0.25
    leverage: int = 25
    tp_usd: float = 2.00
    sl_usd: float = 0.50
    analysis_secs: float = 20.0
    analysis_samples: int = 8
    entry_timeout_s: float = 25.0
    position_timeout_s: float = 180.0
    poll_s: float = 2.0
    min_margin_usd: float = 1.0
    max_daily_loss_usd: float = 3.0
    weekly_target_usd: float = 100_000.0
    active_weekdays: Optional[List[int]] = None
    stop_hour_utc: Optional[int] = None
    maker_fee_pct: float = 0.00012
    taker_fee_pct: float = 0.00050
    tp_pct: float = 0.00418
    sl_pct: float = 0.000835
    regime_adx_min: float = 20.0
    regime_atr_pct: float = 0.20
    regime_di_min: float = 5.0
    price_precision: int = 2
    qty_precision: int = 3
    tick_size: float = 0.01
    step_size: float = 0.001

class TraderEngine:
    """
    Motor de execução de trades. 
    Responsável pelo loop principal, gerenciamento de ordens e persistência.
    """

    def __init__(self, client: SodexClient, account_id: int, strategy: BaseStrategy, config: ScalpConfig = None):
        self.client = client
        self.account_id = account_id
        self.strategy = strategy
        self.cfg = config or ScalpConfig()
        self.tracker = VolumeTracker(self.cfg.weekly_target_usd)
        self._running = False

    def _px(self, price: float) -> str:
        dec = Decimal(str(price)).quantize(
            Decimal(str(self.cfg.tick_size)), rounding=ROUND_DOWN
        )
        return format(dec.normalize(), "f")

    def _qty(self, notional: float, price: float) -> str:
        raw = notional / price
        dec = Decimal(str(raw)).quantize(
            Decimal(str(self.cfg.step_size)), rounding=ROUND_DOWN
        )
        return format(dec.normalize(), "f")

    def _available_margin(self) -> float:
        try:
            state = self.client.perps_account_state()
            return float(state.get("am", 0))
        except Exception as e:
            log.warning(f"[MARGIN] {e}")
            return 0.0

    def _get_position(self) -> Optional[dict]:
        try:
            state = self.client.perps_account_state()
            for p in (state.get("P") or []):
                if p.get("s") == self.cfg.symbol_name and float(p.get("sz", 0)) != 0:
                    return p
        except Exception as e:
            log.warning(f"[POS] {e}")
        return None

    def _open_orders(self) -> list:
        try:
            state = self.client.perps_account_state()
            orders = (state.get("O") or []) if state else []
            return [o for o in orders if o.get("s") == self.cfg.symbol_name]
        except Exception as e:
            log.warning(f"[ORDERS] {e}")
            return []

    def _clid(self, prefix: str) -> str:
        return f"{prefix}{int(time.time())}{uuid.uuid4().hex[:4]}"

    def _place_bracket(self, side: OrderSide, price: float, qty: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Coloca entrada LIMIT. TP/SL serão adicionados após o fill."""
        entry_px = self._px(price - self.cfg.tick_size if side == OrderSide.BUY else price + self.cfg.tick_size)
        entry_cl = self._clid("E")
        entry_order = {
            "clOrdID": entry_cl, "modifier": int(OrderModifier.NORMAL), "side": int(side),
            "type": int(OrderType.LIMIT), "timeInForce": int(TimeInForce.GTC),
            "price": entry_px, "quantity": qty, "reduceOnly": False, "positionSide": int(PositionSide.BOTH)
        }
        try:
            self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [entry_order])
            log.info(f"[ENTRY] {side.name} {qty} @ limit {entry_px}")
            return entry_cl, None, None
        except Exception as e:
            log.error(f"[ENTRY] Falha: {e}")
            return None, None, None

    def _cancel(self, cl: str) -> None:
        try:
            self.client.perps_cancel_order(self.account_id, self.cfg.symbol_id, cl_ord_id=cl)
        except: pass

    def _wait_fill(self, entry_cl: str) -> Optional[float]:
        deadline = time.time() + self.cfg.entry_timeout_s
        while time.time() < deadline:
            time.sleep(self.cfg.poll_s)
            if entry_cl not in {o.get("c") for o in self._open_orders()}:
                pos = self._get_position()
                if pos: return float(pos.get("ep", 0))
                return None
        self._cancel(entry_cl)
        pos = self._get_position()
        return float(pos.get("ep", 0)) if pos else None

    def _place_tp_sl(self, side: OrderSide, fill: float, qty: str, notional: float) -> tuple[Optional[str], Optional[str]]:
        close_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        tp_move, sl_move = self.strategy.get_tp_sl(fill, float(qty), notional)

        tp_px = self._px(fill + tp_move if side == OrderSide.BUY else fill - tp_move)
        sl_px = self._px(fill - sl_move if side == OrderSide.BUY else fill + sl_move)

        tp_cl, sl_cl = self._clid("T"), self._clid("S")

        tp_order = {
            "clOrdID": tp_cl, "modifier": int(OrderModifier.NORMAL), "side": int(close_side),
            "type": int(OrderType.LIMIT), "timeInForce": int(TimeInForce.GTC),
            "price": tp_px, "quantity": qty, "reduceOnly": True, "positionSide": int(PositionSide.BOTH)
        }
        sl_order = {
            "clOrdID": sl_cl, "modifier": int(OrderModifier.STOP), "side": int(close_side),
            "type": int(OrderType.MARKET), "timeInForce": int(TimeInForce.IOC),
            "quantity": qty, "stopPrice": sl_px, "stopType": int(StopType.STOP_LOSS),
            "triggerType": int(TriggerType.MARK_PRICE), "reduceOnly": True, "positionSide": int(PositionSide.BOTH)
        }

        # Try batch first, then separately, up to 3 rounds with increasing backoff
        last_err = None
        for attempt in range(3):
            if attempt > 0:
                time.sleep(1.5 * attempt)
            try:
                self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [tp_order, sl_order])
                log.info(f"[TP/SL] TP={tp_px} SL={sl_px}")
                return tp_cl, sl_cl
            except Exception as e:
                last_err = e
                log.warning(f"[TP/SL] Tentativa {attempt+1} batch falhou: {e}")

        # Batch failed — try placing TP and SL separately
        tp_ok = sl_ok = False
        for attempt in range(3):
            if attempt > 0:
                time.sleep(1.5 * attempt)
            if not tp_ok:
                try:
                    self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [tp_order])
                    log.info(f"[TP] Separado OK: {tp_px}")
                    tp_ok = True
                except Exception as e:
                    log.warning(f"[TP] Separado falhou tentativa {attempt+1}: {e}")
            if not sl_ok:
                try:
                    self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [sl_order])
                    log.info(f"[SL] Separado OK: {sl_px}")
                    sl_ok = True
                except Exception as e:
                    log.warning(f"[SL] Separado falhou tentativa {attempt+1}: {e}")
            if tp_ok and sl_ok:
                break

        if tp_ok or sl_ok:
            return (tp_cl if tp_ok else None), (sl_cl if sl_ok else None)

        log.error(f"[TP/SL] FALHA TOTAL — sem protecao: {last_err}")
        return None, None

    def _place_sl(self, side: OrderSide, stop_price: float, qty: str) -> Optional[str]:
        close_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        sl_px = self._px(stop_price)
        sl_cl = self._clid("S")
        sl_order = {
            "clOrdID": sl_cl, "modifier": int(OrderModifier.STOP), "side": int(close_side),
            "type": int(OrderType.MARKET), "timeInForce": int(TimeInForce.IOC),
            "quantity": qty, "stopPrice": sl_px, "stopType": int(StopType.STOP_LOSS),
            "triggerType": int(TriggerType.MARK_PRICE), "reduceOnly": True,
            "positionSide": int(PositionSide.BOTH)
        }
        try:
            self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [sl_order])
            log.info(f"[SL-MOVE] Novo SL @ {sl_px}")
            return sl_cl
        except Exception as e:
            log.error(f"[SL-MOVE] Falha: {e}")
            return None

    def _market_close(self, side: OrderSide, qty: str, tp_cl: str, sl_cl: str) -> None:
        close_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
        order = {
            "clOrdID": self._clid("M"), "modifier": int(OrderModifier.NORMAL), "side": int(close_side),
            "type": int(OrderType.MARKET), "timeInForce": int(TimeInForce.IOC),
            "quantity": qty, "reduceOnly": True, "positionSide": int(PositionSide.BOTH)
        }
        try: self.client.perps_place_orders(self.account_id, self.cfg.symbol_id, [order])
        except Exception as e: log.error(f"[MKTCLOSE] {e}")
        if tp_cl: self._cancel(tp_cl)
        if sl_cl: self._cancel(sl_cl)

    def _wait_close(self, tp_cl: str, sl_cl: str, fill: float, side: OrderSide, qty: str) -> tuple[str, float]:
        deadline = time.time() + self.cfg.position_timeout_s
        qty_f = float(qty)
        tp_usd = self.cfg.tp_usd  # ex: $1.00

        trail0_triggered = False  # 30% TP → SL para break-even ($0.00)
        trail1_triggered = False  # 55% TP → SL para +30% TP
        trail2_triggered = False  # 80% TP → SL para +60% TP

        while True:
            time.sleep(self.cfg.poll_s)

            pos = self._get_position()
            if pos is None:
                open_cls = {o.get("c") for o in self._open_orders()}
                if tp_cl not in open_cls:
                    if sl_cl in open_cls: self._cancel(sl_cl)
                    return "TP", (fill + tp_usd / qty_f if side == OrderSide.BUY else fill - tp_usd / qty_f)
                if sl_cl not in open_cls:
                    if tp_cl in open_cls: self._cancel(tp_cl)
                    label = "TRAIL2" if trail2_triggered else ("TRAIL1" if trail1_triggered else ("TRAIL0" if trail0_triggered else "SL"))
                    return label, fill
                return "MANUAL", fill

            mark = fill
            try:
                state = self.client.perps_account_state()
                for p in (state.get("P") or []):
                    if p.get("s") == self.cfg.symbol_name:
                        mark = float(p.get("mp", fill))
            except: pass

            pnl_usd = (mark - fill) * qty_f if side == OrderSide.BUY else (fill - mark) * qty_f
            log.info(f"[POS] PnL={pnl_usd:+.3f} mark={mark:,.2f}")

            # Timeout so fecha posicoes negativas — posicoes positivas ficam abertas ate TP ou SL
            if time.time() > deadline and pnl_usd < 0:
                log.info(f"[TIMEOUT] {pnl_usd:+.3f} negativo apos {self.cfg.position_timeout_s:.0f}s — fechando")
                self._market_close(side, qty, tp_cl, sl_cl)
                return "MANUAL", mark

            # Nível 2: PnL >= 80% do TP → SL sobe para +60% do TP
            if not trail2_triggered and pnl_usd >= tp_usd * 0.80:
                lock_price = fill + (tp_usd * 0.60 / qty_f) if side == OrderSide.BUY else fill - (tp_usd * 0.60 / qty_f)
                if sl_cl: self._cancel(sl_cl)
                new_cl = self._place_sl(side, lock_price, qty)
                if new_cl: sl_cl = new_cl
                trail2_triggered = True
                log.info(f"[TRAIL-2] {pnl_usd:+.3f} (80% TP) → SL travado em +${tp_usd*0.60:.2f} @ {lock_price:.2f}")

            # Nível 1: PnL >= 55% do TP → SL sobe para +30% do TP
            elif not trail1_triggered and pnl_usd >= tp_usd * 0.55:
                lock_price = fill + (tp_usd * 0.30 / qty_f) if side == OrderSide.BUY else fill - (tp_usd * 0.30 / qty_f)
                if sl_cl: self._cancel(sl_cl)
                new_cl = self._place_sl(side, lock_price, qty)
                if new_cl: sl_cl = new_cl
                trail1_triggered = True
                log.info(f"[TRAIL-1] {pnl_usd:+.3f} (55% TP) → SL travado em +${tp_usd*0.30:.2f} @ {lock_price:.2f}")

            # Nível 0: PnL >= 30% do TP → SL para break-even (nao vai negativo)
            elif not trail0_triggered and pnl_usd >= tp_usd * 0.30:
                lock_price = fill  # break-even exato
                if sl_cl: self._cancel(sl_cl)
                new_cl = self._place_sl(side, lock_price, qty)
                if new_cl: sl_cl = new_cl
                trail0_triggered = True
                log.info(f"[TRAIL-0] {pnl_usd:+.3f} (30% TP) → SL break-even @ {lock_price:.2f}")

            if self.strategy.check_exit(side, {}):
                log.info(f"[STRAT-EXIT] Sinal de saida detectado")
                self._market_close(side, qty, tp_cl, sl_cl)
                return "MANUAL", mark

    def run(self) -> None:
        log.info("Motor de execução iniciado. Entrando no loop principal...")
        self._running = True
        _entry_backoff = 0.0  # seconds to wait before next entry attempt

        while self._running:
            try:
                if self.tracker.total_volume >= self.cfg.weekly_target_usd:
                    log.info("[DONE] Meta atingida"); break

                existing = self._get_position()
                if existing:
                    # Monitora posicao ja aberta (ex: sobreviveu ao restart)
                    # Recupera TP/SL das ordens abertas e entra no loop de trailing
                    open_orders = self._open_orders()
                    tp_cl_ex = sl_cl_ex = None
                    for o in open_orders:
                        st = o.get("st")  # stopType
                        if st == 2: tp_cl_ex = o.get("c")   # TAKE_PROFIT
                        elif st == 1: sl_cl_ex = o.get("c") # STOP_LOSS
                    fill_ex = float(existing.get("ep", 0))
                    side_ex = OrderSide.BUY if float(existing.get("pa", 0)) > 0 else OrderSide.SELL
                    qty_ex  = str(abs(float(existing.get("pa", 0))))
                    if fill_ex > 0 and qty_ex != "0.0":
                        log.info(f"[RECOVER] Posicao aberta detectada: {side_ex.name} {qty_ex} @ {fill_ex:.2f}")
                        result, exit_px = self._wait_close(tp_cl_ex, sl_cl_ex, fill_ex, side_ex, qty_ex)
                        notional_f = float(qty_ex) * fill_ex
                        pnl = (exit_px - fill_ex) * float(qty_ex) if side_ex == OrderSide.BUY else (fill_ex - exit_px) * float(qty_ex)
                        log.info(f"[RESULT] {result} PnL={pnl:+.4f} (posicao recuperada)")
                    else:
                        time.sleep(10)
                    continue

                # Prevent duplicate entries: skip if there is already an open order
                open_orders = self._open_orders()
                if open_orders:
                    log.info(f"[DEDUP] {len(open_orders)} ordem(ns) abertas — aguardando")
                    time.sleep(5); continue

                if _entry_backoff > 0:
                    time.sleep(_entry_backoff)
                    _entry_backoff = 0.0

                direction, price = self.strategy.analyze({})
                if direction is None:
                    time.sleep(5); continue

                margin_use = self._available_margin() * self.cfg.margin_pct
                notional = margin_use * self.cfg.leverage
                if notional < MIN_NOTIONAL:
                    time.sleep(30); continue

                qty = self._qty(notional, price)
                entry_cl, tp_cl, sl_cl = self._place_bracket(direction, price, qty)
                if not entry_cl:
                    _entry_backoff = 5.0
                    continue

                fill_px = self._wait_fill(entry_cl)
                if not fill_px:
                    _entry_backoff = 30.0  # ordem nao preencheu — espera antes de tentar de novo
                    continue

                # Se o bracket não incluiu TP/SL (fallback para entrada simples),
                # tenta colocá-los agora com retry
                if tp_cl is None:
                    time.sleep(1.0)
                    tp_cl, sl_cl = self._place_tp_sl(direction, fill_px, qty, notional)

                if tp_cl is None and sl_cl is None:
                    log.error("[SAFETY] TP/SL falhou completamente — fechando a mercado")
                    self._market_close(direction, qty, None, None)
                    time.sleep(3)
                    notional_f = float(qty) * fill_px
                    trade = Trade(id=entry_cl, symbol=self.cfg.symbol_name, side=direction.name,
                                  entry_price=fill_px, exit_price=fill_px, quantity=float(qty),
                                  notional=notional_f, pnl=0.0, fees=0, duration_s=0, result="SAFETY")
                    self.tracker.add_trade(trade)
                    log.info("[RESULT] SAFETY PnL=+0.0000 (fechou sem protecao)")
                    continue

                result, exit_px = self._wait_close(tp_cl, sl_cl, fill_px, direction, qty)

                notional_f = float(qty) * fill_px
                pnl = (exit_px - fill_px) * float(qty) if direction == OrderSide.BUY else (fill_px - exit_px) * float(qty)
                trade = Trade(id=entry_cl, symbol=self.cfg.symbol_name, side=direction.name,
                              entry_price=fill_px, exit_price=exit_px, quantity=float(qty),
                              notional=notional_f, pnl=pnl, fees=0, duration_s=0, result=result)
                self.tracker.add_trade(trade)
                log.info(f"[RESULT] {result} PnL={pnl:+.4f}")

            except KeyboardInterrupt: break
            except Exception as e:
                log.error(f"[ERROR] {e}"); time.sleep(10)

# Alias para compatibilidade se necessário
ScalpingBot = TraderEngine
