from datetime import datetime, timedelta

import pytest

from conftest import manana
from panaderia import config


def test_registrar_un_pedido_calcula_el_total_con_el_catalogo(client, pedido):
    r = client.post("/api/pedidos", json=pedido)
    assert r.status_code == 201
    data = r.json()
    assert data["estado"] == "recibido"
    assert data["total"] == 2 * 3800 + 6500
    assert {i["producto_id"] for i in data["items"]} == {"croissant", "pan-campesino"}
    assert len(data["id"]) == 10


def test_el_precio_enviado_por_el_cliente_se_ignora(client, pedido):
    pedido["items"] = [{"producto_id": "baguette", "cantidad": 1, "precio": 1}]
    assert client.post("/api/pedidos", json=pedido).json()["total"] == 4200


def test_el_mismo_producto_repetido_se_suma(client, pedido):
    pedido["items"] = [{"producto_id": "pandebono", "cantidad": 2},
                       {"producto_id": "pandebono", "cantidad": 3}]
    data = client.post("/api/pedidos", json=pedido).json()
    assert data["items"][0]["cantidad"] == 5
    assert data["total"] == 5 * 2500


def test_producto_inexistente_se_rechaza(client, pedido):
    pedido["items"] = [{"producto_id": "pizza", "cantidad": 1}]
    r = client.post("/api/pedidos", json=pedido)
    assert r.status_code == 422
    assert "pizza" in r.json()["detail"]


@pytest.mark.parametrize("campo, valor", [
    ("nombre", "A"),
    ("telefono", "abc"),
    ("telefono", "123"),
    ("items", []),
    ("items", [{"producto_id": "baguette", "cantidad": 0}]),
    ("items", [{"producto_id": "baguette", "cantidad": 51}]),
])
def test_datos_invalidos_se_rechazan(client, pedido, campo, valor):
    pedido[campo] = valor
    assert client.post("/api/pedidos", json=pedido).status_code == 422


def test_la_recogida_necesita_tiempo_de_preparacion(client, pedido):
    pedido["hora_recogida"] = (datetime.now(config.ZONA) + timedelta(minutes=5)).isoformat()
    assert client.post("/api/pedidos", json=pedido).status_code == 422


def test_la_recogida_debe_estar_en_el_horario(client, pedido):
    pedido["hora_recogida"] = manana(hora=22)
    r = client.post("/api/pedidos", json=pedido)
    assert r.status_code == 422
    assert "6:00" in r.json()["detail"]


def test_no_se_aceptan_pedidos_a_mas_de_una_semana(client, pedido):
    lejos = datetime.now(config.ZONA) + timedelta(days=10)
    pedido["hora_recogida"] = lejos.replace(hour=10, minute=0).isoformat()
    assert client.post("/api/pedidos", json=pedido).status_code == 422


def test_listar_pedidos_exige_la_clave(client, pedido):
    client.post("/api/pedidos", json=pedido)
    assert client.get("/api/pedidos").status_code == 401
    otra = {"X-Admin-Key": "otra-clave-0123456789"}
    assert client.get("/api/pedidos", headers=otra).status_code == 401


def test_el_administrador_ve_primero_el_pedido_mas_reciente(client, db, pedido, admin):
    primero = client.post("/api/pedidos", json=pedido).json()["id"]
    hace_un_rato = datetime.now(config.ZONA) - timedelta(minutes=5)
    db.pedidos.update_one({"_id": primero}, {"$set": {"creado_en": hace_un_rato}})
    segundo = client.post("/api/pedidos", json={**pedido, "nombre": "Luis Mora"}).json()["id"]
    r = client.get("/api/pedidos", headers=admin)
    assert r.status_code == 200
    assert [p["id"] for p in r.json()] == [segundo, primero]


def test_los_pedidos_de_prueba_no_salen_en_el_panel(client, pedido, admin):
    client.post("/api/pedidos", json={**pedido, "es_prueba": True})
    assert client.get("/api/pedidos", headers=admin).json() == []
    assert len(client.get("/api/pedidos?pruebas=true", headers=admin).json()) == 1


def test_el_administrador_cambia_el_estado(client, pedido, admin):
    pid = client.post("/api/pedidos", json=pedido).json()["id"]
    assert client.patch(f"/api/pedidos/{pid}", json={"estado": "listo"}).status_code == 401
    r = client.patch(f"/api/pedidos/{pid}", json={"estado": "listo"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["estado"] == "listo"
    r = client.patch("/api/pedidos/noexiste", json={"estado": "listo"}, headers=admin)
    assert r.status_code == 404
    r = client.patch(f"/api/pedidos/{pid}", json={"estado": "volando"}, headers=admin)
    assert r.status_code == 422
    