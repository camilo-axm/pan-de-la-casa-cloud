"""Configuración de la aplicación, reglas de recogida y reglas de acceso."""

import os
import re
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo

ZONA = ZoneInfo("America/Bogota")
HORA_APERTURA = time(6, 0)
HORA_CIERRE = time(20, 0)
MINUTOS_PREPARACION = 30
DIAS_MAXIMOS = 7

# Sesiones del panel y protección contra intentos repetidos de inicio de sesión.
HORAS_SESION = 8
INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15
LARGO_MINIMO_CLAVE = 10

CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Settings:
    """Parámetros de conexión, cuenta inicial del dueño y despliegue."""

    mongodb_uri: str
    mongodb_db: str
    owner_email: str
    owner_password: str
    owner_nombre: str
    app_env: str
    version: str

    @classmethod
    def from_env(cls) -> "Settings":
        """Lee y valida las variables de entorno."""
        uri = os.environ.get("MONGODB_URI", "")
        correo = os.environ.get("OWNER_EMAIL", "").strip().lower()
        clave = os.environ.get("OWNER_PASSWORD", "")
        if not uri:
            raise RuntimeError("Falta la variable MONGODB_URI")
        if not CORREO.match(correo):
            raise RuntimeError("OWNER_EMAIL debe ser el correo del dueño")
        if len(clave) < LARGO_MINIMO_CLAVE:
            raise RuntimeError(
                f"OWNER_PASSWORD debe tener al menos {LARGO_MINIMO_CLAVE} caracteres")
        return cls(
            mongodb_uri=uri,
            mongodb_db=os.environ.get("MONGODB_DB", "panaderia"),
            owner_email=correo,
            owner_password=clave,
            owner_nombre=os.environ.get("OWNER_NOMBRE", "Dueño de la panadería"),
            app_env=os.environ.get("APP_ENV", "local"),
            version=os.environ.get("APP_VERSION", "local"),
        )
