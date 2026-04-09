FROM workspace-template:openclaw
USER root

# Install git + Docker CLI + sudo (required by NemoClaw)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git sudo && \
    curl -fsSL https://get.docker.com | sh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Allow agent user to run docker and nemoclaw via sudo without password, preserving env
RUN echo "agent ALL=(root) NOPASSWD:SETENV: ALL" >> /etc/sudoers.d/agent-docker

# Install NemoClaw via the official NVIDIA installer script.
ENV NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1
RUN curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash || true

# Fix permissions for nemoclaw source files
RUN chmod 755 /root && \
    chmod -R a+rX /root/.nemoclaw 2>/dev/null || true

# Copy nemoclaw config to agent home
RUN cp -r /root/.nemoclaw /home/agent/.nemoclaw 2>/dev/null || true && \
    chown -R agent:agent /home/agent/.nemoclaw 2>/dev/null || true

LABEL com.starfire.tier-required="4"

USER agent
