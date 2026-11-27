"""Reglas del catálogo: existencias, combos y reserva de unidades al registrar pedidos."""

import re
import unicodedata

from fastapi import HTTPException
from pymongo.database import Database

from .models import ComponenteVista, Producto, ProductoAdmin


def mapa_productos(db: Database) -> dict[str, dict]:
    """Productos vigentes. Los eliminados se conservan en la base pero ya no existen para nadie."""
    return {d["_id"]: d for d in db.productos.find({"eliminado": {"$ne": True}})}


def maximo_disponible(doc: dict, mapa: dict[str, dict]) -> int | None:
    """Unidades que se pueden pedir ahora. None significa sin límite de inventario."""
    if doc.get("tipo", "producto") == "producto":
        unidades = doc.get("unidades")
        return None if unidades is None else max(unidades, 0)
    maximo: int | None = None
    for comp in doc.get("componentes", []):
        parte = mapa.get(comp["producto_id"])
        if not parte or not parte.get("disponible", True):
            return 0
        if parte.get("unidades") is not None:
            alcanza = parte["unidades"] // comp["cantidad"]
            maximo = alcanza if maximo is None else min(maximo, alcanza)
    return maximo


def vista(doc: dict, mapa: dict[str, dict], admin: bool = False) -> Producto | ProductoAdmin:
    maximo = maximo_disponible(doc, mapa)
    incluye = [ComponenteVista(producto_id=c["producto_id"], cantidad=c["cantidad"],
                               nombre=mapa.get(c["producto_id"], {}).get("nombre", c["producto_id"]))
               for c in doc.get("componentes", [])]
    datos = {
        "id": doc["_id"], "nombre": doc["nombre"], "descripcion": doc["descripcion"],
        "categoria": doc["categoria"], "precio": doc["precio"], "foto": doc["foto"],
        "tipo": doc.get("tipo", "producto"), "agotado": maximo == 0, "maximo": maximo,
        "incluye": incluye,
    }
    if admin:
        return ProductoAdmin(**datos, unidades=doc.get("unidades"),
                             disponible=doc.get("disponible", True),
                             componentes=doc.get("componentes", []))
    return Producto(**datos)


def necesidades(cantidades: dict[str, int], mapa: dict[str, dict]) -> dict[str, int]:
    """Unidades de cada producto base que consume el pedido. Un combo descuenta sus partes."""
    total: dict[str, int] = {}
    for pid, n in cantidades.items():
        doc = mapa[pid]
        if doc.get("tipo", "producto") == "combo":
            for comp in doc.get("componentes", []):
                total[comp["producto_id"]] = total.get(comp["producto_id"], 0) + n * comp["cantidad"]
        else:
            total[pid] = total.get(pid, 0) + n
    return total


def reservar(db: Database, necesidad: dict[str, int], mapa: dict[str, dict]) -> dict[str, int]:
    """Descuenta las existencias de forma atómica por producto. Si algo falta, deshace lo hecho."""
    hechas: dict[str, int] = {}
    for pid in sorted(necesidad):
        n = necesidad[pid]
        if mapa[pid].get("unidades") is None:
            continue
        r = db.productos.update_one({"_id": pid, "unidades": {"$gte": n}}, {"$inc": {"unidades": -n}})
        if r.modified_count == 0:
            liberar(db, hechas)
            quedan = (db.productos.find_one({"_id": pid}) or {}).get("unidades", 0)
            raise HTTPException(
                409, f"No hay suficientes unidades de {mapa[pid]['nombre']}: quedan {quedan}")
        hechas[pid] = n
    return hechas


def liberar(db: Database, reserva: dict[str, int]) -> None:
    """Devuelve al inventario las unidades de un pedido cancelado."""
    for pid, n in reserva.items():
        db.productos.update_one({"_id": pid, "unidades": {"$ne": None}}, {"$inc": {"unidades": n}})


def identificador(nombre: str, db: Database) -> str:
    """Convierte el nombre en un id legible y único, por ejemplo "pan-de-yuca"."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:50] or "producto"
    candidato, n = base, 2
    while db.productos.find_one({"_id": candidato}):
        candidato, n = f"{base}-{n}", n + 1
    return candidato


def validar_componentes(componentes: list, mapa: dict[str, dict], propio: str | None) -> None:
    if len(componentes) < 2:
        raise HTTPException(422, "Un combo necesita al menos dos productos")
    vistos = set()
    for comp in componentes:
        pid = comp.producto_id
        if pid == propio or pid in vistos:
            raise HTTPException(422, "Cada producto aparece una sola vez en el combo")
        parte = mapa.get(pid)
        if not parte or parte.get("tipo", "producto") != "producto":
            raise HTTPException(422, f"El combo solo puede incluir productos del catálogo: {pid}")
        vistos.add(pid)
