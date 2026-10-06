FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_INSTALL_DIR=/opt/python

RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/

RUN uv python install 3.13 \
    && uv venv /opt/venv --python 3.13
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

RUN useradd --create-home appuser \
    && mkdir -p /app/storage \
    && chown appuser:appuser /app/storage

COPY --chown=appuser:appuser requirements.txt .
RUN uv pip install --python /opt/venv/bin/python -r requirements.txt

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=5)"
ENTRYPOINT ["/app/docker-entrypoint.sh"]