# ── Stage 1: download Siegfried binary ────────────────────────────────────────
FROM debian:bookworm-slim AS siegfried-dl

ARG SIEGFRIED_VERSION=1.11.4

# Releases use dashes in the version string and ship as .zip (e.g. siegfried_1-11-4_linux64.zip)
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates unzip \
    && SF_VER_DASHES="$(echo ${SIEGFRIED_VERSION} | tr '.' '-')" \
    && curl -fsSL \
       "https://github.com/richardlehane/siegfried/releases/download/v${SIEGFRIED_VERSION}/siegfried_${SF_VER_DASHES}_linux64.zip" \
       -o /tmp/sf.zip \
    && unzip /tmp/sf.zip sf -d /usr/local/bin \
    && chmod +x /usr/local/bin/sf \
    && rm /tmp/sf.zip

# ── Stage 2: Python application ───────────────────────────────────────────────
FROM python:3.11-slim AS app

# Copy Siegfried binary
COPY --from=siegfried-dl /usr/local/bin/sf /usr/local/bin/sf

# Update PRONOM signatures at build time so the image ships with a current sig file.
# The signature file is written to ~/.siegfried/; set HOME so it lands predictably.
ENV HOME=/root
RUN sf -update || true

# Install Python deps
WORKDIR /app
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir ".[dev]"

# Non-root user for runtime
RUN useradd -m ffis \
    && mkdir -p /root/.siegfried \
    && chown -R ffis:ffis /app /root/.siegfried
USER ffis

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python", "-m", "uvicorn", "ffis.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2"]
