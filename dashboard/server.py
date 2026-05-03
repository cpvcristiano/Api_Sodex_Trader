"""
Dashboard backend — FastAPI + WebSocket
Serve: python run_dashboard.py
"""
import asyncio
import json
import re
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from config import API_KEY, API_KEY_NAME, PRIVATE_KEY, WALLET_ADDRESS
from sodex import SodexClient

app = FastAPI()

BOT_LOG    = Path(__file__).parent.parent / "bot.log"
MAKER_FEE  = 0.00012
START_BAL  = 12.88

# ── Airdrop config ─────────────────────────────────────────────────────────────
AIRDROP_WEEK      = 11
WEEK_START        = datetime(2026, 4, 10, 21, 0, 0, tzinfo=timezone.utc)
WEEK_END          = datetime(2026, 4, 17, 20, 59, 59, tzinfo=timezone.utc)
WEEKLY_VOL_TARGET = 100_000.0

# Dados persistidos em arquivo JSON (SoPoints + volume confirmado pelo Sodex)
SOPOINTS_FILE = Path(__file__).parent.parent / "sopoints.json"

client = SodexClient(
    api_key=API_KEY,
    private_key=PRIVATE_KEY,
    api_key_name=API_KEY_NAME,
    wallet_address=WALLET_ADDRESS,
    testnet=False,
)

price_history: deque = deque(maxlen=180)

# Cache do volume semanal via API (atualizado a cada 30s)
_vol_cache: dict = {"volume": 0.0, "fees": 0.0, "fills": 0, "source": "pending", "ts": 0}


# ── SoPoints helpers ───────────────────────────────────────────────────────────

def load_sopoints() -> dict:
    if SOPOINTS_FILE.exists():
        try:
            return json.loads(SOPOINTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"points": 0, "rank": 0, "updated": "", "vol_sodex": 0.0, "vol_snapshot_ts": ""}


def save_sopoints(data: dict) -> None:
    SOPOINTS_FILE.write_text(json.dumps(data), encoding="utf-8")


class SoPointsBody(BaseModel):
    points: float = 0
    rank: Optional[int] = 0


class VolSyncBody(BaseModel):
    vol_sodex: float   # volume confirmado pela plataforma Sodex


# ── Airdrop calculations ───────────────────────────────────────────────────────

def get_weekly_volume_from_api() -> dict:
    """
    Busca histórico real de fills na API Sodex e soma o volume
    de todos os trades entre WEEK_START e WEEK_END.
    Retorna volume, fees e contagem de fills da semana.
    """
    week_start_ms = int(WEEK_START.timestamp() * 1000)
    week_end_ms   = int(WEEK_END.timestamp() * 1000)
    try:
        fills = client.perps_trade_history(limit=1000)
        weekly = [
            f for f in fills
            if week_start_ms <= f.get("time", 0) <= week_end_ms
        ]
        vol  = sum(float(f["price"]) * float(f["quantity"]) for f in weekly)
        fees = sum(float(f["fee"]) for f in weekly)
        return {"volume": vol, "fees": fees, "fills": len(weekly), "source": "api"}
    except Exception as e:
        print(f"[VOL-API] {e}")
        return {"volume": 0.0, "fees": 0.0, "fills": 0, "source": "error"}


def get_airdrop_info() -> dict:
    now = datetime.now(timezone.utc)
    remaining = WEEK_END - now
    total_secs = max(int(remaining.total_seconds()), 0)
    elapsed_secs = max(int((now - WEEK_START).total_seconds()), 0)
    week_duration = int((WEEK_END - WEEK_START).total_seconds())
    week_elapsed_pct = min(elapsed_secs / week_duration * 100, 100)

    return {
        "week":        AIRDROP_WEEK,
        "week_start":  WEEK_START.strftime("%d/%m"),
        "week_end":    WEEK_END.strftime("%d/%m"),
        "ended":       total_secs == 0,
        "days":        total_secs // 86400,
        "hours":       (total_secs % 86400) // 3600,
        "minutes":     (total_secs % 3600) // 60,
        "seconds":     total_secs % 60,
        "elapsed_pct": round(week_elapsed_pct, 1),
    }


# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_trades() -> list:
    trades = []
    if not BOT_LOG.exists():
        return trades

    result_re = re.compile(
        r"(\d{2}:\d{2}:\d{2}).*\[RESULT\] (\w+) \| "
        r"entry=\$([0-9,.]+) exit=\$([0-9,.]+) \| "
        r"PnL=([+-][0-9.]+) USD \| "
        r"vol\+=\$([0-9.]+) \| "
        r"dur=(\d+)s"
    )
    entry_re = re.compile(r"\[ENTRY\] (BUY|SELL)")
    sides: list[str] = []

    with open(BOT_LOG, encoding="utf-8", errors="ignore") as f:
        for line in f:
            em = entry_re.search(line)
            if em:
                sides.append(em.group(1))
            m = result_re.search(line)
            if m:
                side = sides[-1] if sides else "BUY"
                vol  = float(m.group(6))
                trades.append({
                    "time":     m.group(1),
                    "result":   m.group(2),
                    "side":     side,
                    "entry":    float(m.group(3).replace(",", "")),
                    "exit":     float(m.group(4).replace(",", "")),
                    "pnl":      float(m.group(5)),
                    "volume":   vol,
                    "duration": int(m.group(7)),
                    "fee":      vol * MAKER_FEE,
                })
    return trades


def get_bot_status() -> dict:
    status = {
        "state":      "OPERANDO",
        "action":     "Inicializando...",
        "signal":     "AGUARDANDO",
        "book":       "NEUTRO",
        "book_value": 0.0,
    }
    if not BOT_LOG.exists():
        return status
    try:
        with open(BOT_LOG, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-40:]

        for line in reversed(lines):
            if "LONG confirmado" in line:
                status.update(signal="COMPRA",     action="Sinal de LONG — entrando"); break
            if "SHORT confirmado" in line:
                status.update(signal="VENDA",      action="Sinal de SHORT — entrando"); break
            if "rejeitado" in line:
                status.update(signal="AGUARDANDO", action="Sinal rejeitado pelo book"); break
            if "lateral" in line:
                status.update(signal="AGUARDANDO", action="Mercado lateral"); break
            if "fraco" in line:
                status.update(signal="AGUARDANDO", action="Sinal fraco — aguardando"); break
            if "Coletando" in line:
                status["action"] = "Coletando amostras de preço..."; break
            if "[ENTRY]" in line:
                s = "COMPRA" if "BUY" in line else "VENDA"
                status.update(signal=s, action=f"Ordem de {s} enviada"); break
            if "[FILL]" in line and "confirmada" in line:
                status["action"] = "Posição aberta — aguardando TP/SL"; break
            if "[TP/SL]" in line:
                status["action"] = "TP e SL configurados"; break
            if "[RESULT]" in line:
                status["action"] = "Trade concluído — reiniciando ciclo"; break

        for line in reversed(lines):
            bm = re.search(r"book=(\S+)\(([+-][0-9.]+)\)", line)
            if bm:
                status["book"]       = bm.group(1)
                status["book_value"] = float(bm.group(2))
                break
    except Exception:
        pass
    return status


def generate_insights(trades: list) -> list:
    if not trades:
        return [
            {"type": "info", "msg": "🤖 Bot iniciado — aguardando primeiros trades"},
            {"type": "info", "msg": "📊 Tape reading + book imbalance ativos"},
        ]

    recent   = trades[-10:]
    wins     = sum(1 for t in recent if t["result"] in ("TP", "BE"))
    manuals  = sum(1 for t in recent if t["result"] == "MANUAL")
    win_rate = wins / len(recent) * 100
    total_pnl = sum(t["pnl"]    for t in trades)
    total_vol = sum(t["volume"] for t in trades)
    avg_dur   = sum(t["duration"] for t in recent) / len(recent)
    avg_vol   = total_vol / len(trades)
    proj_day  = avg_vol * (86400 / max(avg_dur + 35, 1))

    out = []
    if win_rate >= 50:
        out.append({"type": "success", "msg": f"✅ Win rate recente: {win_rate:.0f}% — estratégia sólida"})
    elif win_rate >= 25:
        out.append({"type": "warning", "msg": f"⚠️ Win rate recente: {win_rate:.0f}% — monitorar"})
    else:
        out.append({"type": "danger",  "msg": f"🔴 Win rate recente: {win_rate:.0f}% — considerar pausa"})

    if manuals >= 6:
        out.append({"type": "warning", "msg": "📊 Mercado lateral — muitos fechamentos por timeout"})
    elif avg_dur < 60:
        out.append({"type": "success", "msg": f"⚡ Trades rápidos ({avg_dur:.0f}s médio) — alta frequência"})

    out.append({"type": "info", "msg": f"📦 Projeção 24h: ${proj_day:,.0f} de volume"})

    if total_pnl > 0:
        out.append({"type": "success", "msg": f"💚 PnL líquido: +${total_pnl:.4f} em {len(trades)} trades"})
    else:
        out.append({"type": "info",    "msg": f"💡 Volume acumulado: ${total_vol:,.2f} — airdrop em progresso"})

    return out[:5]


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse((Path(__file__).parent / "index.html").read_text(encoding="utf-8"))


@app.get("/api/sopoints")
async def get_sopoints_route():
    return load_sopoints()


