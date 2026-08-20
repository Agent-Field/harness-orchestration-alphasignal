"""r06 — just in time.

Chapter 04 wired the lens graph by hand: the same nodes fire on every incident,
whether or not they are warranted. Here nobody wires anything. A `choose_lenses`
reasoner reads the incident, picks from the 26-lens vocabulary in
`incidents/lenses.md`, and the fan-out is exactly what it picked.

So the graph is a function of the incident. inc-011 (clock skew) grows a
`clock_time` node; inc-006 (cache stampede) grows `cache_behavior`; neither
grows the other's. That is the whole point of the rung: **different incidents
grow different graphs.**

The cap is MAX_LENSES. A model asked "which lenses apply?" will happily say
"all of them", which is the hand-wired graph again with extra steps. Six is the
number of things a human on-call actually opens.
"""
from agentfield import AgentRouter
from pydantic import BaseModel, Field

from common import MODEL, NODE_ID, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="r06", tags=["rung", "r06"])

#: The vocabulary, transcribed from incidents/lenses.md §3. The generator may
#: only choose from this list — an invented lens is a hallucinated tool.
LENSES: dict[str, str] = {
    "alert_validity": "Is the alert real, or did the monitor change?",
    "blast_scope": "Who is affected, and more importantly who is not?",
    "timeline": "When did it truly start, and does the candidate cause precede it?",
    "change_correlation": "What changed inside the window?",
    "long_horizon_change": "What changed days or weeks ago that is only now visible?",
    "rollback_viability": "Can we undo this safely, or has state moved?",
    "config_drift": "Is the running config what we think it is?",
    "dependency_health": "Are our downstreams healthy?",
    "external_vendor": "Is a third party degraded?",
    "saturation_compute": "Are we out of CPU, memory, threads?",
    "connection_pool": "Is a bounded pool exhausted with a wait queue?",
    "queue_backpressure": "Is work arriving faster than it leaves?",
    "cache_behavior": "Is the cache doing its job, or did the keyspace move?",
    "database_health": "Is the database itself the problem?",
    "retry_amplification": "Are we creating our own load?",
    "capacity_autoscaling": "Do we have the replicas we should?",
    "resource_contention": "Is a neighbour stealing from us?",
    "dns_service_discovery": "Can we even find the callee?",
    "network_path": "Is the path between us broken below the application layer?",
    "credential_expiry": "Did something expire or rotate?",
    "security_abuse": "Is this hostile traffic?",
    "clock_time": "Is time itself wrong — NTP offset, out-of-order logs, boundary times?",
    "data_contract": "Did the shape of the data change?",
    "memory_lifecycle": "Is allocation growing without bound?",
    "traffic_demand": "Is demand actually different from yesterday?",
    "observability_gap": "What can we not see?",
}

#: Hard cap on the fan-out. Not advice to the model — enforced in code below.
MAX_LENSES = 6


class LensPlan(BaseModel):
    """Which lenses this incident warrants, and why."""

    lenses: list[str] = Field(
        description=f"Between 3 and {MAX_LENSES} lens ids, most load-bearing first. Ids only, from the given list."
    )
    reasoning: str = Field(description="One sentence per lens: what in the symptom shape warrants it.")
    ruled_out: list[str] = Field(
        description="Lens ids you deliberately did NOT open, that a careless responder would have."
    )


class LensReading(BaseModel):
    """What one lens saw."""

    lens: str
    answer: str = Field(description="Two or three sentences answering this lens's standing question.")
    quote: str = Field(description="A literal line copied from the incident artifacts")
    verdict: str = Field(description="'supports', 'refutes', or 'inconclusive' — about this lens as the cause")


@router.reasoner(tags=["planner"])
async def choose_lenses(incident_id: str) -> LensPlan:
    """Read the incident and decide which lenses it warrants. This is the graph."""
    catalogue = "\n".join(f"- {lid}: {q}" for lid, q in LENSES.items())
    plan = await router.app.ai(
        system=SYSTEM,
        user=(
            f"{incident_text(incident_id, token_budget=8000)}\n\n"
            "--- INVESTIGATIVE LENSES ---\n"
            "A lens is a standing question plus the discipline of answering it.\n"
            f"{catalogue}\n\n"
            f"Choose at most {MAX_LENSES} lenses this incident actually warrants, from the shape "
            "of the symptom, not the name of the service. Opening a lens costs a responder time, "
            "so an irrelevant lens is a real mistake. Name the ones you deliberately left shut."
        ),
        schema=LensPlan,
        model=MODEL,
    )
    # Enforce the cap and the vocabulary in code. A model told "at most six" will
    # sometimes return nine, and will sometimes invent a lens that sounds right.
    picked = [l for l in dict.fromkeys(plan.lenses) if l in LENSES][:MAX_LENSES]
    plan.lenses = picked or ["timeline", "change_correlation", "blast_scope"]
    return plan


@router.reasoner(tags=["leaf"])
async def apply_lens(incident_id: str, lens: str) -> LensReading:
    """Answer one lens's standing question against the incident."""
    question = LENSES.get(lens, "What does this incident show?")
    return await router.app.ai(
        system=SYSTEM,
        user=(
            f"{incident_text(incident_id, token_budget=8000)}\n\n"
            f"--- LENS: {lens} ---\n{question}\n\n"
            "Answer only this question. Quote one literal line as evidence. Then say whether this "
            "lens supports, refutes, or is inconclusive about being the cause."
        ),
        schema=LensReading,
        model=MODEL,
    )


@router.reasoner(tags=["entry"])
async def diagnose(incident_id: str) -> Diagnosis:
    """Choose the lenses, fan out over exactly those, synthesise what came back."""
    import asyncio

    plan = LensPlan.model_validate(
        await router.app.call(f"{NODE_ID}.r06_choose_lenses", incident_id=incident_id)
    )

    readings = await asyncio.gather(
        *(
            router.app.call(f"{NODE_ID}.r06_apply_lens", incident_id=incident_id, lens=lens)
            for lens in plan.lenses
        )
    )
    body = "\n\n".join(
        f"[{r['lens']}] {r['verdict']}\n{r['answer']}\n  quote: {r['quote']}"
        for r in (dict(x) for x in readings)
    )

    diagnosis = await router.app.ai(
        system=SYSTEM,
        user=(
            f"{incident_text(incident_id, token_budget=6000)}\n\n"
            f"--- LENSES OPENED FOR THIS INCIDENT: {plan.lenses} ---\n"
            f"(deliberately left shut: {plan.ruled_out})\n\n"
            f"{body}\n\n"
            "Write the final diagnosis. Weigh a lens that says 'supports' over one that says "
            "'inconclusive'. Do not invent evidence no lens found."
        ),
        schema=Diagnosis,
        model=MODEL,
    )
    return diagnosis


@router.reasoner(tags=["entry"])
async def plan_only(incident_id: str) -> LensPlan:
    """Just the lens choice, for showing side by side what two incidents grow."""
    return LensPlan.model_validate(
        await router.app.call(f"{NODE_ID}.r06_choose_lenses", incident_id=incident_id)
    )
