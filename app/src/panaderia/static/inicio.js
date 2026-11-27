// Página de inicio: franja de ofertas, carrusel, productos, combos, estado del pedido y contacto.
const $ = (id) => document.getElementById(id);
const pesos = (n) => "$" + n.toLocaleString("es-CO");
const ZONA = "America/Bogota";
const QUIETO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Datos del local. Se editan aquí y se ven en "Visítanos".
const NEGOCIO = {
  direccion: "Calle 45 # 13-20, Chapinero, Bogotá",
  horario: [["Horario de atención todos los días", "6:00 a. m. a 8:00 p. m."]],
};

const ORDEN = ["Panes", "Hojaldres", "Tradicionales", "Salados", "Repostería", "Combos"];
const ESTADOS = {
  recibido: { pill: "Recibido", texto: "Ya tenemos tu pedido. Lo empezamos a preparar antes de tu hora." },
  listo: { pill: "Listo para recoger", texto: "Tu pedido está listo. Te esperamos en el mostrador de la entrada." },
  entregado: { pill: "Entregado", texto: "Ya recogiste este pedido. ¡Que lo disfrutes!" },
  cancelado: { pill: "Cancelado", texto: "Este pedido se canceló. Si no fuiste tú, escríbenos desde Contacto." },
};

let productos = [];
let categoria = "Todos";

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text !== "") node.textContent = text;
  return node;
}

function precioNormal(combo) {
  return combo.incluye.reduce((suma, i) => {
    const parte = productos.find((p) => p.id === i.producto_id);
    return suma + (parte ? parte.precio * i.cantidad : 0);
  }, 0);
}

/* ---------- Menú en celular ---------- */

$("hamburguesa").addEventListener("click", () => {
  const abierta = $("nav").classList.toggle("abierta");
  $("hamburguesa").setAttribute("aria-expanded", String(abierta));
});
$("nav").addEventListener("click", (e) => {
  if (e.target.tagName !== "A") return;
  $("nav").classList.remove("abierta");
  $("hamburguesa").setAttribute("aria-expanded", "false");
});

/* ---------- Franja de ofertas ---------- */

function iniciarOfertas(combos) {
  const mensajes = [
    ...combos.filter((c) => !c.agotado && precioNormal(c) > c.precio)
      .map((c) => ({ texto: `${c.nombre} a ${pesos(c.precio)}: ahorras ${pesos(precioNormal(c) - c.precio)}`, enlace: "#combos" })),
    { texto: "Pedidos para recoger todos los días, de 6:00 a. m. a 8:00 p. m." },
    { texto: "Pides en línea y pagas al recoger, sin crear cuenta", enlace: "/pedir" },
  ];
  let i = 0;
  const mostrar = () => {
    const m = mensajes[i];
    const p = $("oferta-texto");
    p.replaceChildren(m.texto);
    if (m.enlace) p.append(el("a", { href: m.enlace }, "Ver"));
  };
  mostrar();
  if (QUIETO || mensajes.length < 2) return;
  setInterval(() => {
    $("oferta-texto").classList.add("cambiando");
    setTimeout(() => {
      i = (i + 1) % mensajes.length;
      mostrar();
      $("oferta-texto").classList.remove("cambiando");
    }, 300);
  }, 5000);
}
$("oferta-cerrar").addEventListener("click", () => { $("oferta").hidden = true; });

/* ---------- Carrusel ---------- */

function diapositiva(combo) {
  const art = el("article", { class: "promo", "aria-roledescription": "diapositiva" });
  art.append(el("img", { class: "promo-foto", src: combo.foto, alt: "", loading: "lazy" }));
  const txt = el("div", { class: "promo-txt" });
  const acciones = el("div", { class: "promo-acciones" });
  const precio = el("span", { class: "promo-precio" }, pesos(combo.precio));
  const normal = precioNormal(combo);
  if (normal > combo.precio) precio.append(el("s", {}, pesos(normal)));
  acciones.append(el("a", { class: "btn btn-rojo", href: "/pedir" }, "Pedir este combo"), precio);
  txt.append(el("span", { class: "promo-cat" }, "Combo"), el("h2", {}, combo.nombre),
    el("p", {}, `${combo.descripcion} Incluye ${combo.incluye.map((c) => `${c.cantidad} ${c.nombre.toLowerCase()}`).join(", ")}.`), acciones);
  art.append(txt);
  return art;
}

