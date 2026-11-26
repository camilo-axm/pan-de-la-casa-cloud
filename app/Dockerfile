FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY src ./src

CMD ["python", "-m", "uvicorn", "panaderia.asgi:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]
