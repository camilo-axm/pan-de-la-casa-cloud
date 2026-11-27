FROM python:3.12-slim

# El pipeline pasa el commit como versión. /api/info la devuelve y la tienda la muestra en el pie.
ARG APP_VERSION=local
ENV APP_VERSION=${APP_VERSION} PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY src ./src

# La aplicación no corre como root.
RUN useradd --create-home --uid 10001 panaderia
USER panaderia

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "panaderia.asgi:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