function iniciarCarrusel(combos) {
  const pista = $("promos-pista");
  combos.filter((c) => !c.agotado).forEach((c) => pista.append(diapositiva(c)));
  const consulta = el("article", { class: "promo", "aria-roledescription": "diapositiva" });
  consulta.append(el("img", { class: "promo-foto", src: "/img/sitio/fachada.jpg", alt: "", loading: "lazy" }));
  const txt = el("div", { class: "promo-txt" });
  const acciones = el("div", { class: "promo-acciones" });
  acciones.append(el("a", { class: "btn btn-rojo", href: "#mi-pedido" }, "Consultar mi pedido"));
  txt.append(el("span", { class: "promo-cat" }, "Tu pedido"), el("h2", {}, "¿Ya pediste? Mira si está listo"),
    el("p", {}, "Con el número de pedido y tu teléfono ves en qué paso va."), acciones);
  consulta.append(txt);
  pista.append(consulta);

  const slides = [...pista.children];
  slides.forEach((s, n) => s.setAttribute("aria-label", `${n + 1} de ${slides.length}`));
  if (slides.length < 2) return;
  let actual = 0;
  const puntos = slides.map((_, n) => {
    const b = el("button", { type: "button", "aria-label": `Ver destacado ${n + 1}` });
    b.addEventListener("click", () => { ir(n); reiniciar(); });
    return b;
  });
  $("promos-puntos").replaceChildren(...puntos);
  function ir(n) {
    actual = (n + slides.length) % slides.length;
    slides.forEach((s, k) => s.classList.toggle("activa", k === actual));
    puntos.forEach((p, k) => p.setAttribute("aria-current", String(k === actual)));
  }
  let reloj = null;
  function reiniciar() {
    clearInterval(reloj);
    if (!QUIETO) reloj = setInterval(() => ir(actual + 1), 6500);
  }
  $("promos-ant").hidden = false;
  $("promos-sig").hidden = false;
  $("promos-ant").addEventListener("click", () => { ir(actual - 1); reiniciar(); });
  $("promos-sig").addEventListener("click", () => { ir(actual + 1); reiniciar(); });
  // En celular se cambia de destacado deslizando el dedo.
  let inicioX = null;
  $("promos").addEventListener("touchstart", (e) => { inicioX = e.touches[0].clientX; }, { passive: true });
  $("promos").addEventListener("touchend", (e) => {
    if (inicioX === null) return;
    const dx = e.changedTouches[0].clientX - inicioX;
    if (Math.abs(dx) > 40) { ir(actual + (dx < 0 ? 1 : -1)); reiniciar(); }
    inicioX = null;
  });
  $("promos").addEventListener("mouseenter", () => clearInterval(reloj));
  $("promos").addEventListener("mouseleave", reiniciar);
  ir(0);
  reiniciar();
}

/* ---------- Productos ---------- */

function cinta(p) {
  if (p.agotado) return el("span", { class: "prod-cinta" }, "Agotado");
  if (p.tipo === "combo") return el("span", { class: "prod-cinta combo" }, "Combo");
  if (p.maximo !== null && p.maximo <= 5) return el("span", { class: "prod-cinta pocas" }, `Quedan ${p.maximo}`);
  return null;
}

function tarjeta(p) {
  const art = el("article", { class: p.agotado ? "prod sin-stock" : "prod" });
  art.append(el("img", { src: p.foto, alt: p.nombre, width: 300, height: 200, loading: "lazy" }));
  const marca = cinta(p);
  if (marca) art.append(marca);
  const cuerpo = el("div", { class: "prod-cuerpo" });
  cuerpo.append(el("p", { class: "prod-cat" }, p.categoria), el("h3", {}, p.nombre), el("p", { class: "prod-desc" }, p.descripcion));
  const pie = el("div", { class: "prod-pie" });
  pie.append(el("span", { class: "prod-precio" }, pesos(p.precio)),
    p.agotado ? el("span", { class: "agotado" }, "Vuelve mañana") : el("a", { class: "btn btn-rojo", href: "/pedir" }, "Pedir"));
  cuerpo.append(pie);
  art.append(cuerpo);
  return art;
}

