// Panel del personal: sesión con usuario y contraseña, pedidos, catálogo, reportes y usuarios.
const $ = (id) => document.getElementById(id);
const pesos = (n) => "$" + Math.round(n).toLocaleString("es-CO");
const ZONA = "America/Bogota";
const ESTADOS = ["recibido", "listo", "entregado", "cancelado"];
const NOMBRE_ESTADO = { recibido: "Recibido", listo: "Listo", entregado: "Entregado", cancelado: "Cancelado" };
const ACCION_ESTADO = { listo: "Marcar listo", entregado: "Entregar", cancelado: "Cancelar" };
const NOMBRE_ROL = { dueno: "Dueño", administrador: "Administrador", empleado: "Empleado" };
const CLAVE_SESION = "pandelacasa.sesion";

let sesion = null;
let pedidos = [];
let filtroPedidos = "pendientes";
let productos = [];
let fotos = [];
let editando = null;
let recargaPedidos = null;

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text !== "") node.textContent = text;
  return node;
}

function boton(texto, clase, accion) {
  const b = el("button", { type: "button", class: clase }, texto);
  b.addEventListener("click", accion);
  return b;
}

function avisar(texto) {
  $("aviso").textContent = texto;
  clearTimeout(avisar.t);
  avisar.t = setTimeout(() => { $("aviso").textContent = ""; }, 6000);
}

function mostrarError(id, texto) {
  $(id).textContent = texto;
  $(id).hidden = !texto;
}

function detalle(data) {
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => `${(d.loc || []).slice(-1)[0] || "dato"}: ${d.msg}`).join(". ");
  }
  return "No se pudo completar la acción.";
}

/* ---------- Sesión ---------- */

async function api(url, opciones = {}) {
  const headers = { ...(opciones.headers || {}) };
  if (sesion) headers.Authorization = `Bearer ${sesion.token}`;
  if (opciones.body) headers["Content-Type"] = "application/json";
  const r = await fetch(url, { ...opciones, headers, body: opciones.body ? JSON.stringify(opciones.body) : undefined });
  if (r.status === 401 && sesion) {
    cerrarLocal("Tu sesión terminó. Vuelve a ingresar.");
    throw new Error("sin sesión");
  }
  const data = r.status === 204 ? {} : await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(detalle(data)), { status: r.status });
  return data;
}

function guardarSesion(s) {
  sesion = s;
  try { sessionStorage.setItem(CLAVE_SESION, JSON.stringify(s)); } catch { /* sin almacenamiento */ }
}

function cerrarLocal(mensaje = "") {
  sesion = null;
  clearInterval(recargaPedidos);
  try { sessionStorage.removeItem(CLAVE_SESION); } catch { /* sin almacenamiento */ }
  $("panel").hidden = true;
  $("sesion").hidden = true;
  $("acceso").hidden = false;
  mostrarError("error-acceso", mensaje);
}

async function entrar(evento) {
  evento.preventDefault();
  const correo = $("correo").value.trim();
  const clave = $("clave").value;
  if (!correo || !clave) return mostrarError("error-acceso", "Escribe tu correo y tu contraseña.");
  $("entrar").disabled = true;
  try {
    guardarSesion(await api("/api/auth/login", { method: "POST", body: { correo, clave } }));
    $("clave").value = "";
    abrirPanel();
  } catch (e) {
    mostrarError("error-acceso", e.status ? e.message : "Sin conexión. Inténtalo de nuevo.");
  } finally {
    $("entrar").disabled = false;
  }
}

async function salir() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch { /* la sesión ya no existe */ }
  cerrarLocal();
}

function puede(roles) {
  return !roles || roles.split(" ").includes(sesion.usuario.rol);
}

function abrirPanel() {
  $("acceso").hidden = true;
  $("panel").hidden = false;
  $("sesion").hidden = false;
  mostrarError("error-acceso", "");
  $("quien").textContent = sesion.usuario.nombre;
  $("rol").textContent = NOMBRE_ROL[sesion.usuario.rol];
  [...$("tabs").children].forEach((b) => { b.hidden = !puede(b.dataset.roles); });
  abrirTab("pedidos");
  clearInterval(recargaPedidos);
  revisarMensajes();
  recargaPedidos = setInterval(() => {
    if (!$("tab-pedidos").hidden) cargarPedidos(true);
    revisarMensajes();
  }, 60000);
}

