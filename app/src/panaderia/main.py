"""API principal de Pan de la Casa.

Define la aplicación FastAPI con la tienda pública, el inicio de sesión del personal,
la gestión de pedidos, catálogo, reportes y usuarios, y el montaje de los archivos estáticos.
"""

import base64
import binascii
import json
import logging
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pymongo import DESCENDING
from pymongo.database import Database

from . import catalogo, config, reportes
from .config import Settings
from .db import asegurar_dueno, connect, prepare
from .models import (
    CambioClave,
    CambioEstado,
    CambioMensaje,
    Estado,
    FotoNueva,
    FotoSubida,
    Ingreso,
    Mensaje,
    MensajeEntrada,
    Pedido,
    PedidoConsulta,
    PedidoEntrada,
    Producto,
    ProductoAdmin,
    ProductoCambio,
    ProductoNuevo,
    Reporte,
    Sesion,
    Usuario,
    UsuarioCambio,
    UsuarioNuevo,
)
from .seguridad import hash_clave, huella, nuevo_token, verificar_clave

STATIC = Path(__file__).parent / "static"
log = logging.getLogger("panaderia")

# Flujo del pedido: solo se avanza, y cancelar únicamente es posible antes de entregar.
TRANSICIONES: dict[str, tuple[Estado, ...]] = {
    "recibido": ("listo", "cancelado"),
    "listo": ("entregado", "cancelado"),
    "entregado": (),
    "cancelado": (),
}

PERSONAL = ("dueno", "administrador", "empleado")
GESTION = ("dueno", "administrador")
SOLO_DUENO = ("dueno",)
EXTENSIONES_FOTO = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
# Fotos subidas: se reconocen por sus primeros bytes, no por lo que diga el navegador.
FIRMAS_FOTO = ((b"\xff\xd8\xff", "jpg", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "png", "image/png"),
               (b"RIFF", "webp", "image/webp"))
TAMANO_MAXIMO_FOTO = 1_500_000  # Cosmos DB admite documentos de hasta 2 MB


def _pedido(doc: dict) -> Pedido:
    """Convierte un documento de MongoDB al modelo público de pedido."""
    ocultos = ("_id", "es_prueba", "reserva")
    return Pedido(id=doc["_id"], siguientes=list(TRANSICIONES[doc["estado"]]),
                  **{k: v for k, v in doc.items() if k not in ocultos})


def _usuario(doc: dict) -> Usuario:
    return Usuario(correo=doc["_id"], nombre=doc["nombre"], rol=doc["rol"],
                   activo=doc.get("activo", True))


def _aware(fecha: datetime | None) -> datetime | None:
    # Algunos motores devuelven fechas sin zona; todas se guardan en UTC.
    return fecha.replace(tzinfo=UTC) if fecha and fecha.tzinfo is None else fecha


