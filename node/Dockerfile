# Agent node image. node/main.py defines the agent; this file only runs it.
FROM python:3.13-slim

# agentfield 0.1.132 requires >=3.10,<3.14 -- 3.13-slim is deliberate, not incidental.
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# JupyterLab is a notebook-side dep; the node image does not need it.
RUN grep -v -e '^jupyterlab' -e '^nbclient' -e '^nbformat' requirements.txt > /tmp/req.txt \
 && pip install --no-cache-dir -r /tmp/req.txt

COPY node/ /app/node/
COPY lib/  /app/lib/

EXPOSE 8001
CMD ["python", "node/main.py"]
