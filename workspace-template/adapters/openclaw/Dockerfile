FROM workspace-template:base
USER root
RUN npm install -g openclaw 2>/dev/null || true && \
    cd /usr/lib/node_modules/openclaw 2>/dev/null && \
    npm install @buape/carbon @larksuiteoapi/node-sdk @slack/web-api grammy 2>/dev/null || true
USER agent
