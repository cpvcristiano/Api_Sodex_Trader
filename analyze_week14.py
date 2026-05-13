import re
from datetime import datetime
from collections import defaultdict

with open("bot.log", encoding="utf-8") as f:
    lines = f.readlines()

current_date = None
dated_results = []

for line in lines:
    m = re.search(r"SODEX SOL SCALPER - (\d{2}/\d{2}/\d{4}) \d{2}:\d{2} UTC", line)
    if m:
        current_date = m.group(1)
    if "[RESULT]" in line and current_date:
        time_m = re.match(r"(\d{2}:\d{2}:\d{2})", line)
        if time_m:
            try:
                dt = datetime.strptime(current_date + " " + time_m.group(1), "%d/%m/%Y %H:%M:%S")
                dated_results.append((dt, line.strip()))
            except:
                pass

start = datetime(2026, 5, 1, 21, 0, 0)
end   = datetime(2026, 5, 8, 21, 0, 0)
period = [(dt, l) for dt, l in dated_results if start <= dt <= end]

tp = sl = manual = 0
pnl_total = 0.0
vol_total = 0.0
por_dia = defaultdict(lambda: dict(trades=0, wins=0, sl=0, manual=0, pnl=0.0, vol=0.0, pnl_list=[]))

durations = []

for dt, line in period:
    dia = dt.strftime("%d/%m")

    pnl_m = re.search(r"PnL=([+\-]?[\d.]+)", line)
    vol_m  = re.search(r"vol\+=\$?([\d.]+)", line)
    dur_m  = re.search(r"dur=(\d+)s", line)

    pnl = float(pnl_m.group(1)) if pnl_m else 0.0
    vol = float(vol_m.group(1)) if vol_m else 0.0
    dur = int(dur_m.group(1)) if dur_m else 0

    pnl_total += pnl
    vol_total += vol
    if dur: durations.append(dur)

    por_dia[dia]["trades"] += 1
    por_dia[dia]["pnl"]    += pnl
    por_dia[dia]["vol"]    += vol
    por_dia[dia]["pnl_list"].append(pnl)

    if "RESULT] TP" in line or "TRAIL" in line:
        tp += 1
        por_dia[dia]["wins"] += 1
    elif "RESULT] SL" in line:
        sl += 1
        por_dia[dia]["sl"] += 1
    else:
        manual += 1
        por_dia[dia]["manual"] += 1

total = len(period)
avg_dur = sum(durations) / len(durations) if durations else 0
wins = tp

print("=" * 60)
print("  RELATORIO SEMANA 14 — 01/05 21h ate 08/05 21h")
print("=" * 60)
print(f"  Total de trades   : {total}")
print(f"  TP / Trailing wins: {tp}")
print(f"  SL acionados      : {sl}")
print(f"  Manual (timeout)  : {manual}")
print(f"  Win rate          : {wins/total*100:.1f}%" if total else "  Win rate: N/A")
print(f"  PnL total         : {pnl_total:+.4f} USD")
print(f"  Volume gerado     : ${vol_total:,.2f}")
print(f"  Duracao media     : {avg_dur:.0f}s ({avg_dur/60:.1f} min)")
print()

print("  POR DIA:")
print(f"  {'Data':<8} {'Trades':>6} {'Wins':>5} {'SL':>4} {'Manual':>7} {'PnL':>9} {'Volume':>10} {'WR':>6}")
print("  " + "-" * 58)
for dia in sorted(por_dia):
    d = por_dia[dia]
    wr = d["wins"] / d["trades"] * 100 if d["trades"] else 0
    print(f"  {dia:<8} {d['trades']:>6} {d['wins']:>5} {d['sl']:>4} {d['manual']:>7} {d['pnl']:>+9.2f} ${d['vol']:>9,.0f} {wr:>5.0f}%")

print()
# Best/worst day
best = max(por_dia.items(), key=lambda x: x[1]["pnl"])
worst = min(por_dia.items(), key=lambda x: x[1]["pnl"])
print(f"  Melhor dia  : {best[0]} ({best[1]['pnl']:+.2f} USD)")
print(f"  Pior dia    : {worst[0]} ({worst[1]['pnl']:+.2f} USD)")

# Simulacao de estrategias alternativas
print()
print("=" * 60)
print("  SIMULACAO DE ESTRATEGIAS ALTERNATIVAS")
print("  (baseado nos mesmos {total} trades)")
print("=" * 60)

# Config atual
tp_atual = 1.00
sl_atual = 0.30
# Estima notional medio a partir do volume
notional_medio = vol_total / (total * 2) if total else 150

configs = [
    ("Atual (TP=$1.00 SL=$0.30)",       1.00, 0.30),
    ("Agressiva (TP=$0.50 SL=$0.15)",   0.50, 0.15),
    ("Conservadora (TP=$2.00 SL=$0.30)",2.00, 0.30),
    ("Scalp puro (TP=$0.30 SL=$0.10)",  0.30, 0.10),
    ("Alto RR (TP=$1.50 SL=$0.20)",     1.50, 0.20),
]

# Usa win rate real como base para simular
wr_real = wins / total if total else 0.15
maker = 0.00012
taker = 0.00050

print(f"  WR real observado: {wr_real*100:.1f}% | Notional medio: ${notional_medio:.0f}")
print()
print(f"  {'Estrategia':<35} {'PnL sim':>9} {'BE WR':>7} {'Viavel?':>8}")
print("  " + "-" * 62)

for nome, tp_s, sl_s in configs:
    fee_tp  = notional_medio * maker * 2
    fee_sl  = notional_medio * (maker + taker)
    fee_avg = fee_tp * wr_real + fee_sl * (1 - wr_real)
    ev      = wr_real * tp_s - (1 - wr_real) * sl_s - fee_avg
    pnl_sim = ev * total
    be_wr   = (sl_s + fee_avg) / (tp_s + sl_s) * 100
    viavel  = "SIM" if ev > 0 else "NAO"
    print(f"  {nome:<35} {pnl_sim:>+9.2f} {be_wr:>6.1f}% {viavel:>8}")

print()
print("=" * 60)
print("  PARES COM 20x-25x NA SODEX (estimativa)")
print("=" * 60)

pares = [
    ("SOL-USD",  "atual", 20, 88.0,  notional_medio, vol_total),
    ("BTC-USD",  "25x",   25, 95000, 0, 0),
    ("ETH-USD",  "25x",   25, 1800,  0, 0),
    ("DOGE-USD", "20x",   20, 0.17,  0, 0),
    ("AVAX-USD", "20x",   20, 22.0,  0, 0),
]

margem_ref = 14.0  # margem disponivel estimada

print(f"  (Ref: ${margem_ref:.0f} de margem, 50% por trade)")
print()
print(f"  {'Par':<12} {'Lev':>4} {'Preco':>9} {'Notional':>10} {'Vol/RT':>9} {'Trades p/100k':>14}")
print("  " + "-" * 62)
for par, obs, lev, preco, _n, _v in pares:
    not_par = margem_ref * 0.50 * lev
    vol_rt  = not_par * 2
    trades_100k = int(100000 / vol_rt) if vol_rt else 999
    marker = " <--" if par == "SOL-USD" else ""
    print(f"  {par:<12} {lev:>4}x {preco:>9.2f} {not_par:>10.2f} {vol_rt:>9.2f} {trades_100k:>14}{marker}")
