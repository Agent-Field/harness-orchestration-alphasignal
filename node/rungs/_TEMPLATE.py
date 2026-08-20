"""Contract every rung module follows.

    router                    an AgentRouter, included by node/main.py
    diagnose(incident_id)     the entry reasoner, tagged ["entry"], returns Diagnosis

Inside a router, reach the agent through `router.app` -- `router.app.ai(...)` for an
LLM call, `router.app.call("<node>.<reasoner>", ...)` to invoke another reasoner
through the control plane so the edge lands in the DAG.
"""
from agentfield import AgentRouter

from common import MODEL, NODE_ID, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="", tags=["rung"])


@router.reasoner(tags=["entry"])
async def diagnose(incident_id: str, model: str | None = None) -> Diagnosis:
    return await router.app.ai(
        system=SYSTEM,
        user=incident_text(incident_id),
        schema=Diagnosis,
        model=model or MODEL,
    )