function pintarProductos() {
  const posicion = (c) => (ORDEN.includes(c) ? ORDEN.indexOf(c) : ORDEN.length);
  const nombres = [...new Set(productos.map((p) => p.categoria))].sort((a, b) => posicion(a) - posicion(b));
  const cuenta = (c) => (c === "Todos" ? productos.length : productos.filter((p) => p.categoria === c).length);
  $("pestanas").replaceChildren(...["Todos", ...nombres].map((c) => {
    const b = el("button", { type: "button", class: "pestana", "aria-pressed": String(c === categoria) }, c);
    b.append(el("span", {}, String(cuenta(c))));
    b.addEventListener("click", () => { categoria = c; pintarProductos(); });
    return b;
  }));
  $("rejilla").replaceChildren(...productos.filter((p) => categoria === "Todos" || p.categoria === categoria).map(tarjeta));
}

function pintarCombos(combos) {
  $("combos").hidden = combos.length === 0;
  $("lista-combos").replaceChildren(...combos.map((c) => {
    const art = el("article", { class: c.agotado ? "combo sin-stock" : "combo" });
    art.append(el("img", { src: c.foto, alt: c.nombre, loading: "lazy" }));
    const cuerpo = el("div", { class: "combo-cuerpo" });
    const lista = el("ul");
    c.incluye.forEach((i) => lista.append(el("li", {}, `${i.cantidad} ${i.nombre}`)));
    const precio = el("p", { class: "combo-precio" });
    precio.append(el("strong", {}, pesos(c.precio)));
    const normal = precioNormal(c);
    if (normal > c.precio) precio.append(el("s", {}, pesos(normal)), el("span", { class: "ahorro" }, `¡ahorras ${pesos(normal - c.precio)}!`));
    cuerpo.append(el("h3", {}, c.nombre), lista, precio,
      c.agotado ? el("span", { class: "agotado" }, "Agotado por hoy") : el("a", { class: "btn btn-rojo", href: "/pedir" }, "Pedir este combo"));
    art.append(cuerpo);
    return art;
  }));
}

async function cargarCatalogo() {
  try {
    const r = await fetch("/api/productos");
    if (!r.ok) throw new Error(String(r.status));
    productos = await r.json();
    const combos = productos.filter((p) => p.tipo === "combo");
    $("estado-productos").hidden = productos.length > 0;
    if (!productos.length) $("estado-productos").textContent = "Hoy todavía no hay productos publicados. Vuelve en un rato.";
    $("cifra-productos").textContent = String(productos.filter((p) => !p.agotado).length);
    pintarProductos();
    pintarCombos(combos);
    iniciarOfertas(combos);
    iniciarCarrusel(combos);
  } catch {
    $("estado-productos").textContent = "No se pudo cargar el catálogo. Recarga la página en un momento.";
    iniciarOfertas([]);
  }
}

/* ---------- Estado del pedido ---------- */

const enHora = (fecha, opciones) => new Date(fecha).toLocaleString("es-CO", { timeZone: ZONA, ...opciones });

function mostrarError(id, texto) {
  $(id).textContent = texto;
  $(id).hidden = !texto;
}