@app.post("/api/sopoints")
async def set_sopoints_route(body: SoPointsBody):
    data = load_sopoints()
    data.update({
        "points":  body.points,
        "rank":    body.rank or 0,
        "updated": datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC"),
    })
    save_sopoints(data)
    return data


@app.post("/api/vol-sync")
async def set_vol_sync(body: VolSyncBody):
    """
    Sincroniza o volume semanal com o valor reportado pela plataforma Sodex.
    Salva vol_sodex (snapshot do Sodex) e vol_bot_at_snapshot (bot.log neste momento).
    O volume total = vol_sodex + (vol_bot_atual - vol_bot_at_snapshot)
    """
    from dashboard.server import parse_trades as _pt
    trades = _pt()
    vol_bot_now = sum(t["volume"] for t in trades)
    data = load_sopoints()
    data.update({
        "vol_sodex":           body.vol_sodex,
        "vol_bot_at_snapshot": vol_bot_now,
        "vol_snapshot_ts":     datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC"),
    })
    save_sopoints(data)
    return data


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            trades     = parse_trades()
            bot_status = get_bot_status()
            insights   = generate_insights(trades)
            airdrop    = get_airdrop_info()
            sopoints   = load_sopoints()

            try:
                state         = client.perps_account_state()
                balance       = float(state.get("av", 0))
                free_margin   = float(state.get("am", 0))
                positions     = [p for p in (state.get("P") or []) if p.get("s") == "BTC-USD"]
                open_orders_n = len(state.get("O") or [])
            except Exception:
                balance, free_margin, positions, open_orders_n = 0, 0, [], 0

            try:
                marks     = client.perps_mark_prices()
                btc_price = next((float(m["markPrice"]) for m in marks if m["symbol"] == "BTC-USD"), 0)
            except Exception:
                btc_price = 0

            now = datetime.now(timezone.utc)
            if btc_price:
                price_history.append({"t": now.strftime("%H:%M:%S"), "p": btc_price})

            # Volume semanal real via API (cache 30s)
            import time as _time
            if _time.time() - _vol_cache["ts"] > 30:
                _vol_cache.update(get_weekly_volume_from_api())
                _vol_cache["ts"] = _time.time()

            vol_bot_now = sum(t["volume"] for t in trades)
            total_pnl   = sum(t["pnl"]   for t in trades)
            total_fees  = sum(t["fee"]   for t in trades)
            gross_pnl   = total_pnl + total_fees
            wins        = sum(1 for t in trades if t["result"] in ("TP", "BE"))
            win_rate    = wins / len(trades) * 100 if trades else 0
            roi         = total_pnl / START_BAL * 100

            # Volume semanal: direto da API (fills reais) — fonte de verdade
            total_vol   = _vol_cache.get("volume", vol_bot_now)
            api_fees    = _vol_cache.get("fees", 0.0)
            api_fills   = _vol_cache.get("fills", 0)
            vol_source  = _vol_cache.get("source", "log")

            cum_pnl: list[float] = []
            running = 0.0
            for t in trades:
                running += t["pnl"]
                cum_pnl.append(round(running, 6))

            # Projecao de volume restante na semana
            avg_dur = (sum(t["duration"] for t in trades[-10:]) / min(len(trades), 10)) if trades else 180
            avg_vol = total_vol / len(trades) if trades else 160
            secs_remaining = airdrop["days"]*86400 + airdrop["hours"]*3600 + airdrop["minutes"]*60 + airdrop["seconds"]
            trades_remaining = secs_remaining / max(avg_dur + 35, 1)
            vol_proj_week = total_vol + trades_remaining * avg_vol

            await websocket.send_json({
                "ts":             now.isoformat(),
                "btc_price":      btc_price,
                "price_history":  list(price_history),
                "balance":        balance,
                "free_margin":    free_margin,
                "total_volume":   total_vol,
                "total_pnl":      total_pnl,
                "total_fees":     total_fees,
                "gross_pnl":      gross_pnl,
                "win_rate":       round(win_rate, 1),
                "trade_count":    len(trades),
                "open_orders":    open_orders_n,
                "roi":            round(roi, 2),
                "trades":         trades[-12:][::-1],
                "cum_pnl":        cum_pnl,
                "current_pos":    positions[0] if positions else None,
                "bot_status":     bot_status,
                "insights":       insights,
                "airdrop":        airdrop,
                "sopoints":       sopoints,
                "vol_proj_week":  round(vol_proj_week, 0),
                "weekly_target":  WEEKLY_VOL_TARGET,
                "api_fees":       round(api_fees, 4),
                "api_fills":      api_fills,
                "vol_source":     vol_source,
            })
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f"[WS] {exc}")


if __name__ == "__main__":
    print("🚀  Dashboard → http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="warning")
