const $ = (sel) => document.querySelector(sel);

const state = {
  orderType: "MARKET",
  isTestnet: true,
  lastMarkPrice: 0,
};

function log(msg, obj) {
  const el = $("#result-log");
  const time = new Date().toLocaleTimeString();
  let line = `[${time}] ${msg}`;
  if (obj !== undefined) line += "\n" + JSON.stringify(obj, null, 2);
  el.textContent = line + "\n\n" + el.textContent;
}

async function api(path, options) {
  const resp = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return resp.json();
}

// ---------- salud / banner testnet ----------
async function loadHealth() {
  const health = await api("/api/health");
  state.isTestnet = health.testnet;
  const banner = $("#testnet-banner");
  if (health.testnet) {
    banner.className = "banner testnet";
    banner.textContent = "MODO TESTNET — dinero de prueba, no es real";
  } else {
    banner.className = "banner live";
    banner.textContent = "MODO EN VIVO — dinero real, cuidado";
  }
}

// ---------- resumen de cuentas ----------
function renderAccount(cardId, data) {
  const card = $(cardId);
  card.querySelector(".acc-label").textContent = data.label || "";
  if (data.error) {
    card.querySelector(".avail").textContent = "error";
    card.querySelector(".wallet").textContent = "--";
    card.querySelector(".pnl").textContent = "--";
    card.querySelector(".positions").textContent = JSON.stringify(data.error);
    return;
  }
  card.querySelector(".avail").textContent = `${data.available_usdt.toFixed(2)} USDT`;
  card.querySelector(".wallet").textContent = `${data.wallet_usdt.toFixed(2)} USDT`;
  const pnlEl = card.querySelector(".pnl");
  pnlEl.textContent = `${data.cross_unpnl.toFixed(2)} USDT`;
  pnlEl.style.color = data.cross_unpnl >= 0 ? "var(--green)" : "var(--red)";

  const posEl = card.querySelector(".positions");
  posEl.innerHTML = "";
  if (!data.positions.length) {
    posEl.innerHTML = '<div class="position-line"><span>Sin posiciones abiertas</span></div>';
  }
  for (const p of data.positions) {
    const dir = p.amount > 0 ? "LONG" : "SHORT";
    const cls = p.amount > 0 ? "pos-long" : "pos-short";
    const line = document.createElement("div");
    line.className = "position-line";
    line.innerHTML = `<span class="${cls}">${p.symbol} ${dir} x${p.leverage}</span><span>${p.unrealized_pnl.toFixed(2)} USDT</span>`;
    posEl.appendChild(line);
  }
}

async function refreshAccounts() {
  try {
    const summary = await api("/api/accounts/summary");
    renderAccount("#card-main", summary.main);
    renderAccount("#card-sub", summary.sub);
  } catch (e) {
    console.error(e);
  }
}

// ---------- info de símbolo (precio máximo apalancamiento) ----------
async function refreshSymbolInfo() {
  const symbol = $("#symbol").value.trim().toUpperCase();
  if (!symbol) return;
  const info = await api(`/api/symbol/${symbol}`);
  if (info.error) {
    $("#qty-hint").textContent = "No se pudo cargar el símbolo";
    return;
  }
  $("#symbol-label").textContent = info.symbol;
  const leverage = Number($("#leverage").value);
  const summary = await api("/api/accounts/summary");
  const avail = summary.main && !summary.main.error ? summary.main.available_usdt : 0;
  const maxNotional = avail * leverage;
  const maxQty = info.mark_price > 0 ? maxNotional / info.mark_price : 0;
  $("#qty-hint").textContent = `Precio: ${info.mark_price} · Máx. apalancamiento del par: x${info.max_leverage} · Con x${leverage} y tu disponible podrías abrir hasta ~${maxQty.toFixed(4)} ${symbol.replace("USDT", "")}`;
}

