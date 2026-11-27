"""Resumen de pedidos por período, calculado en hora de Colombia."""

from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from pymongo.database import Database

from . import config
from .models import ProductoVendido, PuntoSerie, Reporte, ResumenEstado

ESTADOS = ("recibido", "listo", "entregado", "cancelado")
DIAS_MAXIMOS_REPORTE = 366
# Hasta dos meses se agrupa por día; rangos más largos, por mes.
DIAS_AGRUPACION_DIARIA = 62


def _inicio(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, tzinfo=config.ZONA)


def _periodos(desde: date, hasta: date, por_dia: bool) -> list[str]:
    if por_dia:
        return [(desde + timedelta(days=i)).isoformat() for i in range((hasta - desde).days + 1)]
    periodos, actual = [], desde.replace(day=1)
    while actual <= hasta:
        periodos.append(actual.strftime("%Y-%m"))
        actual = (actual + timedelta(days=32)).replace(day=1)
    return periodos


def generar(db: Database, desde: date, hasta: date) -> Reporte:
    """Cuenta los pedidos cuya recogida cae entre desde y hasta, ambos incluidos."""
    if hasta < desde:
        raise HTTPException(422, "La fecha final no puede ser anterior a la inicial")
    if (hasta - desde).days >= DIAS_MAXIMOS_REPORTE:
        raise HTTPException(422, "El período máximo del reporte es de un año")

    inicio = _inicio(desde).astimezone(UTC)
    fin = _inicio(hasta + timedelta(days=1)).astimezone(UTC)
    pedidos = list(db.pedidos.find({"hora_recogida": {"$gte": inicio, "$lt": fin},
                                    "es_prueba": {"$ne": True}}))

    por_dia = (hasta - desde).days < DIAS_AGRUPACION_DIARIA
    serie = {p: {"pedidos": 0, "ventas": 0} for p in _periodos(desde, hasta, por_dia)}
    por_estado = {e: ResumenEstado() for e in ESTADOS}
    vendidos: dict[str, dict] = {}

    for p in pedidos:
        resumen = por_estado[p["estado"]]
        resumen.pedidos += 1
        resumen.dinero += p["total"]
        local = p["hora_recogida"].astimezone(config.ZONA)
        clave = local.date().isoformat() if por_dia else local.strftime("%Y-%m")
        if clave in serie:
            serie[clave]["pedidos"] += 1
        if p["estado"] != "entregado":
            continue
        if clave in serie:
            serie[clave]["ventas"] += p["total"]
        for item in p["items"]:
            v = vendidos.setdefault(item["producto_id"], {"nombre": item["nombre"],
                                                          "cantidad": 0, "dinero": 0})
            v["cantidad"] += item["cantidad"]
            v["dinero"] += item["subtotal"]

    entregados = por_estado["entregado"]
    productos = sorted((ProductoVendido(producto_id=k, **v) for k, v in vendidos.items()),
                       key=lambda x: (-x.cantidad, x.nombre))[:10]
    return Reporte(
        desde=desde, hasta=hasta, agrupacion="dia" if por_dia else "mes",
        total_pedidos=len(pedidos), por_estado=por_estado,
        entregados=entregados.pedidos, ventas=entregados.dinero,
        ticket_promedio=round(entregados.dinero / entregados.pedidos) if entregados.pedidos else 0,
        unidades_vendidas=sum(v["cantidad"] for v in vendidos.values()),
        productos=productos,
        serie=[PuntoSerie(periodo=k, **v) for k, v in serie.items()],
    )
