"""The agent every notebook drives.

One node, one router per rung. A rung is a different way of organising the same
work, so they all register together and the notebooks pick between them.
"""
from __future__ import annotations

import importlib
import os

from agentfield import Agent, AIConfig

from common import MAX_TOKENS, MODEL, NODE_ID

app = Agent(
    node_id=NODE_ID,
    agentfield_server=os.getenv("AGENTFIELD_SERVER", "http://localhost:8080"),
    version="0.1.0",
    description="Seven ways to diagnose the same incident, from one call to a graph it writes itself.",
    ai_config=AIConfig(model=MODEL, max_tokens=MAX_TOKENS, temperature=0.3),
    dev_mode=False,     # its event dump is unusable in a notebook cell
    enable_did=False,   # DID registration 404s on the local control plane; noisy, non-fatal
)

RUNGS = ["r01", "r02", "r03", "r04", "r05", "r06", "r07"]

for name in RUNGS:
    try:
        module = importlib.import_module(f"rungs.{name}")
    except ModuleNotFoundError:
        continue  # not written yet
    app.include_router(module.router)
    print(f"registered {name}")

if __name__ == "__main__":
    app.serve(port=int(os.getenv("NODE_PORT", "8001")), auto_port=True)
