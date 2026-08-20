"""r05 — the AI-written graph.

Same shape as r04: fan out, then merge. The difference is who writes the questions.
A `plan` reasoner reads the incident first and authors the prompt for each child
lens. The set of nodes is still bounded — at most six — but what each one is *asked*
is composed at runtime, for this incident.
"""
from __future__ import annotations

import asyncio

from agentfield import AgentRouter
from pydantic import BaseModel, Field

from common import MODEL, NODE_ID, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="r05", tags=["rung", "r05"])

MAX_LENSES = 6

# Section 3 of incidents/lenses.md, as vocabulary. The planner picks from it; it does
# not get the routing table, because deriving the routing is the thing being tested.
VOCABULARY = """
alert_validity, blast_scope, timeline, change_correlation, long_horizon_change,
rollback_viability, config_drift, dependency_health, external_vendor, saturation_compute,
connection_pool, queue_backpressure, cache_behavior, database_health, retry_amplification,
capacity_autoscaling, resource_contention, dns_service_discovery, network_path,
credential_expiry, security_abuse, clock_time, data_contract, memory_lifecycle,
traffic_demand, observability_gap
"""


class LensSpec(BaseModel):
    """One node of the graph, written by the model."""

    lens_name: str = Field(description="A lens id from the vocabulary")
    prompt: str = Field(
        description=(
            "The full question to hand this lens, written for THIS incident. Name the specific "
            "series, service, pod, caller or timestamp to check. Two to four sentences."
        )
    )
    why: str = Field(description="One sentence: why this incident warrants this lens")


class Plan(BaseModel):
    """The graph for one incident."""

    symptom_shape: str = Field(description="The shape of the symptom in one line, e.g. 'latency up, CPU flat'")
    lenses: list[LensSpec] = Field(description=f"At most {MAX_LENSES} lenses, most decisive first")


class LensReport(BaseModel):
    lens: str
    answer: str = Field(description="One or two sentences answering the question you were given")
    evidence: list[str] = Field(description="Literal substrings copied out of the artifacts")
    warranted: bool = Field(description="False if this lens turned out to have nothing to say")


@router.reasoner(tags=["plan"])
async def plan(incident_id: str, model: str | None = None) -> Plan:
    """Read the incident and write the questions the children will be asked."""
    return await router.app.ai(
        system=(
            "You are an experienced on-call engineer deciding how to investigate, before you "
            "investigate. You choose lenses from the shape of the symptom, not from the name of "
            "the service. Selecting means leaving lenses out."
        ),
        user=(
            "Below is an incident. Name the shape of the symptom, then write the investigation "
            f"plan: at most {MAX_LENSES} lenses.\n\n"
            f"Lens vocabulary (use these ids):\n{VOCABULARY}\n\n"
            "For each lens, write the actual prompt the investigator will receive. A good prompt "
            "names the specific artifact, series, pod, caller or timestamp to check in THIS "
            "incident. A prompt that would read the same for any incident is a wasted node.\n\n"
            f"{incident_text(incident_id, token_budget=8000)}"
        ),
        schema=Plan,
        model=model or MODEL,
    )


@router.reasoner(tags=["lens"])
async def lens(incident_id: str, lens_name: str, prompt: str, model: str | None = None) -> LensReport:
    """One generic lens, told at runtime what to look for."""
    return await router.app.ai(
        system=SYSTEM + f" You are running one lens only: {lens_name}. Stay inside it.",
        user=(
            f"## Lens: {lens_name}\n{prompt}\n\n"
            "Answer only that. If the evidence is not there, set warranted=false and say so.\n\n"
            f"{incident_text(incident_id, token_budget=6000)}"
        ),
        schema=LensReport,
        model=model or MODEL,
    )


@router.reasoner(tags=["merge"])
async def synthesize(incident_id: str, reports: list, model: str | None = None) -> Diagnosis:
    """Merge the lens reports into one diagnosis."""
    body = "\n\n".join(
        f"### {r.get('lens', '?')}  (warranted={r.get('warranted')})\n"
        f"{r.get('answer', '')}\n"
        + "\n".join(f"- evidence: {e}" for e in (r.get("evidence") or []))
        for r in reports
    )
    return await router.app.ai(
        system=SYSTEM,
        user=(
            "These lenses were chosen for this incident and run in parallel. Merge them.\n\n"
            "A cause must explain the timing, the magnitude, and the blast scope. If nothing "
            "settles it, set confident=false.\n\n"
            f"{body}\n\n--- the alert, for context ---\n"
            f"{incident_text(incident_id, sections=['alert'], token_budget=1500)}"
        ),
        schema=Diagnosis,
        model=model or MODEL,
    )


@router.reasoner(tags=["entry"])
async def diagnose(incident_id: str, model: str | None = None) -> Diagnosis:
    """Plan the graph, run it, merge it."""
    graph = await router.app.call(f"{NODE_ID}.r05_plan", incident_id=incident_id, model=model)
    specs = (graph.get("lenses") or [])[:MAX_LENSES]
    reports = await asyncio.gather(
        *(
            router.app.call(
                f"{NODE_ID}.r05_lens",
                incident_id=incident_id,
                lens_name=s["lens_name"],
                prompt=s["prompt"],
                model=model,
            )
            for s in specs
        )
    )
    return await router.app.call(
        f"{NODE_ID}.r05_synthesize", incident_id=incident_id, reports=list(reports), model=model
    )
