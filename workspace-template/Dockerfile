FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy runtime code
COPY *.py ./
COPY skills/ ./skills/
COPY tools/ ./tools/

# Config is mounted at runtime
VOLUME /configs

# Workspace directory for coding agents (mounted at runtime)
RUN mkdir -p /workspace
VOLUME /workspace

EXPOSE 8000

CMD ["python", "main.py"]
