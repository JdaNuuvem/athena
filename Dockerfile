FROM python:3.11-slim
WORKDIR /app
COPY hermes_agents/ ./
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
CMD ["python", "athena_bridge.py"]
