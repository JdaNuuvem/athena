FROM python:3.11-slim
WORKDIR /app
COPY hermes_agents/ ./
RUN pip install --no-cache-dir -r requirements.txt
ENV PORT=3000
EXPOSE 3000
CMD ["python", "athena_bridge.py"]