// ---------- websocket de precio en vivo ----------
let priceSocket = null;
function connectPriceSocket() {
  const symbol = $("#symbol").value.trim().toUpperCase();
  if (!symbol) return;
  if (priceSocket) priceSocket.close();

  const proto = location.protocol === "https:" ? "wss" : "ws";
  priceSocket = new WebSocket(`${proto}://${location.host}/ws/price/${symbol}`);
  const dot = $("#ws-status");

  priceSocket.onopen = () => {
    dot.className = "dot dot-on";
  };
  priceSocket.onclose = () => {
    dot.className = "dot dot-off";
  };
  priceSocket.onmessage = (evt) => {
    const data = JSON.parse(evt.data);
    if (data.error) return;
    state.lastMarkPrice = data.mark_price;
    $("#live-price").textContent = data.mark_price.toFixed(4);
    $("#symbol-label").textContent = data.symbol;
  };
}

// ---------- tabs mercado/límite ----------
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.orderType = tab.dataset.type;
    $("#price-field").style.display = state.orderType === "LIMIT" ? "block" : "none";
  });
});

// ---------- abrir hedge ----------
async function openHedge(mainDirection) {
  const symbol = $("#symbol").value.trim().toUpperCase();
  const leverage = Number($("#leverage").value);
  const marginType = $("#margin-type").value;
  const quantity = Number($("#quantity").value);
  const price = state.orderType === "LIMIT" ? Number($("#price").value) : null;
  const reduceOnly = $("#reduce-only").checked;

  if (!symbol || !quantity || quantity <= 0) {
    alert("Pon un símbolo y una cantidad válida.");
    return;
  }
  if (state.orderType === "LIMIT" && !price) {
    alert("Pon un precio límite.");
    return;
  }
  if (!state.isTestnet) {
    const ok = confirm(
      `MODO EN VIVO. Vas a abrir ${mainDirection} en Principal y lo contrario en Sub-cuenta, símbolo ${symbol}, cantidad ${quantity}. ¿Confirmas?`
    );
    if (!ok) return;
  }

  setButtonsDisabled(true);
  try {
    log(`Preparando apalancamiento x${leverage} (${marginType}) en las dos cuentas...`);
    await api(`/api/symbol/${symbol}/prepare`, {
      method: "POST",
      body: JSON.stringify({ leverage, margin_type: marginType }),
    });

    log(`Abriendo orden: Principal=${mainDirection}, Sub-cuenta=${mainDirection === "LONG" ? "SHORT" : "LONG"}, cantidad=${quantity}...`);
    const result = await api("/api/hedge/open", {
      method: "POST",
      body: JSON.stringify({
        symbol,
        main_direction: mainDirection,
        order_type: state.orderType,
        quantity,
        price,
        reduce_only: reduceOnly,
      }),
    });
    log(`Resultado (${result.total_ms} ms total):`, result);
    await refreshAccounts();
  } catch (e) {
    log("Error abriendo hedge", String(e));
  } finally {
    setButtonsDisabled(false);
  }
}

async function closeHedge() {
  const symbol = $("#symbol").value.trim().toUpperCase();
  if (!symbol) return;
  const ok = confirm(`¿Cerrar las posiciones abiertas de ${symbol} en las dos cuentas?`);
  if (!ok) return;

  setButtonsDisabled(true);
  try {
    log(`Cerrando posiciones de ${symbol} en las dos cuentas...`);
    const result = await api("/api/hedge/close", {
      method: "POST",
      body: JSON.stringify({ symbol }),
    });
    log(`Resultado cierre (${result.total_ms} ms total):`, result);
    await refreshAccounts();
  } catch (e) {
    log("Error cerrando hedge", String(e));
  } finally {
    setButtonsDisabled(false);
  }
}

function setButtonsDisabled(disabled) {
  $("#btn-long").disabled = disabled;
  $("#btn-short").disabled = disabled;
  $("#btn-close").disabled = disabled;
}

$("#btn-long").addEventListener("click", () => openHedge("LONG"));
$("#btn-short").addEventListener("click", () => openHedge("SHORT"));
$("#btn-close").addEventListener("click", () => closeHedge());
$("#symbol").addEventListener("change", () => {
  connectPriceSocket();
  refreshSymbolInfo();
});
$("#leverage").addEventListener("change", refreshSymbolInfo);

// ---------- arranque ----------
(async function init() {
  await loadHealth();
  await refreshAccounts();
  await refreshSymbolInfo();
  connectPriceSocket();
  setInterval(refreshAccounts, 2000);
})();
