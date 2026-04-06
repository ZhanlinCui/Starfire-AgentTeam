FROM python:3.11-slim

WORKDIR /app

# Install Node.js (needed for CLI runtimes like claude-code, codex)
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI (available for CLI runtime)
RUN npm install -g @anthropic-ai/claude-code 2>/dev/null || true

# Create non-root user (claude --dangerously-skip-permissions refuses root)
RUN useradd -m -s /bin/bash agent

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy runtime code
COPY *.py ./
COPY skills/ ./skills/
COPY tools/ ./tools/

# Create a2a CLI alias (available to all runtimes)
RUN ln -s /app/a2a_cli.py /usr/local/bin/a2a && chmod +x /app/a2a_cli.py /app/a2a_mcp_server.py

# Config is mounted at runtime
VOLUME /configs

# Workspace directory for coding agents (mounted at runtime)
RUN mkdir -p /workspace /plugins /home/agent/.claude && \
    chown -R agent:agent /app /home/agent /workspace
VOLUME /workspace
VOLUME /plugins

EXPOSE 8000

# Run as non-root for CLI runtimes (claude refuses root)
# LangGraph works fine as non-root too
USER agent
CMD ["python", "main.py"]
