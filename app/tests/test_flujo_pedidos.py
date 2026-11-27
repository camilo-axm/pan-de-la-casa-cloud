import pytest


def nuevo(client, pedido, **cambios):
    r = client.post("/api/pedidos", json={**pedido, **cambios})
    assert r.status_code == 201, r.text
    return r.json()


def mover(client, admin, pid, estado):
    return client.patch(f"/api/pedidos/{pid}", json={"estado": estado}, headers=admin)


def test_el_pedido_avanza_de_recibido_a_entregado(client, pedido, admin):
    p = nuevo(client, pedido)
    assert p["siguientes"] == ["listo", "cancelado"]
    assert mover(client, admin, p["id"], "listo").json()["siguientes"] == ["entregado", "cancelado"]
    final = mover(client, admin, p["id"], "entregado").json()
    assert final["siguientes"] == []
    assert [m["estado"] for m in final["historial"]] == ["recibido", "listo", "entregado"]


@pytest.mark.parametrize("camino, prohibido", [
    ([], "entregado"),                       # no se entrega sin estar listo
    (["listo"], "recibido"),                 # no se devuelve a un estado anterior
    (["listo", "entregado"], "cancelado"),   # lo entregado no se cancela
    (["cancelado"], "listo"),                # lo cancelado no revive
])
def test_saltos_y_retrocesos_se_rechazan(client, pedido, admin, camino, prohibido):
    pid = nuevo(client, pedido)["id"]
    for estado in camino:
        assert mover(client, admin, pid, estado).status_code == 200
    r = mover(client, admin, pid, prohibido)
    assert r.status_code == 409
    assert "no puede pasar" in r.json()["detail"]


def test_repetir_el_mismo_estado_se_rechaza(client, pedido, admin):
    pid = nuevo(client, pedido)["id"]
    assert mover(client, admin, pid, "recibido").status_code == 409


def test_el_historial_registra_quien_hizo_el_cambio(client, pedido, admin):
    pid = nuevo(client, pedido)["id"]
    historial = mover(client, admin, pid, "listo").json()["historial"]
    assert historial[0]["por"] == "cliente"
    assert historial[1]["por"] == "duena@pandelacasa.co"


def test_un_pedido_descuenta_las_existencias(client, db, pedido):
    nuevo(client, pedido)
    assert db.productos.find_one({"_id": "croissant"})["unidades"] == 40 - 2
    assert db.productos.find_one({"_id": "pan-campesino"})["unidades"] == 20 - 1


def test_no_se_vende_mas_de_lo_que_hay(client, db, pedido):
    db.productos.update_one({"_id": "croissant"}, {"$set": {"unidades": 1}})
    r = client.post("/api/pedidos", json=pedido)
    assert r.status_code == 409
    assert "quedan 1" in r.json()["detail"]
    # Si una parte falla, no se descuenta nada del resto del pedido.
    assert db.productos.find_one({"_id": "pan-campesino"})["unidades"] == 20


def test_cancelar_devuelve_las_unidades(client, db, pedido, admin):
    pid = nuevo(client, pedido)["id"]
    mover(client, admin, pid, "cancelado")
    assert db.productos.find_one({"_id": "croissant"})["unidades"] == 40


def test_un_producto_agotado_se_muestra_pero_no_se_vende(client, db, pedido):
    db.productos.update_one({"_id": "croissant"}, {"$set": {"unidades": 0}})
    croissant = next(p for p in client.get("/api/productos").json() if p["id"] == "croissant")
    assert croissant["agotado"] is True
    assert client.post("/api/pedidos", json=pedido).status_code == 409


def test_un_combo_descuenta_sus_productos(client, db, pedido):
    combo = next(p for p in client.get("/api/productos").json() if p["id"] == "combo-tradicional")
    assert combo["tipo"] == "combo"
    assert {c["producto_id"]: c["cantidad"] for c in combo["incluye"]} == {"pandebono": 3, "almojabana": 3}
    data = nuevo(client, pedido, items=[{"producto_id": "combo-tradicional", "cantidad": 2}])
    assert data["total"] == 2 * 14500
    assert db.productos.find_one({"_id": "pandebono"})["unidades"] == 60 - 6
    assert db.productos.find_one({"_id": "almojabana"})["unidades"] == 50 - 6


def test_el_combo_se_agota_cuando_falta_una_parte(client, db):
    db.productos.update_one({"_id": "almojabana"}, {"$set": {"unidades": 5}})
    combo = next(p for p in client.get("/api/productos").json() if p["id"] == "combo-tradicional")
    assert combo["maximo"] == 1
    db.productos.update_one({"_id": "almojabana"}, {"$set": {"unidades": 2}})
    combo = next(p for p in client.get("/api/productos").json() if p["id"] == "combo-tradicional")
    assert combo["agotado"] is True


def test_filtrar_pedidos_por_estado(client, pedido, admin):
    a = nuevo(client, pedido)["id"]
    nuevo(client, pedido)
    mover(client, admin, a, "listo")
    listos = client.get("/api/pedidos?estado=listo", headers=admin).json()
    assert [p["id"] for p in listos] == [a]
