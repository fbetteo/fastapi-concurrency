# Dockerfile
FROM python:3.12-slim

# System deps for py-spy (ptrace) and jemalloc
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps curl gdb htop libjemalloc2 \
 && rm -rf /var/lib/apt/lists/*

# Python deps: keep it lean
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] gunicorn\
    psutil \
    py-spy

# App files
COPY ./app /app
WORKDIR /app
# (You will add your app files later.)
# e.g., COPY . /app

# Default: single worker so you can reason about one PID
ENV UVICORN_CMD="uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"
# ENV UVICORN_CMD="LD_PRELOAD=libjemalloc.so.2 uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"
# ENV UVICORN_CMD="LD_PRELOAD=libjemalloc.so.2 gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --max-requests 2 --max-requests-jitter 1"
CMD sh -c "$UVICORN_CMD"
