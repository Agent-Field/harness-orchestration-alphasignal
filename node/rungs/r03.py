"""r03 — nested, improvised.

`diagnose` asks for a hypothesis. `hypothesize` decides for itself which artifact to
open next and calls `inspect_artifact` to read it. Nothing about the path is fixed,
so the graph is different every run — and so, often, is the answer.
"""
from agentfield import AgentRouter
from pydantic import BaseModel, Field

from common import MODEL, NODE_ID, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="r03", tags=["rung", "r03"])

ARTIFACTS = ["alert", "logs", "deploys", "metrics", "topology"]
MAX_LOOKS = 3


class Reading(BaseModel):
    """What one artifact turned out to say."""

    artifact: str
    what_it_shows: str = Field(description="Two or three sentences. Only what this artifact supports.")
    quote: str = Field(description="A literal line copied from the artifact")
    next_artifact: str = Field(description=f"One of {ARTIFACTS}, or 'none' if the picture is complete")


class Hypothesis(BaseModel):
    """A theory, and the trail that produced it."""

    theory: str = Field(description="One sentence naming component and mechanism")
    trail: list[str] = Field(description="Artifacts opened, in order")
    notes: str = Field(description="What the trail established, for the final diagnosis to use")


@router.reasoner(tags=["leaf"])
async def inspect_artifact(incident_id: str, artifact: str, question: str) -> Reading:
    """Read exactly one artifact and say what it supports — and where to look next."""
    section = artifact if artifact in ARTIFACTS else "alert"
    return await router.app.ai(
        system=SYSTEM,
        user=(
            f"You may look at ONE artifact of this incident: {section}.\n\n"
            f"{incident_text(incident_id, sections=[section], token_budget=6000)}\n\n"
            f"Question you are answering: {question}\n"
            f"Then name the next artifact worth opening, from {ARTIFACTS}, or 'none'."
        ),
        schema=Reading,
        model=MODEL,
    )


@router.reasoner(tags=["planner"])
async def hypothesize(incident_id: str) -> Hypothesis:
    """Open the alert, then follow wherever the last reading points. No fixed plan."""
    trail: list[str] = []
    readings: list[str] = []
    nxt = "alert"
    question = "What actually broke, and what would settle it?"

    for _ in range(MAX_LOOKS):
        if nxt == "none" or nxt not in ARTIFACTS:
            break
        reading = await router.app.call(
            f"{NODE_ID}.r03_inspect_artifact",
            incident_id=incident_id,
            artifact=nxt,
            question=question,
        )
        reading = Reading.model_validate(reading)
        trail.append(nxt)
        readings.append(f"[{nxt}] {reading.what_it_shows}\n  quote: {reading.quote}")
        question = f"Given: {reading.what_it_shows}\nWhat does this artifact add or rule out?"
        nxt = reading.next_artifact

    return Hypothesis(
        theory="",  # filled by the model below
        trail=trail,
        notes="\n".join(readings),
    ) if not readings else await router.app.ai(
        system=SYSTEM,
        user=(
            "You followed this trail through the incident:\n\n"
            + "\n\n".join(readings)
            + f"\n\nArtifacts opened, in order: {trail}\n"
            "State the single theory this trail supports."
        ),
        schema=Hypothesis,
        model=MODEL,
    )


@router.reasoner(tags=["entry"])
async def diagnose(incident_id: str) -> Diagnosis:
    """Get a hypothesis from the improvised trail, then write it up."""
    hyp = await router.app.call(f"{NODE_ID}.r03_hypothesize", incident_id=incident_id)
    hyp = Hypothesis.model_validate(hyp)
    return await router.app.ai(
        system=SYSTEM,
        user=(
            f"{incident_text(incident_id, token_budget=6000)}\n\n"
            f"--- AN INVESTIGATOR FOLLOWED THIS TRAIL: {hyp.trail} ---\n"
            f"Theory: {hyp.theory}\n{hyp.notes}\n\n"
            "Write the final diagnosis. Trust the trail; do not invent evidence it did not find."
        ),
        schema=Diagnosis,
        model=MODEL,
    )
