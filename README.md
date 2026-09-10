# Hedge Dashboard — Binance Futures (Cuenta A + Cuenta B)

Panel web que abre y cierra órdenes de Futuros **al mismo tiempo** en dos
cuentas de Binance (la tuya y la de otra persona, o tu cuenta + tu
sub-cuenta — el programa las trata igual: dos API keys independientes),
siempre en **direcciones contrarias** (una long, la otra short), con las
mismas especificaciones de orden (símbolo, tipo, cantidad, apalancamiento).
Muestra en vivo el saldo disponible de cada cuenta, el balance total, el
precio del par y hasta cuánto se puede abrir según el apalancamiento
seleccionado.

## ⚠️ Antes de usarlo

- **Nunca compartas tus API keys ni tu API secret con nadie**, y lo mismo
  para la otra persona si Cuenta B es suya. Cada quien genera su propia API
  key desde su propia cuenta de Binance — nunca se comparten usuario ni
  contraseña de Binance. Estas claves solo se guardan como variables de
  entorno (en Railway o en tu `.env` local) y nunca se envían a ningún lado
  excepto a Binance.
- Al crear las API keys en Binance, actives **solo** los permisos que
  necesitas: **Habilitar Futuros**. **NO actives "Habilitar Retiros"**.
- Se recomienda además restringir las API keys a IPs de confianza (Binance
  permite poner un whitelist de IPs por API key).
- Operar en Futuros con apalancamiento (x20 o más) es de **alto riesgo**:
  se puede perder el margen rápido. Abrir "hedge" en dos cuentas (una long,
  una short) **no elimina el riesgo**: cada cuenta puede liquidarse por su
  lado (por ejemplo por comisiones, funding rate o si una orden falla y la
  otra sí se ejecuta). Empieza siempre en **Testnet**.
- **Si Cuenta B es de otra persona (un amigo, socio, etc.):** las dos
  credenciales van a quedar en el mismo servidor. Asegúrense de estar de
  acuerdo en quién administra el servidor/Railway, qué pasa si una orden
  falla en una cuenta y en la otra no, y que ambos entienden y aceptan el
  riesgo antes de usar dinero real. Este programa no reparte pérdidas ni
  resuelve conflictos entre las dos personas — eso lo acuerdan ustedes.
- Este proyecto es una herramienta de automatización personal. Cada usuario
  es responsable de cómo la usa y de cumplir los Términos de Servicio de
  Binance.

El frontend (`frontend/index.html`) es **un solo archivo** (HTML+CSS+JS
juntos). El servidor (backend en Python) va desplegado en **Railway**, así
que el HTML se lo sirve el propio servidor — no necesitas instalar nada más
para verlo, solo abrir la URL de Railway en tu navegador.

## 1. Requisitos

- Una cuenta de Railway (https://railway.app) — gratis para empezar.
- Dos cuentas de Binance con Futuros habilitado, cada una con su **propia
  API key**: la tuya (Cuenta A) y la de Cuenta B (puede ser tu sub-cuenta,
  o la cuenta de otra persona — para el programa da igual).

## 2. Desplegar el servidor en Railway

1. Sube este proyecto a un repo de GitHub (o usa el que ya tienes).
2. En Railway: **New Project → Deploy from GitHub repo** y elige este repo.
   Railway detecta automáticamente que es Python (por `requirements.txt` y
   `Procfile`) y lo corre solo.
3. En el proyecto de Railway ve a **Variables** y agrega estas (con tus
   datos reales, sin comillas):

   ```
   BINANCE_TESTNET=true
   MAIN_LABEL=Yo
   MAIN_API_KEY=tu_api_key
   MAIN_API_SECRET=tu_api_secret
   SUB_LABEL=Nombre del amigo
   SUB_API_KEY=api_key_de_la_segunda_cuenta
   SUB_API_SECRET=api_secret_de_la_segunda_cuenta
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
- Dos tarjetas: **Cuenta A** y **Cuenta B** (con el nombre que hayas puesto
  en `MAIN_LABEL`/`SUB_LABEL`), con el saldo disponible, balance total, PnL
  no realizado y posiciones abiertas de cada una — se refrescan cada 2
  segundos.
- El panel de orden: un campo de **símbolo con autocompletado** (escribe y
  te sugiere entre todos los pares de Futuros Perpetuos de Binance, por
  ejemplo `ARKMUSDT`, `BTCUSDT`, etc. — se carga solo al abrir el panel),
  apalancamiento, margen (Cruzado/Aislado), Mercado o Límite, cantidad.
- Dos botones grandes: **Comprar/Long (Cuenta A)** y **Vender/Short (Cuenta
  A)**. Al presionar cualquiera de los dos, el programa:
  1. Fija el apalancamiento y el tipo de margen en **ambas** cuentas.
  2. Manda la orden en Cuenta A en la dirección elegida y, **en paralelo**
     (con `asyncio.gather`, no una después de la otra), la orden contraria
     en Cuenta B.
  3. Te muestra abajo el resultado de las dos órdenes y cuántos
     milisegundos tardó cada una, para que veas que no hay desface.
- El botón **Cerrar posiciones (las dos cuentas)** cierra a mercado, con
  `reduceOnly`, lo que esté abierto en cada cuenta al mismo tiempo.
- **Ganancia combinada**: pones cuánto puso cada quien como "capital
  inicial" (por defecto $10 en cada campo, dentro de Configuración) y el
  panel calcula, con el balance + PnL no realizado actual de cada cuenta,
  cuánto lleva ganando/perdiendo cada una y la **suma neta de las dos**. Por
  ejemplo: si Cuenta A puso $10 y los perdió todos (queda en $0, PnL
  -$10), y Cuenta B puso $10 y ya lleva $22 (PnL +$12), la ganancia
  combinada que se muestra es **+$2** (-10 + 12). Es un estimado tuyo, no
  algo que Binance sepa — tú defines el capital inicial.
- **Alerta de transferencia manual**: si el disponible de una cuenta baja
  del umbral que configures (por defecto $5 USDT), aparece una barra
  arriba avisando cuál cuenta se quedó sin fondos y sugiriendo transferirle
  ~$10 desde la otra. **La transferencia la hacen ustedes manualmente en la
  app de Binance** — el programa no mueve dinero entre las dos cuentas de
  forma automática, porque hacerlo solo, sin que nadie confirme, requeriría
  activar un permiso de nivel "retiros" en una de las API keys, lo cual
  expondría toda esa cuenta (no solo Futuros) si esa clave se filtra algún
  día. El botón "Ya transferí" solo oculta el aviso 10 minutos.

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

1. Genera API keys reales en Cuenta A y en Cuenta B (cada quien la suya,
   con permiso de Futuros, sin retiros, idealmente con whitelist de IP).
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
  accounts.py          -> instancia los dos clientes (Cuenta A y Cuenta B)
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
