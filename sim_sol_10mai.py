import sys, io, requests, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Busca candles SOL 1min da Binance para 10/05/2026 ─────────────────────────
def get_klines(symbol, interval, start_ms, end_ms):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval,
              "startTime": start_ms, "endTime": end_ms, "limit": 1000}
    r = requests.get(url, params=params, timeout=10)
    return r.json()

from datetime import datetime, timezone, timedelta

def ts(hour, minute, day=10, month=5, year=2026):
    dt = datetime(year, month, day, hour, minute, 0, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

# Busca dados do dia 10/05 (00:00 - 11:00 UTC)
print("Buscando precos SOL 1min do dia 10/05/2026...")
start = ts(0, 0)
end   = ts(11, 0)
candles = get_klines("SOLUSDT", "1m", start, end)
print(f"  {len(candles)} candles recebidos")

# Indexa por minuto
price_map = {}
for c in candles:
    t = datetime.fromtimestamp(c[0]/1000, tz=timezone.utc)
    price_map[(t.hour, t.minute)] = {
        "open": float(c[1]), "high": float(c[2]),
        "low":  float(c[3]), "close": float(c[4]),
    }

# ── Parametros SOL (20x) ────────────────────────────────────────────────────
LEVERAGE    = 20
MARGIN_PCT  = 0.50
CAIXA       = 18.5    # saldo estimado dia 10
TP_USD      = 1.50
SL_USD      = 0.20
TIMEOUT_MIN = 5       # position_timeout = 300s = 5 min

margin   = CAIXA * MARGIN_PCT
notional = margin * LEVERAGE  # ~$185

# ── Horarios das entradas do bot (copiados do historico BTC) ──────────────────
entradas = [
    (0,  0),  # 00:00
    (0,  6),  # 00:06
    (0, 14),  # 00:14
    (0, 19),  # 00:19
    (9, 54),  # 09:54
    (9, 57),  # 09:57
    (10,15),  # 10:15
    (10,20),  # 10:20
    (10,25),  # 10:25
    (10,30),  # 10:30
    (10,37),  # 10:37
    (10,41),  # 10:41
]

print()
print("=" * 68)
print("  SIMULACAO: MESMOS TRADES — SOL-USD 20x — DIA 10/05")
print("=" * 68)
print(f"  Caixa: ${CAIXA} | Notional: ${notional:.0f} | TP: ${TP_USD} | SL: ${SL_USD}")
print()
print(f"  {'Hora':>6}  {'Entry':>8}  {'Exit':>8}  {'Qty':>6}  {'Resultado':>10}  {'PnL':>8}")
print("  " + "-" * 60)

total_pnl = 0
resultados = []

for (h, m) in entradas:
    # Pega preco de entrada (open do minuto)
    c0 = price_map.get((h, m))
    if not c0:
        print(f"  {h:02d}:{m:02d}  sem dados")
        continue

    entry_px = c0["open"]
    qty      = notional / entry_px
    tp_move  = TP_USD / qty
    sl_move  = SL_USD / qty

    tp_px    = entry_px + tp_move   # LONG
    sl_px    = entry_px - sl_move

    # Simula os proximos 5 candles (5 minutos)
    resultado = "TIMEOUT"
    exit_px   = entry_px
    pnl       = 0.0

    for i in range(TIMEOUT_MIN):
        cm = m + i
        ch = h + cm // 60
        cm = cm % 60
        c = price_map.get((ch, cm))
        if not c:
            break
        # Verifica TP e SL na ordem: TP primeiro se ambos no mesmo candle
        hit_tp = c["high"] >= tp_px
        hit_sl = c["low"]  <= sl_px
        if hit_tp and hit_sl:
            # Ambos no mesmo candle — assume TP (otimista) ou SL (pessimista)
            # Usamos SL (mais conservador)
            resultado = "SL"
            exit_px   = sl_px
            pnl       = -SL_USD
            break
        elif hit_tp:
            resultado = "TP"
            exit_px   = tp_px
            pnl       = TP_USD
            break
        elif hit_sl:
            resultado = "SL"
            exit_px   = sl_px
            pnl       = -SL_USD
            break

    if resultado == "TIMEOUT":
        # Fecha pelo preco de fechamento do ultimo candle
        cm_last = m + TIMEOUT_MIN - 1
        ch_last = h + cm_last // 60
        cm_last = cm_last % 60
        c_last  = price_map.get((ch_last, cm_last))
        if c_last:
            exit_px = c_last["close"]
            pnl     = (exit_px - entry_px) * qty

    total_pnl += pnl
    resultados.append(resultado)
    mark = " <-- TP!" if resultado == "TP" else (" <-- SL" if resultado == "SL" else "")
    print(f"  {h:02d}:{m:02d}  {entry_px:>8.2f}  {exit_px:>8.2f}  {qty:>6.3f}  {resultado:>10}  {pnl:>+7.2f}{mark}")

# ── Resumo ────────────────────────────────────────────────────────────────────
wins     = resultados.count("TP")
sls      = resultados.count("SL")
timeouts = resultados.count("TIMEOUT")

print()
print("=" * 68)
print("  RESUMO")
print("=" * 68)
print(f"  TPs     : {wins}")
print(f"  SLs     : {sls}")
print(f"  Timeout : {timeouts}")
print(f"  PnL total: {total_pnl:+.2f} USDC")
print()

# Comparativo
btc_pnl = -1.93
print(f"  BTC-USD mesmo periodo: {btc_pnl:+.2f} USDC")
print(f"  SOL-USD simulado     : {total_pnl:+.2f} USDC")
print(f"  Diferenca            : {total_pnl - btc_pnl:+.2f} USDC")

print()
# Range SOL no periodo
sol_prices = [price_map.get((h,m),{}) for h,m in entradas if price_map.get((h,m))]
if sol_prices:
    all_prices = [c["open"] for c in sol_prices] + [c["close"] for c in sol_prices]
    print(f"  Range SOL no periodo: ${min(all_prices):.2f} — ${max(all_prices):.2f}")
    rng = max(all_prices) - min(all_prices)
    tp_pts = TP_USD / (notional / (sum(all_prices)/len(all_prices)))
    print(f"  Range total: ${rng:.2f}")
    print(f"  TP precisava de: ${tp_pts:.2f} de movimento")
    print(f"  Razao range/TP: {rng/tp_pts:.1f}x")
