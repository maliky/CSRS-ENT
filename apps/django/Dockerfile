FROM node:24-alpine AS frontend

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY apps/django/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/django ./
COPY --from=frontend /build/apps/django/gateway/static/react ./gateway/static/react
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "pent.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
