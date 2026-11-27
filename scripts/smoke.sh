#!/usr/bin/env bash
set -euo pipefail
die() { echo "Error: $*" >&2; exit 1; }
BASE="${1:-}"
BASE="${BASE%/}"
[[ "$BASE" == https://* || "$BASE" == http://* ]] || die "uso: $0 <url>"
command -v curl >/dev/null && command -v jq >/dev/null || die "se requieren curl y jq"

request() {
  curl --silent --show-error --fail-with-body --max-time 60 -H 'Content-Type: application/json' "$@"
}

echo "Esperando la app (arranque en frio)"
for attempt in {1..20}; do
  curl --silent --fail --max-time 30 "$BASE/readyz" >/dev/null && break
  [[ "$attempt" == 20 ]] && die "la app no quedo lista en $BASE"
  sleep 10
done

echo "Consultando el catalogo"
CATALOGO="$(request "$BASE/api/productos")"
[[ "$(jq length <<<"$CATALOGO")" -ge 1 ]] || die "el catalogo llego vacio"
PRODUCTO="$(jq -r '.[0].id' <<<"$CATALOGO")"
PRECIO="$(jq -r '.[0].precio' <<<"$CATALOGO")"

echo "Registrando un pedido de prueba"
HORA="$(TZ=America/Bogota date -d tomorrow +%Y-%m-%dT10:00:00-05:00)"
PEDIDO="$(jq -n --arg p "$PRODUCTO" --arg h "$HORA" \
  '{nombre: "Prueba de humo", telefono: "3000000000", hora_recogida: $h, es_prueba: true,
    items: [{producto_id: $p, cantidad: 2}]}')"
RESPUESTA="$(request -X POST "$BASE/api/pedidos" -d "$PEDIDO")"
[[ "$(jq -r .estado <<<"$RESPUESTA")" == "recibido" ]] || die "el pedido no quedo registrado"
[[ "$(jq -r .total <<<"$RESPUESTA")" == "$((PRECIO * 2))" ]] || die "total inesperado"

echo "Comprobando que el panel exige la clave"
CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' "$BASE/api/pedidos")"
[[ "$CODE" == 401 ]] || die "la API listo pedidos sin clave ($CODE)"

echo "Prueba de humo correcta en $BASE"
