"""Acceso a MongoDB. En Azure es Cosmos DB for MongoDB; en pruebas, una base en memoria."""

from datetime import UTC, datetime

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

from .seguridad import hash_clave

# Catálogo inicial. "unidades" es la existencia del día; None significa sin control de inventario.
CATALOGO = [
    {"_id": "pan-campesino", "nombre": "Pan campesino", "precio": 6500, "categoria": "Panes",
     "descripcion": "Hogaza de masa madre con corteza crocante.", "unidades": 20},
    {"_id": "baguette", "nombre": "Baguette", "precio": 4200, "categoria": "Panes",
     "descripcion": "Barra francesa horneada cada mañana.", "unidades": 30},
    {"_id": "pan-integral", "nombre": "Pan integral", "precio": 7800, "categoria": "Panes",
     "descripcion": "Molde de harina integral con semillas.", "unidades": 15},
    {"_id": "croissant", "nombre": "Croissant de mantequilla", "precio": 3800,
     "categoria": "Hojaldres", "descripcion": "Hojaldre de mantequilla, 27 capas.", "unidades": 40},
    {"_id": "pandebono", "nombre": "Pandebono", "precio": 2500, "categoria": "Tradicionales",
     "descripcion": "Receta valluna con queso costeño.", "unidades": 60},
    {"_id": "almojabana", "nombre": "Almojábana", "precio": 2800, "categoria": "Tradicionales",
     "descripcion": "Suave, de cuajada fresca.", "unidades": 50},
    {"_id": "pan-de-yuca", "nombre": "Pan de yuca", "precio": 2300, "categoria": "Tradicionales",
     "descripcion": "Almidón de yuca y queso, crocante por fuera.", "unidades": 50},
    {"_id": "roscon", "nombre": "Roscón de bocadillo", "precio": 3500, "categoria": "Tradicionales",
     "descripcion": "Pan dulce en rosca, relleno de bocadillo de guayaba.", "unidades": 30},
    {"_id": "bunuelos", "nombre": "Buñuelo", "precio": 1800, "categoria": "Tradicionales",
     "descripcion": "De queso costeño, fritos en el día.", "unidades": 60},
    {"_id": "tamal-tolimense", "nombre": "Tamal tolimense", "precio": 14000, "categoria": "Salados",
     "descripcion": "Masa de maíz con cerdo, pollo, huevo y arveja, en hoja de plátano.",
     "unidades": 20},
    {"_id": "torta-zanahoria", "nombre": "Torta de zanahoria", "precio": 5500,
     "categoria": "Repostería", "descripcion": "Porción con nueces y crema de queso.",
     "unidades": 12},
    {"_id": "galletas-avena", "nombre": "Galletas de avena", "precio": 9000,
     "categoria": "Repostería", "descripcion": "Paquete de seis con uvas pasas.", "unidades": 20},
    {"_id": "tres-leches", "nombre": "Torta tres leches", "precio": 7000, "categoria": "Repostería",
     "descripcion": "Porción bañada en tres leches, con merengue.", "unidades": 15},
    {"_id": "milhoja", "nombre": "Milhoja de arequipe", "precio": 6500, "categoria": "Repostería",
     "descripcion": "Hojaldre con crema pastelera y arequipe.", "unidades": 15},
    {"_id": "natilla", "nombre": "Natilla", "precio": 5500, "categoria": "Repostería",
     "descripcion": "Porción de natilla de panela con canela.", "unidades": 20},
    {"_id": "combo-tradicional", "nombre": "Combo tradicional", "precio": 14500,
     "categoria": "Combos", "descripcion": "Tres pandebonos y tres almojábanas para compartir.",
     "tipo": "combo", "componentes": [{"producto_id": "pandebono", "cantidad": 3},
                                      {"producto_id": "almojabana", "cantidad": 3}]},
    {"_id": "combo-familiar", "nombre": "Combo familiar", "precio": 16900,
     "categoria": "Combos", "descripcion": "Pan campesino, baguette y pan integral.",
     "tipo": "combo", "componentes": [{"producto_id": "pan-campesino", "cantidad": 1},
                                      {"producto_id": "baguette", "cantidad": 1},
                                      {"producto_id": "pan-integral", "cantidad": 1}]},
]


def connect(uri: str, name: str) -> Database:
    if uri.startswith("mongomock://"):
        # Base en memoria para desarrollo y pruebas.
        import mongomock

        return mongomock.MongoClient(tz_aware=True)[name]
    client = MongoClient(uri, serverSelectionTimeoutMS=8000, tz_aware=True, appname="panaderia")
    return client[name]


def prepare(db: Database) -> None:
    """Crea los índices y carga el catálogo sin sobrescribir lo que el administrador cambió."""
    # Cosmos DB for MongoDB solo indexa _id por defecto y exige un índice para ordenar o filtrar.
    db.productos.create_index([("nombre", ASCENDING)])
    db.pedidos.create_index([("creado_en", DESCENDING)])
    db.pedidos.create_index([("hora_recogida", ASCENDING)])
    db.sesiones.create_index([("usuario", ASCENDING)])
    db.mensajes.create_index([("creado_en", DESCENDING)])
    db.fotos.create_index([("creado_en", DESCENDING)])
    for producto in CATALOGO:
        inicial = {"tipo": "producto", "unidades": None, "componentes": [], **producto,
                   "foto": f"/img/{producto['_id']}.jpg", "disponible": True}
        db.productos.update_one({"_id": producto["_id"]}, {"$setOnInsert": inicial}, upsert=True)
        # Las bases creadas con la versión anterior tenían ilustraciones SVG en lugar de fotos.
        db.productos.update_one({"_id": producto["_id"], "foto": f"/img/{producto['_id']}.svg"},
                                {"$set": {"foto": f"/img/{producto['_id']}.jpg"}})


def asegurar_dueno(db: Database, correo: str, clave: str, nombre: str) -> None:
    """Crea la cuenta del dueño en el primer arranque. Si ya existe, no cambia su contraseña."""
    if db.usuarios.find_one({"rol": "dueno"}):
        return
    db.usuarios.update_one(
        {"_id": correo},
        {"$set": {"nombre": nombre, "rol": "dueno", "activo": True,
                  "clave": hash_clave(clave), "intentos": 0, "bloqueado_hasta": None},
         "$setOnInsert": {"creado_en": datetime.now(UTC)}},
        upsert=True,
    )
