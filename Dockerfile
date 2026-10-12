FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MINTTOWN_LIVE=0 MINTTOWN_FRAUD_LIVE=0
WORKDIR /app
COPY web/requirements-google.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home minttown
COPY web/*.py /app/web/
COPY web/dist /app/web/dist
RUN mkdir -p /app/web/data && chown -R 10001:10001 /app/web
USER 10001
CMD ["python", "-B", "web/server.py"]
