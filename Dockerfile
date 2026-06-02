FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMNIFORUM_HOST=0.0.0.0 \
    OMNIFORUM_PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY app.py ./
COPY assets ./assets
COPY css ./css
COPY js ./js
COPY omniforum ./omniforum
COPY pages ./pages
COPY plugins ./plugins
COPY scripts ./scripts
COPY index.html README.md ./
COPY docs ./docs

RUN addgroup --system omniforum \
    && adduser --system --ingroup omniforum --home /app omniforum \
    && mkdir -p \
        data/logs \
        data/exports/backups \
        data/uploads/avatars \
        data/uploads/posts \
        data/uploads/thumbs \
    && touch \
        data/logs/.gitkeep \
        data/exports/.gitkeep \
        data/uploads/avatars/.gitkeep \
        data/uploads/posts/.gitkeep \
        data/uploads/thumbs/.gitkeep \
    && chown -R omniforum:omniforum /app

USER omniforum

EXPOSE 8000
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python scripts/container_healthcheck.py

CMD ["python", "app.py"]
