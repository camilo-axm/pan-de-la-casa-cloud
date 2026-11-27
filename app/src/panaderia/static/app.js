// Tienda de Pan de la Casa: catálogo, pedido y confirmación en una sola página.
const $ = (id) => document.getElementById(id);
const pesos = (n) => "$" + n.toLocaleString("es-CO");

// Reglas de la API (app/src/panaderia/config.py). Bogotá no tiene horario de verano: UTC-5 fijo.
const DESFASE_HORAS = 5;
const APERTURA = 6 * 60;
const CIERRE = 20 * 60;
const MINUTOS_PREPARACION = 30;
const DIAS_MAXIMOS = 7;
const MINUTO = 60000;

const carrito = new Map();
let productos = [];
let categoria = "Todos";
let horaElegida = { dia: "", minutos: null };

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text) node.textContent = text;
  return node;
}

/* ---------- Catálogo ---------- */

function pintarCategorias() {
  // Orden de la vitrina; una categoría nueva en el catálogo aparece al final.
  const ORDEN = ["Panes", "Hojaldres", "Tradicionales", "Salados", "Repostería", "Combos"];
  const posicion = (c) => (ORDEN.includes(c) ? ORDEN.indexOf(c) : ORDEN.length);
  const nombres = ["Todos", ...[...new Set(productos.map((p) => p.categoria))].sort((a, b) => posicion(a) - posicion(b))];
  $("categorias").replaceChildren(...nombres.map((c) => {
    const chip = el("button", { type: "button", class: "chip", "aria-pressed": String(c === categoria) }, c);
    chip.addEventListener("click", () => { categoria = c; pintarCategorias(); pintarCatalogo(); });
    return chip;
  }));
}

/* Existencias: un combo consume unidades de sus productos, así que se revisa el pedido completo. */

function consumo(pedido) {
  const usado = new Map();
  pedido.forEach((n, id) => {
    const p = productos.find((x) => x.id === id);
    if (!p) return;
    const partes = p.tipo === "combo" ? p.incluye.map((c) => [c.producto_id, c.cantidad]) : [[p.id, 1]];
    partes.forEach(([base, cantidad]) => usado.set(base, (usado.get(base) || 0) + n * cantidad));
  });
  return usado;
}

function cabe(id, n) {
  if (n > 50) return false;
  const prueba = new Map(carrito);
  prueba.set(id, n);
  for (const [base, usado] of consumo(prueba)) {
    const p = productos.find((x) => x.id === base);
    if (p && p.maximo !== null && usado > p.maximo) return false;
  }
  return true;
}

function accion(p) {
  const n = carrito.get(p.id) || 0;
  if (p.agotado) return el("span", { class: "agotado" }, "Agotado");
  if (!n) {
    const btn = el("button", { type: "button" }, "Agregar");
    btn.disabled = !cabe(p.id, 1);
    btn.addEventListener("click", () => cambiar(p.id, 1));
    return btn;
  }
  const qty = el("span", { class: "qty" });
  const menos = el("button", { type: "button", "aria-label": `Quitar un ${p.nombre}` }, "−");
  const mas = el("button", { type: "button", "aria-label": `Agregar otro ${p.nombre}` }, "+");
  mas.disabled = !cabe(p.id, n + 1);
  if (mas.disabled) mas.title = "No hay más unidades disponibles";
  menos.addEventListener("click", () => cambiar(p.id, -1));
  mas.addEventListener("click", () => cambiar(p.id, 1));
  qty.append(menos, el("output", { "aria-label": `Cantidad de ${p.nombre}` }, String(n)), mas);
  return qty;
}

function quedan(p) {
  if (p.agotado || p.maximo === null || p.maximo > 5) return null;
  return el("p", { class: "quedan" }, p.maximo === 1 ? "Queda 1" : `Quedan ${p.maximo}`);
}

