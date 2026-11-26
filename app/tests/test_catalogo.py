from panaderia.db import prepare


def test_el_catalogo_trae_foto_y_precio(client):
    r = client.get("/api/productos")
    assert r.status_code == 200
    productos = r.json()
    assert len(productos) == 8
    for p in productos:
        assert p["precio"] > 0
        assert p["foto"].startswith("/img/")
        assert client.get(p["foto"]).status_code == 200


def test_el_catalogo_llega_ordenado_por_nombre(client):
    nombres = [p["nombre"] for p in client.get("/api/productos").json()]
    assert nombres == sorted(nombres)


def test_reiniciar_la_app_no_duplica_ni_pisa_el_catalogo(client, db):
    client.get("/api/productos")
    db.productos.update_one({"_id": "baguette"}, {"$set": {"precio": 5000}})
    # Simula un reinicio del contenedor: la preparacion vuelve a ejecutarse.
    prepare(db)
    assert db.productos.count_documents({}) == 8
    assert db.productos.find_one({"_id": "baguette"})["precio"] == 5000


def test_un_producto_no_disponible_no_aparece(client, db):
    client.get("/api/productos")
    db.productos.update_one({"_id": "croissant"}, {"$set": {"disponible": False}})
    ids = [p["id"] for p in client.get("/api/productos").json()]
    assert "croissant" not in ids
    assert len(ids) == 7


def test_salud_e_informacion(client):
    assert client.get("/healthz").json() == {"estado": "ok"}
    assert client.get("/readyz").json() == {"estado": "ok"}
    assert client.get("/api/info").json() == {"ambiente": "test", "version": "abc1234"}


def test_el_sitio_sirve_la_pagina_y_el_panel(client):
    inicio = client.get("/")
    assert inicio.status_code == 200
    assert "Pan de la Casa" in inicio.text
    assert inicio.headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/admin.html").status_code == 200