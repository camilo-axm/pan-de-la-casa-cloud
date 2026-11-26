// Panel de administración: acceso con clave, lista de pedidos y cambio de estado.
const $ = (id) => document.getElementById(id);
const pesos = (n) => "$" + n.toLocaleString("es-CO");
const ESTADOS = ["recibido", "listo", "entregado", "cancelado"];
const nombreEstado = (e) => e.charAt(0).toUpperCase() + e.slice(1);

// La clave solo vive en memoria: se pierde al cerrar la pestaña y nunca se guarda en el navegador.
let clave = "";
let pedidos = [];
let filtro = "todos";

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text) node.textContent = text;
  return node;
}

function errorAcceso(titulo, texto) {
  $("error-titulo").textContent = titulo;
  $("error-texto").textContent = texto;
  $("error").hidden = false;
  $("clave").setAttribute("aria-invalid", "true");
}

async function pedir(url, opciones = {}) {
  return fetch(url, { ...opciones, headers: { ...(opciones.headers || {}), "X-Admin-Key": clave } });
}

async function cargar() {
  const r = await pedir("/api/pedidos");
  if (r.status === 401) {
    salir();
    errorAcceso("Clave incorrecta", "Revísala e inténtalo otra vez.");
    return false;
  }
  if (!r.ok) {
    errorAcceso("No se pudieron cargar los pedidos", "Intenta de nuevo en un momento.");
    return false;
  }
  pedidos = (await r.json()).sort((a, b) => new Date(a.hora_recogida) - new Date(b.hora_recogida));
  pintar();
  return true;
}

async function entrar(evento) {
  evento.preventDefault();
  clave = $("clave").value;
  if (!clave) return errorAcceso("Falta la clave", "Escribe la clave de administrador.");
  $("entrar").disabled = true;
  try {
    if (await cargar()) {
      $("acceso").hidden = true;
      $("pedidos").hidden = false;
      $("salir").hidden = false;
      $("ir-tienda").hidden = true;
      $("error").hidden = true;
      $("clave").value = "";
    }
  } catch {
    errorAcceso("Sin conexión", "Revisa tu conexión e inténtalo otra vez.");
  } finally {
    $("entrar").disabled = false;
  }
}

function salir() {
  clave = "";
  pedidos = [];
  $("pedidos").hidden = true;
  $("acceso").hidden = false;
  $("salir").hidden = true;
  $("ir-tienda").hidden = false;
}

function pintarResumen() {
  ESTADOS.slice(0, 3).forEach((e) => { $(`n-${e}`).textContent = String(pedidos.filter((p) => p.estado === e).length); });
  const vendido = pedidos.filter((p) => p.estado !== "cancelado").reduce((s, p) => s + p.total, 0);
  $("vendido").textContent = pesos(vendido);

  $("filtros").replaceChildren(...["todos", ...ESTADOS].map((e) => {
    const chip = el("button", { type: "button", class: "chip", "aria-pressed": String(e === filtro) }, nombreEstado(e));
    chip.addEventListener("click", () => { filtro = e; pintar(); });
    return chip;
  }));
}

function fila(p) {
  const recogida = new Date(p.hora_recogida);
  const minutosFaltan = (recogida - Date.now()) / 60000;
  const tr = el("tr", minutosFaltan >= 0 && minutosFaltan <= 30 && p.estado === "recibido" ? { class: "pronto" } : {});

  const id = el("td");
  id.append(el("span", { class: "code" }, p.id));
  const hora = el("td");
  hora.append(el("strong", {}, recogida.toLocaleTimeString("es-CO", { timeZone: "America/Bogota", hour: "numeric", minute: "2-digit" })),
    el("small", {}, recogida.toLocaleDateString("es-CO", { timeZone: "America/Bogota", weekday: "short", day: "numeric", month: "short" })));
  const cliente = el("td", {}, p.nombre);
  cliente.append(el("small", {}, p.telefono));
  const productos = el("td", {}, p.items.map((i) => `${i.cantidad} ${i.nombre}`).join(", "));
  const total = el("td");
  total.append(el("strong", {}, pesos(p.total)));
  const estado = el("td");
  estado.append(el("span", { class: `pill ${p.estado}` }, nombreEstado(p.estado)));

  const cambio = el("td");
  const select = el("select", { "aria-label": `Cambiar estado del pedido ${p.id}` });
  ESTADOS.forEach((e) => select.append(new Option(nombreEstado(e), e, false, e === p.estado)));
  select.addEventListener("change", () => cambiarEstado(p, select));
  cambio.append(select);

  tr.append(id, hora, cliente, productos, total, estado, cambio);
  return tr;
}

function pintar() {
  pintarResumen();
  const visibles = pedidos.filter((p) => filtro === "todos" || p.estado === filtro);
  $("filas").replaceChildren(...visibles.map(fila));
  if (!pedidos.length) $("aviso").textContent = "Todavía no hay pedidos.";
  else if (!visibles.length) $("aviso").textContent = "No hay pedidos con ese estado.";
  else $("aviso").textContent = "";
}

async function cambiarEstado(p, select) {
  select.disabled = true;
  try {
    const r = await pedir(`/api/pedidos/${p.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ estado: select.value }),
    });
    if (r.status === 401) { salir(); errorAcceso("La sesión ya no es válida", "Vuelve a escribir la clave."); return; }
    if (!r.ok) throw new Error(String(r.status));
    const actualizado = await r.json();
    pedidos = pedidos.map((x) => (x.id === actualizado.id ? actualizado : x));
    pintar();
    $("aviso").textContent = `Pedido ${actualizado.id} marcado como ${actualizado.estado}.`;
  } catch {
    select.value = p.estado;
    $("aviso").textContent = `No se pudo cambiar el estado del pedido ${p.id}. Intenta de nuevo.`;
  } finally {
    select.disabled = false;
  }
}

$("acceso").addEventListener("submit", entrar);
$("salir").addEventListener("click", salir);
$("actualizar").addEventListener("click", () => cargar().catch(() => { $("aviso").textContent = "Sin conexión. Intenta de nuevo."; }));
