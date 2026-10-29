FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /app

RUN useradd --create-home appuser \
    && mkdir /data \
    && chown appuser:appuser /data

COPY src/ ./

USER appuser

ENTRYPOINT ["python", "add_reading.py"]
