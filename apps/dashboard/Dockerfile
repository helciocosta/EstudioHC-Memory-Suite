FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/
COPY static/ static/

EXPOSE 8585

CMD ["python3", "-c", "from src import main; main()"]