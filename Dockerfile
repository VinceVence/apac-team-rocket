FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0
ENV PATH="/app/.venv/bin:$PATH" UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock /app/
RUN uv sync --locked --no-default-groups --no-install-project --no-cache && useradd --uid 10001 --create-home minttown
COPY web/*.py /app/web/
COPY web/dist /app/web/dist
COPY web/model_artifacts /app/web/model_artifacts
RUN mkdir -p /app/web/data && chown -R 10001:10001 /app/web
USER 10001
CMD ["python", "-B", "web/server.py"]
