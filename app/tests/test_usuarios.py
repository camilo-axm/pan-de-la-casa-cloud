from conftest import CLAVE_DUENO, DUENO, ingresar


def test_el_dueno_existe_desde_el_primer_arranque(client, admin):
    r = client.get("/api/auth/yo", headers=admin)
    assert r.status_code == 200
    assert r.json() == {"correo": DUENO, "nombre": "Marta Ruiz", "rol": "dueno", "activo": True}


def test_la_contrasena_se_guarda_con_hash(client, db, admin):
    guardada = db.usuarios.find_one({"_id": DUENO})["clave"]
    assert CLAVE_DUENO not in guardada
    assert guardada.startswith("scrypt$")


def test_credenciales_incorrectas_no_dicen_cual_fallo(client):
    malo = client.post("/api/auth/login", json={"correo": DUENO, "clave": "otra-clave-xyz"})
    nadie = client.post("/api/auth/login", json={"correo": "nadie@x.co", "clave": "otra-clave-xyz"})
    assert malo.status_code == nadie.status_code == 401
    assert malo.json() == nadie.json()


def test_cinco_intentos_fallidos_bloquean_la_cuenta(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"correo": DUENO, "clave": "equivocada-123"})
    r = client.post("/api/auth/login", json={"correo": DUENO, "clave": CLAVE_DUENO})
    assert r.status_code == 429


def test_cerrar_sesion_invalida_el_token(client, admin):
    assert client.post("/api/auth/logout", headers=admin).status_code == 204
    assert client.get("/api/auth/yo", headers=admin).status_code == 401


def test_solo_el_dueno_gestiona_usuarios(client, crear_usuario):
    administrador = crear_usuario("administrador")
    empleado = crear_usuario("empleado")
    for cabeceras in (administrador, empleado):
        assert client.get("/api/usuarios", headers=cabeceras).status_code == 403


def test_el_dueno_no_puede_crear_otro_dueno(client, admin):
    r = client.post("/api/usuarios", headers=admin, json={
        "correo": "otro@x.co", "nombre": "Otro", "rol": "dueno", "clave": "clave-segura-123"})
    assert r.status_code == 422


def test_correo_repetido_se_rechaza(client, admin, crear_usuario):
    crear_usuario("empleado", correo="ana@x.co")
    r = client.post("/api/usuarios", headers=admin, json={
        "correo": "ANA@x.co", "nombre": "Ana", "rol": "empleado", "clave": "clave-segura-123"})
    assert r.status_code == 409


def test_cambiar_el_rol_cierra_las_sesiones_del_usuario(client, admin, crear_usuario):
    empleado = crear_usuario("empleado", correo="luis@x.co")
    r = client.patch("/api/usuarios/luis@x.co", headers=admin, json={"rol": "administrador"})
    assert r.json()["rol"] == "administrador"
    assert client.get("/api/auth/yo", headers=empleado).status_code == 401
    nueva = ingresar(client, "luis@x.co", "clave-segura-123")
    assert client.get("/api/admin/productos", headers=nueva).status_code == 200


def test_un_usuario_desactivado_no_entra(client, admin, crear_usuario):
    crear_usuario("empleado", correo="sofi@x.co")
    client.patch("/api/usuarios/sofi@x.co", headers=admin, json={"activo": False})
    r = client.post("/api/auth/login", json={"correo": "sofi@x.co", "clave": "clave-segura-123"})
    assert r.status_code == 403


def test_la_cuenta_del_dueno_no_se_modifica_desde_usuarios(client, admin):
    r = client.patch(f"/api/usuarios/{DUENO}", headers=admin, json={"activo": False})
    assert r.status_code == 403


def test_cambiar_mi_contrasena(client, admin):
    r = client.post("/api/auth/clave", headers=admin,
                    json={"actual": "no-es-esta-123", "nueva": "nueva-clave-2026"})
    assert r.status_code == 422
    r = client.post("/api/auth/clave", headers=admin,
                    json={"actual": CLAVE_DUENO, "nueva": "nueva-clave-2026"})
    assert r.status_code == 204
    assert ingresar(client, DUENO, "nueva-clave-2026")


def test_el_empleado_solo_atiende_pedidos(client, crear_usuario):
    empleado = crear_usuario("empleado")
    assert client.get("/api/pedidos", headers=empleado).status_code == 200
    assert client.get("/api/admin/productos", headers=empleado).status_code == 403
    assert client.get("/api/admin/reportes?desde=2026-11-01&hasta=2026-11-30",
                      headers=empleado).status_code == 403
