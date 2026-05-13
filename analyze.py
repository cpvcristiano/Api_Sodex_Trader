import re

log_path = 'bot.log'
trades = []
sides = []
seen = set()

with open(log_path, encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

result_re = re.compile(
    r'(\d{2}:\d{2}:\d{2}).*\[RESULT\] (\w+) \| '
    r'entry=\$([0-9,.]+) exit=\$([0-9,.]+) \| '
    r'PnL=([+-][0-9.]+) USD \| '
    r'vol\+=\$([0-9.]+) \| '
    r'dur=(\d+)s'
)

for line in lines:
    if '[ENTRY]' in line and ('BUY' in line or 'SELL' in line):
        s = 'BUY' if 'BUY' in line else 'SELL'
        sides.append(s)
    if '[RESULT]' in line:
        key = line.strip()
        if key in seen:
            continue
        seen.add(key)
        p = result_re.search(line)
        if p:
            side = sides[-1] if sides else '?'
            trades.append({
                'time':   p.group(1),
                'result': p.group(2),
                'side':   side,
                'entry':  float(p.group(3).replace(',', '')),
                'exit':   float(p.group(4).replace(',', '')),
                'pnl':    float(p.group(5)),
                'vol':    float(p.group(6)),
                'dur':    int(p.group(7)),
            })

total = len(trades)
if total == 0:
    print("Nenhum trade encontrado.")
    exit()

tp   = [t for t in trades if t['result'] == 'TP']
sl   = [t for t in trades if t['result'] == 'SL']
be   = [t for t in trades if t['result'] == 'BE']
mn   = [t for t in trades if t['result'] == 'MANUAL']
mn_pos = [t for t in mn if t['pnl'] > 0]
mn_neg = [t for t in mn if t['pnl'] <= 0]

total_pnl = sum(t['pnl'] for t in trades)
total_vol = sum(t['vol'] for t in trades)
avg_dur   = sum(t['dur'] for t in trades) / total

print('=' * 60)
print('  RELATORIO COMPLETO DO BOT')
print('=' * 60)
print(f'  Total de trades    : {total}')
print(f'  TP (take profit)   : {len(tp):3d}  ({len(tp)/total*100:.1f}%)')
print(f'  SL (stop loss)     : {len(sl):3d}  ({len(sl)/total*100:.1f}%)')
print(f'  BE (breakeven)     : {len(be):3d}  ({len(be)/total*100:.1f}%)')
print(f'  MANUAL - positivo  : {len(mn_pos):3d}  ({len(mn_pos)/total*100:.1f}%)')
print(f'  MANUAL - negativo  : {len(mn_neg):3d}  ({len(mn_neg)/total*100:.1f}%)')
print(f'  PnL total          : {total_pnl:+.4f} USD')
print(f'  Volume total       : ${total_vol:,.2f}')
print(f'  Duracao media      : {avg_dur:.0f}s')
print()

# Ultimas 24h estimado pelos ultimos trades com vol semelhante
recent = trades[-200:]
tp24   = [t for t in recent if t['result'] == 'TP']
mn24   = [t for t in recent if t['result'] == 'MANUAL']
mn24p  = [t for t in mn24 if t['pnl'] > 0]
mn24n  = [t for t in mn24 if t['pnl'] <= 0]
pnl24  = sum(t['pnl'] for t in recent)
vol24  = sum(t['vol'] for t in recent)
dur24  = sum(t['dur'] for t in recent) / len(recent)

print('=' * 60)
print('  ULTIMAS 24H (ultimos 200 trades)')
print('=' * 60)
print(f'  Total              : {len(recent)}')
print(f'  TP                 : {len(tp24):3d}  ({len(tp24)/len(recent)*100:.1f}%)')
print(f'  MANUAL positivo    : {len(mn24p):3d}  ({len(mn24p)/len(recent)*100:.1f}%)')
print(f'  MANUAL negativo    : {len(mn24n):3d}  ({len(mn24n)/len(recent)*100:.1f}%)')
print(f'  PnL 24h            : {pnl24:+.4f} USD')
print(f'  Volume 24h         : ${vol24:,.2f}')
print(f'  Duracao media      : {dur24:.0f}s')
print()

print('=' * 60)
print('  TODOS OS TPs - ANALISE DE MOVIMENTO')
print('=' * 60)
for t in tp:
    move = abs(t['exit'] - t['entry'])
    print(f"  {t['time']}  {t['side']:4}  BTC move=${move:.0f}  pnl={t['pnl']:+.3f}  vol=${t['vol']:.0f}")

print()
print('=' * 60)
print('  DISTANCIA TP/SL POR TAMANHO DE CONTA (BTC~$78,400)')
print('=' * 60)
btc  = 78400
mk   = 0.00012
tk   = 0.00050
tp_u = 0.30
sl_u = 0.10

print(f"  {'Conta':>6}  {'Notional':>10}  {'TP move':>9}  {'TP%':>6}  {'SL move':>9}  {'SL%':>6}  {'BE winrate':>10}  {'EV@30%':>8}")
for bal in [1.73, 10, 20, 30]:
    notional = bal * 0.50 * 25
    qty      = notional / btc
    tp_move  = tp_u / qty
    sl_move  = sl_u / qty
    tp_pct   = tp_move / btc * 100
    sl_pct   = sl_move / btc * 100
    fee_tp   = notional * (mk + mk)
    fee_sl   = notional * (mk + tk)
    fee_avg  = 0.30 * fee_tp + 0.70 * fee_sl
    ev30     = 0.30 * tp_u - 0.70 * sl_u - fee_avg
    be_wr    = (sl_u + fee_avg) / (tp_u + sl_u) * 100
    print(f"  ${bal:>5.2f}  ${notional:>9.2f}  ${tp_move:>8.0f}  {tp_pct:>5.2f}%  ${sl_move:>8.0f}  {sl_pct:>5.2f}%  {be_wr:>9.1f}%  {ev30:>+7.4f}")
