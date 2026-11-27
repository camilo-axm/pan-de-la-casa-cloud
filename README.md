# Pan de la Casa

Sitio web de la panadería con una página de inicio, una tienda para registrar pedidos para recoger y una consulta del estado del pedido. El personal entra a un panel aparte con su correo y contraseña. Desde ahí atiende los pedidos, administra el catálogo (precios, unidades, agotados y combos), consulta reportes por período y, en el caso del dueño, gestiona los usuarios y sus roles.

## Ejecutar en Windows

Con Python 3.12, abre PowerShell en la raíz del repositorio y ejecuta:

```powershell
Set-Location app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PYTHONPATH = (Resolve-Path .\src).Path
Copy-Item .env.example .env
```

Si ya tienes `.env`, conserva ese archivo y omite la copia. En `.env`, escribe el correo del dueño en `OWNER_EMAIL` y una contraseña de al menos 10 caracteres en `OWNER_PASSWORD`. La URI de ejemplo apunta a MongoDB publicado en el puerto `27017` de Windows. También puedes usar `MONGODB_URI=mongomock://local` para guardar los datos en memoria durante la ejecución. `.env` está excluido de Git.

```powershell
.\.venv\Scripts\python.exe -m uvicorn panaderia.asgi:app --env-file .env
```

La página de inicio queda en [localhost:8000](http://localhost:8000), la tienda en [localhost:8000/pedir](http://localhost:8000/pedir), el panel del personal en [localhost:8000/admin](http://localhost:8000/admin) y la documentación interactiva de la API en [localhost:8000/api/docs](http://localhost:8000/api/docs).

| Variable | Uso |
| --- | --- |
| `MONGODB_URI` | Obligatoria. URI de conexión a MongoDB. |
| `OWNER_EMAIL` | Obligatoria. Correo de la cuenta del dueño, que se crea en el primer arranque. |
| `OWNER_PASSWORD` | Obligatoria, mínimo 10 caracteres. Contraseña inicial del dueño. Solo se usa cuando la cuenta todavía no existe. Después se cambia desde **Mi cuenta**. |
| `OWNER_NOMBRE` | Nombre que muestra el panel para el dueño. |
| `MONGODB_DB` | Nombre de la base de datos. Por defecto, `panaderia`. |
| `APP_ENV` | Entorno que devuelve `/api/info`. Por defecto, `local`. |
| `APP_VERSION` | Versión que devuelve `/api/info`. Por defecto, `local`. |

## Ejecutar con Docker Compose

Con Docker Desktop abierto, ejecuta estos comandos desde la raíz del repositorio. Usa el archivo `app/.env` configurado en la sección anterior.

```powershell
docker compose up --build -d
docker compose ps
```

La tienda queda disponible en [localhost:8002](http://localhost:8002) y la API en [localhost:8002/api/docs](http://localhost:8002/api/docs). Comprueba la conexión con MongoDB en [localhost:8002/readyz](http://localhost:8002/readyz). Compose usa `mongodb://mongo:27017` dentro de su red y guarda los datos de MongoDB en el volumen `datos_mongo`.

Para verificar la persistencia, crea un pedido, reinicia MongoDB con `docker compose restart mongo` y vuelve a consultarlo en el panel. Para detener los servicios conservando el volumen, ejecuta `docker compose down`.

## Roles del panel

| Rol | Puede |
| --- | --- |
| Dueño | Todo lo del administrador, y además crear usuarios, cambiar su rol, desactivarlos y asignarles contraseña. Hay un solo dueño. |
| Administrador | Atender pedidos, editar el catálogo y consultar reportes. |
| Empleado | Atender pedidos. |

Las contraseñas se guardan con hash scrypt y sal propia. El panel usa un token de sesión que vence a las 8 horas y que en la base se guarda solo como huella SHA-256. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos. Cambiar el rol, la contraseña o desactivar a alguien cierra sus sesiones abiertas.

## Reglas del negocio

- La recogida se programa en hora de Colombia, entre las 06:00 y las 20:00, con un mínimo de 30 minutos de preparación y hasta siete días de anticipación.
- Los precios y las unidades disponibles salen del catálogo, no de lo que envía el navegador.
- Registrar un pedido descuenta las unidades de forma atómica. Si una parte del pedido no alcanza, no se descuenta nada.
- Un combo no tiene unidades propias: consume las de sus productos, y se agota cuando falta cualquiera de ellos.
- El pedido sigue un flujo fijo: **Recibido → Listo → Entregado**. Se puede **cancelar** mientras no esté entregado, y cancelar devuelve las unidades al inventario. Entregado y cancelado son estados finales. Cada cambio queda en el historial con la hora y la persona que lo hizo.
- Un producto oculto no aparece en la tienda. Uno agotado aparece marcado y no se puede pedir.
- Eliminar un producto lo retira para siempre de la tienda y del panel, pero los pedidos ya hechos conservan su detalle. Un producto que hace parte de un combo no se puede eliminar hasta quitarlo del combo.
- El cliente consulta su pedido con el número y el teléfono. Si alguno no coincide, la respuesta es la misma, para no revelar qué pedidos existen.

## Páginas

| Ruta | Página |
| --- | --- |
| `/` | Inicio: portada, accesos rápidos, productos, combos, cómo pedir, estado del pedido, visita y contacto. |
| `/pedir` (o `/tienda.html`) | Tienda: catálogo, pedido y confirmación. |
| `/admin` (o `/admin.html`) | Panel del personal. No se enlaza desde el sitio. |

La dirección y el horario que muestra "Visítanos" se editan en `NEGOCIO`, al inicio de `app/src/panaderia/static/inicio.js`.

## Rutas principales

| Ruta | Acceso | Uso |
| --- | --- | --- |
| `GET /api/productos` | Público | Catálogo visible, con agotados y combos. |
| `POST /api/pedidos` | Público | Registra un pedido y descuenta existencias. |
| `GET /api/pedidos/consulta?numero=…&telefono=…` | Público | Estado de un pedido, sin datos del personal. |
| `POST /api/mensajes` | Público | Mensaje del formulario de contacto. |
| `POST /api/auth/login` | Público | Inicia sesión con correo y contraseña. |
| `POST /api/auth/logout`, `GET /api/auth/yo`, `POST /api/auth/clave` | Personal | Cierra sesión, consulta el usuario y cambia la contraseña propia. |
| `GET /api/pedidos`, `PATCH /api/pedidos/{id}` | Personal | Lista pedidos y avanza su estado según el flujo. |
| `GET/POST /api/admin/productos`, `PATCH` y `DELETE /api/admin/productos/{id}`, `GET /api/admin/fotos` | Dueño y administrador | Gestiona el catálogo y los combos. |
| `GET /api/admin/mensajes`, `PATCH` y `DELETE /api/admin/mensajes/{id}` | Dueño y administrador | Lee, marca y borra los mensajes de contacto. |
| `GET /api/admin/reportes?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` | Dueño y administrador | Pedidos, dinero y más vendidos del período. |
| `GET/POST /api/usuarios`, `PATCH /api/usuarios/{correo}` | Dueño | Gestiona usuarios y roles. |
| `GET /healthz`, `GET /readyz` | Público | Comprueban el proceso y la base de datos. |

## Pruebas

Desde `app/`, después de instalar `requirements-dev.txt`, ejecuta:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas usan una base de datos en memoria. Cubren el catálogo, los pedidos y sus reglas de horario, el flujo de estados, el inventario y los combos, los reportes, el inicio de sesión, los roles y la gestión de usuarios. Algunos casos verifican archivos del frontend en `app/src/panaderia/static/`: la tienda, el panel y las fotos del catálogo.
