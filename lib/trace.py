"""Turn one real AgentField run into one meter-shaped trace.

The meter (`meter.blast_radius`) argues the thesis from a pile of JSON objects,
one per run. This module is the plumbing that produces those objects from things
that actually happened: a `Diagnosis` returned by a rung, and the execution graph
the control plane recorded while producing it.

    from lib import trace
    t = trace.build_trace("r01_diagnose", "inc-002", run_id, result, wall_time_s=41.2)
    trace.save_trace(t)          # -> traces/runs/r1/inc-002/run_....json

Two halves, from two different places:

  the ANSWER   comes from the rung's return value (`Diagnosis`): root_cause,
               findings[{location, claim, severity, evidence}], remediation,
               confident.
  the PROCESS  comes from the control plane via `lib.dag.fetch_run`, which
               returns a FLAT list of executions whose edges are implicit in
               `parent_execution_id`. Node labels are `reasoner_id`, never an
               execution id: `meter.blast_radius.process_variance` compares
               label MULTISETS across runs, so a label that is unique per run
               would report every run as maximally different from every other.

Cost and tokens are deliberately not invented. AgentField's CostTracker is
per-process and in-memory, so a completed run's spend is not readable from the
control plane after the fact. `cost_usd` is therefore None and `tokens` is 0
unless the caller passes real numbers it measured itself. A None cost makes the
meter's cost column blank rather than confidently wrong.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:                      # `import lib.trace` from the repo root
    from . import dag as dag_api
except ImportError:       # `import trace` with lib/ on sys.path (the notebooks)
    import dag as dag_api

DEFAULT_SERVER = dag_api.DEFAULT_SERVER
TRACE_ROOT = "traces/runs"

_RUNG_RE = re.compile(r"r0*(\d+)")


def normalise_rung(rung: Any) -> str:
    """'r01_diagnose', 'r01', 'r1', 1  ->  'r1'.

    Reasoner ids are zero-padded and suffixed ('r04_graph'); the meter's RUNGS
    vocabulary is 'r1'..'r7'. One place to reconcile the two spellings.
    """
    if isinstance(rung, int):
        return f"r{rung}"
    m = _RUNG_RE.search(str(rung).lower())
    if not m:
        raise ValueError(f"cannot read a rung number out of {rung!r}")
    return f"r{int(m.group(1))}"


# ------------------------------------------------------------------ the answer

def _findings(result: dict) -> list[dict]:
    """Diagnosis.findings -> meter findings, with synthesised stable ids.

    The meter requires an `id`; the rungs do not produce one, because a model
    asked to invent identifiers wastes tokens and invents inconsistent ones.
    f1..fN in returned order is enough: ids are never compared across runs,
    only location and claim are. `evidence` is carried through untouched --
    `meter.adapter.score_evidence` is the only consumer, and it needs the
    literal string to look for it in the artifact.
    """
    out = []
    for i, f in enumerate(result.get("findings") or [], start=1):
        out.append({
            "id": f.get("id") or f"f{i}",
            "location": str(f.get("location", "")),
            "claim": str(f.get("claim", "")),
            "severity": str(f.get("severity", "medium")).lower(),
            "evidence": f.get("evidence", ""),
        })
    return out


def _escalations(result: dict) -> list[str]:
    """A rung that says it is not confident has escalated to a human, whether or
    not anyone was listening. The meter counts these, it does not read them."""
    if result.get("confident") is False:
        return ["diagnosis returned confident=false"]
    return []


# ----------------------------------------------------------------- the process

def fetch_dag(any_id: str, server: str = DEFAULT_SERVER) -> dict:
    """Control-plane executions -> {"nodes": [...], "edges": [...]}.

    The control plane hands back a flat list; the parent pointer is the whole
    graph. Edges whose parent is outside this run (a caller in another run) are
    dropped, because `validate_run` rejects an edge to an unknown node.
    """
    data = dag_api.fetch_run(any_id, server)
    execs = data.get("executions") or []
    nodes = [{"id": e["execution_id"],
              "label": e.get("reasoner_id") or e.get("node_id") or "?"}
             for e in execs]
    known = {n["id"] for n in nodes}
    edges = [[e["parent_execution_id"], e["execution_id"]]
             for e in execs
             if e.get("parent_execution_id") in known]
    return {"nodes": nodes, "edges": edges}


# -------------------------------------------------------------------- assembly

def build_trace(
    rung: str,
    incident_id: str,
    run_id: str,
    result: dict,
    wall_time_s: float,
    server: str = DEFAULT_SERVER,
    *,
    cost_usd: float | None = None,
    tokens: int = 0,
    human_touchpoints: int = 0,
) -> dict:
    """One completed run -> one object that `validate_run` accepts.

    `result` is the rung's Diagnosis as a dict. `run_id` may be a run id or any
    execution id inside the run; the DAG fetch resolves either. If the control
    plane cannot be reached the trace is still emitted, with an empty DAG, so a
    measured answer is never thrown away over a missing graph.
    """
    try:
        graph = fetch_dag(run_id, server)
    except Exception:  # noqa: BLE001 - a missing graph must not lose the answer
        graph = {"nodes": [], "edges": []}

    return {
        "rung": normalise_rung(rung),
        "input_id": incident_id,
        "run_id": run_id,
        "findings": _findings(result),
        "cost_usd": cost_usd,       # see module docstring: not in the control plane
        "tokens": tokens,           # ditto
        "wall_time_s": float(wall_time_s),
        "human_touchpoints": human_touchpoints,
        "escalations": _escalations(result),
        "dag": graph,
        # Carried for the corpus scorers in meter.adapter; the meter ignores
        # extra keys, and re-deriving these from the findings is lossy.
        "root_cause": result.get("root_cause", ""),
        "remediation": result.get("remediation", ""),
        "confident": result.get("confident"),
    }


# ------------------------------------------------------------------------ disk

def save_trace(trace: dict, root: str | Path = TRACE_ROOT) -> Path:
    """traces/runs/<rung>/<incident>/<run_id>.json. One file per run, append-only.

    Laid out by rung then incident because that is how the meter groups them:
    variance is always measured within one (rung, input) cell.
    """
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", str(trace["run_id"]))
    path = Path(root) / trace["rung"] / trace["input_id"] / f"{safe}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, indent=1, sort_keys=False))
    return path


def load_traces(root: str | Path = TRACE_ROOT) -> list[dict]:
    """Every saved trace, ready to hand to `meter.blast_radius.ladder_table`."""
    return [json.loads(p.read_text()) for p in sorted(Path(root).rglob("*.json"))]