def validar_hora(hora: datetime, ahora: datetime) -> datetime:
    """Normaliza la hora de recogida a la zona local y valida la ventana disponible."""
    # Las horas sin zona horaria se interpretan como hora de Colombia.
    if hora.tzinfo is None:
        hora = hora.replace(tzinfo=config.ZONA)
    local = hora.astimezone(config.ZONA)
    if local < ahora + timedelta(minutes=config.MINUTOS_PREPARACION):
        raise HTTPException(
            422, f"El pedido necesita {config.MINUTOS_PREPARACION} minutos de preparación")
    if local > ahora + timedelta(days=config.DIAS_MAXIMOS):
        raise HTTPException(
            422, f"Solo se reciben pedidos para los próximos {config.DIAS_MAXIMOS} días")
    # La comprobación usa la hora local normalizada, no la zona horaria del cliente.
    if not config.HORA_APERTURA <= local.time() <= config.HORA_CIERRE:
        raise HTTPException(422, "La panadería entrega pedidos entre las 6:00 y las 20:00")
    return local


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    """Construye y configura la aplicación con las rutas y dependencias necesarias."""
    settings = settings or Settings.from_env()
    app = FastAPI(title="Pan de la Casa", version=settings.version, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None)
    # Mantiene el estado compartido de la conexión y evita inicializaciones repetidas.
    state: dict = {"db": db, "listo": False}

    def get_db() -> Database:
        """Conecta con MongoDB de forma diferida y prepara la base una sola vez."""
        if state["db"] is None:
            state["db"] = connect(settings.mongodb_uri, settings.mongodb_db)
        if not state["listo"]:
            prepare(state["db"])
            asegurar_dueno(state["db"], settings.owner_email, settings.owner_password,
                           settings.owner_nombre)
            state["listo"] = True
        return state["db"]

    Db = Annotated[Database, Depends(get_db)]

    # ---------- Sesión y permisos ----------

    def sesion_actual(db: Db, authorization: str = Header(default="")) -> dict:
        """Valida el token "Bearer" del panel y devuelve el usuario con su sesión."""
        token = authorization.removeprefix("Bearer ").strip()
        sesion = db.sesiones.find_one({"_id": huella(token)}) if token else None
        if not sesion or _aware(sesion["expira"]) <= datetime.now(UTC):
            raise HTTPException(401, "Inicia sesión para continuar")
        usuario = db.usuarios.find_one({"_id": sesion["usuario"], "activo": True})
        if not usuario:
            db.sesiones.delete_one({"_id": sesion["_id"]})
            raise HTTPException(401, "Inicia sesión para continuar")
        return {**usuario, "_sesion": sesion["_id"]}

    def requiere(*roles: str):
        def verificar(usuario: Annotated[dict, Depends(sesion_actual)]) -> dict:
            if usuario["rol"] not in roles:
                raise HTTPException(403, "Tu rol no tiene permiso para esta acción")
            return usuario
        return verificar

    Personal = Annotated[dict, Depends(requiere(*PERSONAL))]
    Gestion = Annotated[dict, Depends(requiere(*GESTION))]
    Dueno = Annotated[dict, Depends(requiere(*SOLO_DUENO))]

    # ---------- Registro y cabeceras ----------

    @app.middleware("http")
    async def registro(request: Request, call_next):
        # Una línea JSON por solicitud permite enviar las métricas a Log Analytics.
        inicio = time.perf_counter()
        response = await call_next(request)
        if request.url.path not in ("/healthz", "/readyz"):
            log.info(json.dumps({
                "metodo": request.method, "ruta": request.url.path, "estado": response.status_code,
                "ms": round((time.perf_counter() - inicio) * 1000), "ambiente": settings.app_env,
            }))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        ruta = request.url.path
        if ruta.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        elif ruta.startswith("/img/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        else:
            # HTML, JS y CSS se revalidan siempre para que un despliegue nuevo se vea de inmediato.
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        """Confirma que el proceso está activo; no requiere acceso a MongoDB."""
        return {"estado": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz():
        """Comprueba la disponibilidad real de la aplicación antes de recibir tráfico."""
        try:
            get_db().command("ping")
        except Exception:
            log.exception("La base de datos no responde")
            return JSONResponse({"estado": "sin base de datos"}, status_code=503)
        return {"estado": "ok"}

    @app.get("/api/info")
    def info():
        """Expone metadatos de despliegue útiles para diagnósticos."""
        return {"ambiente": settings.app_env, "version": settings.version}

    # ---------- Tienda ----------

    @app.get("/api/productos", response_model=list[Producto])
    def productos(db: Db):
        """Catálogo visible para el cliente, ordenado por nombre. Incluye los agotados marcados."""
        mapa = catalogo.mapa_productos(db)
        docs = sorted((d for d in mapa.values() if d.get("disponible", True)),
                      key=lambda d: d["nombre"])
        return [catalogo.vista(d, mapa) for d in docs]

    @app.post("/api/pedidos", response_model=Pedido, status_code=201)
    def crear_pedido(entrada: PedidoEntrada, db: Db):
        """Valida, descuenta existencias y registra un pedido con los precios del catálogo."""
        ahora = datetime.now(config.ZONA)
        hora = validar_hora(entrada.hora_recogida, ahora)
        # Agrupa repeticiones del mismo producto y obtiene la cantidad total solicitada.
        cantidades: dict[str, int] = {}
        for item in entrada.items:
            cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad
        mapa = catalogo.mapa_productos(db)

        def vendible(pid: str) -> bool:
            doc = mapa.get(pid)
            if not doc or not doc.get("disponible", True):
                return False
            if doc.get("tipo", "producto") == "combo":
                return all(mapa.get(c["producto_id"], {}).get("disponible", False)
                           for c in doc.get("componentes", []))
            return True

        faltan = sorted(pid for pid in cantidades if not vendible(pid))
        if faltan:
            raise HTTPException(422, f"Producto no disponible: {', '.join(faltan)}")
        for pid, n in cantidades.items():
            if n > 50:
                raise HTTPException(422, f"Máximo 50 unidades de {mapa[pid]['nombre']} por pedido")

        # El precio se toma del servidor y no de los valores enviados por el navegador.
        items = []
        for pid, n in cantidades.items():
            doc = mapa[pid]
            incluye = ", ".join(f"{c['cantidad']} {mapa[c['producto_id']]['nombre']}"
                                for c in doc.get("componentes", [])) or None
            items.append({"producto_id": pid, "nombre": doc["nombre"], "precio": doc["precio"],
                          "cantidad": n, "subtotal": doc["precio"] * n, "incluye": incluye})
        reserva = catalogo.reservar(db, catalogo.necesidades(cantidades, mapa), mapa)
        creado = datetime.now(UTC)
        doc = {
            "_id": uuid.uuid4().hex[:10],
            "nombre": entrada.nombre.strip(),
            "telefono": entrada.telefono,
            "hora_recogida": hora.astimezone(UTC),
            "items": items,
            "total": sum(i["subtotal"] for i in items),
            "estado": "recibido",
            "creado_en": creado,
            "historial": [{"estado": "recibido", "en": creado, "por": "cliente"}],
            "reserva": reserva,
            "es_prueba": entrada.es_prueba,
        }
        try:
            db.pedidos.insert_one(doc)
        except Exception:
            catalogo.liberar(db, reserva)
            raise
        return _pedido(doc)

    @app.get("/api/pedidos/consulta", response_model=PedidoConsulta)
    def consultar_pedido(numero: str, telefono: str, db: Db):
        """El cliente consulta su pedido con el número y el teléfono con que lo registró."""
        numero = numero.strip().lower()
        telefono = "".join(c for c in telefono if c.isdigit())
        doc = db.pedidos.find_one({"_id": numero, "telefono": telefono}) if numero and telefono else None
        # El mismo mensaje para número o teléfono equivocados: no revela si el pedido existe.
        if not doc:
            raise HTTPException(404, "No encontramos un pedido con ese número y ese teléfono")
        return PedidoConsulta(
            id=doc["_id"], nombre=doc["nombre"].split()[0], estado=doc["estado"],
            hora_recogida=doc["hora_recogida"], total=doc["total"],
            items=[{"nombre": i["nombre"], "cantidad": i["cantidad"]} for i in doc["items"]],
            historial=[{"estado": m["estado"], "en": m["en"]} for m in doc.get("historial", [])],
        )

    @app.post("/api/mensajes", status_code=201)
    def recibir_mensaje(entrada: MensajeEntrada, db: Db):
        """Mensaje del formulario de contacto. Queda en el panel para el dueño y los administradores."""
        if entrada.sitio:
            # Respuesta normal para no darle pistas al bot; el mensaje no se guarda.
            return {"recibido": True}
        db.mensajes.insert_one({
            "_id": uuid.uuid4().hex[:10], "nombre": entrada.nombre.strip(),
            "contacto": entrada.contacto.strip(), "asunto": entrada.asunto,
            "mensaje": entrada.mensaje.strip(), "creado_en": datetime.now(UTC), "leido": False,
        })
        return {"recibido": True}

    # ---------- Sesión del personal ----------

    @app.post("/api/auth/login", response_model=Sesion)
    def login(datos: Ingreso, db: Db):
        """Inicia sesión con correo y contraseña. Bloquea la cuenta tras varios intentos fallidos."""
        correo = datos.correo.strip().lower()
        usuario = db.usuarios.find_one({"_id": correo})
        ahora = datetime.now(UTC)
        bloqueo = _aware(usuario.get("bloqueado_hasta")) if usuario else None
        if bloqueo and bloqueo > ahora:
            minutos = max(1, round((bloqueo - ahora).total_seconds() / 60))
            raise HTTPException(429, f"Demasiados intentos. Vuelve a intentarlo en {minutos} minutos")
        if not usuario or not verificar_clave(datos.clave, usuario["clave"]):
            if usuario:
                intentos = usuario.get("intentos", 0) + 1
                cambio = {"intentos": intentos}
                if intentos >= config.INTENTOS_MAXIMOS:
                    cambio = {"intentos": 0, "bloqueado_hasta":
                              ahora + timedelta(minutes=config.MINUTOS_BLOQUEO)}
                db.usuarios.update_one({"_id": correo}, {"$set": cambio})
            raise HTTPException(401, "Correo o contraseña incorrectos")
        if not usuario.get("activo", True):
            raise HTTPException(403, "Tu cuenta está desactivada. Habla con el dueño")
        db.usuarios.update_one({"_id": correo}, {"$set": {"intentos": 0, "bloqueado_hasta": None,
                                                           "ultimo_ingreso": ahora}})
        token = nuevo_token()
        expira = ahora + timedelta(hours=config.HORAS_SESION)
        db.sesiones.insert_one({"_id": huella(token), "usuario": correo, "creada": ahora,
                                "expira": expira})
        return Sesion(token=token, usuario=_usuario(usuario), expira=expira)

    @app.post("/api/auth/logout", status_code=204)
    def logout(usuario: Personal, db: Db):
        db.sesiones.delete_one({"_id": usuario["_sesion"]})

    @app.get("/api/auth/yo", response_model=Usuario)
    def yo(usuario: Personal):
        return _usuario(usuario)

    @app.post("/api/auth/clave", status_code=204)
    def cambiar_mi_clave(datos: CambioClave, usuario: Personal, db: Db):
        """Cambia la contraseña propia y cierra las demás sesiones abiertas."""
        if not verificar_clave(datos.actual, usuario["clave"]):
            raise HTTPException(422, "La contraseña actual no es correcta")
        db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"clave": hash_clave(datos.nueva)}})
        db.sesiones.delete_many({"usuario": usuario["_id"], "_id": {"$ne": usuario["_sesion"]}})

    # ---------- Usuarios (solo el dueño) ----------

    @app.get("/api/usuarios", response_model=list[Usuario])
    def listar_usuarios(_: Dueno, db: Db):
        orden = {"dueno": 0, "administrador": 1, "empleado": 2}
        docs = sorted(db.usuarios.find({}), key=lambda d: (orden[d["rol"]], d["nombre"]))
        return [_usuario(d) for d in docs]

    @app.post("/api/usuarios", response_model=Usuario, status_code=201)
    def crear_usuario(datos: UsuarioNuevo, _: Dueno, db: Db):
        correo = datos.correo.strip().lower()
        if db.usuarios.find_one({"_id": correo}):
            raise HTTPException(409, "Ya existe un usuario con ese correo")
        doc = {"_id": correo, "nombre": datos.nombre.strip(), "rol": datos.rol, "activo": True,
               "clave": hash_clave(datos.clave), "intentos": 0, "bloqueado_hasta": None,
               "creado_en": datetime.now(UTC)}
        db.usuarios.insert_one(doc)
        return _usuario(doc)

    @app.patch("/api/usuarios/{correo}", response_model=Usuario)
    def cambiar_usuario(correo: str, datos: UsuarioCambio, _: Dueno, db: Db):
        """Cambia nombre, rol, estado o contraseña. La cuenta del dueño no se toca desde aquí."""
        correo = correo.strip().lower()
        doc = db.usuarios.find_one({"_id": correo})
        if not doc:
            raise HTTPException(404, "Usuario no encontrado")
        if doc["rol"] == "dueno":
            raise HTTPException(403, "La cuenta del dueño solo se cambia desde Mi cuenta")
        cambios = datos.model_dump(exclude_none=True)
        if "clave" in cambios:
            cambios["clave"] = hash_clave(cambios["clave"])
            cambios.update(intentos=0, bloqueado_hasta=None)
        if cambios:
            db.usuarios.update_one({"_id": correo}, {"$set": cambios})
        # Un cambio de rol, contraseña o desactivación obliga a iniciar sesión de nuevo.
        if {"rol", "clave", "activo"} & cambios.keys():
            db.sesiones.delete_many({"usuario": correo})
        return _usuario(db.usuarios.find_one({"_id": correo}))

    # ---------- Pedidos (todo el personal) ----------

    @app.get("/api/pedidos", response_model=list[Pedido])
    def listar_pedidos(_: Personal, db: Db, pruebas: bool = False, estado: Estado | None = None):
        """Lista los pedidos recientes, excluyendo los registros marcados como prueba."""
        filtro: dict = {} if pruebas else {"es_prueba": {"$ne": True}}
        if estado:
            filtro["estado"] = estado
        return [_pedido(d) for d in db.pedidos.find(filtro).sort("creado_en", -1).limit(200)]

    @app.patch("/api/pedidos/{pedido_id}", response_model=Pedido)
    def cambiar_estado(pedido_id: str, cambio: CambioEstado, usuario: Personal, db: Db):
        """Avanza el pedido según el flujo permitido y devuelve las unidades si se cancela."""
        doc = db.pedidos.find_one({"_id": pedido_id})
        if not doc:
            raise HTTPException(404, "Pedido no encontrado")
        actual = doc["estado"]
        if cambio.estado == actual:
            raise HTTPException(409, f"El pedido ya está en estado {actual}")
        if not TRANSICIONES[actual]:
            raise HTTPException(
                409, f"Un pedido {actual} ya está cerrado y no puede pasar a {cambio.estado}")
        if cambio.estado not in TRANSICIONES[actual]:
            permitidos = " o ".join(TRANSICIONES[actual])
            raise HTTPException(
                409, f"Un pedido {actual} no puede pasar a {cambio.estado}. Solo puede pasar a {permitidos}")
        movimiento = {"estado": cambio.estado, "en": datetime.now(UTC), "por": usuario["_id"]}
        # El filtro por estado evita que dos personas cambien el mismo pedido a la vez.
        r = db.pedidos.update_one({"_id": pedido_id, "estado": actual},
                                  {"$set": {"estado": cambio.estado},
                                   "$push": {"historial": movimiento}})
        if r.modified_count == 0:
            raise HTTPException(409, "Otra persona cambió este pedido. Actualiza la lista")
        if cambio.estado == "cancelado":
            catalogo.liberar(db, doc.get("reserva", {}))
        return _pedido(db.pedidos.find_one({"_id": pedido_id}))

    # ---------- Catálogo (dueño y administradores) ----------

    @app.get("/api/admin/productos", response_model=list[ProductoAdmin])
    def productos_admin(_: Gestion, db: Db):
        mapa = catalogo.mapa_productos(db)
        docs = sorted(mapa.values(), key=lambda d: (d.get("tipo", "producto") == "combo", d["nombre"]))
        return [catalogo.vista(d, mapa, admin=True) for d in docs]

    @app.get("/api/admin/fotos", response_model=list[str])
    def fotos(_: Gestion, db: Db):
        """Primero las fotos subidas (la más reciente arriba) y luego las del catálogo inicial."""
        subidas = [f"/img/subidas/{d['_id']}.{d['extension']}"
                   for d in db.fotos.find({}, {"extension": 1}).sort("creado_en", DESCENDING)]
        carpeta = STATIC / "img"
        iniciales = sorted(f"/img/{f.name}" for f in carpeta.iterdir()
                           if f.suffix.lower() in EXTENSIONES_FOTO) if carpeta.is_dir() else []
        return subidas + iniciales

    @app.post("/api/admin/fotos", response_model=FotoSubida, status_code=201)
    def subir_foto(datos: FotoNueva, usuario: Gestion, db: Db):
        try:
            contenido = base64.b64decode(datos.datos.split(",")[-1], validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(422, "La foto no llegó completa. Inténtalo de nuevo.") from None
        if len(contenido) > TAMANO_MAXIMO_FOTO:
            raise HTTPException(413, "La foto pesa más de 1,5 MB.")
        firma = next((f for f in FIRMAS_FOTO if contenido.startswith(f[0])
                      and (f[1] != "webp" or contenido[8:12] == b"WEBP")), None)
        if not firma:
            raise HTTPException(422, "El archivo no es una foto JPG, PNG o WebP.")
        foto_id = uuid.uuid4().hex
        db.fotos.insert_one({"_id": foto_id, "extension": firma[1], "tipo": firma[2], "datos": contenido,
                             "nombre": datos.nombre.strip(), "subida_por": usuario["_id"],
                             "creado_en": datetime.now(UTC)})
        return FotoSubida(url=f"/img/subidas/{foto_id}.{firma[1]}")

    @app.get("/img/subidas/{archivo}", include_in_schema=False)
    def ver_foto(archivo: str, db: Db):
        foto_id, _, extension = archivo.partition(".")
        doc = db.fotos.find_one({"_id": foto_id, "extension": extension})
        if not doc:
            raise HTTPException(404, "Foto no encontrada")
        return Response(content=bytes(doc["datos"]), media_type=doc["tipo"])

    @app.post("/api/admin/productos", response_model=ProductoAdmin, status_code=201)
    def crear_producto(datos: ProductoNuevo, _: Gestion, db: Db):
        mapa = catalogo.mapa_productos(db)
        if datos.tipo == "combo":
            catalogo.validar_componentes(datos.componentes, mapa, None)
        doc = {"_id": catalogo.identificador(datos.nombre, db), **datos.model_dump(),
               "disponible": True}
        doc["nombre"] = doc["nombre"].strip()
        if datos.tipo == "combo":
            doc["unidades"] = None
        else:
            doc["componentes"] = []
        db.productos.insert_one(doc)
        mapa[doc["_id"]] = doc
        return catalogo.vista(doc, mapa, admin=True)

    @app.patch("/api/admin/productos/{producto_id}", response_model=ProductoAdmin)
    def cambiar_producto(producto_id: str, datos: ProductoCambio, _: Gestion, db: Db):
        """Edita el producto. Enviar "unidades": null quita el control de inventario."""
        mapa = catalogo.mapa_productos(db)
        doc = mapa.get(producto_id)
        if not doc:
            raise HTTPException(404, "Producto no encontrado")
        cambios = {k: getattr(datos, k) for k in datos.model_fields_set}
        for campo in ("nombre", "descripcion", "categoria", "precio", "foto", "disponible"):
            if campo in cambios and cambios[campo] is None:
                raise HTTPException(422, f"El campo {campo} no puede quedar vacío")
        es_combo = doc.get("tipo", "producto") == "combo"
        if es_combo and "unidades" in cambios:
            raise HTTPException(422, "Las unidades de un combo dependen de sus productos")
        if "componentes" in cambios:
            if not es_combo:
                raise HTTPException(422, "Solo los combos tienen productos incluidos")
            catalogo.validar_componentes(cambios["componentes"] or [], mapa, producto_id)
            cambios["componentes"] = [c.model_dump() for c in cambios["componentes"]]
        if cambios:
            db.productos.update_one({"_id": producto_id}, {"$set": cambios})
        mapa = catalogo.mapa_productos(db)
        return catalogo.vista(mapa[producto_id], mapa, admin=True)

    @app.delete("/api/admin/productos/{producto_id}", status_code=204)
    def eliminar_producto(producto_id: str, usuario: Gestion, db: Db):
        """Retira el producto del catálogo para siempre. Los pedidos ya hechos conservan su detalle."""
        mapa = catalogo.mapa_productos(db)
        if producto_id not in mapa:
            raise HTTPException(404, "Producto no encontrado")
        combos = sorted(d["nombre"] for d in mapa.values()
                        if any(c["producto_id"] == producto_id for c in d.get("componentes", [])))
        if combos:
            raise HTTPException(409, f"{mapa[producto_id]['nombre']} hace parte de: {', '.join(combos)}. "
                                     "Quítalo de esos combos o elimínalos primero")
        # Se marca en lugar de borrar: así el catálogo inicial no lo vuelve a crear al reiniciar.
        db.productos.update_one({"_id": producto_id}, {"$set": {
            "eliminado": True, "disponible": False, "eliminado_en": datetime.now(UTC),
            "eliminado_por": usuario["_id"]}})

    # ---------- Mensajes (dueño y administradores) ----------

    @app.get("/api/admin/mensajes", response_model=list[Mensaje])
    def listar_mensajes(_: Gestion, db: Db):
        docs = db.mensajes.find({}).sort("creado_en", -1).limit(200)
        return [Mensaje(id=d["_id"], **{k: v for k, v in d.items() if k != "_id"}) for d in docs]

    @app.patch("/api/admin/mensajes/{mensaje_id}", response_model=Mensaje)
    def marcar_mensaje(mensaje_id: str, cambio: CambioMensaje, _: Gestion, db: Db):
        r = db.mensajes.update_one({"_id": mensaje_id}, {"$set": {"leido": cambio.leido}})
        if r.matched_count == 0:
            raise HTTPException(404, "Mensaje no encontrado")
        d = db.mensajes.find_one({"_id": mensaje_id})
        return Mensaje(id=d["_id"], **{k: v for k, v in d.items() if k != "_id"})

    @app.delete("/api/admin/mensajes/{mensaje_id}", status_code=204)
    def borrar_mensaje(mensaje_id: str, _: Gestion, db: Db):
        if db.mensajes.delete_one({"_id": mensaje_id}).deleted_count == 0:
            raise HTTPException(404, "Mensaje no encontrado")

    # ---------- Reportes (dueño y administradores) ----------

    @app.get("/api/admin/reportes", response_model=Reporte)
    def reporte(_: Gestion, db: Db, desde: date, hasta: date):
        """Pedidos, dinero y productos más vendidos por fecha de recogida."""
        return reportes.generar(db, desde, hasta)

    # ---------- Sitio web ----------

    @app.get("/pedir", include_in_schema=False)
    def ir_a_la_tienda():
        return RedirectResponse("/tienda.html")

    @app.get("/admin", include_in_schema=False)
    def ir_al_panel():
        return RedirectResponse("/admin.html")

    # El montaje en "/" va después de las rutas de la API.
    if STATIC.is_dir():
        app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
