FROM node:22-alpine

# Create non-root user (claude --dangerously-skip-permissions refuses root)
RUN addgroup -S agent && adduser -S agent -G agent

WORKDIR /app

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install workspace runtime deps
COPY package.json ./
RUN npm install

# Copy runtime code
COPY *.ts *.json ./

# Create dirs and set permissions
RUN mkdir -p /configs /workspace /plugins /home/agent/.claude && \
    chown -R agent:agent /app /home/agent /workspace

VOLUME /configs
VOLUME /workspace
VOLUME /plugins

EXPOSE 8000

USER agent
CMD ["npx", "tsx", "main.ts"]
