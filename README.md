# Hedge Dashboard — Binance Futures (Cuenta Principal + Sub-cuenta)

Panel web local que abre y cierra órdenes de Futuros **al mismo tiempo** en
tu cuenta principal y tu sub-cuenta de Binance, siempre en **direcciones
contrarias** (una long, la otra short), con las mismas especificaciones de
orden (símbolo, tipo, cantidad, apalancamiento). Muestra en vivo tu saldo
disponible, tu balance total, el precio del par y hasta cuánto puedes abrir
según el apalancamiento seleccionado.

## ⚠️ Antes de usarlo

- **Nunca compartas tus API keys ni tu API secret con nadie.** Este programa
  las guarda solo en tu archivo `.env`, en tu propia computadora/servidor, y
  nunca las envía a ningún lado excepto a Binance.
- Al crear las API keys en Binance, actives **solo** los permisos que
  necesitas: **Habilitar Futuros**. **NO actives "Habilitar Retiros"**.
- Se recomienda además restringir las API keys a la IP desde donde corres
  este programa (Binance permite poner un whitelist de IPs por API key).
- Operar en Futuros con apalancamiento (x20 o más) es de **alto riesgo**:
  puedes perder tu margen rápido. Abrir "hedge" en dos cuentas (una long,
  una short) **no elimina el riesgo**: cada cuenta puede liquidarse por su
  lado (por ejemplo por comisiones, funding rate o si una orden falla y la
  otra sí se ejecuta). Empieza siempre en **Testnet**.
- Este proyecto es una herramienta de automatización personal para tus
  propias cuentas. Tú eres responsable de cómo la usas y de cumplir los
  Términos de Servicio de Binance.

El frontend (`frontend/index.html`) es **un solo archivo** (HTML+CSS+JS
juntos). El servidor (backend en Python) va desplegado en **Railway**, así
que el HTML se lo sirve el propio servidor — no necesitas instalar nada más
para verlo, solo abrir la URL de Railway en tu navegador.

## 1. Requisitos

