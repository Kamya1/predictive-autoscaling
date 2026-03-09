FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir numpy pandas requests statsmodels

COPY predictor/ ./predictor/
WORKDIR /app/predictor

CMD ["python", "predictive_scaler.py"]

