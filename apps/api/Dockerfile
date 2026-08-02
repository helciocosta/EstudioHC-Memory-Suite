FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 5050

RUN useradd --create-home --uid 1000 appuser
USER appuser

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5050", "--ssl-keyfile", "/etc/estudiohc/ssl/estudiohc.key", "--ssl-certfile", "/etc/estudiohc/ssl/estudiohc.crt"]