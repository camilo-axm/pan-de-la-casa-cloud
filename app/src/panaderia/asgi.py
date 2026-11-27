"""Punto de entrada de uvicorn: uvicorn panaderia.asgi:app"""

import logging

from .main import create_app

logging.basicConfig(level=logging.INFO, format="%(message)s")
app = create_app()
