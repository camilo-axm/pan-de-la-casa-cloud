# Requerimientos y casos de uso de Pan de la Casa

El MVP permite consultar el catálogo de la panadería y registrar pedidos para recoger. El personal entra a un panel aparte con correo y contraseña. Desde ahí atiende los pedidos, administra el catálogo y consulta reportes. El dueño, además, gestiona los usuarios y sus roles.

## 1. Lista general de requerimientos

### 1.1 Requerimientos funcionales

El sistema de pan de la casa debe tener la capacidad de:

1. La tienda debe mostrar los productos disponibles con nombre, descripción, categoría, precio e imagen. 
2. El cliente debe poder seleccionar productos, ajustar cantidades y revisar el resumen antes de enviar el pedido.
3. El sistema debe recibir el nombre, el teléfono y la hora de recogida, validar el pedido, calcular el total con los precios del catálogo y devolver un identificador de confirmación.
4. El personal debe ingresar al panel con su correo y su contraseña. El panel no se enlaza desde la tienda y debe informar si las credenciales fueron rechazadas.
5. El sistema debe mostrar al personal autorizado los pedidos, ordenados por hora de recogida, con sus productos, cliente, total y estado. Los pedidos marcados como prueba se excluyen de la consulta predeterminada.
6. El personal debe poder avanzar un pedido solo por el flujo `recibido` → `listo` → `entregado`, o cancelarlo antes de entregarlo. Cada cambio queda registrado con la hora y la persona que lo hizo.
7. El dueño y los administradores deben poder editar el catálogo: crear productos, cambiar precio, descripción, categoría y foto, ajustar las unidades disponibles, marcar un producto como agotado y ocultarlo o mostrarlo en la tienda.
8. El dueño y los administradores deben poder crear y ajustar combos formados por productos del catálogo. Un combo consume las unidades de sus productos.
9. El dueño y los administradores deben poder consultar un reporte por día, semana, mes, año o rango de fechas, con la cantidad de pedidos y el dinero por estado, las ventas entregadas, el valor promedio por pedido y los productos más vendidos.
10. El dueño debe poder crear usuarios con rol de administrador o empleado, cambiar su rol, desactivarlos y asignarles una contraseña nueva. Cada persona puede cambiar su propia contraseña.
11. El dueño y los administradores deben poder eliminar productos y combos del catálogo. Un producto que hace parte de un combo no se elimina hasta quitarlo del combo, y los pedidos ya registrados conservan su detalle.
12. El sitio debe tener una página de inicio con la presentación de la panadería y accesos a los productos, al pedido, a la consulta del estado del pedido, a la ubicación y al contacto.
13. El cliente debe poder consultar el estado de su pedido con el número de pedido y su teléfono, sin iniciar sesión.
14. El cliente debe poder enviar un mensaje desde la sección de contacto. El dueño y los administradores lo leen en el panel.


### 1.2 Requerimientos no funcionales

El sistema de pan de la casa debe tener:

1. Las rutas del personal deben exigir un token de sesión vigente y el rol adecuado. Responden HTTP `401` sin sesión y `403` si el rol no alcanza. Las contraseñas se guardan con hash scrypt, la sesión vence a las 8 horas y la cuenta se bloquea 15 minutos tras 5 intentos fallidos. La contraseña inicial del dueño se configura fuera del control de versiones.
2. El catálogo, la revisión y la confirmación deben poder usarse en escritorio y en móvil. Los mensajes de validación deben indicar el dato o la condición que impide registrar el pedido.
3. Los pedidos deben seguir disponibles al reiniciar MongoDB mientras se conserve el volumen de datos.
4. La API y MongoDB deben poder iniciarse con `docker compose up --build` usando la configuración local documentada.
5. El servicio debe exponer `/healthz` para comprobar el proceso y `/readyz` para comprobar la conexión a MongoDB. El registro de las solicitudes de negocio debe incluir método, ruta, código HTTP y duración.
6. El proyecto debe incluir pruebas automatizadas del catálogo, la creación de pedidos, el flujo de estados, el inventario, los reportes, los roles y las operaciones administrativas. La suite completa debe pasar antes de fusionar el MVP a `develop`.
7. Registrar un pedido debe descontar las unidades de forma atómica: si una parte no alcanza, no se descuenta nada y el cliente recibe el motivo.

### 1.3 Requerimientos no funcionales del enunciado

El enunciado fija seis requisitos no funcionales para cualquier caso. Así los cubre la arquitectura:

