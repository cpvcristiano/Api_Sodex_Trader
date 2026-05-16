"""
Volume and PnL tracker for airdrop volume generation with persistence.
"""
import os
import csv
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Optional

log = logging.getLogger("tracker")

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

    def to_dict(self):
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict):
        d['timestamp'] = datetime.fromisoformat(d['timestamp'])
        # Ensure numeric types are floats
        for key in ['entry_price', 'exit_price', 'quantity', 'notional', 'pnl', 'fees', 'duration_s']:
            if key in d:
                d[key] = float(d[key])
        return cls(**d)

class VolumeTracker:
    def __init__(self, weekly_target: float = 100_000.0, data_dir: str = "data"):
        self.weekly_target = weekly_target
        self.data_dir = data_dir
        self.trades: List[Trade] = []
        
        # Paths
        self.trades_file = os.path.join(data_dir, "trades.csv")
        self.state_file = os.path.join(data_dir, "state.json")
        self.decisions_file = os.path.join(data_dir, "decisions.jsonl")
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        self.load_trades()

    def add_trade(self, trade: Trade) -> None:
        self.trades.append(trade)
        self.save_trade_to_csv(trade)
        self.save_state()

    def load_trades(self) -> None:
        """Loads trade history from CSV."""
        if not os.path.exists(self.trades_file):
            return
            
        try:
            with open(self.trades_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        self.trades.append(Trade.from_dict(row))
                    except Exception as e:
                        log.error(f"Error parsing trade row: {e}")
            log.info(f"Loaded {len(self.trades)} trades from {self.trades_file}")
        except Exception as e:
            log.error(f"Failed to load trades: {e}")

    def save_trade_to_csv(self, trade: Trade) -> None:
        """Appends a single trade to the CSV file."""
        file_exists = os.path.exists(self.trades_file)
        fieldnames = list(trade.to_dict().keys())
        
        try:
            with open(self.trades_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(trade.to_dict())
        except Exception as e:
            log.error(f"Failed to save trade to CSV: {e}")

    def save_state(self) -> None:
        """Saves current summary state to JSON."""
        state = {
            "last_update": datetime.now(timezone.utc).isoformat(),
            "total_volume": self.total_volume,
            "total_pnl": self.total_pnl,
            "total_trades": len(self.trades),
            "weekly_target": self.weekly_target,
            "progress_pct": self.progress_pct
        }
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save state: {e}")

    def log_decision(self, decision: dict) -> None:
        """Logs a technical analysis decision to a JSONL file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **decision
        }
        try:
            with open(self.decisions_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log.error(f"Failed to log decision: {e}")

    @property
    def total_volume(self) -> float:
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