- Una cuenta de Railway (https://railway.app) — gratis para empezar.
- Una cuenta de Binance con Futuros habilitado.
- Una sub-cuenta de Binance con su **propia API key de Futuros** (se crea
  desde Binance → Sub-cuentas → [tu sub-cuenta] → Administrar API).

## 2. Desplegar el servidor en Railway

1. Sube este proyecto a un repo de GitHub (o usa el que ya tienes).
2. En Railway: **New Project → Deploy from GitHub repo** y elige este repo.
   Railway detecta automáticamente que es Python (por `requirements.txt` y
   `Procfile`) y lo corre solo.
3. En el proyecto de Railway ve a **Variables** y agrega estas (con tus
   datos reales, sin comillas):

   ```
   BINANCE_TESTNET=true
   MAIN_LABEL=Principal
   MAIN_API_KEY=tu_api_key_cuenta_principal
   MAIN_API_SECRET=tu_api_secret_cuenta_principal
   SUB_LABEL=Subcuenta
   SUB_API_KEY=tu_api_key_subcuenta
   SUB_API_SECRET=tu_api_secret_subcuenta
   DASHBOARD_TOKEN=algo-largo-y-dificil-de-adivinar
   ```

   `DASHBOARD_TOKEN` es tu propia contraseña para el panel — como el
   servidor queda con una URL pública en internet, sin este token
   **cualquiera que la encuentre podría abrir/cerrar órdenes en tus
   cuentas**. Invéntate algo largo (por ejemplo 32 caracteres random).

4. Railway te da una URL pública, tipo
   `https://tu-app.up.railway.app`. Ábrela en el navegador: ahí carga el
   panel directamente (es el mismo servidor sirviendo el HTML).
5. La primera vez, abre el desplegable **"Configuración"** arriba del
   panel, pon:
   - **URL del servidor**: la misma URL de Railway (normalmente ya viene
     puesta sola).
   - **Token**: el mismo valor que pusiste en `DASHBOARD_TOKEN`.

   Se guarda en tu navegador (localStorage) para que no lo tengas que
   escribir cada vez.

Para Testnet, genera las API keys de prueba en
https://testnet.binancefuture.com (son distintas a las de tu cuenta real).

## 3. Cómo se usa el panel

Al abrir la URL (de Railway, o `http://127.0.0.1:8000` si lo corres local)
vas a ver:
- Arriba, el precio en vivo del par (actualizado por WebSocket).
- Dos tarjetas: **Principal** y **Sub-cuenta**, con tu saldo disponible,
  balance total, PnL no realizado y posiciones abiertas — se refrescan cada
  2 segundos.
- El panel de orden: símbolo, apalancamiento, margen (Cruzado/Aislado),
  Mercado o Límite, cantidad.
- Dos botones grandes: **Comprar/Long (Principal)** y **Vender/Short
  (Principal)**. Al presionar cualquiera de los dos, el programa:
  1. Fija el apalancamiento y el tipo de margen en **ambas** cuentas.
  2. Manda la orden en la cuenta principal en la dirección elegida y, **en
     paralelo** (con `asyncio.gather`, no una después de la otra), la orden
     contraria en la sub-cuenta.
  3. Te muestra abajo el resultado de las dos órdenes y cuántos
     milisegundos tardó cada una, para que veas que no hay desface.
- El botón **Cerrar posiciones (las dos cuentas)** cierra a mercado, con
  `reduceOnly`, lo que esté abierto en cada cuenta al mismo tiempo.

## 4. Alternativa: correrlo en tu computadora (sin Railway)

Si prefieres probarlo local antes de subirlo:

```bash
python -m venv .venv
source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` y pon tus API keys reales (`DASHBOARD_TOKEN` es opcional en
local, ya que 127.0.0.1 no es accesible desde internet).

```bash
python -m backend.main
```

Abre **http://127.0.0.1:8000** — el campo "URL del servidor" en
Configuración se auto-completa solo con esa misma dirección.

## 5. Pasar a cuentas reales

Cuando ya probaste todo en Testnet y funciona como esperas:

1. Genera API keys reales en tu cuenta principal y en tu sub-cuenta (con
   permiso de Futuros, sin retiros, idealmente con whitelist de IP).
2. Cambia las variables en Railway (o en tu `.env` local): pon
   `BINANCE_TESTNET=false` y reemplaza las 4 API keys/secrets por las
   reales.
3. El servidor se reinicia solo (Railway) o reinícialo tú (local). Vas a
   ver una barra roja arriba que dice **"MODO EN VIVO"** para que nunca
   confundas testnet con dinero real. Además, en modo en vivo el panel te
   pide una confirmación extra antes de mandar cualquier orden.

## Estructura del proyecto

```
backend/
  binance_client.py   -> llamadas firmadas a la API de Binance Futures
  accounts.py          -> instancia los dos clientes (principal y sub)
  hedge.py              -> abre/cierra órdenes en paralelo, direcciones contrarias
  config.py             -> lee variables de entorno (.env local o Railway)
  main.py               -> servidor FastAPI + endpoints + token + websocket de precio
frontend/
  index.html             -> el panel completo: HTML + CSS + JS en un solo archivo
Procfile                 -> comando de arranque que usa Railway
```

## Limitaciones conocidas / ideas para mejorar

- El saldo/posiciones se actualizan cada 2 segundos por consulta REST; el
  precio sí es 100% en vivo por WebSocket. Se podría mejorar conectando
  también el *user data stream* de cada cuenta para que el balance se
  actualice al instante en vez de cada 2s.
- Actualmente asume "one-way mode" (no hedge mode) en cada cuenta de
  Binance por separado, lo cual es más simple porque cada cuenta solo
  sostiene una posición (long o short) a la vez.
- Si una de las dos órdenes falla (por ejemplo por fondos insuficientes en
  una cuenta) y la otra sí se ejecuta, vas a quedar con una posición
  abierta sin cobertura en la otra cuenta. El panel te muestra claramente
  el resultado de cada cuenta por separado para que lo detectes al toque y
  puedas cerrarla manualmente.
