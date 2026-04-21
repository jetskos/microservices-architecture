# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --upgrade pip && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd -g 1000 appgroup && useradd -u 1000 -g appgroup -m appuser
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels
COPY . .
RUN python manage.py collectstatic --noinput || true
USER 1000:1000
EXPOSE 8000
CMD ["gunicorn", "auth_service.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