function abrirTab(nombre) {
  [...$("tabs").children].forEach((b) => b.setAttribute("aria-current", String(b.dataset.tab === nombre)));
  document.querySelectorAll(".tab").forEach((s) => { s.hidden = s.id !== `tab-${nombre}`; });
  ({ pedidos: cargarPedidos, catalogo: cargarCatalogo, reportes: iniciarReportes,
    mensajes: cargarMensajes, usuarios: cargarUsuarios, cuenta: () => {} })[nombre]();
}

/* ---------- Pedidos ---------- */

const enHora = (fecha, opciones) => new Date(fecha).toLocaleString("es-CO", { timeZone: ZONA, ...opciones });

async function cargarPedidos(silencioso = false) {
  try {
    const lista = await api("/api/pedidos");
    pedidos = lista.sort((a, b) => new Date(a.hora_recogida) - new Date(b.hora_recogida));
    pintarPedidos();
  } catch (e) {
    if (!silencioso && e.status !== undefined) avisar(e.message);
  }
}

function pintarPedidos() {
  ESTADOS.forEach((e) => { $(`n-${e}`).textContent = String(pedidos.filter((p) => p.estado === e).length); });
  const filtros = { pendientes: "Pendientes", todos: "Todos", ...NOMBRE_ESTADO };
  $("filtros").replaceChildren(...Object.entries(filtros).map(([clave, texto]) => {
    const chip = boton(texto, "chip", () => { filtroPedidos = clave; pintarPedidos(); });
    chip.setAttribute("aria-pressed", String(clave === filtroPedidos));
    return chip;
  }));
  const visibles = pedidos.filter((p) => filtroPedidos === "todos"
    || (filtroPedidos === "pendientes" ? ["recibido", "listo"].includes(p.estado) : p.estado === filtroPedidos));
  const filas = visibles.map(filaPedido);
  if (!filas.length) {
    const td = el("td", { colspan: 7, class: "vacio" }, pedidos.length ? "No hay pedidos en esta vista." : "Todavía no hay pedidos.");
    filas.push(el("tr")); filas[0].append(td);
  }
  $("filas-pedidos").replaceChildren(...filas);
}

function filaPedido(p) {
  const recogida = new Date(p.hora_recogida);
  const minutos = (recogida - Date.now()) / 60000;
  const urgente = ["recibido", "listo"].includes(p.estado) && minutos <= 30;
  const tr = el("tr", urgente ? { class: "pronto" } : {});

  const id = el("td");
  id.append(el("span", { class: "code" }, p.id));
  const hora = el("td");
  hora.append(el("strong", {}, enHora(recogida, { hour: "numeric", minute: "2-digit" })),
    el("small", {}, enHora(recogida, { weekday: "short", day: "numeric", month: "short" })));
  const cliente = el("td", {}, p.nombre);
  cliente.append(el("small", {}, p.telefono));
  const prods = el("td");
  p.items.forEach((i) => {
    const linea = el("div", {}, `${i.cantidad} × ${i.nombre}`);
    if (i.incluye) linea.append(el("small", {}, i.incluye));
    prods.append(linea);
  });
  const total = el("td");
  total.append(el("strong", {}, pesos(p.total)));
  const estado = el("td");
  estado.append(el("span", { class: `pill ${p.estado}` }, NOMBRE_ESTADO[p.estado]));
  const ultimo = p.historial[p.historial.length - 1];
  if (ultimo && ultimo.por !== "cliente") {
    estado.append(el("small", {}, `${enHora(ultimo.en, { hour: "numeric", minute: "2-digit" })} · ${ultimo.por.split("@")[0]}`));
  }
  const acciones = el("td", { class: "acciones-fila" });
  p.siguientes.forEach((s) => {
    acciones.append(boton(ACCION_ESTADO[s], s === "cancelado" ? "peligro" : "", () => moverPedido(p, s)));
  });
  if (!p.siguientes.length) acciones.append(el("small", {}, "Cerrado"));
  tr.append(id, hora, cliente, prods, total, estado, acciones);
  return tr;
}

async function moverPedido(p, estado) {
  if (estado === "cancelado" && !confirm(`¿Cancelar el pedido ${p.id} de ${p.nombre}? Esta acción no se puede deshacer y las unidades vuelven al inventario.`)) return;
  if (estado === "entregado" && !confirm(`¿Confirmas que ${p.nombre} recogió y pagó el pedido ${p.id}?`)) return;
  try {
    const nuevo = await api(`/api/pedidos/${p.id}`, { method: "PATCH", body: { estado } });
    pedidos = pedidos.map((x) => (x.id === nuevo.id ? nuevo : x));
    pintarPedidos();
    avisar(`Pedido ${nuevo.id}: ${NOMBRE_ESTADO[nuevo.estado]}.`);
  } catch (e) {
    if (e.status !== undefined) { avisar(e.message); cargarPedidos(true); }
  }
}

