import asyncio
import json
import secrets
import time

import websockets
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.accounts import ACCOUNTS, close_all
from backend.binance_client import BinanceAPIError
from backend.config import settings
from backend.hedge import close_hedge, open_hedge, prepare_symbol

app = FastAPI(title="Binance Hedge Dashboard")

# El HTML es un solo archivo que puede abrirse desde cualquier origen
# (file://, otro dominio, etc.), así que se habilita CORS. La protección
# real la da el token (ver require_token / DASHBOARD_TOKEN).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = "frontend"


def require_token(x_dashboard_token: str = Header(default="")):
    """Protege el panel cuando el servidor está público (Railway, etc).
    Si DASHBOARD_TOKEN no está configurado, no exige nada (solo pensado
    para correr en tu propia máquina, 127.0.0.1)."""
    if settings.dashboard_token and not secrets.compare_digest(
        x_dashboard_token or "", settings.dashboard_token
    ):
        raise HTTPException(status_code=401, detail="Token inválido o faltante")


@app.get("/")
async def index():
    return FileResponse(f"{FRONTEND_DIR}/index.html")


@app.on_event("shutdown")
async def _shutdown():
    await close_all()


@app.get("/api/health")
async def health():
    return {"ok": True, "testnet": settings.binance_testnet, "requires_token": bool(settings.dashboard_token)}


_symbols_cache: dict = {"symbols": None, "fetched_at": 0}
_SYMBOLS_CACHE_TTL = 6 * 60 * 60  # 6 horas: la lista de pares casi no cambia


@app.get("/api/symbols", dependencies=[Depends(require_token)])
async def list_symbols():
    now = time.time()
    if _symbols_cache["symbols"] is not None and now - _symbols_cache["fetched_at"] < _SYMBOLS_CACHE_TTL:
        return {"symbols": _symbols_cache["symbols"]}

    client = ACCOUNTS["main"]
    try:
        info = await client.get_exchange_info()
    except BinanceAPIError as e:
        # Si Binance falla pero ya teníamos una lista vieja en caché, mejor
        # devolver esa que dejar el selector vacío.
        if _symbols_cache["symbols"] is not None:
            return {"symbols": _symbols_cache["symbols"]}
        return {"error": e.payload}
    except Exception as e:
        if _symbols_cache["symbols"] is not None:
            return {"symbols": _symbols_cache["symbols"]}
        return {"error": str(e)}

    symbols = sorted(
        s["symbol"]
        for s in info["symbols"]
        if s.get("status") == "TRADING" and s.get("contractType") == "PERPETUAL"
    )
    _symbols_cache["symbols"] = symbols
    _symbols_cache["fetched_at"] = now
    return {"symbols": symbols}


@app.get("/api/accounts/summary", dependencies=[Depends(require_token)])
async def accounts_summary():
    async def _summary(key: str):
        client = ACCOUNTS[key]
        try:
            balances, positions = await asyncio.gather(
                client.get_balance(), client.get_position_risk()
            )
            usdt = next((b for b in balances if b["asset"] == "USDT"), None)
            open_positions = [p for p in positions if float(p["positionAmt"]) != 0]
            return {
                "label": client.label,
                "available_usdt": float(usdt["availableBalance"]) if usdt else 0.0,
                "wallet_usdt": float(usdt["balance"]) if usdt else 0.0,
                "cross_unpnl": float(usdt["crossUnPnl"]) if usdt else 0.0,
                "positions": [
                    {
                        "symbol": p["symbol"],
                        "amount": float(p["positionAmt"]),
                        "entry_price": float(p["entryPrice"]),
                        "leverage": int(p["leverage"]),
                        "liquidation_price": float(p["liquidationPrice"]),
                        "unrealized_pnl": float(p["unRealizedProfit"]),
                        "margin_type": p["marginType"],
                    }
                    for p in open_positions
                ],
            }
        except BinanceAPIError as e:
            return {"label": client.label, "error": e.payload}
        except Exception as e:
            return {"label": client.label, "error": str(e)}

    results = await asyncio.gather(*[_summary(k) for k in ACCOUNTS])
    return dict(zip(ACCOUNTS.keys(), results))


@app.get("/api/symbol/{symbol}", dependencies=[Depends(require_token)])
async def symbol_info(symbol: str):
    symbol = symbol.upper()
    client = ACCOUNTS["main"]
    try:
        mark, filters, brackets = await asyncio.gather(
            client.get_mark_price(symbol),
            client.get_symbol_filters(symbol),
            client.get_leverage_brackets(symbol),
        )
    except BinanceAPIError as e:
        return {"error": e.payload}

    lot = next((f for f in filters["filters"] if f["filterType"] == "LOT_SIZE"), {})
    price_filter = next((f for f in filters["filters"] if f["filterType"] == "PRICE_FILTER"), {})
    max_leverage = brackets[0]["brackets"][0]["initialLeverage"] if brackets else None

    return {
        "symbol": symbol,
        "mark_price": float(mark["markPrice"]),
        "step_size": lot.get("stepSize"),
        "min_qty": lot.get("minQty"),
        "tick_size": price_filter.get("tickSize"),
        "max_leverage": max_leverage,
    }


@app.post("/api/symbol/{symbol}/prepare", dependencies=[Depends(require_token)])
async def prepare(symbol: str, body: dict):
    symbol = symbol.upper()
    leverage = int(body.get("leverage", 10))
    margin_type = body.get("margin_type", "CROSSED").upper()
    result = await prepare_symbol(symbol, leverage, margin_type)
    return result


@app.post("/api/hedge/open", dependencies=[Depends(require_token)])
async def hedge_open(body: dict):
    symbol = body["symbol"].upper()
    main_direction = body["main_direction"].upper()
    order_type = body.get("order_type", "MARKET").upper()
    quantity = float(body["quantity"])
    price = float(body["price"]) if body.get("price") else None
    reduce_only = bool(body.get("reduce_only", False))

    try:
        result = await open_hedge(
            symbol=symbol,
            main_direction=main_direction,
            order_type=order_type,
            quantity=quantity,
            price=price,
            reduce_only=reduce_only,
        )
        return result
    except ValueError as e:
        return {"error": str(e)}


@app.post("/api/hedge/close", dependencies=[Depends(require_token)])
async def hedge_close(body: dict):
    symbol = body["symbol"].upper()
    result = await close_hedge(symbol)
    return result


@app.websocket("/ws/price/{symbol}")
async def ws_price(websocket: WebSocket, symbol: str):
    token = websocket.query_params.get("token", "")
    if settings.dashboard_token and not secrets.compare_digest(token, settings.dashboard_token):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    symbol = symbol.lower()
    stream_host = "wss://stream.binancefuture.com" if settings.binance_testnet else "wss://fstream.binance.com"
    stream_url = f"{stream_host}/ws/{symbol}@markPrice@1s"

    try:
        async with websockets.connect(stream_url) as upstream:
            async def upstream_to_client():
                async for message in upstream:
                    data = json.loads(message)
                    await websocket.send_json(
                        {
                            "symbol": data.get("s"),
                            "mark_price": float(data.get("p", 0)),
                            "funding_rate": float(data.get("r", 0)),
                            "time": data.get("E"),
                        }
                    )

            async def watch_disconnect():
                try:
                    while True:
                        await websocket.receive_text()
                except WebSocketDisconnect:
                    pass

            task_up = asyncio.create_task(upstream_to_client())
            task_watch = asyncio.create_task(watch_disconnect())
            done, pending = await asyncio.wait(
                {task_up, task_watch}, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=True)
