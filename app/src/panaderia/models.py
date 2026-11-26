"""Esquemas de entrada y salida utilizados por la API.

Los modelos de Pydantic validan los datos recibidos, documentan su estructura
y garantizan que las respuestas tengan un formato consistente.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Estado = Literal["recibido", "listo", "entregado", "cancelado"]
"""Estados posibles del ciclo de vida de un pedido."""


class Producto(BaseModel):
    """Representa un producto disponible en el catálogo."""

    id: str
    nombre: str
    descripcion: str
    categoria: str
    precio: int
    foto: str


class ItemEntrada(BaseModel):
    """Describe un producto solicitado y la cantidad incluida en el pedido."""

    producto_id: str = Field(min_length=1, max_length=60)
    cantidad: int = Field(ge=1, le=50)


class PedidoEntrada(BaseModel):
    """Contiene la información necesaria para crear un nuevo pedido."""

    nombre: str = Field(min_length=2, max_length=80)
    telefono: str = Field(pattern=r"^[0-9]{7,10}$")
    hora_recogida: datetime
    items: list[ItemEntrada] = Field(min_length=1, max_length=20)
    # Permite identificar pedidos de prueba y excluirlos del panel administrativo.
    es_prueba: bool = False


class ItemPedido(BaseModel):
    """Representa una línea calculada dentro de un pedido confirmado."""

    producto_id: str
    nombre: str
    precio: int
    cantidad: int
    subtotal: int


class Pedido(BaseModel):
    """Modelo público con el detalle completo y actual de un pedido."""

    id: str
    nombre: str
    telefono: str
    hora_recogida: datetime
    items: list[ItemPedido]
    total: int
    estado: Estado
    creado_en: datetime


class CambioEstado(BaseModel):
    """Datos requeridos para actualizar el estado de un pedido."""

    estado: Estado