/* ---------- Catálogo ---------- */

async function cargarCatalogo() {
  try {
    [productos, fotos] = await Promise.all([api("/api/admin/productos"), api("/api/admin/fotos")]);
    pintarCatalogo();
  } catch (e) {
    if (e.status !== undefined) avisar(e.message);
  }
}

function estadoProducto(p) {
  if (!p.disponible) return ["Oculto", "cancelado"];
  if (p.agotado) return ["Agotado", "recibido"];
  return ["A la venta", "entregado"];
}

function pintarCatalogo() {
  $("filas-catalogo").replaceChildren(...productos.map((p) => {
    const tr = el("tr", p.disponible ? {} : { class: "apagado" });
    const nombre = el("td", { class: "producto" });
    nombre.append(el("img", { src: p.foto, alt: "", width: 60, height: 40 }));
    const texto = el("div");
    texto.append(el("strong", {}, p.nombre), el("small", {}, p.tipo === "combo"
      ? `Combo · ${p.incluye.map((c) => `${c.cantidad} ${c.nombre}`).join(", ")}` : p.categoria));
    nombre.append(texto);
    const precio = el("td", {}, pesos(p.precio));

    const unidades = el("td");
    if (p.tipo === "combo") {
      unidades.append(el("span", {}, p.maximo === null ? "Sin límite" : `Alcanza para ${p.maximo}`));
    } else {
      const input = el("input", { type: "number", min: 0, max: 10000, step: 1, class: "mini",
        "aria-label": `Unidades de ${p.nombre}`, placeholder: "Sin límite" });
      input.value = p.unidades ?? "";
      input.addEventListener("change", () => {
        const valor = input.value === "" ? null : Number(input.value);
        guardarProducto(p.id, { unidades: valor }, valor === null ? "sin control de inventario" : `${valor} unidades`);
      });
      unidades.append(input);
    }
    const [textoEstado, clase] = estadoProducto(p);
    const estado = el("td");
    estado.append(el("span", { class: `pill ${clase}` }, textoEstado));

    const acciones = el("td", { class: "acciones-fila" });
    acciones.append(boton("Editar", "sec", () => abrirEditor(p)));
    if (p.tipo === "producto" && !p.agotado) {
      acciones.append(boton("Marcar agotado", "sec", () => guardarProducto(p.id, { unidades: 0 }, "agotado")));
    }
    acciones.append(boton(p.disponible ? "Ocultar" : "Mostrar", "sec",
      () => guardarProducto(p.id, { disponible: !p.disponible }, p.disponible ? "oculto en la tienda" : "visible en la tienda")));
    acciones.append(boton("Eliminar", "peligro", () => eliminarProducto(p)));
    tr.append(nombre, precio, unidades, estado, acciones);
    return tr;
  }));
}

async function guardarProducto(id, cambios, descripcion) {
  try {
    const nuevo = await api(`/api/admin/productos/${id}`, { method: "PATCH", body: cambios });
    // Un cambio de unidades puede agotar combos, así que se recarga todo el catálogo.
    productos = await api("/api/admin/productos");
    pintarCatalogo();
    avisar(`${nuevo.nombre}: ${descripcion}.`);
  } catch (e) {
    if (e.status !== undefined) { avisar(e.message); pintarCatalogo(); }
  }
}

async function eliminarProducto(p) {
  const aviso = [
    `¿Eliminar "${p.nombre}" del catálogo?`,
    "Deja de aparecer en la tienda y en el panel. Los pedidos que ya lo incluyen lo conservan. Esta acción no se puede deshacer.",
    "Si solo quieres sacarlo un tiempo, usa Ocultar.",
  ].join("\n\n");
  if (!confirm(aviso)) return;
  try {
    await api(`/api/admin/productos/${p.id}`, { method: "DELETE" });
    productos = await api("/api/admin/productos");
    pintarCatalogo();
    avisar(`${p.nombre} se eliminó del catálogo.`);
  } catch (e) {
    if (e.status !== undefined) avisar(e.message);
  }
}

function filaComponente(c = {}) {
  const fila = el("div", { class: "componente" });
  const select = el("select", { "aria-label": "Producto del combo" });
  productos.filter((p) => p.tipo === "producto").forEach((p) => {
    select.append(new Option(p.nombre, p.id, false, p.id === c.producto_id));
  });
  const cantidad = el("input", { type: "number", min: 1, max: 20, step: 1, class: "mini", "aria-label": "Cantidad" });
  cantidad.value = c.cantidad || 1;
  fila.append(select, cantidad, boton("Quitar", "sec", () => fila.remove()));
  return fila;
}

