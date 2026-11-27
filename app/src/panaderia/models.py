"""Esquemas de entrada y salida utilizados por la API.

Los modelos de Pydantic validan los datos recibidos, documentan su estructura
y garantizan que las respuestas tengan un formato consistente.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Estado = Literal["recibido", "listo", "entregado", "cancelado"]
"""Estados posibles del ciclo de vida de un pedido."""

Rol = Literal["dueno", "administrador", "empleado"]
RolAsignable = Literal["administrador", "empleado"]
TipoProducto = Literal["producto", "combo"]


# ---------- Catálogo ----------

class Componente(BaseModel):
    """Producto incluido en un combo y cuántas unidades lleva."""

    producto_id: str = Field(min_length=1, max_length=60)
    cantidad: int = Field(ge=1, le=20)


class ComponenteVista(Componente):
    nombre: str


class Producto(BaseModel):
    """Producto que ve el cliente en la tienda."""

    id: str
    nombre: str
    descripcion: str
    categoria: str
    precio: int
    foto: str
    tipo: TipoProducto = "producto"
    agotado: bool = False
    # Máximo que se puede pedir ahora. None significa sin límite de inventario.
    maximo: int | None = None
    incluye: list[ComponenteVista] = []


class ProductoAdmin(Producto):
    """Producto con los datos de gestión que solo ve el personal."""

    unidades: int | None = None
    disponible: bool = True
    componentes: list[Componente] = []


class ProductoNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    descripcion: str = Field(min_length=2, max_length=140)
    categoria: str = Field(min_length=2, max_length=30)
    precio: int = Field(ge=100, le=1_000_000)
    foto: str = Field(pattern=r"^/img/[a-z0-9-]+\.(jpg|jpeg|png|webp|svg)$")
    tipo: TipoProducto = "producto"
    unidades: int | None = Field(default=None, ge=0, le=10_000)
    componentes: list[Componente] = Field(default=[], max_length=8)


class ProductoCambio(BaseModel):
    """Cambios parciales. Solo se aplican los campos que llegan en la solicitud."""

    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    descripcion: str | None = Field(default=None, min_length=2, max_length=140)
    categoria: str | None = Field(default=None, min_length=2, max_length=30)
    precio: int | None = Field(default=None, ge=100, le=1_000_000)
    foto: str | None = Field(default=None, pattern=r"^/img/[a-z0-9-]+\.(jpg|jpeg|png|webp|svg)$")
    unidades: int | None = Field(default=None, ge=0, le=10_000)
    disponible: bool | None = None
    componentes: list[Componente] | None = Field(default=None, max_length=8)


# ---------- Pedidos ----------

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
    incluye: str | None = None


class Movimiento(BaseModel):
    """Un cambio de estado del pedido: cuál, cuándo y quién lo hizo."""

    estado: Estado
    en: datetime
    por: str


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
    historial: list[Movimiento] = []
    # Estados a los que se puede pasar desde el actual.
    siguientes: list[Estado] = []


class CambioEstado(BaseModel):
    """Datos requeridos para actualizar el estado de un pedido."""

    estado: Estado


# ---------- Usuarios y sesiones ----------

class Ingreso(BaseModel):
    correo: str = Field(min_length=3, max_length=120)
    clave: str = Field(min_length=1, max_length=200)


class Usuario(BaseModel):
    correo: str
    nombre: str
    rol: Rol
    activo: bool = True


class Sesion(BaseModel):
    token: str
    usuario: Usuario
    expira: datetime


class UsuarioNuevo(BaseModel):
    correo: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    nombre: str = Field(min_length=2, max_length=80)
    rol: RolAsignable
    clave: str = Field(min_length=10, max_length=200)


class UsuarioCambio(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    rol: RolAsignable | None = None
    activo: bool | None = None
    clave: str | None = Field(default=None, min_length=10, max_length=200)


class CambioClave(BaseModel):
    actual: str = Field(min_length=1, max_length=200)
    nueva: str = Field(min_length=10, max_length=200)


# ---------- Reportes ----------

class ResumenEstado(BaseModel):
    pedidos: int = 0
    dinero: int = 0


class ProductoVendido(BaseModel):
    producto_id: str
    nombre: str
    cantidad: int
    dinero: int


class PuntoSerie(BaseModel):
    periodo: str
    pedidos: int
    ventas: int


class Reporte(BaseModel):
    desde: date
    hasta: date
    agrupacion: Literal["dia", "mes"]
    total_pedidos: int
    por_estado: dict[str, ResumenEstado]
    entregados: int
    ventas: int
    ticket_promedio: int
    unidades_vendidas: int
    productos: list[ProductoVendido]
    serie: list[PuntoSerie]


# ---------- Consulta pública de un pedido ----------

class LineaConsulta(BaseModel):
    nombre: str
    cantidad: int


class PasoConsulta(BaseModel):
    estado: Estado
    en: datetime


class PedidoConsulta(BaseModel):
    """Lo que ve el cliente de su pedido: sin teléfono ni datos del personal."""

    id: str
    nombre: str
    estado: Estado
    hora_recogida: datetime
    items: list[LineaConsulta]
    total: int
    historial: list[PasoConsulta]


# ---------- Mensajes de contacto ----------

Asunto = Literal["pedido", "encargo", "sugerencia", "otro"]


class MensajeEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    contacto: str = Field(min_length=5, max_length=120)
    asunto: Asunto
    mensaje: str = Field(min_length=5, max_length=1000)
    # Campo trampa: las personas no lo ven; si llega con texto, lo llenó un bot.
    sitio: str = Field(default="", max_length=200)


class Mensaje(BaseModel):
    id: str
    nombre: str
    contacto: str
    asunto: Asunto
    mensaje: str
    creado_en: datetime
    leido: bool = False


class CambioMensaje(BaseModel):
    leido: bool
