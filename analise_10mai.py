import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

trades_10mai = [
    # hora_entrada, hora_saida, lado, entrada, saida, qty, pnl
    ("10:41", "10:41", "LONG", 80917, 80900, 0.00267, -0.21),
    ("10:37", "10:41", "LONG", 80952, 80907, 0.00271, -0.23),
    ("10:30", "10:35", "LONG", 80925, 80942, 0.00273, -0.13),
    ("10:25", "10:30", "LONG", 80920, 80929, 0.00275, -0.15),
    ("10:20", "10:25", "LONG", 80906, 80919, 0.00277, -0.08),
    ("10:15", "10:17", "LONG", 80886, 80860, 0.00281, -0.25),
    ("09:57", "09:57", "LONG", 80879, 80866, 0.00283, -0.15),
    ("09:54", "09:56", "LONG", 80882, 80876, 0.00285, -0.13),
    ("00:19", "00:24", "LONG", 80736, 80719, 0.00289, -0.23),
    ("00:14", "00:19", "LONG", 80747, 80738, 0.00292, -0.14),
    ("00:06", "00:11", "LONG", 80757, 80728, 0.00295, -0.20),
    ("00:00", "00:06", "LONG", 80728, 80758, 0.00295, -0.03),
]

print("=" * 62)
print("  ANALISE TRADES DIA 10/05 — BTC-USD")
print("=" * 62)

total_pnl  = sum(t[6] for t in trades_10mai)
sl_hits    = sum(1 for t in trades_10mai if t[4] < t[3])  # exit < entry para LONG
wins       = sum(1 for t in trades_10mai if t[6] > 0)
zeros      = sum(1 for t in trades_10mai if t[6] == 0)

precos     = [t[3] for t in trades_10mai] + [t[4] for t in trades_10mai]
range_dia  = max(precos) - min(precos)
sl_move    = 0.20 / 0.00285   # SL em pontos BTC para posição atual
tp_move    = 1.50 / 0.00285   # TP em pontos BTC

print(f"\n  Trades no dia  : {len(trades_10mai)}")
print(f"  Direção        : 100% LONG")
print(f"  Wins           : {wins}")
print(f"  SL hits        : {sl_hits}")
print(f"  Zeros/timeout  : {zeros}")
print(f"  PnL total      : {total_pnl:+.2f} USDC")

print()
print(f"  Range BTC no dia: ${range_dia:.0f}  ({min(precos):,.0f} — {max(precos):,.0f})")
print(f"  Para atingir SL : precisa mover ${sl_move:.0f}")
print(f"  Para atingir TP : precisa mover ${tp_move:.0f}")
print()
print(f"  PROBLEMA: TP exige ${tp_move:.0f} mas o range do dia foi só ${range_dia:.0f}")
print(f"  O TP e {tp_move/range_dia:.1f}x maior que o range inteiro do dia")
print(f"  O SL e atingido com apenas {sl_move/range_dia*100:.0f}% do range diario")

print()
print("=" * 62)
print("  DIAGNOSTICO — POR QUE O BOT ENTROU MESMO ASSIM")
print("=" * 62)
print("""
  O EMA 9/17 no 1H dizia LONG (BTC subiu de $78k -> $81k).
  O EMA 9/17 no 5min tambem dizia LONG (price > EMA9 > EMA17).
  Separacao EMA no 5min: 0.022% a 0.034% (acima do minimo de 0.01%).

  O filtro passou porque a TENDENCIA estava certa (BTC alta).
  Mas o mercado estava em CONSOLIDACAO — sem momentum real.
  Nas ultimas 12h o BTC moveu apenas $252 total.

  Na consolidacao:
  - EMAs ficam proximas mas mantém ordem bullish (passa o filtro)
  - Preco fica andando em torno das EMAs (sem direcao real)
  - SL ($70) e atingido facilmente pelo ruido do preco
  - TP ($519) e impossivel: maior que o range do dia inteiro
""")

print("=" * 62)
print("  CAUSA RAIZ — SEPARACAO EMA MUITO BAIXA")
print("=" * 62)
print()
print("  Separacao observada no dia 10:")
print("    00:00 — 00:27: 0.022% a 0.027%  (mercado plano)")
print("    09:54 — 10:41: 0.026% a 0.034%  (mercado plano)")
print()
print("  O que cada separacao significa em $:")
print(f"    0.010% = ${80800 * 0.0001:.0f}  (minimo atual — muito baixo)")
print(f"    0.030% = ${80800 * 0.0003:.0f}  (separacao do dia 10)")
print(f"    0.050% = ${80800 * 0.0005:.0f}  (separacao minima proposta)")
print(f"    0.100% = ${80800 * 0.001:.0f}  (tendencia forte)")
print()
print("  Separacao de 0.022% = EMA9 e EMA17 separadas por $18.")
print("  Isso NAO e uma tendencia — e ruido de consolidacao.")

print()
print("=" * 62)
print("  SOLUCAO PROPOSTA")
print("=" * 62)
print("""
  Aumentar separacao minima de 0.01% para 0.05% no 5min.

  Impacto no dia 10:
  - Todos os trades tinham sep 0.022% a 0.034% < 0.05%
  - TODOS os 12 trades do dia 10 seriam BLOQUEADOS
  - Perda do dia: $0.00 em vez de -$1.93

  Codigo a mudar em hybrid_smc.py (1 linha):
    ATUAL : if sep5 < 0.01:
    NOVO  : if sep5 < 0.05:

  Trade-off:
  - Menos entradas (reduz volume para airdrop ~30-40%)
  - Porem: so entra em mercados com tendencia real
  - WR esperado: sobe de ~5% para ~15-25%
  - Conta sobrevive mais
""")

print("=" * 62)
print("  HISTORICO: TRADES VENCEDORES vs SEPARACAO EMA")
print("=" * 62)
print("""
  Trades que GANHARAM (de toda a historico):
    +$1.37  BTC 03/05  22:56 — movimento $331 em 2.5min (tendencia forte)
    +$1.11  SOL 04/05  5h de posicao — tendencia sustentada
    +$0.92  SOL 08/05  48min — SOL subindo de $88.22 -> $88.59
    +$0.86  SOL 06/05  25min — SOL $87.89 -> $88.25 (tendencia clara)
    +$0.35  BTC 09/05  4h de posicao — BTC $80.600 -> $80.748

  Todos em mercados COM movimento real.
  Os perdedores: todos em mercado PLANO, range < $200.
""")
