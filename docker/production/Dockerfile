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

# Copia o build estatico do Next.js para onde o Flask serve
RUN cp -r /app/web/out/* /app/hermes_agents/dashboard/

WORKDIR /app/hermes_agents

ENV PYTHONUNBUFFERED=1
ENV PORT=3000
ENV DB_PORT=5432
ENV DB_NAME=hermes_factory

EXPOSE 3000

CMD python athena_bridge.py
