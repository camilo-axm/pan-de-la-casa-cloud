"""API principal de Pan de la Casa.

Define la aplicación FastAPI, sus endpoints de productos y pedidos,
la autenticación administrativa y el montaje de los archivos estáticos.
"""

import hmac
import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pymongo.database import Database

from . import config
from .config import Settings
from .db import connect, prepare
from .models import CambioEstado, Pedido, PedidoEntrada, Producto

STATIC = Path(__file__).parent / "static"
log = logging.getLogger("panaderia")


def _pedido(doc: dict) -> Pedido:
    """Convierte un documento de MongoDB al modelo público de pedido."""
    return Pedido(id=doc["_id"], **{k: v for k, v in doc.items() if k not in ("_id", "es_prueba")})


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
            state["listo"] = True
        return state["db"]

    Db = Annotated[Database, Depends(get_db)]

    def admin(x_admin_key: str = Header(default="")) -> None:
        """Protege las operaciones administrativas frente a accesos no autorizados."""
        # Compara la clave en tiempo constante.
        if not hmac.compare_digest(x_admin_key.encode(), settings.admin_api_key.encode()):
            raise HTTPException(401, "Clave de administrador inválida")

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

    @app.get("/api/productos", response_model=list[Producto])
    def productos(db: Db):
        """Consulta el catálogo ordenado alfabéticamente y solo devuelve productos activos."""
        docs = db.productos.find({"disponible": True}).sort("nombre", 1)
        return [Producto(id=d["_id"], **{k: d[k] for k in Producto.model_fields if k != "id"})
                for d in docs]

    @app.post("/api/pedidos", response_model=Pedido, status_code=201)
    def crear_pedido(entrada: PedidoEntrada, db: Db):
        """Valida y registra un pedido usando los precios vigentes del catálogo."""
        ahora = datetime.now(config.ZONA)
        hora = validar_hora(entrada.hora_recogida, ahora)
        cantidades: dict[str, int] = {}
        for item in entrada.items:
            cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad
        catalogo = {p["_id"]: p for p in db.productos.find({"_id": {"$in": list(cantidades)},
                                                             "disponible": True})}
        faltan = sorted(set(cantidades) - set(catalogo))
        if faltan:
            raise HTTPException(422, f"Producto no disponible: {', '.join(faltan)}")
        # El precio se toma del servidor y no de los valores enviados por el navegador.
        items = [{"producto_id": pid, "nombre": catalogo[pid]["nombre"],
                  "precio": catalogo[pid]["precio"], "cantidad": n,
                  "subtotal": catalogo[pid]["precio"] * n} for pid, n in cantidades.items()]
        # Las fechas se almacenan en UTC para mantener un formato uniforme en MongoDB.
        doc = {
            "_id": uuid.uuid4().hex[:10],
            "nombre": entrada.nombre.strip(),
            "telefono": entrada.telefono,
            "hora_recogida": hora.astimezone(UTC),
            "items": items,
            "total": sum(i["subtotal"] for i in items),
            "estado": "recibido",
            "creado_en": datetime.now(UTC),
            "es_prueba": entrada.es_prueba,
        }
        db.pedidos.insert_one(doc)
        return _pedido(doc)

    @app.get("/api/pedidos", response_model=list[Pedido], dependencies=[Depends(admin)])
    def listar_pedidos(db: Db, pruebas: bool = False):
        """Lista los pedidos recientes, excluyendo los registros marcados como prueba."""
        filtro = {} if pruebas else {"es_prueba": {"$ne": True}}
        return [_pedido(d) for d in db.pedidos.find(filtro).sort("creado_en", -1).limit(200)]

    @app.patch("/api/pedidos/{pedido_id}", response_model=Pedido, dependencies=[Depends(admin)])
    def cambiar_estado(pedido_id: str, cambio: CambioEstado, db: Db):
        """Actualiza el estado de un pedido existente y confirma que fue localizado."""
        resultado = db.pedidos.update_one({"_id": pedido_id}, {"$set": {"estado": cambio.estado}})
        if resultado.matched_count == 0:
            raise HTTPException(404, "Pedido no encontrado")
        return _pedido(db.pedidos.find_one({"_id": pedido_id}))

    # El montaje en "/" va después de las rutas de la API.
    if STATIC.is_dir():
        app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
