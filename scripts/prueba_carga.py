"""Prueba de carga para comprobar que la Container App escala con el pico de fin de semana.

Manda solicitudes GET al catálogo desde varios hilos a la vez durante un tiempo fijo. La regla de
escalado agrega una réplica por cada 20 solicitudes simultáneas, así que con 60 hilos la app debe
pasar de 1 a 3 réplicas. Mientras corre se puede mirar la métrica Replica Count en el portal.

Uso:
    python scripts/prueba_carga.py https://ca-panaderia-dev.<dominio>.azurecontainerapps.io
    python scripts/prueba_carga.py <url> --concurrencia 60 --duracion 180

Solo usa la biblioteca estándar de Python.
"""

import argparse
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import Counter


def trabajar(url: str, fin: float, tiempos: list, codigos: Counter, candado: threading.Lock) -> None:
    """Hace solicitudes seguidas hasta que se acaba el tiempo."""
    while time.monotonic() < fin:
        inicio = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=30) as respuesta:
                respuesta.read()
                codigo = respuesta.status
        except urllib.error.HTTPError as error:
            codigo = error.code
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            codigo = "sin respuesta"
        duracion = (time.monotonic() - inicio) * 1000
        with candado:
            tiempos.append(duracion)
            codigos[codigo] += 1


def percentil(valores: list, p: float) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, int(len(ordenados) * p))]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba de carga del catálogo de Pan de la Casa")
    parser.add_argument("url", help="URL base de la app, sin la ruta")
    parser.add_argument("--ruta", default="/api/productos", help="Ruta que se consulta (por defecto el catálogo)")
    parser.add_argument("--concurrencia", type=int, default=60, help="Solicitudes simultáneas (por defecto 60)")
    parser.add_argument("--duracion", type=int, default=180, help="Segundos que dura la prueba (por defecto 180)")
    args = parser.parse_args()

    url = args.url.rstrip("/") + args.ruta
    print(f"Calentando la app en {url}")
    for _ in range(20):  # dev escala a cero, la primera respuesta puede tardar
        try:
            urllib.request.urlopen(url, timeout=60).read()
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(5)

    tiempos, codigos, candado = [], Counter(), threading.Lock()
    fin = time.monotonic() + args.duracion
    hilos = [threading.Thread(target=trabajar, args=(url, fin, tiempos, codigos, candado), daemon=True)
             for _ in range(args.concurrencia)]
    print(f"{args.concurrencia} solicitudes simultáneas durante {args.duracion} s")
    comienzo = time.monotonic()
    for hilo in hilos:
        hilo.start()

    anterior = 0
    while any(hilo.is_alive() for hilo in hilos):
        time.sleep(15)
        with candado:
            total = len(tiempos)
            ultimos = tiempos[anterior:]
        if ultimos:
            print(f"  {int(time.monotonic() - comienzo):>4} s  {total:>7} solicitudes  "
                  f"{len(ultimos) / 15:>6.1f} por segundo  mediana {statistics.median(ultimos):>6.0f} ms")
        anterior = total

    segundos = time.monotonic() - comienzo
    exitosas = codigos.get(200, 0)
    print()
    print(f"Solicitudes: {len(tiempos)} en {segundos:.0f} s, {len(tiempos) / segundos:.1f} por segundo")
    print(f"Respuestas 200: {exitosas} ({exitosas / max(1, len(tiempos)):.1%})")
    print(f"Códigos: {dict(codigos)}")
    if tiempos:
        print(f"Tiempo de respuesta: mediana {statistics.median(tiempos):.0f} ms, "
              f"p95 {percentil(tiempos, 0.95):.0f} ms, máximo {max(tiempos):.0f} ms")


if __name__ == "__main__":
    main()
