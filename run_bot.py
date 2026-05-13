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
from strategy import ScalpConfig, TraderEngine, HybridSMCStrategy

# ─── Logging ──────────────────────────────────────────────────────────────────
import os
project_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(project_dir, "bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger("run_bot")

# ─── Configuracao ─────────────────────────────────────────────────────────────
cfg = ScalpConfig()

# Par e alavancagem
cfg.symbol_name = "SOL-USD"
cfg.symbol_id   = 6
cfg.leverage    = 20

# Precisao SOL na Sodex
cfg.price_precision = 2
cfg.qty_precision   = 3
cfg.tick_size       = 0.01
cfg.step_size       = 0.001

# Sizing: 50% da margem disponivel por trade
cfg.margin_pct  = 0.50

# BTC-USD 25x | TP=$1.50 R:R 7.5:1 | Break-even WR ~11.8%
cfg.tp_usd = 1.50            # lucro alvo por trade
cfg.sl_usd = 0.20            # stop loss por trade

# Analise de entrada: ~30s simulando ritmo de grafico 1-minuto
# 6 amostras a cada 6s cobrem o range de uma vela de 1min
cfg.analysis_secs    = 15
cfg.analysis_samples = 4

# Timeouts
cfg.entry_timeout_s    = 20.0
cfg.position_timeout_s = 300.0  # 5 min — fecha rapido para aumentar frequencia de trades
cfg.poll_s             = 2.0

# Protecoes
# Com SL de $0.20, 10 losses consecutivos = $2.00 de perda diaria
cfg.min_margin_usd     = 1.0   # minimo para operar
cfg.max_daily_loss_usd = 3.0   # para o dia se perder mais que $3 (15 SL seguidos)

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
    log.info(f"  SODEX SOL SCALPER - {now.strftime('%d/%m/%Y %H:%M UTC')}")
    log.info("=" * 58)
    log.info(f"  Wallet  : {WALLET_ADDRESS}")
    log.info(f"  API Key : {API_KEY}")
    log.info(f"  Conta   : #{ACCOUNT_ID}")
    log.info(f"  Ativo   : SOL-USD (ID: 6)")
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

    # ── TP/SL fixos + limites dinamicos por caixa ────────────────────────────
    caixa = av if av > 0 else 12.0  # usa saldo total (inclui posicoes abertas)

    # TP e SL FIXOS em dolar — mais TPs alcancaveis, melhor WR
    # Simulacao mostrou: com $50 conta WR=16.9% (vs 0% do dinamico)
    # Break-even: 20.6% WR — filtro 1H deve empurrar acima disso
    cfg.tp_usd = 1.50
    cfg.sl_usd = 0.20

    # Limites DINAMICOS (escalam com caixa para proteger proporcionalmente)
    # 15% do caixa = ~15 SLs antes de parar o dia
    # 5% do caixa  = margem minima para continuar operando
    cfg.max_daily_loss_usd = round(max(1.0, caixa * 0.15), 2)
    cfg.min_margin_usd     = round(max(0.50, caixa * 0.05), 2)

    # Nivel de risco por faixa de caixa
    if caixa < 5:
        nivel = "CRITICO"
    elif caixa < 10:
        nivel = "BAIXO"
    elif caixa < 30:
        nivel = "NORMAL"
    elif caixa < 200:
        nivel = "CONFORTAVEL"
    else:
        nivel = "ROBUSTO"

    # Calcula movimento SOL necessario para TP e SL
    notional_atual = caixa * cfg.margin_pct * cfg.leverage
    qty_atual      = notional_atual / 95  # estimativa SOL ~$95
    mov_tp_sol     = cfg.tp_usd / qty_atual if qty_atual > 0 else 0
    mov_sl_sol     = cfg.sl_usd / qty_atual if qty_atual > 0 else 0
    tp_pct         = cfg.tp_usd / notional_atual * 100 if notional_atual > 0 else 0
    sl_pct         = cfg.sl_usd / notional_atual * 100 if notional_atual > 0 else 0
    max_sls_conta  = int(caixa / (cfg.sl_usd + notional_atual * 0.00024))

    log.info("-" * 58)
    log.info(f"  PARAMETROS (caixa=${caixa:.2f} — nivel {nivel}):")
    log.info(f"    TP fixo          : ${cfg.tp_usd:.2f}  ({tp_pct:.2f}% notional | SOL move ${mov_tp_sol:.2f})")
    log.info(f"    SL fixo          : ${cfg.sl_usd:.2f}  ({sl_pct:.2f}% notional | SOL move ${mov_sl_sol:.2f})")
    log.info(f"    R:R              : {cfg.tp_usd/cfg.sl_usd:.1f}:1  | Break-even WR: {cfg.sl_usd/(cfg.tp_usd+cfg.sl_usd)*100:.1f}%")
    log.info(f"    Limite diario    : ${cfg.max_daily_loss_usd:.2f}  (caixa x 15% = ~{cfg.max_daily_loss_usd/cfg.sl_usd:.0f} SLs/dia)")
    log.info(f"    Margem minima    : ${cfg.min_margin_usd:.2f}  (caixa x 5%)")
    log.info(f"    SLs p/ zerar     : {max_sls_conta}  | Modo: TP/SL FIXO")

    # ── Projecao de volume ────────────────────────────────────────────────────
    margin_total = caixa * cfg.margin_pct
    notional_est = margin_total * cfg.leverage
    vol_per_trip = notional_est * 2
    trades_needed = int(cfg.weekly_target_usd / vol_per_trip) if vol_per_trip > 0 else 999
    log.info("-" * 58)
    log.info(f"  PROJECAO COM ${caixa:.2f} DE CAIXA:")
    log.info(f"    Margem por trade : ${caixa:.2f} x 50% = ${margin_total:.2f}")
    log.info(f"    Notional (20x)   : ${margin_total:.2f} x 20 = ${notional_est:.2f}")
    log.info(f"    Volume/round trip: ${vol_per_trip:.2f}")
    log.info(f"    Para $100k vol   : ~{trades_needed} trades")
    fee_tp     = notional_est * cfg.maker_fee_pct * 2
    fee_sl     = notional_est * (cfg.maker_fee_pct + cfg.taker_fee_pct)
    fee_avg    = fee_tp * 0.30 + fee_sl * 0.70
    be_winrate = (cfg.sl_usd + fee_avg) / (cfg.tp_usd + cfg.sl_usd) * 100
    ev_30      = 0.30 * cfg.tp_usd - 0.70 * cfg.sl_usd - fee_avg
    log.info(f"    TP: ${cfg.tp_usd:.2f} | SL: ${cfg.sl_usd:.2f} | R:R {cfg.tp_usd/cfg.sl_usd:.1f}:1")
    log.info(f"    Break-even win rate   : ~{be_winrate:.1f}%")
    log.info(f"    EV @ 30% win          : ~{ev_30:+.4f}/trade")
    log.info("-" * 58)
    log.info("  SOL na Sodex configurado para 20x.")
    log.info("=" * 58)

    # ── Configurar leverage (se necessario) ───────────────────────────────────
    try:
        from sodex import MarginMode
        client.perps_update_leverage(
            account_id=ACCOUNT_ID,
            symbol_id=6,
            leverage=20,
            margin_mode=MarginMode.CROSS,
        )
        log.info("  Leverage SOL-USD configurado: 20x CROSS")
    except Exception as e:
        log.warning(f"  Nao foi possivel configurar leverage via API: {e}")
        log.warning("  >> Configure manualmente na UI da Sodex: SOL-USD 20x Cross")

    # ── Iniciar bot ───────────────────────────────────────────────────────────
    strategy = HybridSMCStrategy(client=client, config=cfg)
    bot = TraderEngine(client=client, account_id=ACCOUNT_ID, strategy=strategy, config=cfg)
    bot.run()


if __name__ == "__main__":
    main()