function abrirEditor(p = null, tipo = "producto") {
  editando = p;
  tipo = p ? p.tipo : tipo;
  $("e-titulo").textContent = p ? `Editar ${p.nombre}` : (tipo === "combo" ? "Nuevo combo" : "Nuevo producto");
  $("form-producto").dataset.tipo = tipo;
  mostrarError("error-producto", "");
  $("p-nombre").value = p?.nombre || "";
  $("p-descripcion").value = p?.descripcion || "";
  $("p-categoria").value = p?.categoria || (tipo === "combo" ? "Combos" : "");
  $("p-precio").value = p?.precio || "";
  $("categorias-lista").replaceChildren(...[...new Set(productos.map((x) => x.categoria))].map((c) => new Option(c)));
  elegirFoto(p?.foto || "");
  estadoFoto("La tienda la muestra recortada en formato horizontal (3:2).");
  $("p-galeria-caja").open = false;
  $("p-inventario").hidden = tipo === "combo";
  $("p-sin-limite").checked = p ? p.unidades === null : false;
  $("p-unidades").value = p?.unidades ?? (p ? "" : 0);
  $("p-unidades").disabled = $("p-sin-limite").checked;
  $("p-componentes-caja").hidden = tipo !== "combo";
  $("p-componentes").replaceChildren(...(tipo === "combo"
    ? (p?.componentes?.length ? p.componentes : [{}, {}]).map(filaComponente) : []));
  pintarVista();
  $("editor").showModal();
}

/* ---------- Foto del producto ---------- */

const ANCHO_FOTO = 1200;
const ALTO_FOTO = 800;
const MAXIMO_ORIGINAL = 15 * 1024 * 1024;

function estadoFoto(texto, error = false) {
  $("p-foto-estado").textContent = texto;
  $("p-foto-estado").classList.toggle("error", error);
}

function elegirFoto(url) {
  $("p-foto").value = url;
  if (url) $("p-foto-vista").src = url; else $("p-foto-vista").removeAttribute("src");
  $("p-zona").classList.toggle("sin-foto", !url);
  pintarGaleria();
  pintarVista();
}

function pintarGaleria() {
  const actual = $("p-foto").value;
  $("p-galeria").replaceChildren(...fotos.map((f) => {
    const b = el("button", { type: "button", "aria-pressed": String(f === actual), title: f.split("/").pop() });
    b.append(el("img", { src: f, alt: "", loading: "lazy" }));
    b.addEventListener("click", () => {
      elegirFoto(f);
      estadoFoto("Foto elegida de las guardadas.");
    });
    return b;
  }));
}

// Recorta al centro en 3:2 y la deja en 1200 x 800 px como JPG, el mismo formato de la tienda.
async function prepararFoto(archivo) {
  const imagen = await createImageBitmap(archivo);
  // El trozo más grande en 3:2 que cabe en la foto, tomado del centro.
  const proporcion = Math.min(imagen.width / ANCHO_FOTO, imagen.height / ALTO_FOTO);
  const corteAncho = ANCHO_FOTO * proporcion;
  const corteAlto = ALTO_FOTO * proporcion;
  const lienzo = document.createElement("canvas");
  lienzo.width = Math.min(ANCHO_FOTO, Math.round(corteAncho));
  lienzo.height = Math.round(lienzo.width * ALTO_FOTO / ANCHO_FOTO);
  const ctx = lienzo.getContext("2d");
  ctx.fillStyle = "#fff"; // las partes transparentes de un PNG quedan blancas
  ctx.fillRect(0, 0, lienzo.width, lienzo.height);
  ctx.drawImage(imagen, (imagen.width - corteAncho) / 2, (imagen.height - corteAlto) / 2, corteAncho, corteAlto,
    0, 0, lienzo.width, lienzo.height);
  imagen.close();
  return lienzo.toDataURL("image/jpeg", 0.85);
}

async function subirFoto(archivo) {
  if (!["image/jpeg", "image/png", "image/webp"].includes(archivo.type)) {
    return estadoFoto("Ese archivo no es una foto. Usa un JPG, PNG o WebP.", true);
  }
  if (archivo.size > MAXIMO_ORIGINAL) {
    return estadoFoto("La foto pesa más de 15 MB. Elige una más liviana.", true);
  }
  $("p-zona").classList.add("cargando");
  estadoFoto(`Subiendo ${archivo.name}…`);
  try {
    const datos = await prepararFoto(archivo);
    $("p-foto-vista").src = datos;
    $("p-zona").classList.remove("sin-foto");
    const { url } = await api("/api/admin/fotos", { method: "POST", body: { nombre: archivo.name, datos } });
    fotos = [url, ...fotos];
    elegirFoto(url);
    estadoFoto(`Listo, ${archivo.name} quedó guardada. Se usa al guardar el producto.`);
  } catch (e) {
    elegirFoto($("p-foto").value);
    estadoFoto(e.status ? e.message : "No se pudo leer la foto. Prueba con otra.", true);
  } finally {
    $("p-zona").classList.remove("cargando");
  }
}