function pintarCatalogo() {
  const visibles = productos.filter((p) => categoria === "Todos" || p.categoria === categoria);
  $("catalogo").replaceChildren(...visibles.map((p) => {
    const card = el("article", { class: p.agotado ? "card sin-stock" : "card" });
    card.append(el("img", { src: p.foto, alt: p.nombre, width: 240, height: 160, loading: "lazy" }));
    const body = el("div", { class: "card-body" });
    body.append(el("p", { class: "cat" }, p.categoria), el("h3", {}, p.nombre), el("p", { class: "desc" }, p.descripcion));
    if (p.tipo === "combo") {
      body.append(el("p", { class: "incluye" }, "Incluye " + p.incluye.map((c) => `${c.cantidad} ${c.nombre}`).join(", ")));
    }
    const aviso = quedan(p);
    if (aviso) body.append(aviso);
    const row = el("div", { class: "row" });
    row.append(el("span", { class: "precio" }, pesos(p.precio)), accion(p));
    body.append(row);
    card.append(body);
    return card;
  }));
}

/* ---------- Pedido ---------- */

function cambiar(id, delta) {
  const n = (carrito.get(id) || 0) + delta;
  if (delta > 0 && !cabe(id, n)) return;
  if (n <= 0) carrito.delete(id); else carrito.set(id, n);
  $("error").hidden = true;
  pintarCatalogo();
  pintarPedido();
}

function lineas() {
  return [...carrito].map(([id, n]) => {
    const p = productos.find((x) => x.id === id);
    return { p, n, subtotal: p.precio * n };
  });
}

function pintarPedido() {
  const items = lineas();
  const total = items.reduce((s, i) => s + i.subtotal, 0);
  const unidades = items.reduce((s, i) => s + i.n, 0);

  $("carrito").replaceChildren(...items.map(({ p, n, subtotal }) => {
    const li = el("li");
    const ctrl = el("span", { class: "ctrl" });
    const menos = el("button", { type: "button", "aria-label": `Quitar un ${p.nombre}` }, "−");
    const mas = el("button", { type: "button", "aria-label": `Agregar otro ${p.nombre}` }, "+");
    menos.addEventListener("click", () => cambiar(p.id, -1));
    mas.disabled = !cabe(p.id, n + 1);
    mas.addEventListener("click", () => cambiar(p.id, 1));
    ctrl.append(menos, document.createTextNode(String(n)), mas);
    li.append(el("span", { class: "nom" }, p.nombre), ctrl, el("span", { class: "sub" }, pesos(subtotal)));
    return li;
  }));

  const hay = items.length > 0;
  $("vacio").hidden = hay;
  const formularioOculto = $("form").hidden;
  $("form").hidden = !hay;
  if (hay && formularioOculto) mostrarHoraElegida();
  $("total").textContent = pesos(total);
  $("enviar").textContent = `Confirmar pedido · ${pesos(total)}`;
  marcarPaso(hay ? 1 : 0);

  $("contador").textContent = String(unidades);
  $("ir-pedido").hidden = !hay;
  $("barra").hidden = !hay;
  $("barra-texto").textContent = `Ver pedido (${unidades})`;
  $("barra-total").textContent = pesos(total);
}

function marcarPaso(paso) {
  [...$("pasos").children].forEach((li, i) => li.classList.toggle("on", i <= paso));
}

/* ---------- Día y hora de recogida (siempre en hora de Bogotá) ---------- */

const dosCifras = (n) => String(n).padStart(2, "0");

function instante(fecha, minutos) {
  // fecha es un Date en UTC que representa el día en Bogotá.
  return Date.UTC(fecha.getUTCFullYear(), fecha.getUTCMonth(), fecha.getUTCDate(),
    Math.floor(minutos / 60) + DESFASE_HORAS, minutos % 60);
}

function franjas(fecha) {
  const desde = Date.now() + (MINUTOS_PREPARACION + 1) * MINUTO;
  const hasta = Date.now() + DIAS_MAXIMOS * 24 * 60 * MINUTO;
  const lista = [];
  for (let m = APERTURA; m <= CIERRE; m += 30) {
    const t = instante(fecha, m);
    lista.push({ minutos: m, etiqueta: `${Math.floor(m / 60)}:${dosCifras(m % 60)}`, libre: t >= desde && t <= hasta });
  }
  return lista;
}

