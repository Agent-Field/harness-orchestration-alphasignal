"""r07 — headless.

Every rung so far was driven by a notebook cell. This one runs when nobody is
watching, and stops to ask when it matters.

Two mechanisms, and they are the same two every production agent needs:

1. **A trigger.** `@on_schedule` registers a row on the control plane at import
   time. From then on the control plane owns the schedule, not the notebook. A
   trigger-fired run gets a `wf_` run id instead of `run_` — free proof that
   nothing was driving it.

2. **An approval gate.** `triage` diagnoses, then classifies its own proposed
   remediation. If the fix is destructive — a rollback, a restart, a truncate —
   it calls `app.pause()` and blocks on a human. Read-only fixes proceed.

Three traps are baked into the code below, all of them the kind that look like
success on the control plane and a hang in the agent:

- The callback URL must be `127.0.0.1`, never `localhost`. The Go control plane
  resolves `localhost` to `::1`; uvicorn binds IPv4. Set `AGENT_CALLBACK_URL`.
- The control plane's SSRF guard rejects private hosts unless it was started
  with `AGENTFIELD_WEBHOOK_ALLOWED_HOSTS=localhost,127.0.0.1`.
- Approval feedback must be nested under `response`. A top-level `feedback` key
  is accepted by the control plane and silently dropped before it reaches here.

Cron is used rather than a webhook because the `cron` source needs no secret,
and `secret_env` names a variable on the *control plane* process, not on this
agent. See docs/approvals-triggers-memory.md.
"""
from __future__ import annotations

from agentfield import AgentRouter, TriggerContext, on_schedule
from pydantic import BaseModel, Field

from common import MODEL, NODE_ID, SYSTEM, Diagnosis, incident_text

router = AgentRouter(prefix="r07", tags=["rung", "r07"])

#: Deliberately not "* * * * *". A minute cron keeps firing after the agent dies
#: and there is no delete for a code-managed trigger — only pause. Daily at 04:00
#: is a schedule you can leave on a laptop. The notebook fires it by hand.
SWEEP_CRON = "0 4 * * *"

#: Verbs that mean "this changes the world and cannot be un-run".
DESTRUCTIVE = (
    "roll back", "rollback", "revert", "restart", "reboot", "failover", "fail over",
    "delete", "drop", "truncate", "flush", "purge", "evict", "scale down",
    "terminate", "kill", "disable", "rotate", "redeploy",
)


class Remediation(BaseModel):
    """A proposed fix, and whether a human has to see it first."""

    action: str = Field(description="The immediate fix, one imperative sentence")
    destructive: bool = Field(description="True if this cannot be un-run: rollback, restart, delete, failover")
    reason: str = Field(description="One sentence: why it is or is not destructive")
    blast_radius: str = Field(description="What else this touches if it goes wrong")


class TriageResult(BaseModel):
    """What one unattended triage produced."""

    incident_id: str
    root_cause: str
    action: str
    destructive: bool
    approval: str = Field(description="'not_required', 'approved', 'rejected', 'request_changes', or 'expired'")
    feedback: str = ""
    ran_headless: bool = False


@router.reasoner(tags=["leaf"])
async def classify_remediation(incident_id: str, remediation: str) -> Remediation:
    """Decide whether the proposed fix needs a human before it runs."""
    out = await router.app.ai(
        system=SYSTEM,
        user=(
            f"{incident_text(incident_id, sections=['alert', 'topology'], token_budget=3000)}\n\n"
            f"--- PROPOSED REMEDIATION ---\n{remediation}\n\n"
            "Classify it. Destructive means it cannot be un-run: rollback, restart, failover, "
            "delete, truncate, scaling down, rotating a credential. Reading a dashboard is not."
        ),
        schema=Remediation,
        model=MODEL,
    )
    # Belt and braces: the model is the judge, but a verb match can only escalate.
    if any(v in remediation.lower() for v in DESTRUCTIVE):
        out.destructive = True
    return out


@router.reasoner(tags=["entry"])
@on_schedule(SWEEP_CRON, timezone="UTC")
async def sweep(
    event: dict | None = None,
    incident_id: str = "inc-011",
    trigger: TriggerContext | None = None,
) -> TriageResult:
    """Fired by the control plane on a schedule. Nothing is driving this."""
    result = await router.app.call(f"{NODE_ID}.r07_triage", incident_id=incident_id)
    result = TriageResult.model_validate(result)
    result.ran_headless = trigger is not None
    return result


@router.reasoner(tags=["gate"])
async def triage(incident_id: str, auto_approve_timeout: float = 45.0) -> TriageResult:
    """Diagnose, then stop and ask if the fix is one you cannot take back."""
    diagnosis = Diagnosis.model_validate(
        await router.app.call(f"{NODE_ID}.r06_diagnose", incident_id=incident_id)
    )
    plan = Remediation.model_validate(
        await router.app.call(
            f"{NODE_ID}.r07_classify_remediation",
            incident_id=incident_id,
            remediation=diagnosis.remediation,
        )
    )

    if not plan.destructive:
        return TriageResult(
            incident_id=incident_id,
            root_cause=diagnosis.root_cause,
            action=plan.action,
            destructive=False,
            approval="not_required",
        )

    # The gate. The execution goes status_reason="waiting_for_approval" on the
    # control plane and this coroutine parks on a Future until a human resolves it:
    #   POST /api/v1/executions/<execution_id>/approval-response
    #   {"decision":"approved","response":{"feedback":"..."}}   <- nested, not top-level
    # A timeout is data, not an exception: decision becomes "expired".
    router.app.note(
        f"destructive remediation proposed for {incident_id}: {plan.action}",
        tags=["approval", "gate"],
    )
    try:
        res = await router.app.pause(
            approval_request_id=f"remediate-{incident_id}",
            approval_request_url=f"http://127.0.0.1:8080/review/{incident_id}",
            expires_in_hours=1,
            timeout=auto_approve_timeout,
        )
    except Exception as exc:  # noqa: BLE001
        # The control plane refuses a callback to a private address unless it was
        # started with AGENTFIELD_WEBHOOK_ALLOWED_HOSTS=localhost,127.0.0.1. Fail
        # CLOSED: no approval means the destructive action does not run. An agent
        # that treats a broken gate as consent is worse than one with no gate.
        return TriageResult(
            incident_id=incident_id,
            root_cause=diagnosis.root_cause,
            action=f"HELD — gate unavailable, not executed: {plan.action}",
            destructive=True,
            approval="gate_unavailable",
            feedback=str(exc)[:400],
        )
    feedback = res.feedback or ((res.raw_response or {}).get("feedback", ""))

    return TriageResult(
        incident_id=incident_id,
        root_cause=diagnosis.root_cause,
        action=plan.action if res.approved else f"HELD — not executed: {plan.action}",
        destructive=True,
        approval=res.decision,
        feedback=feedback,
    )
