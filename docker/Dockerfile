# syntax=docker/dockerfile:1
# Setu Guide API - Day 2 image. Owner: DevOps 1.
# No secrets are baked in: every setting arrives at runtime from the
# environment (.env / docker-compose.yml). See .dockerignore.

# ---------------------------------------------------------------- builder
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------- runtime
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000

# Non-root user (no login shell, no home permissions needed).
RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app

# Model / knowledge-base files are NOT baked into the image (they are large and
# change independently). Mount them at runtime instead:
#   docker run -v ./models:/app/models:ro ...   (or /app/data)
# TODO(AI/ML): once those files are added, re-check `docker images` - the image
# size must stay small, so keep mounting them as a volume rather than COPYing.
RUN mkdir -p /app/models /app/data && chown -R app:app /app

USER app

EXPOSE 8000

# curl is not in slim images, so probe with the standard library.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
