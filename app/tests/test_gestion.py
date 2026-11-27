from datetime import UTC, datetime, timedelta

from panaderia import config


def test_el_administrador_ve_todo_el_catalogo(client, db, admin):
    db.productos.update_one({"_id": "baguette"}, {"$set": {"disponible": False}})
    productos = client.get("/api/admin/productos", headers=admin).json()
    baguette = next(p for p in productos if p["id"] == "baguette")
    assert baguette["disponible"] is False
    assert baguette["unidades"] == 30


def test_ajustar_unidades_y_marcar_agotado(client, admin):
    r = client.patch("/api/admin/productos/pandebono", headers=admin, json={"unidades": 0})
    assert r.json()["agotado"] is True
    r = client.patch("/api/admin/productos/pandebono", headers=admin, json={"unidades": 25})
    assert r.json()["agotado"] is False and r.json()["maximo"] == 25
    r = client.patch("/api/admin/productos/pandebono", headers=admin, json={"unidades": None})
    assert r.json()["unidades"] is None and r.json()["maximo"] is None


def test_cambiar_precio_afecta_los_pedidos_nuevos(client, admin, pedido):
    client.patch("/api/admin/productos/croissant", headers=admin, json={"precio": 4000})
    assert client.post("/api/pedidos", json=pedido).json()["total"] == 2 * 4000 + 6500


def test_ocultar_un_producto_lo_saca_de_la_tienda(client, admin):
    client.patch("/api/admin/productos/galletas-avena", headers=admin, json={"disponible": False})
    assert "galletas-avena" not in [p["id"] for p in client.get("/api/productos").json()]


def test_crear_un_producto(client, admin):
    r = client.post("/api/admin/productos", headers=admin, json={
        "nombre": "Pan aliñado", "descripcion": "Recién horneado.", "categoria": "Tradicionales",
        "precio": 2200, "foto": "/img/pandebono.jpg", "unidades": 30})
    assert r.status_code == 201
    assert r.json()["id"] == "pan-alinado"
    assert "pan-alinado" in [p["id"] for p in client.get("/api/productos").json()]


def test_crear_y_ajustar_un_combo(client, admin):
    r = client.post("/api/admin/productos", headers=admin, json={
        "nombre": "Combo onces", "descripcion": "Croissant y torta.", "categoria": "Combos",
        "precio": 8500, "foto": "/img/croissant.jpg", "tipo": "combo",
        "componentes": [{"producto_id": "croissant", "cantidad": 1},
                        {"producto_id": "torta-zanahoria", "cantidad": 1}]})
    assert r.status_code == 201
    combo = r.json()
    assert combo["maximo"] == 12  # lo limita la torta de zanahoria
    r = client.patch(f"/api/admin/productos/{combo['id']}", headers=admin, json={
        "componentes": [{"producto_id": "croissant", "cantidad": 2},
                        {"producto_id": "torta-zanahoria", "cantidad": 1}]})
    assert r.json()["componentes"][0]["cantidad"] == 2


def test_un_combo_necesita_productos_validos(client, admin):
    base = {"nombre": "Combo raro", "descripcion": "Prueba.", "categoria": "Combos",
            "precio": 5000, "foto": "/img/croissant.jpg", "tipo": "combo"}
    solo_uno = client.post("/api/admin/productos", headers=admin,
                           json={**base, "componentes": [{"producto_id": "croissant", "cantidad": 1}]})
    con_combo = client.post("/api/admin/productos", headers=admin, json={**base, "componentes": [
        {"producto_id": "croissant", "cantidad": 1},
        {"producto_id": "combo-familiar", "cantidad": 1}]})
    assert solo_uno.status_code == con_combo.status_code == 422


def test_las_fotos_disponibles_existen(client, admin):
    fotos = client.get("/api/admin/fotos", headers=admin).json()
    assert "/img/pandebono.jpg" in fotos
    assert all(client.get(f).status_code == 200 for f in fotos)


def _pedido_en(db, dias_atras: int, estado: str, total: int, items: list):
    hora = (datetime.now(config.ZONA) - timedelta(days=dias_atras)).replace(hour=10, minute=0)
    db.pedidos.insert_one({"_id": f"p{dias_atras}{estado}{total}", "nombre": "X", "telefono": "3000000",
                           "hora_recogida": hora.astimezone(UTC), "items": items, "total": total,
                           "estado": estado, "creado_en": datetime.now(UTC), "historial": []})


def test_reporte_por_periodo(client, db, admin):
    client.get("/api/productos")
    pan = [{"producto_id": "pandebono", "nombre": "Pandebono", "precio": 2500, "cantidad": 4,
            "subtotal": 10000}]
    _pedido_en(db, 1, "entregado", 10000, pan)
    _pedido_en(db, 2, "entregado", 10000, pan)
    _pedido_en(db, 2, "cancelado", 7000, pan)
    _pedido_en(db, 40, "entregado", 99000, pan)  # fuera del período
    hoy = datetime.now(config.ZONA).date()
    r = client.get(f"/api/admin/reportes?desde={hoy - timedelta(days=6)}&hasta={hoy}", headers=admin)
    data = r.json()
    assert r.status_code == 200
    assert data["total_pedidos"] == 3
    assert data["entregados"] == 2 and data["ventas"] == 20000
    assert data["ticket_promedio"] == 10000
    assert data["por_estado"]["cancelado"] == {"pedidos": 1, "dinero": 7000}
    assert data["productos"][0] == {"producto_id": "pandebono", "nombre": "Pandebono",
                                    "cantidad": 8, "dinero": 20000}
    assert data["agrupacion"] == "dia" and len(data["serie"]) == 7


def test_reporte_anual_se_agrupa_por_mes(client, admin):
    r = client.get("/api/admin/reportes?desde=2026-01-01&hasta=2026-12-31", headers=admin)
    assert r.json()["agrupacion"] == "mes"
    assert len(r.json()["serie"]) == 12


def test_reporte_con_fechas_invalidas(client, admin):
    al_reves = client.get("/api/admin/reportes?desde=2026-11-30&hasta=2026-11-01", headers=admin)
    muy_largo = client.get("/api/admin/reportes?desde=2024-01-01&hasta=2026-01-01", headers=admin)
    assert al_reves.status_code == muy_largo.status_code == 422