/* ---------- Vista previa de la tarjeta ---------- */

function pintarVista() {
  const tipo = $("form-producto").dataset.tipo;
  const precio = Number($("p-precio").value);
  const sinLimite = $("p-sin-limite").checked;
  const unidades = Number($("p-unidades").value || 0);
  const agotado = tipo !== "combo" && !sinLimite && unidades <= 0;
  const nombre = $("p-nombre").value.trim() || "Nombre del producto";
  const card = el("article", { class: agotado ? "card sin-stock" : "card" });
  card.append($("p-foto").value
    ? el("img", { src: $("p-foto").value, alt: "", width: 240, height: 160 })
    : el("div", { class: "foto-vacia" }, "Aquí va la foto"));
  const body = el("div", { class: "card-body" });
  body.append(el("p", { class: "cat" }, $("p-categoria").value.trim() || "Categoría"), el("h3", {}, nombre),
    el("p", { class: "desc" }, $("p-descripcion").value.trim() || "Descripción corta del producto."));
  if (tipo === "combo") {
    const partes = [...$("p-componentes").children].map((f) => {
      const elegido = productos.find((x) => x.id === f.querySelector("select").value);
      return elegido ? `${Number(f.querySelector("input").value) || 1} ${elegido.nombre}` : null;
    }).filter(Boolean);
    if (partes.length) body.append(el("p", { class: "incluye" }, "Incluye " + partes.join(", ")));
  } else if (!agotado && !sinLimite && unidades <= 5) {
    body.append(el("p", { class: "quedan" }, unidades === 1 ? "Queda 1" : `Quedan ${unidades}`));
  }
  const row = el("div", { class: "row" });
  row.append(el("span", { class: "precio" }, precio >= 100 ? pesos(precio) : "$0"),
    agotado ? el("span", { class: "agotado" }, "Agotado") : el("button", { type: "button", tabindex: "-1" }, "Agregar"));
  body.append(row);
  card.append(body);
  $("p-vista-tarjeta").replaceChildren(card);
}

async function guardarEditor(evento) {
  evento.preventDefault();
  const tipo = $("form-producto").dataset.tipo;
  const datos = {
    nombre: $("p-nombre").value.trim(),
    descripcion: $("p-descripcion").value.trim(),
    categoria: $("p-categoria").value.trim(),
    precio: Number($("p-precio").value),
    foto: $("p-foto").value,
  };
  if (!datos.foto) return mostrarError("error-producto", "Sube una foto o elige una de las guardadas.");
  if (datos.nombre.length < 2 || datos.descripcion.length < 2 || datos.categoria.length < 2) {
    return mostrarError("error-producto", "Completa nombre, descripción y categoría.");
  }
  if (!Number.isInteger(datos.precio) || datos.precio < 100) {
    return mostrarError("error-producto", "El precio debe ser un número entero de al menos $100.");
  }
  if (tipo === "combo") {
    datos.componentes = [...$("p-componentes").children].map((f) => ({
      producto_id: f.querySelector("select").value, cantidad: Number(f.querySelector("input").value),
    }));
  } else {
    datos.unidades = $("p-sin-limite").checked ? null : Number($("p-unidades").value || 0);
  }
  $("p-guardar").disabled = true;
  try {
    const nuevo = editando
      ? await api(`/api/admin/productos/${editando.id}`, { method: "PATCH", body: datos })
      : await api("/api/admin/productos", { method: "POST", body: { ...datos, tipo } });
    $("editor").close();
    productos = await api("/api/admin/productos");
    pintarCatalogo();
    avisar(`${nuevo.nombre} guardado.`);
  } catch (e) {
    if (e.status !== undefined) mostrarError("error-producto", e.message);
  } finally {
    $("p-guardar").disabled = false;
  }
}

/* ---------- Reportes ---------- */

