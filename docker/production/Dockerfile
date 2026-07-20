FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app/hermes_agents
COPY hermes_agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hermes_agents/ .

ENV API_PORT=3000

EXPOSE 3000
CMD ["python", "-u", "athena_bridge.py"]
