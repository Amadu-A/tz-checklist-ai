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

# ----------------------------------------------------------------------
# Dependency layer
# ----------------------------------------------------------------------
#
# Сначала копируется только pyproject.toml.
#
# Все runtime и dev dependencies устанавливаются отдельно от самого
# application package. Благодаря этому изменение Python-кода не
# заставляет Docker заново скачивать и устанавливать Celery, FastAPI,
# PyMuPDF и остальные библиотеки.
#
# tomllib входит в Python 3.12, поэтому дополнительная зависимость
# для чтения pyproject.toml не требуется.
COPY pyproject.toml /app/pyproject.toml

RUN pip install --upgrade pip \
    && python -c "import subprocess, sys, tomllib; \
data = tomllib.load(open('/app/pyproject.toml', 'rb')); \
dependencies = data['project']['dependencies']; \
dev_dependencies = data['project']['optional-dependencies']['dev']; \
subprocess.check_call([sys.executable, '-m', 'pip', 'install', *dependencies, *dev_dependencies])"

# ----------------------------------------------------------------------
# Application package
# ----------------------------------------------------------------------
#
# Только после установки внешних dependencies копируется настоящий
# пакет app со всеми слоями:
#
# app.api
# app.core
# app.domain
# app.application
# app.infrastructure
# app.worker
#
# Затем сам project package устанавливается БЕЗ повторной установки
# dependencies.
COPY app /app/app

RUN pip install --no-deps .

# ----------------------------------------------------------------------
# Runtime resources and tests
# ----------------------------------------------------------------------

COPY resources /app/resources
COPY tests /app/tests
COPY scripts /app/scripts

RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]