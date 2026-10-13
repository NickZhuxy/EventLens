FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    EVENTLENS_STATE_DIR=/var/lib/eventlens
WORKDIR /app
COPY deploy/requirements.lock /app/deploy/requirements.lock
RUN pip install --no-cache-dir -r deploy/requirements.lock
COPY pyproject.toml /app/
COPY src /app/src
RUN pip install --no-cache-dir --no-build-isolation --no-deps . && \
    useradd --uid 10001 --create-home eventlens && \
    mkdir -p /var/lib/eventlens && chown eventlens:eventlens /var/lib/eventlens
USER eventlens
EXPOSE 8000
CMD ["eventlens-service", "serve", "--host", "0.0.0.0", "--port", "8000"]
