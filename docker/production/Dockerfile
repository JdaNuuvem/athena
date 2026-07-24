FROM node:22-alpine AS frontend
WORKDIR /app
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
ENV NEXT_STATIC_EXPORT=true
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app/hermes_agents
COPY hermes_agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hermes_agents/ .
COPY --from=frontend /app/out ./dashboard

ENV API_PORT=3000
EXPOSE 3000
CMD ["python", "-u", "athena_bridge.py"]
