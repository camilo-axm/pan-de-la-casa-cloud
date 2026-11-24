"""Acceso a MongoDB. En Azure es Cosmos DB for MongoDB; en pruebas, una base en memoria."""

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

CATALOGO = [
    {"_id": "pan-campesino", "nombre": "Pan campesino", "precio": 6500, "categoria": "Panes",
     "descripcion": "Hogaza de masa madre con corteza crocante.", "foto": "/img/pan-campesino.svg"},
    {"_id": "baguette", "nombre": "Baguette", "precio": 4200, "categoria": "Panes",
     "descripcion": "Barra francesa horneada cada mañana.", "foto": "/img/baguette.svg"},
    {"_id": "pan-integral", "nombre": "Pan integral", "precio": 7800, "categoria": "Panes",
     "descripcion": "Molde de harina integral con semillas.", "foto": "/img/pan-integral.svg"},
    {"_id": "croissant", "nombre": "Croissant de mantequilla", "precio": 3800,
     "categoria": "Hojaldres", "descripcion": "Hojaldre de mantequilla, 27 capas.",
     "foto": "/img/croissant.svg"},
    {"_id": "pandebono", "nombre": "Pandebono", "precio": 2500, "categoria": "Tradicionales",
     "descripcion": "Receta valluna con queso costeño.", "foto": "/img/pandebono.svg"},
    {"_id": "almojabana", "nombre": "Almojábana", "precio": 2800, "categoria": "Tradicionales",
     "descripcion": "Suave, de cuajada fresca.", "foto": "/img/almojabana.svg"},
    {"_id": "torta-zanahoria", "nombre": "Torta de zanahoria", "precio": 5500,
     "categoria": "Repostería", "descripcion": "Porción con nueces y crema de queso.",
     "foto": "/img/torta-zanahoria.svg"},
    {"_id": "galletas-avena", "nombre": "Galletas de avena", "precio": 9000,
     "categoria": "Repostería", "descripcion": "Paquete de seis con uvas pasas.",
     "foto": "/img/galletas-avena.svg"},
]


def connect(uri: str, name: str) -> Database:
    if uri.startswith("mongomock://"):
        # Base en memoria para desarrollar sin Docker ni cuenta de Azure. Solo existe en el extra dev.
        import mongomock

        return mongomock.MongoClient(tz_aware=True)[name]
    client = MongoClient(uri, serverSelectionTimeoutMS=8000, tz_aware=True, appname="panaderia")
    return client[name]


def prepare(db: Database) -> None:
    """Crea los indices y carga el catalogo inicial. Se puede repetir sin duplicar datos."""
    # Cosmos DB for MongoDB solo indexa _id por defecto y exige un indice para ordenar.
    db.productos.create_index([("nombre", ASCENDING)])
    db.pedidos.create_index([("creado_en", DESCENDING)])
    for producto in CATALOGO:
        db.productos.update_one(
            {"_id": producto["_id"]},
            {"$setOnInsert": {**producto, "disponible": True}},
            upsert=True,
        )
    