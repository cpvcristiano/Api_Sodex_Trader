import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def cenario(caixa, leverage=25, margin_pct=0.50, wr=0.014):
    tp_usd = round(max(0.30, min(200.0, caixa * 0.075)), 2)
    sl_usd = round(max(0.05, min(30.0,  caixa * 0.010)), 2)
    margin = caixa * margin_pct
    notional = margin * leverage
    vol_rt = notional * 2
    trades_100k = int(100_000 / vol_rt)
    fee = notional * 0.00012 * 2
    be_wr = (sl_usd + fee) / (tp_usd + sl_usd) * 100
    ev = wr * tp_usd - (1 - wr) * sl_usd - fee
    pnl_total = ev * trades_100k
    dias = trades_100k / ((20 * 60) / 20)  # 20 horas/dia, 1 trade/20min
    daily_limit = round(caixa * 0.06, 2)
    return {
        "caixa": caixa, "tp": tp_usd, "sl": sl_usd, "margin": margin,
        "notional": notional, "vol_rt": vol_rt, "trades_100k": trades_100k,
        "fee": fee, "be_wr": be_wr, "ev": ev, "pnl_total": pnl_total,
        "dias": dias, "daily_limit": daily_limit,
    }

# Tabela comparativa
caixas = [12, 20, 50, 100, 200]
print("=" * 72)
print("COMPARATIVO POR TAMANHO DE CONTA | BTC-USD 25x | WR 1.4%")
print("=" * 72)
print()
print(f"  {'Conta':>7} {'TP':>6} {'SL':>5} {'Notional':>10} {'Vol/RT':>8} {'p/100k':>7} {'Dias':>6} {'EV/trade':>10}")
print("  " + "-" * 66)
for c in caixas:
    s = cenario(c)
    mark = " <-- ATUAL" if c == 20 else (" <-- $50 DEP" if c == 50 else "")
    print(f"  ${c:>6}  ${s['tp']:>5.2f} ${s['sl']:>4.2f} ${s['notional']:>9.0f} ${s['vol_rt']:>7.0f} {s['trades_100k']:>7} {s['dias']:>6.1f} {s['ev']:>+10.3f}{mark}")

# Cenario detalhado $50
print()
print("=" * 72)
print("CENARIO DETALHADO: DEPOSITO DE $50")
print("=" * 72)
s = cenario(50)
print()
print(f"  Parametros dinamicos:")
print(f"    TP : ${s['tp']:.2f}  ($50 x 7.5%)")
print(f"    SL : ${s['sl']:.2f}  ($50 x 1.0%)")
print(f"    R:R: {s['tp']/s['sl']:.1f}:1  |  Break-even WR: {s['be_wr']:.1f}%")
print()
print(f"  Por trade (BTC-USD 25x):")
print(f"    Margem usada      : ${s['margin']:.0f}")
print(f"    Notional          : ${s['notional']:.0f}")
print(f"    Volume round trip : ${s['vol_rt']:.0f}")
print(f"    Fee por trade     : ${s['fee']:.4f}")
print()
print(f"  Para $100k de volume:")
print(f"    Trades necessarios: {s['trades_100k']}")
print(f"    Tempo estimado    : {s['dias']:.1f} dias  (1 trade/20min, 20h/dia)")
print(f"    Limite perda/dia  : ${s['daily_limit']:.2f}  (6% do caixa)")
print()

# Simulacao PnL por WR
print("  SIMULACAO PNL — 80 TRADES:")
print(f"  {'WR':>6} {'Wins':>6} {'SLs':>5} {'PnL bruto':>12} {'Fees':>8} {'PnL liq':>10} {'Caixa final':>12}")
print("  " + "-" * 62)
fee_total = 80 * s["fee"]
for wr_pct in [0.5, 1.4, 5.0, 10.0, 15.3, 20.0, 30.0]:
    wins = wr_pct / 100 * 80
    losses = 80 - wins
    pnl_bruto = wins * s["tp"] - losses * s["sl"]
    pnl_liq = pnl_bruto - fee_total
    caixa_final = 50 + pnl_liq
    tag = ""
    if abs(wr_pct - 1.4) < 0.2:   tag = "  <- WR atual BTC"
    if abs(wr_pct - 4.5) < 0.2:   tag = "  <- WR atual SOL"
    if abs(wr_pct - 15.3) < 0.5:  tag = "  <- break-even"
    print(f"  {wr_pct:>5.1f}%  {wins:>5.1f}  {losses:>5.1f}  {pnl_bruto:>+11.2f}  ${fee_total:>6.2f}  {pnl_liq:>+9.2f}  ${caixa_final:>9.2f}{tag}")

print()
print("=" * 72)
print("VANTAGENS E RISCOS")
print("=" * 72)
print("""
  VANTAGENS:
  + Volume por trade: $1,250  (atual $300 com $20)  -- 4x mais rapido
  + Meta em 80 trades vs ~333 trades atuais
  + Bot completa em 1.5 dias em vez de 7 dias
  + Menos tempo exposto ao mercado
  + TP de $3.75 por win (nao $0.75) -- mais impacto quando acerta

  RISCOS:
  - SL de $0.50 por trade (era $0.10 com $12)
  - WR 1.4% = 79 SLs + 1 TP = PnL esperado -$47 nos 80 trades
  - Pode zerar a conta antes de completar o farming

  CONCLUSAO:
  Depositar $50 so faz sentido se:
  1. O airdrop SOSO vale mais que ~$40 de perda esperada
  2. Voce aceita o risco de perder $50 durante o farming
  3. Estrategia futura ($1000) ja esta definida e testada

  Com $50, a meta pode ser atingida em 1.5 dias.
  Com $20, pode levar 7+ dias.
  O custo dessa aceleracao e um risco maior de perda total.
""")
