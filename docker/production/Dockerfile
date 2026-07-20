FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app/hermes_agents
COPY hermes_agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hermes_agents/ .

ENV DATABASE_URL=postgres://postgres:hpj7Zi4vwe7i2uThIhS46nszrblsbNhzqblpYovRBdJgqtAU5L5giL8hLli5Tz54@h3bdeft4hgsbg9rcxklxidwt:5432/postgres
ENV ATHENA_TOKEN=athena-token-123456789
ENV BLING_DOMAIN=athena.zoikom.site

EXPOSE 3000
CMD ["python", "-u", "athena_bridge.py"]
