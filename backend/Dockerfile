FROM node:24-slim AS node-runtime

FROM node:24-slim AS frontend-deps
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FRONTEND_NODE_MODULES_PATH=/opt/codelens/node_modules

WORKDIR /app
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-deps /frontend/node_modules /opt/codelens/node_modules
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

EXPOSE 8000
CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
