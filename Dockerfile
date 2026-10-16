# Strategy Lab as one container: the built React app served by the FastAPI API.
#   docker build -t strategy-lab .
#   docker run -p 8020:8020 strategy-lab     → http://localhost:8020
# On Render (render.yaml), the platform sets $PORT and the same image runs unchanged.

# --- 1. Build the web app -----------------------------------------------------------------------
FROM node:24-alpine AS web
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- 2. Python runtime: research engine + API ---------------------------------------------------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8020
WORKDIR /app
COPY requirements-api.txt ./
RUN pip install -r requirements-api.txt
COPY *.py ./
COPY strategies/ strategies/
COPY api/ api/
COPY --from=web /src/web/dist web/dist
RUN useradd --create-home --uid 10001 lab
USER lab
EXPOSE 8020
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/health', timeout=4)"
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
