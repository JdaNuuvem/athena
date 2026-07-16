FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY hermes_agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hermes_agents/ /app/hermes_agents/

COPY web/ /app/web/
WORKDIR /app/web
RUN npm install && npm run build

WORKDIR /app/hermes_agents

ENV API_PORT=3001
ENV PYTHONUNBUFFERED=1
ENV DB_PORT=5432
ENV DB_NAME=hermes_factory

EXPOSE 3000 3001

CMD (cd /app/web && npx next start -p 3000) & \
    python /app/hermes_agents/athena_bridge.py & \
    wait -n