const mayuscula = (texto) => texto.charAt(0).toLocaleUpperCase("es-CO") + texto.slice(1);

function dias() {
  const hoy = new Date(Date.now() - DESFASE_HORAS * 60 * MINUTO);
  const base = Date.UTC(hoy.getUTCFullYear(), hoy.getUTCMonth(), hoy.getUTCDate());
  const lista = [];
  for (let i = 0; i <= DIAS_MAXIMOS; i += 1) {
    const fecha = new Date(base + i * 24 * 60 * MINUTO);
    if (!franjas(fecha).some((f) => f.libre)) continue;
    const parte = (opcion) => fecha.toLocaleDateString("es-CO", { timeZone: "UTC", ...opcion });
    const texto = `${parte({ weekday: "long" })} ${fecha.getUTCDate()} de ${parte({ month: "long" })}`;
    // "Hoy, jueves 26 de noviembre", "Mañana, viernes 27 de noviembre", "Sábado 28 de noviembre"
    const prefijo = i === 0 ? "Hoy, " : i === 1 ? "Mañana, " : "";
    lista.push({ fecha, texto: prefijo ? prefijo + texto : mayuscula(texto) });
  }
  return lista;
}

function pintarDias() {
  const opciones = dias();
  $("dia").replaceChildren(...opciones.map((d) => new Option(d.texto, d.fecha.toISOString().slice(0, 10))));
  pintarHoras();
}

// Deja visible la hora elegida dentro de la lista, sin mover el resto de la página.
function mostrarHoraElegida() {
  const lista = $("horas");
  const elegida = lista.querySelector('[aria-pressed="true"]');
  if (!elegida || lista.offsetParent === null) return;
  lista.scrollTop += elegida.getBoundingClientRect().top - lista.getBoundingClientRect().top - 6;
}

function pintarHoras() {
  const fecha = new Date($("dia").value + "T00:00:00Z");
  const lista = franjas(fecha);
  if (!lista.some((f) => f.libre && f.minutos === horaElegida.minutos && $("dia").value === horaElegida.dia)) {
    const primera = lista.find((f) => f.libre);
    horaElegida = { dia: $("dia").value, minutos: primera ? primera.minutos : null };
  }
  $("horas").replaceChildren(...lista.map((f) => {
    const elegida = f.libre && f.minutos === horaElegida.minutos;
    const b = el("button", { type: "button", class: "slot", "aria-pressed": String(elegida) }, f.etiqueta);
    b.disabled = !f.libre;
    b.addEventListener("click", () => { horaElegida = { dia: $("dia").value, minutos: f.minutos }; pintarHoras(); });
    return b;
  }));
  mostrarHoraElegida();
}

function horaRecogida() {
  const m = horaElegida.minutos;
  return `${horaElegida.dia}T${dosCifras(Math.floor(m / 60))}:${dosCifras(m % 60)}:00-05:00`;
}

/* ---------- Envío ---------- */

const CAMPOS = {
  nombre: "Escribe tu nombre (entre 2 y 80 caracteres).",
  telefono: "El teléfono debe tener entre 7 y 10 dígitos, sin espacios.",
  hora_recogida: "Elige una hora de recogida válida.",
  items: "Revisa las cantidades del pedido (máximo 50 por producto).",
};

