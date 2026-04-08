FROM workspace-template:base
USER root
COPY adapters/autogen/requirements.txt /tmp/adapter-requirements.txt
RUN pip install --no-cache-dir -r /tmp/adapter-requirements.txt && rm /tmp/adapter-requirements.txt
USER agent
