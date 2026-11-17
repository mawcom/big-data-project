FROM python:3.12-slim-bookworm

# Java para o PySpark
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências antes do código, para não reinstalar tudo a cada mudança
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

CMD ["uv", "run", "--no-sync", "python", "dashboard/prototipo/app.py", "--host", "0.0.0.0"]
