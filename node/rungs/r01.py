"""r01 — one shot.

The whole incident, one call, one schema. The baseline everything else is measured
against.
"""
from agentfield import AgentRouter

from common import MODEL, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="r01", tags=["rung", "r01"])


@router.reasoner(tags=["entry"])
async def diagnose(incident_id: str, model: str | None = None) -> Diagnosis:
    """Read everything, answer once."""
    return await router.app.ai(
        system=SYSTEM,
        user=incident_text(incident_id),
        schema=Diagnosis,
        model=model or MODEL,
    )