function mostrarError(texto) {
  $("error-texto").textContent = texto;
  $("error").hidden = false;
  $("error").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function explicar(detalle) {
  if (typeof detalle === "string") return `${detalle}. Corrige el dato y vuelve a intentarlo.`;
  if (Array.isArray(detalle)) {
    const campos = [...new Set(detalle.map((d) => d.loc && d.loc[1]))];
    return campos.map((c) => CAMPOS[c] || "Revisa los datos del formulario.").join(" ");
  }
  return "Revisa los datos y vuelve a intentarlo.";
}

async function enviar(evento) {
  evento.preventDefault();
  const nombre = $("nombre");
  const telefono = $("telefono");
  nombre.setAttribute("aria-invalid", String(!nombre.checkValidity()));
  telefono.setAttribute("aria-invalid", String(!telefono.checkValidity()));
  if (!nombre.checkValidity()) return mostrarError(CAMPOS.nombre);
  if (!telefono.checkValidity()) return mostrarError(CAMPOS.telefono);
  if (horaElegida.minutos === null) return mostrarError(CAMPOS.hora_recogida);

  $("enviar").disabled = true;
  $("error").hidden = true;
  try {
    const r = await fetch("/api/pedidos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nombre: nombre.value.trim(),
        telefono: telefono.value,
        hora_recogida: horaRecogida(),
        items: [...carrito].map(([producto_id, cantidad]) => ({ producto_id, cantidad })),
      }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      // Si alguien compró primero, se actualizan las existencias que ve el cliente.
      if (r.status === 409) await cargarCatalogo();
      return mostrarError(explicar(data.detail));
    }
    confirmar(data);
  } catch {
    mostrarError("Revisa tu conexión e inténtalo de nuevo. Tu pedido sigue guardado en esta página.");
  } finally {
    $("enviar").disabled = false;
  }
}

function confirmar(pedido) {
  const hora = new Date(pedido.hora_recogida);
  const parte = (opcion) => hora.toLocaleDateString("es-CO", { timeZone: "America/Bogota", ...opcion });
  const dia = `${parte({ weekday: "long" })} ${parte({ day: "numeric" })} de ${parte({ month: "long" })}`;
  const horaTexto = hora.toLocaleTimeString("es-CO", { timeZone: "America/Bogota", hour: "numeric", minute: "2-digit" });
  $("conf-id").textContent = pedido.id;
  $("conf-consulta").href = `/?pedido=${encodeURIComponent(pedido.id)}#mi-pedido`;
  $("conf-hora").textContent = `el ${dia} a las ${horaTexto}`;
  const filas = pedido.items.map((i) => {
    const p = el("p");
    p.append(el("span", {}, `${i.cantidad} × ${i.nombre}`), el("span", {}, pesos(i.subtotal)));
    return p;
  });
  const tot = el("p", { class: "tot" });
  tot.append(el("span", {}, "Total"), el("span", {}, pesos(pedido.total)));
  $("conf-resumen").replaceChildren(...filas, tot);

  carrito.clear();
  cargarCatalogo();
  pintarPedido();
  $("vista-pedido").hidden = true;
  $("vista-confirmacion").hidden = false;
  marcarPaso(2);
  $("pedido").scrollIntoView({ behavior: "smooth", block: "start" });
}

function otroPedido() {
  $("vista-confirmacion").hidden = true;
  $("vista-pedido").hidden = false;
  pintarDias();
  pintarPedido();
  $("tienda").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- Inicio ---------- */

async function cargarCatalogo() {
  try {
    const r = await fetch("/api/productos");
    if (!r.ok) throw new Error(String(r.status));
    productos = await r.json();
    // Quita del pedido lo que ya no está en el catálogo o lo deja dentro de lo disponible.
    [...carrito.keys()].forEach((id) => {
      const p = productos.find((x) => x.id === id);
      if (!p || p.agotado) carrito.delete(id);
    });
    $("estado-catalogo").hidden = productos.length > 0;
    if (!productos.length) $("estado-catalogo").textContent = "Hoy no hay productos disponibles. Vuelve más tarde.";
    pintarCategorias();
    pintarCatalogo();
    pintarPedido();
  } catch {
    $("estado-catalogo").hidden = false;
    $("estado-catalogo").textContent = "No pudimos cargar el catálogo. Recarga la página en un momento.";
  }
}

async function iniciar() {
  $("form").addEventListener("submit", enviar);
  $("dia").addEventListener("change", pintarHoras);
  $("otro").addEventListener("click", otroPedido);
  $("ver-pedido").addEventListener("click", () => $("pedido").scrollIntoView({ behavior: "smooth", block: "start" }));
  pintarDias();
  pintarPedido();

  await cargarCatalogo();
}

iniciar();
