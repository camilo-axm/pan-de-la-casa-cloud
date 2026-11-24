"""Configuración central de la aplicación.

Los parámetros operativos y los secretos se reciben mediante variables de entorno.
De esta forma, la configuración puede cambiar entre entornos sin modificar el código.
"""

import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

# Zona horaria utilizada para interpretar y presentar las fechas de recogida.
ZONA = ZoneInfo("America/Bogota")
# Hora inicial a partir de la cual se aceptan pedidos de recogida.
HORA_APERTURA = time(6, 0)
# Hora límite hasta la cual se aceptan pedidos de recogida.
HORA_CIERRE = time(20, 0)
# Tiempo mínimo requerido para preparar un pedido antes de su recogida.
MINUTOS_PREPARACION = 30
# Anticipación máxima permitida al momento de realizar un pedido.
DIAS_MAXIMOS = 7


@dataclass(frozen=True)
class Settings:
    """Agrupa la configuración necesaria para ejecutar la aplicación.

    Al ser una instancia inmutable, sus valores permanecen constantes durante
    el ciclo de vida del proceso y no pueden modificarse accidentalmente.
    """

    mongodb_uri: str
    mongodb_db: str
    admin_api_key: str
    app_env: str
    version: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Construye la configuración a partir de las variables de entorno.

        Valida los valores indispensables y aplica valores predeterminados
        para los parámetros opcionales asociados al despliegue.
        """
        # La URI de MongoDB es obligatoria porque la aplicación depende de la base.
        uri = os.environ.get("MONGODB_URI", "")
        key = os.environ.get("ADMIN_API_KEY", "")
        if not uri:
            raise RuntimeError("Falta la variable MONGODB_URI")
        # Se exige una longitud mínima para reducir el uso de claves débiles.
        if len(key) < 16:
            raise RuntimeError("ADMIN_API_KEY debe tener al menos 16 caracteres")
        return cls(
            mongodb_uri=uri,
            mongodb_db=os.environ.get("MONGODB_DB", "panaderia"),
            admin_api_key=key,
            app_env=os.environ.get("APP_ENV", "local"),
            version=os.environ.get("APP_VERSION", "local"),
        )