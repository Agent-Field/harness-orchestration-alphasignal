"""r02 — loop.

One draft, then a judge. If the judge says the draft is thin, the draft goes back
in with the critique attached. Same schema out; a second opinion in the middle.
"""
from agentfield import AgentRouter
from pydantic import BaseModel, Field

from common import MODEL, NODE_ID, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="r02", tags=["rung", "r02"])

MAX_ROUNDS = 3


class Critique(BaseModel):
    """What the judge returns. `sufficient` is what stops the loop."""

    sufficient: bool = Field(description="True only if the diagnosis is settled by the cited evidence")
    what_is_missing: str = Field(description="One or two sentences: the specific gap the next draft must close")


@router.reasoner(tags=["judge"])
async def critique(incident_id: str, draft: dict) -> Critique:
    """Judge a draft against the incident. Harsh, specific, cheap."""
    return await router.app.ai(
        system=(
            "You review root-cause analyses. You are hard to satisfy. "
            "A diagnosis is sufficient only if the cited evidence actually settles it "
            "and the remediation addresses the cause rather than the symptom. "
            "Name the single most important missing check."
        ),
        user=(
            f"{incident_text(incident_id)}\n\n"
            f"--- DRAFT DIAGNOSIS ---\n{draft}\n\n"
            "Is this sufficient? If not, what is the one gap that matters most?"
        ),
        schema=Critique,
        model=MODEL,
    )


@router.reasoner(tags=["entry"])
async def diagnose(incident_id: str, max_rounds: int = MAX_ROUNDS) -> Diagnosis:
    """Draft, judge, redraft. At most `max_rounds` drafts, always."""
    rounds = max(1, min(int(max_rounds), MAX_ROUNDS))
    text = incident_text(incident_id)
    feedback = ""
    draft: Diagnosis | None = None

    for _ in range(rounds):
        draft = await router.app.ai(
            system=SYSTEM,
            user=text + feedback,
            schema=Diagnosis,
            model=MODEL,
        )
        verdict = await router.app.call(
            f"{NODE_ID}.r02_critique",
            incident_id=incident_id,
            draft=draft.model_dump(),
        )
        verdict = Critique.model_validate(verdict)
        if verdict.sufficient:
            break
        feedback = (
            f"\n\n--- YOUR PREVIOUS DIAGNOSIS ---\n{draft.model_dump()}\n"
            f"--- A REVIEWER REJECTED IT ---\n{verdict.what_is_missing}\n"
            "Re-diagnose. Close that gap or explain, with evidence, why it does not matter."
        )

    return draft
