"""Configuración de la aplicación y reglas de recogida."""

import os
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Bogota")
HORA_APERTURA = time(6, 0)
HORA_CIERRE = time(20, 0)
MINUTOS_PREPARACION = 30
DIAS_MAXIMOS = 7


@dataclass(frozen=True)
class Settings:
    """Parámetros de conexión, autenticación y despliegue."""

    mongodb_uri: str
    mongodb_db: str
    admin_api_key: str
    app_env: str
    version: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Lee y valida las variables de entorno."""
        uri = os.environ.get("MONGODB_URI", "")
        key = os.environ.get("ADMIN_API_KEY", "")
        if not uri:
            raise RuntimeError("Falta la variable MONGODB_URI")
        if len(key) < 16:
            raise RuntimeError("ADMIN_API_KEY debe tener al menos 16 caracteres")
        return cls(
            mongodb_uri=uri,
            mongodb_db=os.environ.get("MONGODB_DB", "panaderia"),
            admin_api_key=key,
            app_env=os.environ.get("APP_ENV", "local"),
            version=os.environ.get("APP_VERSION", "local"),
        )
