"""Eliminar productos, consultar un pedido y mensajes de contacto."""

from panaderia.db import prepare

# ---------- Eliminar del catálogo ----------

def test_eliminar_un_producto_lo_quita_de_todas_partes(client, admin):
    assert client.delete("/api/admin/productos/galletas-avena", headers=admin).status_code == 204
    assert "galletas-avena" not in [p["id"] for p in client.get("/api/productos").json()]
    assert "galletas-avena" not in [p["id"] for p in client.get("/api/admin/productos", headers=admin).json()]
    assert client.delete("/api/admin/productos/galletas-avena", headers=admin).status_code == 404


def test_un_producto_eliminado_no_se_puede_pedir(client, admin, pedido):
    client.delete("/api/admin/productos/galletas-avena", headers=admin)
    r = client.post("/api/pedidos", json={**pedido, "items": [{"producto_id": "galletas-avena", "cantidad": 1}]})
    assert r.status_code == 422


def test_un_producto_eliminado_no_vuelve_al_reiniciar(client, db, admin):
    client.delete("/api/admin/productos/galletas-avena", headers=admin)
    prepare(db)  # el arranque vuelve a cargar el catálogo inicial
    assert "galletas-avena" not in [p["id"] for p in client.get("/api/productos").json()]


def test_no_se_elimina_un_producto_que_esta_en_un_combo(client, admin):
    r = client.delete("/api/admin/productos/pandebono", headers=admin)
    assert r.status_code == 409
    assert "Combo tradicional" in r.json()["detail"]


def test_eliminar_el_combo_libera_sus_productos(client, admin):
    assert client.delete("/api/admin/productos/combo-tradicional", headers=admin).status_code == 204
    assert client.delete("/api/admin/productos/pandebono", headers=admin).status_code == 204
    # La baguette sigue dentro del combo familiar.
    assert client.delete("/api/admin/productos/baguette", headers=admin).status_code == 409


def test_los_pedidos_conservan_lo_que_se_elimino(client, admin, pedido):
    pid = client.post("/api/pedidos", json=pedido).json()["id"]
    client.delete("/api/admin/productos/croissant", headers=admin)
    p = next(x for x in client.get("/api/pedidos", headers=admin).json() if x["id"] == pid)
    assert "Croissant de mantequilla" in [i["nombre"] for i in p["items"]]


def test_un_empleado_no_elimina_productos(client, crear_usuario):
    empleado = crear_usuario("empleado")
    assert client.delete("/api/admin/productos/baguette", headers=empleado).status_code == 403


def test_el_id_de_un_producto_eliminado_no_se_reutiliza(client, admin):
    client.delete("/api/admin/productos/galletas-avena", headers=admin)
    r = client.post("/api/admin/productos", headers=admin, json={
        "nombre": "Galletas avena", "descripcion": "Nueva receta.", "categoria": "Repostería",
        "precio": 9500, "foto": "/img/galletas-avena.jpg", "unidades": 10})
    assert r.status_code == 201
    assert r.json()["id"] == "galletas-avena-2"


# ---------- Consultar un pedido ----------

def test_el_cliente_consulta_su_pedido(client, admin, pedido):
    pid = client.post("/api/pedidos", json=pedido).json()["id"]
    client.patch(f"/api/pedidos/{pid}", json={"estado": "listo"}, headers=admin)
    r = client.get(f"/api/pedidos/consulta?numero={pid}&telefono={pedido['telefono']}")
    assert r.status_code == 200
    data = r.json()
    assert data["estado"] == "listo"
    assert data["nombre"] == "Ana"
    assert [h["estado"] for h in data["historial"]] == ["recibido", "listo"]
    # No expone el teléfono ni quién del personal hizo los cambios.
    assert "telefono" not in data
    assert all("por" not in h for h in data["historial"])


def test_la_consulta_exige_el_telefono_correcto(client, pedido):
    pid = client.post("/api/pedidos", json=pedido).json()["id"]
    malo = client.get(f"/api/pedidos/consulta?numero={pid}&telefono=3110000000")
    inexistente = client.get("/api/pedidos/consulta?numero=0000000000&telefono=3001234567")
    assert malo.status_code == inexistente.status_code == 404
    assert malo.json() == inexistente.json()


# ---------- Mensajes de contacto ----------

def test_un_mensaje_llega_al_panel(client, admin):
    r = client.post("/api/mensajes", json={"nombre": "Juan Díaz", "contacto": "3001234567",
                                           "asunto": "encargo", "mensaje": "Quiero 50 pandebonos para el sábado."})
    assert r.status_code == 201
    mensajes = client.get("/api/admin/mensajes", headers=admin).json()
    assert mensajes[0]["nombre"] == "Juan Díaz" and mensajes[0]["leido"] is False
    mid = mensajes[0]["id"]
    assert client.patch(f"/api/admin/mensajes/{mid}", json={"leido": True}, headers=admin).json()["leido"]
    assert client.delete(f"/api/admin/mensajes/{mid}", headers=admin).status_code == 204
    assert client.get("/api/admin/mensajes", headers=admin).json() == []


def test_los_mensajes_de_bots_no_se_guardan(client, admin):
    client.post("/api/mensajes", json={"nombre": "Bot", "contacto": "bot@x.co", "asunto": "otro",
                                       "mensaje": "Oferta increíble", "sitio": "http://spam"})
    assert client.get("/api/admin/mensajes", headers=admin).json() == []


def test_los_mensajes_son_privados(client, crear_usuario):
    assert client.get("/api/admin/mensajes").status_code == 401
    assert client.get("/api/admin/mensajes", headers=crear_usuario("empleado")).status_code == 403


# ---------- Páginas del sitio ----------

def test_el_sitio_tiene_inicio_tienda_y_panel_separados(client):
    inicio = client.get("/").text
    assert "Hacer pedido" in inicio and "admin" not in inicio  # el panel no se enlaza desde el sitio
    assert "Pan de la Casa" in client.get("/tienda.html").text
    assert client.get("/pedir", follow_redirects=False).headers["location"] == "/tienda.html"
    assert client.get("/admin", follow_redirects=False).headers["location"] == "/admin.html"
    assert client.get("/img/sitio/portada.jpg").status_code == 200
