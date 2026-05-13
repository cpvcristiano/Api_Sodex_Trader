"""Comparativo de ativos Sodex 20x+ para a estrategia de scalping."""
import sys, io, requests, time, statistics
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def get_klines(symbol, interval="5m", limit=500, fapi=True):
    base = "https://fapi.binance.com/fapi/v1/klines" if fapi else "https://api.binance.com/api/v3/klines"
    try:
        r = requests.get(base, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=8)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def vol_stats(klines):
    ranges = [(float(c[2]) - float(c[3])) / float(c[1]) * 100 for c in klines]
    s = sorted(ranges)
    return {
        "median": statistics.median(ranges),
        "p75": s[int(len(s) * 0.75)],
        "p90": s[int(len(s) * 0.90)],
    }

def wr_sim(klines, tp_pct, sl_pct, window=5):
    """Simula abertura a cada nova oportunidade, janela de ate 5 candles (25min)."""
    wins = losses = 0
    i = 0
    while i < len(klines) - window:
        op = float(klines[i][1])
        tp_p = op * (1 + tp_pct / 100)
        sl_p = op * (1 - sl_pct / 100)
        hit_tp = hit_sl = False
        for c in klines[i : i + window]:
            if float(c[2]) >= tp_p:
                hit_tp = True
                break
            if float(c[3]) <= sl_p:
                hit_sl = True
                break
        if hit_tp:
            wins += 1
            i += window
        elif hit_sl:
            losses += 1
            i += window
        else:
            i += 1
    total = wins + losses
    return (wins / total * 100 if total else 0), wins, losses

# ── Coleta dados
crypto = [("BTC-USD", "BTCUSDT", 25), ("SOL-USD", "SOLUSDT", 20), ("ETH-USD", "ETHUSDT", 20)]
data = {}
print("Buscando dados Binance FAPI...")
for name, sym, lev in crypto:
    kl = get_klines(sym)
    if kl:
        data[name] = {"klines": kl, "lev": lev, "vol": vol_stats(kl), "price": float(kl[-1][4])}
        print(f"  {name}: OK  preco=${data[name]['price']:,.0f}  candles={len(kl)}")
    time.sleep(0.3)

acct = 20.0

# ── Tabela principal
print()
print("=" * 72)
print("COMPARATIVO ATIVOS SODEX 20x+ | 500 candles 5min | Conta $20 | $20")
print("=" * 72)
print()

for name, sym, lev in crypto:
    if name not in data:
        continue
    d = data[name]
    v = d["vol"]
    notional = acct * 0.5 * lev
    vrt = notional * 2

    # TP/SL atual (0.60% / 0.08%)
    wr_cur, w1, l1 = wr_sim(d["klines"], 0.60, 0.08)
    tp_usd = notional * 0.60 / 100
    sl_usd = notional * 0.08 / 100
    fee = notional * 0.00012 * 2
    be_wr = (sl_usd + fee) / (tp_usd + sl_usd) * 100
    ev_cur = (wr_cur / 100) * tp_usd - (1 - wr_cur / 100) * sl_usd - fee

    # TP/SL adaptado a volatilidade (1.5x / 0.5x mediana)
    tp_a = round(v["median"] * 1.5, 3)
    sl_a = round(v["median"] * 0.5, 3)
    wr_a, w2, l2 = wr_sim(d["klines"], tp_a, sl_a)
    tp_usd_a = notional * tp_a / 100
    sl_usd_a = notional * sl_a / 100
    ev_a = (wr_a / 100) * tp_usd_a - (1 - wr_a / 100) * sl_usd_a - fee
    be_a = (sl_usd_a + fee) / (tp_usd_a + sl_usd_a) * 100

    mov_tp = 0.60 / 100 * d["price"]
    mov_sl = 0.08 / 100 * d["price"]

    print(f"  [{name} | {lev}x | ${d['price']:,.0f}]")
    print(f"    Vol 5m: median={v['median']:.3f}%  p75={v['p75']:.3f}%  p90={v['p90']:.3f}%")
    print(f"    TP=0.60% move ${mov_tp:.0f}  |  SL=0.08% move ${mov_sl:.1f}")
    print(f"    WR(atual 0.60/0.08): {wr_cur:.1f}%  | BE={be_wr:.1f}%  | EV={ev_cur:+.3f}/trade")
    print(f"    WR(adaptado {tp_a:.3f}/{sl_a:.3f}): {wr_a:.1f}%  | BE={be_a:.1f}%  | EV={ev_a:+.3f}/trade")
    print(f"    Notional: ${notional:.0f}  | Vol/RT: ${vrt:.0f}  | Trades p/100k: {int(100000/vrt)}")
    print()

# ── Commodities (estimativas)
print("=" * 72)
print("COMMODITIES E INDICES (sem dados Binance FAPI -- estimativas)")
print("=" * 72)
print()
commodities = [
    ("XAUT-USD",      25, 0.15, 0.05, 20, "Ouro - vol baixa, spread alto"),
    ("USTECH100-USD", 25, 0.20, 0.07, 17, "Nasdaq - apenas 17h/dia"),
    ("US500-USD",     20, 0.18, 0.06, 17, "SP500 - apenas 17h/dia"),
    ("CL-USD",        20, 0.30, 0.10, 22, "Petroleo - vol alta, spike noticias"),
    ("COPPER-USD",    20, 0.15, 0.05, 20, "Cobre - vol baixa"),
    ("SILVER-USD",    20, 0.25, 0.08, 20, "Prata - vol media, segue ouro"),
]
print(f"  {'Ativo':<18} {'Lev':>4} {'Vol est':>8} {'Horas':>6} {'Vol/RT':>8}  Obs")
print("  " + "-" * 68)
for name, lev, vol_e, sl_e, hrs, obs in commodities:
    notional = acct * 0.5 * lev
    vrt = notional * 2
    print(f"  {name:<18} {lev:>4}x  {vol_e:.2f}%    {hrs:>3}h  ${vrt:>7.0f}  {obs}")

# ── Resumo
print()
print("=" * 72)
print("RANKING FINAL")
print("=" * 72)
print("""
  AIRDROP FARMING (meta $100k volume):
  1. BTC-USD (25x)  -- $500/RT = 200 trades p/ meta -- MELHOR VOLUME/TRADE
  2. USTECH100 (25x) -- $500/RT mas apenas 17h/dia e horario bolsa
  3. ETH/SOL (20x)  -- $400/RT = 250 trades p/ meta

  ESTRATEGIA LUCRATIVA ($1000 no futuro):
  - SOL-USD e o mais viavel: vol 3x maior que BTC em 5min
  - Com TP/SL adaptado: WR teoricamente superior ao BTC
  - ETH similar ao BTC, vol um pouco melhor
  - BTC: perfeito para volume/airdrop, dificil de ser lucravel em 5min

  DESCARTADOS para automacao:
  - Indices (USTECH100, US500): 17h/dia, sem sinal EMA na Binance FAPI
  - Commodities (CL, COPPER, SILVER, XAUT): spreads altos Sodex,
    liquidez menor, sinal inconsistente

  CONCLUSAO:
  Manter BTC para farming (maior volume/trade)
  Testar SOL secundariamente para validar rentabilidade real
""")
