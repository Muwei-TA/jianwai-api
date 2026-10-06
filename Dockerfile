FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini pyproject.toml ./
RUN groupadd --system jianwai && useradd --system --gid jianwai --home-dir /app jianwai && mkdir -p /app/var/media /app/var/outbox && chown -R jianwai:jianwai /app/var
USER jianwai
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
