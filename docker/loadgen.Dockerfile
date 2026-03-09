FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir httpx

COPY load-generator/ ./load-generator/
WORKDIR /app/load-generator

CMD ["python", "run_load.py"]

