FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir flask prometheus-client

COPY app/ ./app/
WORKDIR /app/app

EXPOSE 5000

CMD ["python", "app.py"]

