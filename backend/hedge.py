"""
Orquesta abrir/cerrar posiciones EN PARALELO en las dos cuentas (A y B,
sean tuyas o de otra persona), siempre en direcciones contrarias. Usa
asyncio.gather para que las dos órdenes salgan al mismo tiempo (mínimo
desface posible).
"""
import asyncio
import math
import time

from backend.accounts import ACCOUNTS
from backend.binance_client import BinanceAPIError

OPPOSITE = {"LONG": "SHORT", "SHORT": "LONG"}
SIDE_FOR_DIRECTION = {"LONG": "BUY", "SHORT": "SELL"}
CLOSE_SIDE_FOR_DIRECTION = {"LONG": "SELL", "SHORT": "BUY"}


def _round_step(value: float, step: str) -> float:
    step_f = float(step)
    if step_f == 0:
        return value
    precision = max(0, -int(round(math.log10(step_f))))
    rounded = math.floor(value / step_f) * step_f
    return round(rounded, precision)


async def _symbol_step_size(client, symbol: str) -> str:
    info = await client.get_symbol_filters(symbol)
    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            return f["stepSize"]
    return "0.001"


async def prepare_symbol(symbol: str, leverage: int, margin_type: str):
    """Fija apalancamiento y modo de margen en las DOS cuentas, en paralelo."""

    async def _prepare(client):
        await client.set_margin_type(symbol, margin_type)
        return await client.set_leverage(symbol, leverage)

    results = await asyncio.gather(
        *[_prepare(client) for client in ACCOUNTS.values()],
        return_exceptions=True,
    )
    out = {}
    for (key, _client), result in zip(ACCOUNTS.items(), results):
        if isinstance(result, Exception):
            out[key] = {"error": str(result)}
        else:
            out[key] = result
    return out


async def open_hedge(
    symbol: str,
    main_direction: str,  # "LONG" o "SHORT" -- lo que hará la Cuenta A
    order_type: str,  # "MARKET" o "LIMIT"
    quantity: float,
    price: float | None = None,
    reduce_only: bool = False,
    time_in_force: str = "GTC",
):
    """
    Abre una orden en la Cuenta A en `main_direction` y, al mismo
    tiempo, una orden en la Cuenta B en la dirección contraria.
    """
    main_direction = main_direction.upper()
    sub_direction = OPPOSITE[main_direction]

    directions = {"main": main_direction, "sub": sub_direction}

    # Redondear cantidad al step size del símbolo (se asume igual en ambas
    # cuentas porque es el mismo mercado de Binance Futures).
    step = await _symbol_step_size(ACCOUNTS["main"], symbol)
    qty = _round_step(quantity, step)
    if qty <= 0:
        raise ValueError("La cantidad calculada es 0, sube el monto o revisa el símbolo.")

    async def _place(key: str):
        client = ACCOUNTS[key]
        side = SIDE_FOR_DIRECTION[directions[key]]
        t0 = time.perf_counter()
        order = await client.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=qty,
            price=price,
            reduce_only=reduce_only,
            time_in_force=time_in_force,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        return {"account": client.label, "direction": directions[key], "elapsed_ms": elapsed_ms, "order": order}

    t_start = time.perf_counter()
    results = await asyncio.gather(*[_place(k) for k in ACCOUNTS], return_exceptions=True)
    total_ms = round((time.perf_counter() - t_start) * 1000, 1)

    out = {"symbol": symbol, "quantity": qty, "total_ms": total_ms, "results": {}}
    for key, result in zip(ACCOUNTS.keys(), results):
        if isinstance(result, BinanceAPIError):
            out["results"][key] = {"error": result.payload, "status_code": result.status_code}
        elif isinstance(result, Exception):
            out["results"][key] = {"error": str(result)}
        else:
            out["results"][key] = result
    return out


async def close_hedge(symbol: str):
    """Cierra (reduceOnly, a mercado) la posición abierta en cada cuenta, en paralelo."""

    async def _close(key: str):
        client = ACCOUNTS[key]
        positions = await client.get_position_risk(symbol)
        pos = next((p for p in positions if float(p["positionAmt"]) != 0), None)
        if pos is None:
            return {"account": client.label, "status": "sin posición abierta"}

        amt = float(pos["positionAmt"])
        side = "SELL" if amt > 0 else "BUY"
        t0 = time.perf_counter()
        order = await client.place_order(
            symbol=symbol,
            side=side,
            order_type="MARKET",
            quantity=abs(amt),
            reduce_only=True,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        return {"account": client.label, "elapsed_ms": elapsed_ms, "closed_amount": abs(amt), "order": order}

    t_start = time.perf_counter()
    results = await asyncio.gather(*[_close(k) for k in ACCOUNTS], return_exceptions=True)
    total_ms = round((time.perf_counter() - t_start) * 1000, 1)

    out = {"symbol": symbol, "total_ms": total_ms, "results": {}}
    for key, result in zip(ACCOUNTS.keys(), results):
        if isinstance(result, BinanceAPIError):
            out["results"][key] = {"error": result.payload, "status_code": result.status_code}
        elif isinstance(result, Exception):
            out["results"][key] = {"error": str(result)}
        else:
            out["results"][key] = result
    return out
