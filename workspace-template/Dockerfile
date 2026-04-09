FROM python:3.11-slim

WORKDIR /app

# Install Node.js (needed for CLI runtimes like claude-code, openclaw)
RUN apt-get update && apt-get install -y --no-install-recommends curl git && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    # GitHub CLI for PR creation
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends gh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user (claude --dangerously-skip-permissions refuses root)
RUN useradd -m -s /bin/bash agent

# Install base Python dependencies (A2A SDK + HTTP only)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy runtime code
COPY *.py ./
COPY entrypoint.sh ./
COPY skills/ ./skills/
COPY tools/ ./tools/
COPY adapters/ ./adapters/
COPY policies/ ./policies/

# Create CLI aliases
RUN ln -s /app/a2a_cli.py /usr/local/bin/a2a && chmod +x /app/a2a_cli.py /app/a2a_mcp_server.py && \
    ln -s /app/agent_molecule_status.py /usr/local/bin/agent-molecule-status && chmod +x /app/agent_molecule_status.py

# Dirs and permissions
RUN mkdir -p /workspace /plugins /home/agent/.claude /home/agent/.config /home/agent/.local && \
    chown -R agent:agent /app /home/agent /workspace

VOLUME /configs
VOLUME /workspace
VOLUME /plugins

EXPOSE 8000
RUN chmod +x /app/entrypoint.sh
USER agent
CMD ["./entrypoint.sh"]