| Requisito | Meta | Cómo se cumple |
| --- | --- | --- |
| Presupuesto | Máximo USD 150 al mes en producción | Estimación de producción de USD 25,85 al mes y de USD 46,80 en alta demanda, con alerta de presupuesto en Azure. |
| Disponibilidad | 99,5 % en horario comercial | Container Apps y Cosmos DB con SLA de 99,9 % o más, y comprobaciones `/healthz` y `/readyz` para que la plataforma reemplace réplicas con problemas. |
| Seguridad | HTTPS, secretos fuera del código y mínimo privilegio | Solo HTTPS en el ingreso, secretos en Key Vault leídos por una identidad administrada, despliegue con OIDC sin secretos guardados, roles RBAC acotados y roles propios en el panel. |
| Respaldo | RPO 24 h y RTO 4 h | Respaldo continuo de Cosmos DB con restauración a un punto en el tiempo de hasta 7 días, y recreación de la infraestructura con Terraform desde el pipeline. |
| Escalabilidad | Soportar 3 veces la carga en temporada alta | Container Apps escala por solicitudes HTTP y Cosmos DB tiene autoescalado de rendimiento. |
| Observabilidad | Logs centralizados, métricas y al menos una alerta | Cada solicitud deja una línea JSON en Log Analytics con ruta, código y duración. Métricas de Container Apps y alertas de errores y de presupuesto en Azure Monitor. |

## 2. Casos de uso

### 2.1 CU-01 · Consultar el catálogo

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-01 |
| **Actor** | Cliente |
| **Precondiciones** | La tienda y el servicio de catálogo están disponibles. |
| **Flujo principal** | 1. El cliente abre la tienda.<br>2. El sistema consulta los productos disponibles y los ordena por nombre.<br>3. La tienda muestra la información de cada producto. |
| **Flujo alternativo** | Si el catálogo está vacío, la tienda indica que no hay productos disponibles. |
| **Diagrama de caso de uso** | <img width="827" height="248" alt="image" src="https://github.com/user-attachments/assets/533db934-230b-45bd-b294-9875bebb9cef" />|
| **Poscondiciones** | El cliente puede seleccionar productos del catálogo. |

### 2.2 CU-02 · Revisar el pedido

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-02 |
| **Actor** | Cliente |
| **Precondiciones** | El cliente abrió el catálogo y seleccionó al menos un producto. |
| **Flujo principal** | 1. El cliente abre el resumen.<br>2. La tienda muestra los productos, las cantidades y el total estimado.<br>3. El cliente ajusta las cantidades si es necesario y continúa al registro. |
| **Flujo alternativo** | Si elimina todos los productos, el cliente debe volver al catálogo y seleccionar al menos uno para continuar. |
| **Diagrama de caso de uso** |<img width="802" height="272" alt="image" src="https://github.com/user-attachments/assets/7d842642-6263-40c3-8354-a10992b2ebd8" />|
| **Poscondiciones** | La selección queda lista para confirmar. |

### 2.3 CU-03 · Registrar un pedido para recoger

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-03 |
| **Actor** | Cliente |
| **Precondiciones** | El cliente revisó un pedido con al menos un producto. |
| **Flujo principal** | 1. El cliente ingresa nombre, teléfono y hora de recogida.<br>2. Confirma el pedido.<br>3. El sistema valida los datos, el horario y la disponibilidad de los productos.<br>4. El servidor calcula el total con los precios del catálogo y guarda el pedido en estado `recibido`.<br>5. La tienda muestra el identificador del pedido y el total confirmado. |
| **Flujo alternativo** | Si los datos son inválidos, la hora no cumple las reglas o un producto dejó de estar disponible, el sistema rechaza el registro e indica el motivo. El cliente puede corregir el pedido y volver a enviarlo. |
| **Reglas de negocio** | La recogida se programa en hora de Colombia, entre las 06:00 y las 20:00, con al menos 30 minutos de preparación y hasta siete días de anticipación. |
| **Diagrama de caso de uso** |<img width="831" height="257" alt="image" src="https://github.com/user-attachments/assets/f6f9f578-be73-4b83-9434-e3cf8abd50c4" />|
| **Poscondiciones** | El pedido queda registrado y disponible para consulta administrativa. |

### 2.4 CU-04 · Acceder al panel

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-04 |
| **Actor** | Administrador |
| **Precondiciones** | La persona tiene una cuenta activa creada por el dueño, o es el dueño. |
| **Flujo principal** | 1. La persona abre `/admin` e ingresa su correo y su contraseña.<br>2. La API verifica la contraseña contra su hash y crea una sesión de 8 horas.<br>3. El panel muestra solo las secciones que permite su rol. |
| **Flujo alternativo** | Si las credenciales son incorrectas, el panel lo indica sin revelar cuál dato falló. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos. Una cuenta desactivada no puede entrar. |
| **Diagrama de caso de uso** |<img width="847" height="238" alt="image" src="https://github.com/user-attachments/assets/5daf7918-89ef-430d-9d0b-9d6f52543545" />|
| **Poscondiciones** | La persona usa el panel con su sesión. La API verifica la sesión y el rol en cada solicitud. |

