"""
Sodex BTC Scalping Bot - Airdrop SOSO
======================================
  python run_bot.py

Regras:
  - BTC-USD perps, 25x (maximo permitido na Sodex)
  - 25% da margem disponivel por trade
  - Uma posicao de cada vez
  - 24h / 7 dias
  - Analisa preco ~30s (ritmo de grafico 1min) antes de cada entrada
  - TP: $0.50 | SL: $0.10 (R:R 5:1, break-even em ~20% win rate)
  - Para ao atingir a meta semanal de volume

Semana do airdrop: 10/04 a 17/04

Matematica com $12 de conta:
  Margem/trade : $12 x 25% = $3.00
  Notional 25x : $3.00 x 25 = $75.00
  TP ($0.50)   : preco move ~$446 (0.62%) -> fecha em ~2-4 min
  SL ($0.10)   : preco move ~$89  (0.12%) -> fecha em segundos
  Fee/trade    : ~$0.019 (0.012% x 2 lados)
  EV @ 40% win : +$0.12/trade
  Volume/trade : ~$150 (ambos lados)
  Para $100k   : ~667 trades (~2 dias a 24h)
"""
import io
import logging
import sys
from datetime import datetime, timezone

# Forcar UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from config import API_KEY, API_KEY_NAME, PRIVATE_KEY, WALLET_ADDRESS
from sodex import SodexClient
from strategy import ScalpConfig, ScalpingBot

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("run_bot")

# ─── Configuracao ─────────────────────────────────────────────────────────────
cfg = ScalpConfig()

# Par e alavancagem
cfg.symbol_name = "BTC-USD"
cfg.symbol_id   = 1
cfg.leverage    = 25         # maximo permitido na Sodex para BTC (usuario queria 40x)

# Sizing: 25% da margem disponivel por trade
cfg.margin_pct  = 0.50   # 50% da margem por trade (saldo baixo)

# TP/SL em dolares fixos — calibrado para conta de ~$12 com 25x
# R:R = 5:1 | break-even win rate = 20% | EV positivo acima de 20% wins
cfg.tp_usd = 0.30            # lucro alvo por trade
cfg.sl_usd = 0.10            # stop loss por trade (R:R 3:1)

# Analise de entrada: ~30s simulando ritmo de grafico 1-minuto
# 6 amostras a cada 6s cobrem o range de uma vela de 1min
cfg.analysis_secs    = 15
cfg.analysis_samples = 4

# Timeouts
cfg.entry_timeout_s    = 20.0
cfg.position_timeout_s = 300.0  # 5 min failsafe — saida real: 90s negativo ou TP/BE
cfg.poll_s             = 2.0

# Protecoes
# Com SL de $0.10, 20 losses consecutivos = $2.00 de perda diaria
cfg.min_margin_usd     = 0.5   # minimo para operar (conta pequena de $12)
cfg.max_daily_loss_usd = 2.0   # para o dia se perder mais que $2 (20 SL seguidos)

# Meta semanal
cfg.weekly_target_usd = 100_000.0

# Dias ativos (None = todos os 7 dias)
cfg.active_weekdays = None

# Encerrar as 23:00 UTC = 20:00 horario de Brasilia (BRT = UTC-3)
cfg.stop_hour_utc = 23

# ─── Account ID ───────────────────────────────────────────────────────────────
ACCOUNT_ID = 6692

# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    now = datetime.now(timezone.utc)
    log.info("=" * 58)
    log.info(f"  SODEX BTC SCALPER - {now.strftime('%d/%m/%Y %H:%M UTC')}")
    log.info("=" * 58)
    log.info(f"  Wallet  : {WALLET_ADDRESS}")
    log.info(f"  API Key : {API_KEY}")
    log.info(f"  Conta   : #{ACCOUNT_ID}")
    log.info("-" * 58)

    client = SodexClient(
        api_key=API_KEY,
        private_key=PRIVATE_KEY,
        api_key_name=API_KEY_NAME,
        wallet_address=WALLET_ADDRESS,
        testnet=False,
    )

    # ── Verificar conta ───────────────────────────────────────────────────────
    av = 0.0
    am = 0.0
    try:
        state  = client.perps_account_state()
        av     = float(state.get("av", 0))
        am     = float(state.get("am", 0))
        pos    = state.get("P") or []
        orders = state.get("O") or []

        log.info(f"  Saldo total    : ${av:.4f} vUSDC")
        log.info(f"  Margem livres  : ${am:.4f} vUSDC")
        log.info(f"  Posicoes abertas: {len(pos)}")
        log.info(f"  Ordens abertas  : {len(orders)}")

        if am < cfg.min_margin_usd:
            log.warning(
                f"\n  ATENCAO: Margem disponivel ${am:.4f} muito baixa!\n"
                f"  >> Deposite vUSDC na conta perps via UI da Sodex.\n"
                f"  >> Com $12 depositados a 25x: cada trade vale ~$75 notional\n"
                f"  >> TP $0.50 (~0.62%) | SL $0.10 (~0.12%)\n"
                f"  >> O bot continuara tentando..."
            )
    except Exception as e:
        log.error(f"  Erro ao verificar conta: {e}")

    # ── Projecao de volume ────────────────────────────────────────────────────
    margin_total = am if am > 0 else 12.0
    margin_trade = margin_total * cfg.margin_pct
    notional_est = margin_trade * cfg.leverage
    vol_per_trip = notional_est * 2
    trades_needed = int(cfg.weekly_target_usd / vol_per_trip) if vol_per_trip > 0 else 999
    log.info("-" * 58)
    log.info(f"  PROJECAO COM ${margin_total:.2f} DEPOSITADOS:")
    log.info(f"    Margem por trade : ${margin_total:.2f} x 25% = ${margin_trade:.2f}")
    log.info(f"    Notional (25x)   : ${margin_trade:.2f} x 25 = ${notional_est:.2f}")
    log.info(f"    Volume/round trip: ${vol_per_trip:.2f}")
    log.info(f"    Para $100k vol   : ~{trades_needed} trades")
    log.info(f"    TP: $0.50 (~0.62% mov.) | SL: $0.10 (~0.12% mov.)")
    log.info(f"    R:R 5:1 | Break-even win rate: ~20%")
    log.info(f"    EV @ 40% win     : ~+$0.12/trade")
    log.info(f"    Fee/trade (est.) : ~${notional_est * cfg.maker_fee_pct * 2:.4f}")
    log.info("-" * 58)
    log.info("  AVISO: BTC na Sodex suporta max 25x (nao 40x).")
    log.info("  O bot usa 25x - o maximo disponivel.")
    log.info("=" * 58)

    # ── Configurar leverage (se necessario) ───────────────────────────────────
    try:
        from sodex import MarginMode
        client.perps_update_leverage(
            account_id=ACCOUNT_ID,
            symbol_id=1,
            leverage=25,
            margin_mode=MarginMode.CROSS,
        )
        log.info("  Leverage BTC-USD configurado: 25x CROSS")
    except Exception as e:
        log.warning(f"  Nao foi possivel configurar leverage via API: {e}")
        log.warning("  >> Configure manualmente na UI da Sodex: BTC-USD 25x Cross")

    # ── Iniciar bot ───────────────────────────────────────────────────────────
    bot = ScalpingBot(client=client, account_id=ACCOUNT_ID, config=cfg)
    bot.run()


if __name__ == "__main__":
    main()
