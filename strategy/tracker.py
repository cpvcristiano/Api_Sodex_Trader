"""
Volume and PnL tracker for airdrop volume generation.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class Trade:
    id: str
    symbol: str
    side: str           # LONG / SHORT
    entry_price: float
    exit_price: float
    quantity: float     # BTC/ETH/SOL qty
    notional: float     # USD notional
    pnl: float          # USD profit/loss (after fees)
    fees: float         # USD fees paid
    duration_s: float   # seconds in trade
    result: str         # TP / SL / MANUAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class VolumeTracker:
    def __init__(self, weekly_target: float = 100_000.0):
        self.weekly_target = weekly_target
        self.trades: List[Trade] = []

    def add_trade(self, trade: Trade) -> None:
        self.trades.append(trade)

    @property
    def total_volume(self) -> float:
        # Each buy + sell side counts separately
        return sum(t.notional * 2 for t in self.trades)

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def total_fees(self) -> float:
        return sum(t.fees for t in self.trades)

    @property
    def win_count(self) -> int:
        return sum(1 for t in self.trades if t.result == "TP")

    @property
    def loss_count(self) -> int:
        return sum(1 for t in self.trades if t.result == "SL")

    @property
    def win_rate(self) -> float:
        total = len(self.trades)
        return (self.win_count / total * 100) if total > 0 else 0.0

    @property
    def progress_pct(self) -> float:
        return min(self.total_volume / self.weekly_target * 100, 100.0)

    def print_dashboard(self) -> None:
        bar_len = 40
        filled = int(self.progress_pct / 100 * bar_len)
        bar = "#" * filled + "." * (bar_len - filled)

        print("\n" + "=" * 60)
        print("  SODEX SCALPING BOT - AIRDROP VOLUME TRACKER")
        print("=" * 60)
        print(f"  Volume gerado : ${self.total_volume:>12,.2f}")
        print(f"  Meta semanal  : ${self.weekly_target:>12,.2f}")
        print(f"  Progresso     : [{bar}] {self.progress_pct:.1f}%")
        print(f"  Restante      : ${max(self.weekly_target - self.total_volume, 0):>12,.2f}")
        print("-" * 60)
        print(f"  Total trades  : {len(self.trades)}")
        print(f"  Vitorias (TP) : {self.win_count}  |  Perdas (SL): {self.loss_count}")
        print(f"  Win rate      : {self.win_rate:.1f}%")
        print(f"  PnL liquido   : ${self.total_pnl:>+.4f}")
        print(f"  Fees pagas    : ${self.total_fees:.4f}")
        print("=" * 60)
