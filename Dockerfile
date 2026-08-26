# Dockerfile

FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd \
        --uid 1000 \
        --gid app \
        --create-home \
        --shell /bin/bash \
        app \
    && mkdir -p /data \
    && chown -R app:app /data

# Создаём минимальный placeholder package.
# Благодаря этому dependency layer зависит от pyproject.toml,
# но не зависит от изменений production-кода.
COPY pyproject.toml /app/pyproject.toml

RUN mkdir -p /app/app \
    && touch /app/app/__init__.py \
    && pip install --upgrade pip \
    && pip install '.[dev]'

# Production code копируется уже после установки dependencies.
COPY app /app/app
COPY resources /app/resources
COPY tests /app/tests
COPY scripts /app/scripts

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]