function pintarPedido(p) {
  const info = ESTADOS[p.estado];
  const cab = el("div", { class: "res-cab" });
  cab.append(el("span", { class: `estado-pill ${p.estado}` }, info.pill), el("span", { class: "res-numero" }, p.id));
  const hora = el("p");
  hora.append("Recogida: ", el("strong", {}, `${enHora(p.hora_recogida, { weekday: "long", day: "numeric", month: "long" })}, ${enHora(p.hora_recogida, { hour: "numeric", minute: "2-digit" })}`));
  const pasos = p.estado === "cancelado" ? ["recibido", "cancelado"] : ["recibido", "listo", "entregado"];
  const nombres = { recibido: "Recibido", listo: "Listo", entregado: "Entregado", cancelado: "Cancelado" };
  const linea = el("ol", { class: "linea" });
  pasos.forEach((estado) => {
    const paso = p.historial.find((h) => h.estado === estado);
    const li = el("li", paso ? { class: estado === "cancelado" ? "hecho cancelado" : "hecho" } : {});
    li.append(el("strong", {}, nombres[estado]),
      el("small", {}, paso ? enHora(paso.en, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "Pendiente"));
    linea.append(li);
  });
  const items = el("ul", { class: "res-items" });
  p.items.forEach((i) => items.append(el("li", {}, `${i.cantidad} ${i.nombre}`)));
  const total = el("p", { class: "res-total" });
  total.append(el("span", {}, "Pagas al recoger"), el("strong", {}, pesos(p.total)));
  $("resultado").replaceChildren(cab, el("h3", {}, `Hola, ${p.nombre}`), el("p", {}, info.texto), hora, linea, items, total);
}

$("form-consulta").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const numero = $("consulta-numero").value.trim();
  const telefono = $("consulta-telefono").value.replace(/\D/g, "");
  if (numero.length < 6) return mostrarError("error-consulta", "Escribe el número de pedido que te dimos al confirmarlo.");
  if (!/^[0-9]{7,10}$/.test(telefono)) return mostrarError("error-consulta", "Escribe el teléfono con el que hiciste el pedido, de 7 a 10 dígitos.");
  mostrarError("error-consulta", "");
  $("consultar").disabled = true;
  try {
    const r = await fetch(`/api/pedidos/consulta?${new URLSearchParams({ numero, telefono })}`);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return mostrarError("error-consulta", typeof data.detail === "string" ? data.detail : "Revisa los datos e inténtalo de nuevo.");
    pintarPedido(data);
  } catch {
    mostrarError("error-consulta", "Sin conexión. Revisa tu internet e inténtalo de nuevo.");
  } finally {
    $("consultar").disabled = false;
  }
});

/* ---------- Visítanos ---------- */

$("direccion").textContent = NEGOCIO.direccion;
$("horario").replaceChildren(...NEGOCIO.horario.flatMap(([dias, horas]) => [el("dt", {}, dias), el("dd", {}, horas)]));
$("como-llegar").href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(NEGOCIO.direccion)}`;

/* ---------- Contacto ---------- */

$("form-contacto").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  mostrarError("error-contacto", "");
  $("ok-contacto").hidden = true;
  const datos = {
    nombre: $("contacto-nombre").value.trim(),
    contacto: $("contacto-medio").value.trim(),
    asunto: $("contacto-asunto").value,
    mensaje: $("contacto-mensaje").value.trim(),
    sitio: $("contacto-sitio").value,
  };
  if (datos.nombre.length < 2) return mostrarError("error-contacto", "Escribe tu nombre.");
  if (datos.contacto.length < 5) return mostrarError("error-contacto", "Déjanos un teléfono o un correo para responderte.");
  if (datos.mensaje.length < 5) return mostrarError("error-contacto", "Cuéntanos qué necesitas.");
  $("enviar-contacto").disabled = true;
  try {
    const r = await fetch("/api/mensajes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) });
    if (!r.ok) throw new Error(String(r.status));
    $("form-contacto").reset();
    $("ok-contacto").textContent = `Listo, ${datos.nombre.split(" ")[0]}. Te respondemos pronto.`;
    $("ok-contacto").hidden = false;
  } catch {
    mostrarError("error-contacto", "El mensaje no se envió. Inténtalo de nuevo en un momento.");
  } finally {
    $("enviar-contacto").disabled = false;
  }
});

/* ---------- Inicio ---------- */

cargarCatalogo();

// Desde la confirmación de la tienda llega con el número ya escrito.
const numeroPedido = new URLSearchParams(location.search).get("pedido");
if (numeroPedido) {
  $("consulta-numero").value = numeroPedido;
  $("consulta-telefono").focus({ preventScroll: true });
}
