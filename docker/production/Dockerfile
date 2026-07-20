FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY hermes_agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hermes_agents/ /app/hermes_agents/

WORKDIR /app/hermes_agents

ENV PYTHONUNBUFFERED=1
ENV PORT=3000
ENV DB_PORT=5432
ENV DB_NAME=hermes_factory

# Force cache invalidate v2
RUN echo "BUILD_OK"

EXPOSE 3000

CMD python athena_bridge.py
