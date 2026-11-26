# Pan de la Casa

API de FastAPI para consultar el catálogo y registrar pedidos para recoger en la panadería. El panel de administración usa la misma API para consultar los pedidos y actualizar su estado.

## Ejecutar en Windows

Con Python 3.12, abre PowerShell en la raíz del repositorio y ejecuta:

```powershell
Set-Location app
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:PYTHONPATH = (Resolve-Path .\src).Path
Copy-Item .env.example .env
```

Si ya tienes `.env`, conserva ese archivo y omite la copia. En `.env`, asigna una clave de al menos 16 caracteres a `ADMIN_API_KEY`. La URI de ejemplo apunta a MongoDB publicado en el puerto `27017` de Windows. También puedes usar `MONGODB_URI=mongomock://local` para guardar los pedidos en memoria durante la ejecución. Mantén la clave en `.env`, que está excluido de Git.

```powershell
.\.venv\Scripts\python.exe -m uvicorn panaderia.asgi:app --env-file .env
```

La documentación interactiva está en [localhost:8000/api/docs](http://localhost:8000/api/docs). Para ejecutar la API con MongoDB, basta con instalar `requirements.txt` y configurar la URI de tu instancia.

| Variable | Uso |
| --- | --- |
| `MONGODB_URI` | Obligatoria. URI de conexión a MongoDB. |
| `ADMIN_API_KEY` | Obligatoria. Clave de al menos 16 caracteres para el encabezado `X-Admin-Key`. |
| `MONGODB_DB` | Nombre de la base de datos. Por defecto, `panaderia`. |
| `APP_ENV` | Entorno que devuelve `/api/info`. Por defecto, `local`. |
| `APP_VERSION` | Versión que devuelve `/api/info`. Por defecto, `local`. |

## Ejecutar con Docker Compose

Con Docker Desktop abierto, ejecuta estos comandos desde la raíz del repositorio. Usa el archivo `app/.env` configurado en la sección anterior.

```powershell
docker compose up --build -d
docker compose ps
```

La API queda disponible en [localhost:8002/api/docs](http://localhost:8002/api/docs). Comprueba la conexión con MongoDB en [localhost:8002/readyz](http://localhost:8002/readyz). Compose usa `mongodb://mongo:27017` dentro de su red y guarda los datos de MongoDB en el volumen `datos_mongo`.

Para verificar la persistencia, crea un pedido desde Swagger, reinicia MongoDB con `docker compose restart mongo` y vuelve a consultar el pedido. Si lo creaste con `es_prueba: true`, usa `pruebas=true` al listar. Para detener los servicios conservando el volumen, ejecuta `docker compose down`.

## Rutas principales

| Ruta | Uso |
| --- | --- |
| `GET /api/productos` | Consulta los productos disponibles. |
| `POST /api/pedidos` | Registra un pedido y calcula el total con los precios del catálogo. |
| `GET /api/pedidos` | Lista los pedidos recientes. Requiere la clave administrativa. |
| `PATCH /api/pedidos/{pedido_id}` | Actualiza el estado de un pedido. Requiere la clave administrativa. |
| `GET /healthz` | Comprueba que el proceso está activo. |
| `GET /readyz` | Comprueba que la base de datos responde. |

La recogida se programa en hora de Colombia, entre las 06:00 y las 20:00, con un mínimo de 30 minutos de preparación y hasta siete días de anticipación.

## Pruebas

Desde `app/`, después de instalar `requirements-dev.txt`, ejecuta:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas usan una base de datos en memoria. Dos casos verifican archivos del frontend en `app/src/panaderia/static/`: la página de inicio y el panel, y las imágenes del catálogo.
