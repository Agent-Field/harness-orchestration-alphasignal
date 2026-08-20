"""Shared vocabulary for every rung.

The rungs differ in how they organise thinking, not in what they are asked to do.
Everything they hold in common lives here: the model, the finding schema, and the
incident text they read.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "incidents"))

import loader as incidents  # noqa: E402  (path set above)

NODE_ID = os.getenv("AGENT_NODE_ID", "blast-radius")
MODEL = os.getenv("AI_MODEL", "openrouter/deepseek/deepseek-v4-flash")
MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "2000"))

Severity = Literal["low", "medium", "high", "critical"]


class Finding(BaseModel):
    """One claim about one incident, pinned to something a scorer can check."""

    location: str = Field(description="Where the evidence is: 'logs.txt:412', 'deploys.json', 'metrics.json'")
    claim: str = Field(description="One sentence. What is wrong, and why this evidence shows it.")
    severity: Severity = Field(description="How much of the incident this explains")
    evidence: str = Field(description="A literal substring copied from the artifact named in location")


class Diagnosis(BaseModel):
    """What a rung returns. Every rung returns exactly this, whatever it did to get here."""

    root_cause: str = Field(description="One sentence naming the component and the mechanism")
    findings: list[Finding] = Field(description="Supporting findings, most load-bearing first")
    remediation: str = Field(description="The immediate fix")
    confident: bool = Field(description="False if the evidence does not actually settle it")


def incident_text(
    incident_id: str,
    sections: list[str] | None = None,
    token_budget: int = 12000,
    **kw,
) -> str:
    """Render an incident (or a slice of one) as prose for a model to read.

    `sections` picks artifacts: "alert", "logs", "deploys", "metrics", "topology".
    Only the log section scales to fit `token_budget`; it says how much it elided.
    """
    return incidents.to_prompt(
        incidents.load_incident(incident_id),
        sections=sections,
        token_budget=token_budget,
        **kw,
    )


def incident_ids() -> list[str]:
    return incidents.list_incidents()


SYSTEM = (
    "You are an experienced on-call engineer doing root-cause analysis. "
    "You cite evidence by copying literal text out of the artifact you name. "
    "You never invent a log line. If the evidence does not settle it, you say so."
)