const hoyBogota = () => new Date().toLocaleDateString("en-CA", { timeZone: ZONA });
const desplazar = (fecha, dias) => {
  const d = new Date(`${fecha}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + dias);
  return d.toISOString().slice(0, 10);
};

// Los pedidos se cuentan por fecha de recogida, que puede ser futura: cada período va completo.
function rangoDe(periodo) {
  const hoy = hoyBogota();
  const d = new Date(`${hoy}T12:00:00Z`);
  if (periodo === "hoy") return [hoy, hoy];
  if (periodo === "semana") {
    const lunes = desplazar(hoy, -((d.getUTCDay() + 6) % 7));
    return [lunes, desplazar(lunes, 6)];
  }
  if (periodo === "mes") {
    const ultimo = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).toISOString().slice(0, 10);
    return [`${hoy.slice(0, 8)}01`, ultimo];
  }
  if (periodo === "anio") return [`${hoy.slice(0, 4)}-01-01`, `${hoy.slice(0, 4)}-12-31`];
  if (periodo === "30") return [desplazar(hoy, -29), hoy];
  return null;
}

let periodoActual = "mes";

function iniciarReportes() {
  const opciones = { hoy: "Hoy", semana: "Esta semana", mes: "Este mes", 30: "Últimos 30 días", anio: "Este año" };
  $("periodos").replaceChildren(...Object.entries(opciones).map(([clave, texto]) => {
    const chip = boton(texto, "chip", () => { periodoActual = clave; iniciarReportes(); });
    chip.setAttribute("aria-pressed", String(clave === periodoActual));
    return chip;
  }));
  const rango = rangoDe(periodoActual);
  if (rango) [$("desde").value, $("hasta").value] = rango;
  cargarReporte();
}

async function cargarReporte() {
  const desde = $("desde").value;
  const hasta = $("hasta").value;
  if (!desde || !hasta) return avisar("Elige las dos fechas del reporte.");
  try {
    const r = await api(`/api/admin/reportes?desde=${desde}&hasta=${hasta}`);
    pintarReporte(r);
  } catch (e) {
    if (e.status !== undefined) avisar(e.message);
  }
}

function fechaLarga(iso) {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("es-CO", { timeZone: "UTC", day: "numeric", month: "long", year: "numeric" });
}

function pintarReporte(r) {
  $("rango-texto").textContent = r.desde === r.hasta
    ? `Reporte del ${fechaLarga(r.desde)} · ${r.total_pedidos} pedidos en total`
    : `Del ${fechaLarga(r.desde)} al ${fechaLarga(r.hasta)} · ${r.total_pedidos} pedidos en total`;
  $("r-ventas").textContent = pesos(r.ventas);
  $("r-entregados").textContent = String(r.entregados);
  $("r-ticket").textContent = pesos(r.ticket_promedio);
  $("r-unidades").textContent = String(r.unidades_vendidas);

  $("r-estados").replaceChildren(...ESTADOS.map((e) => {
    const tr = el("tr");
    const nombre = el("td");
    nombre.append(el("span", { class: `pill ${e}` }, NOMBRE_ESTADO[e]));
    tr.append(nombre, el("td", {}, String(r.por_estado[e].pedidos)), el("td", {}, pesos(r.por_estado[e].dinero)));
    return tr;
  }));
  const top = r.productos.map((p) => {
    const tr = el("tr");
    tr.append(el("td", {}, p.nombre), el("td", {}, String(p.cantidad)), el("td", {}, pesos(p.dinero)));
    return tr;
  });
  if (!top.length) {
    const tr = el("tr");
    tr.append(el("td", { colspan: 3, class: "vacio" }, "Sin ventas entregadas en este período."));
    top.push(tr);
  }
  $("r-productos").replaceChildren(...top);

  $("r-serie-titulo").textContent = r.agrupacion === "dia" ? "Ventas por día" : "Ventas por mes";
  const maximo = Math.max(1, ...r.serie.map((s) => s.ventas));
  // Con muchos días solo se rotulan algunas fechas para que la gráfica quepa.
  const cada = Math.ceil(r.serie.length / 12);
  $("r-serie-tope").textContent = r.ventas ? `Máximo: ${pesos(Math.max(...r.serie.map((s) => s.ventas)))}` : "Sin ventas en el período";
  $("r-serie").replaceChildren(...r.serie.map((s, i) => {
    const etiqueta = r.agrupacion === "dia"
      ? new Date(`${s.periodo}T12:00:00Z`).toLocaleDateString("es-CO", { timeZone: "UTC", day: "numeric", month: "short" })
      : new Date(`${s.periodo}-15T12:00:00Z`).toLocaleDateString("es-CO", { timeZone: "UTC", month: "short" });
    const col = el("div", { class: "barra", title: `${etiqueta}: ${pesos(s.ventas)} en ${s.pedidos} pedidos` });
    const relleno = el("span", { class: "relleno" });
    relleno.style.height = `${Math.round((s.ventas / maximo) * 100)}%`;
    col.append(relleno, el("small", {}, i % cada === 0 ? etiqueta : ""));
    return col;
  }));
}

/* ---------- Mensajes ---------- */

const ASUNTO = { pedido: "Sobre un pedido", encargo: "Encargo especial", sugerencia: "Sugerencia", otro: "Otro" };

function contarNoLeidos(mensajes) {
  const n = mensajes.filter((m) => !m.leido).length;
  $("no-leidos").textContent = String(n);
  $("no-leidos").hidden = n === 0;
}

async function revisarMensajes() {
  if (!puede("dueno administrador")) return;
  try { contarNoLeidos(await api("/api/admin/mensajes")); } catch { /* se reintenta en la próxima revisión */ }
}

async function cargarMensajes() {
  try {
    const mensajes = await api("/api/admin/mensajes");
    contarNoLeidos(mensajes);
    const filas = mensajes.map((m) => {
      const tr = el("tr", m.leido ? { class: "leido" } : {});
      const cuando = el("td");
      cuando.append(el("strong", {}, enHora(m.creado_en, { day: "numeric", month: "short" })),
        el("small", {}, enHora(m.creado_en, { hour: "numeric", minute: "2-digit" })));
      const de = el("td", {}, m.nombre);
      de.append(el("small", {}, m.contacto));
      const texto = el("td", { class: "mensaje" }, m.mensaje);
      const acciones = el("td", { class: "acciones-fila" });
      acciones.append(
        boton(m.leido ? "Marcar sin leer" : "Marcar leído", "sec", () => marcarMensaje(m, !m.leido)),
        boton("Eliminar", "peligro", () => borrarMensaje(m)));
      tr.append(cuando, de, el("td", {}, ASUNTO[m.asunto]), texto, acciones);
      return tr;
    });
    if (!filas.length) {
      const tr = el("tr");
      tr.append(el("td", { colspan: 5, class: "vacio" }, "No hay mensajes."));
      filas.push(tr);
    }
    $("filas-mensajes").replaceChildren(...filas);
  } catch (e) {
    if (e.status !== undefined) avisar(e.message);
  }
}

async function marcarMensaje(m, leido) {
  try { await api(`/api/admin/mensajes/${m.id}`, { method: "PATCH", body: { leido } }); } catch (e) { if (e.status !== undefined) avisar(e.message); }
  cargarMensajes();
}

async function borrarMensaje(m) {
  if (!confirm(`¿Eliminar el mensaje de ${m.nombre}? No se puede deshacer.`)) return;
  try { await api(`/api/admin/mensajes/${m.id}`, { method: "DELETE" }); avisar("Mensaje eliminado."); } catch (e) { if (e.status !== undefined) avisar(e.message); }
  cargarMensajes();
}

/* ---------- Usuarios ---------- */

async function cargarUsuarios() {
  try {
    const usuarios = await api("/api/usuarios");
    $("filas-usuarios").replaceChildren(...usuarios.map(filaUsuario));
  } catch (e) {
    if (e.status !== undefined) avisar(e.message);
  }
}

function filaUsuario(u) {
  const tr = el("tr", u.activo ? {} : { class: "apagado" });
  const rol = el("td");
  const acciones = el("td", { class: "acciones-fila" });
  if (u.rol === "dueno") {
    rol.append(el("strong", {}, "Dueño"));
    acciones.append(el("small", {}, "Su contraseña se cambia en Mi cuenta"));
  } else {
    const select = el("select", { "aria-label": `Rol de ${u.nombre}`, class: "mini" });
    ["empleado", "administrador"].forEach((r) => select.append(new Option(NOMBRE_ROL[r], r, false, r === u.rol)));
    select.addEventListener("change", () => cambiarUsuario(u, { rol: select.value }, `ahora es ${NOMBRE_ROL[select.value]}`));
    rol.append(select);
    acciones.append(
      boton(u.activo ? "Desactivar" : "Activar", u.activo ? "peligro" : "sec",
        () => cambiarUsuario(u, { activo: !u.activo }, u.activo ? "desactivado" : "activado")),
      boton("Nueva contraseña", "sec", () => {
        const clave = prompt(`Nueva contraseña para ${u.nombre} (mínimo 10 caracteres):`);
        if (clave) cambiarUsuario(u, { clave }, "tiene una contraseña nueva");
      }));
  }
  const estado = el("td");
  estado.append(el("span", { class: `pill ${u.activo ? "entregado" : "cancelado"}` }, u.activo ? "Activo" : "Inactivo"));
  tr.append(el("td", {}, u.nombre), el("td", {}, u.correo), rol, estado, acciones);
  return tr;
}

async function cambiarUsuario(u, cambios, descripcion) {
  try {
    await api(`/api/usuarios/${encodeURIComponent(u.correo)}`, { method: "PATCH", body: cambios });
    avisar(`${u.nombre} ${descripcion}.`);
  } catch (e) {
    if (e.status !== undefined) avisar(e.message);
  }
  cargarUsuarios();
}

async function crearUsuario(evento) {
  evento.preventDefault();
  const datos = { nombre: $("u-nombre").value.trim(), correo: $("u-correo").value.trim(),
    rol: $("u-rol").value, clave: $("u-clave").value };
  if (datos.nombre.length < 2 || !datos.correo.includes("@")) return mostrarError("error-usuario", "Escribe el nombre y un correo válido.");
  if (datos.clave.length < 10) return mostrarError("error-usuario", "La contraseña inicial necesita al menos 10 caracteres.");
  try {
    await api("/api/usuarios", { method: "POST", body: datos });
    $("form-usuario").reset();
    mostrarError("error-usuario", "");
    avisar(`${datos.nombre} ya puede ingresar como ${NOMBRE_ROL[datos.rol]}.`);
    cargarUsuarios();
  } catch (e) {
    if (e.status !== undefined) mostrarError("error-usuario", e.message);
  }
}

/* ---------- Mi cuenta ---------- */

async function cambiarClave(evento) {
  evento.preventDefault();
  const actual = $("c-actual").value;
  const nueva = $("c-nueva").value;
  if (nueva.length < 10) return mostrarError("error-clave", "La contraseña nueva necesita al menos 10 caracteres.");
  if (nueva !== $("c-repite").value) return mostrarError("error-clave", "Las dos contraseñas nuevas no coinciden.");
  try {
    await api("/api/auth/clave", { method: "POST", body: { actual, nueva } });
    $("form-clave").reset();
    mostrarError("error-clave", "");
    avisar("Contraseña actualizada.");
  } catch (e) {
    if (e.status !== undefined) mostrarError("error-clave", e.message);
  }
}

/* ---------- Inicio ---------- */

$("acceso").addEventListener("submit", entrar);
$("salir").addEventListener("click", salir);
$("tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) abrirTab(e.target.dataset.tab); });
$("actualizar").addEventListener("click", () => cargarPedidos());
$("nuevo-producto").addEventListener("click", () => abrirEditor(null, "producto"));
$("nuevo-combo").addEventListener("click", () => abrirEditor(null, "combo"));
$("form-producto").addEventListener("submit", guardarEditor);
$("p-cancelar").addEventListener("click", () => $("editor").close());
$("p-zona").addEventListener("click", () => $("p-archivo").click());
$("p-zona").addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("p-archivo").click(); }
});
$("p-archivo").addEventListener("change", () => {
  if ($("p-archivo").files[0]) subirFoto($("p-archivo").files[0]);
  $("p-archivo").value = "";
});
["dragenter", "dragover"].forEach((tipo) => $("p-zona").addEventListener(tipo, (e) => {
  e.preventDefault();
  $("p-zona").classList.add("encima");
}));
["dragleave", "drop"].forEach((tipo) => $("p-zona").addEventListener(tipo, () => $("p-zona").classList.remove("encima")));
$("p-zona").addEventListener("drop", (e) => {
  e.preventDefault();
  if (e.dataTransfer.files[0]) subirFoto(e.dataTransfer.files[0]);
});
// La vista previa sigue lo que se escribe en el editor.
$("form-producto").addEventListener("input", pintarVista);
$("form-producto").addEventListener("change", pintarVista);
$("p-componentes").addEventListener("click", () => setTimeout(pintarVista));
$("p-sin-limite").addEventListener("change", () => { $("p-unidades").disabled = $("p-sin-limite").checked; });
$("p-agregar-componente").addEventListener("click", () => $("p-componentes").append(filaComponente()));
$("rango").addEventListener("submit", (e) => { e.preventDefault(); periodoActual = "personalizado"; iniciarReportes(); });
$("form-usuario").addEventListener("submit", crearUsuario);
$("form-clave").addEventListener("submit", cambiarClave);

(async () => {
  try { sesion = JSON.parse(sessionStorage.getItem(CLAVE_SESION) || "null"); } catch { sesion = null; }
  if (!sesion) return;
  try {
    sesion.usuario = await api("/api/auth/yo");
    abrirPanel();
  } catch { /* la sesión guardada ya no sirve */ }
})();
