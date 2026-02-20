# ── Stage 1: download Siegfried binary ────────────────────────────────────────
FROM debian:bookworm-slim AS siegfried-dl

ARG SIEGFRIED_VERSION=1.11.1

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL \
       "https://github.com/richardlehane/siegfried/releases/download/v${SIEGFRIED_VERSION}/siegfried_${SIEGFRIED_VERSION}_linux64.tar.gz" \
       -o /tmp/sf.tar.gz \
    && tar -xzf /tmp/sf.tar.gz -C /usr/local/bin sf \
    && chmod +x /usr/local/bin/sf

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
RUN pip install --no-cache-dir ".[dev]"

# Copy source
COPY src/ ./src/

# Non-root user for runtime
RUN useradd -m ffis && chown -R ffis:ffis /app /root/.siegfried
USER ffis

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python", "-m", "uvicorn", "ffis.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2"]
