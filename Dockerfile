# syntax=docker/dockerfile:1

# Pinned to the bookworm variant for reproducibility.  Stricter follow-up:
# pin to an immutable @sha256:… digest (get it via `docker buildx imagetools
# inspect python:3.11-slim-bookworm`).
ARG PY_IMAGE=python:3.11-slim-bookworm

# ---- builder: install deps into an isolated virtualenv ----
FROM ${PY_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /app
COPY Requirements.txt requirements-dev.txt ./

# Production deps always installed.
RUN pip install --no-cache-dir -r Requirements.txt

# Dev/test deps only when BUILD_ENV=dev (keeps prod image lean).
ARG BUILD_ENV=production
RUN if [ "$BUILD_ENV" = "dev" ]; then \
        pip install --no-cache-dir -r requirements-dev.txt; \
    fi

# ---- runtime: slim image, non-root, no build tooling ----
FROM ${PY_IMAGE} AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Bring in the prepared virtualenv only — no compilers/pip cache in the runtime.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY code ./code

# Drop root: run as an unprivileged user that owns the app tree.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/code

EXPOSE 5001

# Liveness: /login is public and returns 200 when the app is serving.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5001/login').status==200 else 1)"

CMD ["python", "run.py"]
