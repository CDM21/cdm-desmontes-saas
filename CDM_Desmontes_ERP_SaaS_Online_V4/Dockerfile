# Build do frontend React/Vite
FROM node:22-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Backend FastAPI + frontend estático no mesmo domínio
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST=/app/frontend_dist
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
# CDM V47: modelo local leve para remoção de fundo; sem custo por foto.
RUN mkdir -p /app/backend/app/models && python -c "import urllib.request,hashlib,pathlib; u='https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx'; p=pathlib.Path('/app/backend/app/models/u2netp.onnx'); urllib.request.urlretrieve(u,p); h=hashlib.md5(p.read_bytes()).hexdigest(); assert h=='8e83ca70e441ab06c318d82300c84806', h"
COPY --from=frontend-build /src/frontend/dist /app/frontend_dist
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