### 2.5 CU-05 · Consultar los pedidos

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-05 |
| **Actor** | Administrador |
| **Precondiciones** | El panel dispone de una clave administrativa válida y MongoDB está disponible. |
| **Flujo principal** | 1. El administrador abre o actualiza la lista.<br>2. El panel solicita los pedidos recientes con la clave.<br>3. La API devuelve los pedidos en orden descendente de creación, excluyendo los registros de prueba por defecto.<br>4. El panel muestra los productos, la hora de recogida y el estado de cada pedido. |
| **Flujo alternativo** | Si no hay pedidos para mostrar, el panel presenta una lista vacía con el mensaje correspondiente. |
| **Diagrama de caso de uso** |<<img width="857" height="253" alt="image" src="https://github.com/user-attachments/assets/01261248-83ab-4eb2-a453-6ec85159227e" />|
| **Poscondiciones** | El administrador puede revisar los pedidos y seleccionar uno para actualizarlo. |

### 2.6 CU-06 · Actualizar el estado de un pedido

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-06 |
| **Actor** | Administrador |
| **Precondiciones** | El administrador tiene una clave válida y puede seleccionar un pedido del listado. |
| **Flujo principal** | 1. El panel muestra en cada pedido solo las acciones permitidas: *Marcar listo*, *Entregar* o *Cancelar*.<br>2. La persona elige una acción y confirma la entrega o la cancelación.<br>3. La API comprueba que el paso respete el flujo, guarda el cambio y lo agrega al historial.<br>4. Si el pedido se cancela, las unidades vuelven al inventario. |
| **Flujo alternativo** | Si el pedido ya no existe, la API devuelve HTTP `404`. Si el paso salta o retrocede en el flujo, o si otra persona cambió el pedido al mismo tiempo, devuelve HTTP `409`. El panel informa el motivo y recarga la lista. |
| **Diagrama de caso de uso** |<<img width="862" height="295" alt="image" src="https://github.com/user-attachments/assets/d6bbb227-5fa4-48ee-855c-ff958db9ecd9" />|
| **Poscondiciones** | El nuevo estado queda guardado y aparece en las próximas consultas. |

### 2.7 CU-07 · Gestionar el catálogo y los combos

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-07, RF-08 |
| **Actor** | Dueño o administrador |
| **Precondiciones** | La persona inició sesión con uno de esos roles. |
| **Flujo principal** | 1. Abre la sección Catálogo.<br>2. Ajusta las unidades, marca un producto como agotado, lo oculta o lo edita.<br>3. Para un combo, elige los productos que incluye y sus cantidades.<br>4. La API valida los datos y guarda el cambio. La tienda lo refleja en la siguiente consulta. |
| **Flujo alternativo** | Un combo con menos de dos productos, con productos repetidos o que incluye otro combo se rechaza con HTTP `422`. |
| **Poscondiciones** | El catálogo de la tienda muestra los precios, existencias y combos actualizados. |

### 2.8 CU-08 · Consultar el reporte de un período

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-09 |
| **Actor** | Dueño o administrador |
| **Precondiciones** | La persona inició sesión con uno de esos roles. |
| **Flujo principal** | 1. Abre la sección Reportes.<br>2. Elige hoy, esta semana, este mes, este año o un rango de fechas.<br>3. El panel muestra pedidos y dinero por estado, ventas entregadas, valor promedio por pedido, productos más vendidos y la gráfica de ventas por día o por mes. |
| **Flujo alternativo** | Si la fecha final es anterior a la inicial o el rango supera un año, la API responde HTTP `422`. |
| **Poscondiciones** | La persona conoce el resultado del período elegido. |

### 2.9 CU-09 · Gestionar usuarios y roles

| Campo | Descripción |
| --- | --- |
| **Requerimiento asociado** | RF-10 |
| **Actor** | Dueño |
| **Precondiciones** | El dueño inició sesión. |
| **Flujo principal** | 1. Abre la sección Usuarios.<br>2. Crea una persona con nombre, correo, rol y contraseña inicial, o cambia el rol, desactiva o asigna una contraseña nueva a alguien existente.<br>3. La API guarda el cambio y cierra las sesiones abiertas de esa persona cuando cambia su rol, su contraseña o su estado. |
| **Flujo alternativo** | Un correo repetido se rechaza con HTTP `409`. La cuenta del dueño no se modifica desde esta sección, y no se puede crear un segundo dueño. |
| **Poscondiciones** | Cada persona ve en el panel solo lo que permite su rol. |
