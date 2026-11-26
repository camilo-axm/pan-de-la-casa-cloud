from datetime import datetime, timedelta

import mongomock
import pytest
from fastapi.testclient import TestClient

from panaderia import config
from panaderia.config import Settings
from panaderia.main import create_app

ADMIN_KEY = "clave-de-prueba-0123456789"


@pytest.fixture
def db():
    return mongomock.MongoClient(tz_aware=True)["pruebas"]


@pytest.fixture
def client(db):
    settings = Settings(mongodb_uri="mongomock://pruebas", mongodb_db="pruebas",
                        admin_api_key=ADMIN_KEY, app_env="test", version="abc1234")
    with TestClient(create_app(settings, db)) as c:
        yield c


@pytest.fixture
def admin():
    return {"X-Admin-Key": ADMIN_KEY}


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