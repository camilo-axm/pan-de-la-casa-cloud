from datetime import datetime, timedelta

import mongomock
import pytest
from fastapi.testclient import TestClient

from panaderia import config
from panaderia.config import Settings
from panaderia.main import create_app

DUENO = "duena@pandelacasa.co"
CLAVE_DUENO = "clave-del-dueno-2026"


@pytest.fixture
def db():
    return mongomock.MongoClient(tz_aware=True)["pruebas"]


@pytest.fixture
def client(db):
    settings = Settings(mongodb_uri="mongomock://pruebas", mongodb_db="pruebas",
                        owner_email=DUENO, owner_password=CLAVE_DUENO,
                        owner_nombre="Marta Ruiz", app_env="test", version="abc1234")
    with TestClient(create_app(settings, db)) as c:
        # La primera solicitud carga el catálogo y crea la cuenta del dueño.
        assert c.get("/readyz").status_code == 200
        yield c


def ingresar(client, correo: str, clave: str) -> dict:
    r = client.post("/api/auth/login", json={"correo": correo, "clave": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def admin(client):
    """Cabeceras de la sesión del dueño, que tiene todos los permisos."""
    return ingresar(client, DUENO, CLAVE_DUENO)


@pytest.fixture
def crear_usuario(client, admin):
    def crear(rol: str, correo: str | None = None, clave: str = "clave-segura-123") -> dict:
        correo = correo or f"{rol}@pandelacasa.co"
        r = client.post("/api/usuarios", headers=admin,
                        json={"correo": correo, "nombre": f"Persona {rol}", "rol": rol, "clave": clave})
        assert r.status_code == 201, r.text
        return ingresar(client, correo, clave)
    return crear


def manana(hora: int = 10, minuto: int = 0) -> str:
    """Una hora de recogida valida: mañana, dentro del horario, en hora de Colombia."""
    d = datetime.now(config.ZONA) + timedelta(days=1)
    return d.replace(hour=hora, minute=minuto, second=0, microsecond=0).isoformat()


@pytest.fixture
def pedido():
    return {
        "nombre": "Ana Rojas",
        "telefono": "3001234567",
        "hora_recogida": manana(),
        "items": [{"producto_id": "croissant", "cantidad": 2},
                  {"producto_id": "pan-campesino", "cantidad": 1}],
    }
