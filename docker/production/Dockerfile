FROM python:3.11-slim
ARG CACHE_BUST=1
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY hermes_agents/requirements.txt ./hermes_agents/
RUN pip install --no-cache-dir -r hermes_agents/requirements.txt
COPY hermes_agents/ ./hermes_agents/
COPY web/package.json web/package-lock.json* ./web/
WORKDIR /app/web
RUN npm ci
COPY web/ ./
ENV NEXT_STATIC_EXPORT=true
ENV NEXT_PUBLIC_ROCKETCHAT_URL=https://chat.athena.zoikom.site
RUN npm run build
WORKDIR /app/hermes_agents
RUN mkdir -p dashboard && cp -r /app/web/out/* dashboard/
ENV API_PORT=3000
EXPOSE 3000
CMD ["python", "-u", "athena_bridge.py"]
