FROM python:3.12-slim-bookworm

# Java para o PySpark
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . .
RUN uv sync --frozen

CMD ["uv", "run", "python", "dashboard/prototipo/app.py", "--host", "0.0.0.0"]
