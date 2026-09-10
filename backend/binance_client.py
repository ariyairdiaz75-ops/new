"""
Cliente async para la API de Binance Futures (USDT-M).
Se usa una instancia por cuenta (Cuenta A y Cuenta B), cada una con
su propio API key/secret. No guarda ni imprime nunca el secret.
"""
import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx

LIVE_BASE_URL = "https://fapi.binance.com"
TESTNET_BASE_URL = "https://testnet.binancefuture.com"


class BinanceAPIError(Exception):
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Binance API error {status_code}: {payload}")


class BinanceFuturesClient:
    def __init__(self, label: str, api_key: str, api_secret: str, testnet: bool = True):
        self.label = label
        self.api_key = api_key
        self._api_secret = api_secret.encode()
        self.testnet = testnet
        self.base_url = TESTNET_BASE_URL if testnet else LIVE_BASE_URL
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-MBX-APIKEY": api_key},
            timeout=10.0,
        )

    async def aclose(self):
        await self._client.aclose()

    def _sign(self, params: dict) -> str:
        query = urlencode(params, doseq=True)
        signature = hmac.new(self._api_secret, query.encode(), hashlib.sha256).hexdigest()
        return f"{query}&signature={signature}"

    async def _request(self, method: str, path: str, params: dict | None = None, signed: bool = False):
        params = dict(params or {})
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params.setdefault("recvWindow", 5000)
            query = self._sign(params)
            url = f"{path}?{query}"
            resp = await self._client.request(method, url)
        else:
            resp = await self._client.request(method, path, params=params)

        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except Exception:
                payload = {"raw": resp.text}
            raise BinanceAPIError(resp.status_code, payload)
        return resp.json()

    # ---------- lectura de cuenta ----------

    async def get_balance(self) -> list[dict]:
        """Balances por activo (USDT incluido): disponible, wallet, etc."""
        return await self._request("GET", "/fapi/v2/balance", signed=True)

    async def get_position_risk(self, symbol: str | None = None) -> list[dict]:
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v2/positionRisk", params, signed=True)

    async def get_account_info(self) -> dict:
        return await self._request("GET", "/fapi/v2/account", signed=True)

    # ---------- info de mercado ----------

    async def get_mark_price(self, symbol: str) -> dict:
        return await self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})

    async def get_symbol_filters(self, symbol: str) -> dict:
        info = await self._request("GET", "/fapi/v1/exchangeInfo")
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                return s
        raise ValueError(f"Símbolo {symbol} no encontrado")

    async def get_leverage_brackets(self, symbol: str) -> list[dict]:
        data = await self._request("GET", "/fapi/v1/leverageBracket", {"symbol": symbol}, signed=True)
        return data

    # ---------- configuración de posición ----------

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        return await self._request(
            "POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage}, signed=True
        )

    async def set_margin_type(self, symbol: str, margin_type: str) -> dict | None:
        """margin_type: 'ISOLATED' o 'CROSSED'. Ignora el error si ya estaba así."""
        try:
            return await self._request(
                "POST", "/fapi/v1/marginType", {"symbol": symbol, "marginType": margin_type}, signed=True
            )
        except BinanceAPIError as e:
            if e.payload.get("code") == -4046:  # "No need to change margin type."
                return None
            raise

    # ---------- órdenes ----------

    async def place_order(
        self,
        symbol: str,
        side: str,  # BUY | SELL
        order_type: str,  # MARKET | LIMIT
        quantity: float,
        price: float | None = None,
        reduce_only: bool = False,
        time_in_force: str = "GTC",
        stop_price: float | None = None,
    ) -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "reduceOnly": "true" if reduce_only else "false",
        }
        if order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = time_in_force
        if stop_price is not None:
            params["stopPrice"] = stop_price
        return await self._request("POST", "/fapi/v1/order", params, signed=True)

    async def cancel_all_open_orders(self, symbol: str) -> dict:
        return await self._request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": symbol}, signed=True)
