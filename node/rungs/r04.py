"""r04 — the hand-written graph.

Five lenses, transcribed out of `incidents/lenses.md`, run in parallel on every
incident. Then one synthesis call merges them. The graph is written down once, so
it is the same graph every time: same five nodes, same fan-out, same merge, whether
the incident is a bad deploy or a dying disk.
"""
from __future__ import annotations

import asyncio

from agentfield import AgentRouter
from pydantic import BaseModel, Field

from common import MODEL, NODE_ID, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="r04", tags=["rung", "r04"])


class LensReport(BaseModel):
    """What one lens hands back to the synthesiser."""

    lens: str = Field(description="The lens id, e.g. 'timeline'")
    answer: str = Field(description="One or two sentences answering this lens's standing question")
    evidence: list[str] = Field(description="Literal substrings copied out of the artifacts")
    warranted: bool = Field(description="False if this lens found nothing that bears on the incident")


# The five standing lenses. Question, and the artifacts each one reads.
LENSES = {
    "timeline": (
        "When did this truly start? Compare first-bad timestamps against the alert time and "
        "against every change time. The alert time is never the incident time. A candidate "
        "cause that postdates the symptom is not the cause.",
        ["alert", "logs", "metrics", "deploys"],
    ),
    "change_correlation": (
        "What changed inside the window, and does the diff touch the failing path? Do not blame "
        "a change for being the newest, and do not dismiss a one-line change for being small.",
        ["alert", "deploys", "logs"],
    ),
    "blast_scope": (
        "Who is affected and, more importantly, who is not? Look for a clean split along one "
        "dimension: per-pod, per-region, per-tenant, per-currency, per-endpoint, per-caller. "
        "The negative half is the powerful half.",
        ["alert", "metrics", "topology", "logs"],
    ),
    "dependency_health": (
        "Are our downstreams healthy? Look for one dependency diverging from the others rather "
        "than a dependency that is merely slow and always was.",
        ["topology", "metrics", "logs"],
    ),
    "resource_contention": (
        "Are we out of CPU, memory, threads, connections — or is a neighbour stealing from us? "
        "Saturation is often a consequence, not a cause. Say which one this is.",
        ["metrics", "logs", "alert"],
    ),
}


async def _lens(name: str, incident_id: str, model: str | None) -> LensReport:
    question, sections = LENSES[name]
    return await router.app.ai(
        system=SYSTEM + f" You are running one lens only: {name}. Stay inside it.",
        user=(
            f"## Lens: {name}\n{question}\n\n"
            f"Answer only that question about the incident below. If this lens has nothing to "
            f"say here, set warranted=false and say so plainly rather than reaching.\n\n"
            f"{incident_text(incident_id, sections=sections, token_budget=6000)}"
        ),
        schema=LensReport,
        model=model or MODEL,
    )


@router.reasoner(tags=["lens"])
async def lens_timeline(incident_id: str, model: str | None = None) -> LensReport:
    """When did it truly start?"""
    return await _lens("timeline", incident_id, model)


@router.reasoner(tags=["lens"])
async def lens_change_correlation(incident_id: str, model: str | None = None) -> LensReport:
    """What changed in the window?"""
    return await _lens("change_correlation", incident_id, model)


@router.reasoner(tags=["lens"])
async def lens_blast_scope(incident_id: str, model: str | None = None) -> LensReport:
    """Who is affected, and who is not?"""
    return await _lens("blast_scope", incident_id, model)


@router.reasoner(tags=["lens"])
async def lens_dependency_health(incident_id: str, model: str | None = None) -> LensReport:
    """Are our downstreams healthy?"""
    return await _lens("dependency_health", incident_id, model)


@router.reasoner(tags=["lens"])
async def lens_resource_contention(incident_id: str, model: str | None = None) -> LensReport:
    """Are we out of a resource, or is a neighbour taking it?"""
    return await _lens("resource_contention", incident_id, model)


@router.reasoner(tags=["merge"])
async def synthesize(incident_id: str, reports: list, model: str | None = None) -> Diagnosis:
    """Merge five lens reports into one diagnosis."""
    body = "\n\n".join(
        f"### {r.get('lens', '?')}  (warranted={r.get('warranted')})\n"
        f"{r.get('answer', '')}\n"
        + "\n".join(f"- evidence: {e}" for e in (r.get("evidence") or []))
        for r in reports
    )
    return await router.app.ai(
        system=SYSTEM,
        user=(
            "Five lenses were run in parallel over one incident. Each answered its own standing "
            "question and saw only part of the evidence. Merge them.\n\n"
            "A cause must explain the timing, the magnitude, and the blast scope. If the lenses "
            "disagree, say which one you trust and why. If nothing settles it, set confident=false.\n\n"
            f"{body}\n\n--- the alert, for context ---\n"
            f"{incident_text(incident_id, sections=['alert'], token_budget=1500)}"
        ),
        schema=Diagnosis,
        model=model or MODEL,
    )


@router.reasoner(tags=["entry"])
async def diagnose(incident_id: str, model: str | None = None) -> Diagnosis:
    """Fan out to five fixed lenses in parallel, then merge."""
    reports = await asyncio.gather(
        *(
            router.app.call(f"{NODE_ID}.r04_lens_{name}", incident_id=incident_id, model=model)
            for name in LENSES
        )
    )
    return await router.app.call(
        f"{NODE_ID}.r04_synthesize", incident_id=incident_id, reports=list(reports), model=model
    )
