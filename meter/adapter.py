"""Bridge the incident corpus's ground truth to the meter, and score what the
meter cannot see on its own.

`meter.blast_radius` is domain-agnostic: it knows about findings, locations and
claims. The corpus in `incidents/ground_truth.json` knows about a specific
incident: which log line proves it, which plausible-looking artifact is a trap,
which diagnostic lenses were actually warranted. This module is the only place
those two vocabularies meet.

    from meter import adapter
    gt   = adapter.to_meter_ground_truth("incidents/ground_truth.json")
    df   = blast_radius.ladder_table(runs, gt)      # unchanged machinery
    ev   = adapter.score_evidence(trace, gt_corpus) # {"cited_real", "hallucinated"}

The interesting one is `score_evidence`. Every `match` string in the corpus was
verified to exist verbatim in the artifact it names, and the rungs are asked to
copy a literal substring into `Finding.evidence`. So a citation can be checked
against the artifact rather than merely judged for plausibility: we can prove a
quote is real. A model that invents a convincing log line is caught by string
containment, not by another model's opinion.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "incidents"))

import loader  # noqa: E402  (path set above)

DEFAULT_GROUND_TRUTH = ROOT / "incidents" / "ground_truth.json"

#: artifact name -> the loader section that renders it. Both spellings are
#: accepted: the corpus names files ("topology.json"), and a rung sometimes
#: writes the bare section ("topology") because that is what the prompt headed
#: the block with. Rejecting the bare form would score a correct citation as a
#: hallucination, which is the one mistake this module must not make.
_ARTIFACT_SECTION = {v: k for k, v in loader.ARTIFACTS.items()}
_ARTIFACT_SECTION.update({k: k for k in loader.ARTIFACTS})

#: how confidently a piece of required evidence pins the diagnosis down. The
#: meter weights recall by severity, so evidence that IS the root cause has to
#: outweigh evidence that merely bounds the blast scope.
_KIND_SEVERITY = {
    "stack_frame": "critical",
    "log_line": "critical",
    "change_event": "high",
    "heap": "high",
    "metric_series": "medium",
    "long_window": "medium",
    "alert_field": "low",
    "topology_attribute": "low",
}


# --------------------------------------------------------------- ground truth

def _corpus(path_or_obj: Any = None) -> dict:
    """Accept a path, an already-loaded corpus dict, or nothing (the default file)."""
    if isinstance(path_or_obj, dict) and "incidents" in path_or_obj:
        return path_or_obj
    return json.loads(Path(path_or_obj or DEFAULT_GROUND_TRUTH).read_text())


def incident_entry(gt: Any, incident_id: str) -> dict:
    """One incident's corpus entry, from a corpus dict, a path, or the entry itself."""
    if isinstance(gt, dict) and gt.get("id") == incident_id:
        return gt
    for inc in _corpus(gt)["incidents"]:
        if inc["id"] == incident_id:
            return inc
    raise KeyError(incident_id)


def to_meter_ground_truth(path: Any = None) -> dict[str, list[dict]]:
    """Corpus -> {incident_id: [{location, claim, severity}]}, the shape
    `blast_radius.ladder_table` already expects.

    Each `required_evidence` entry becomes one planted defect. The artifact name
    is the location: the corpus pins evidence to a file, not a line, and
    `location_match` treats a location with no line number as matching any line
    in that file -- so a rung that cites "logs.txt:412" still matches "logs.txt"
    while a rung that cites the wrong file does not. The claim is the `why`
    sentence, because that is the human-readable assertion the finding has to
    paraphrase; the raw `match` is often a bare identifier that would defeat the
    token-overlap similarity.
    """
    out: dict[str, list[dict]] = {}
    for inc in _corpus(path)["incidents"]:
        out[inc["id"]] = [
            {
                "location": ev["artifact"],
                "claim": f"{ev['why']} ({ev['match']})",
                "severity": _KIND_SEVERITY.get(ev.get("kind"), "medium"),
                "evidence_id": ev["id"],
                "match": ev["match"],
            }
            for ev in inc.get("required_evidence", [])
        ]
    return out


# ------------------------------------------------- is this quote actually real?

def _artifact_text(incident_id: str, artifact: str) -> str:
    """Everything a rung could honestly have quoted from one artifact.

    Two renderings are concatenated: the raw file bytes, and the prose the
    loader produced for the prompt. The rungs never see the raw JSON -- they see
    `loader.to_prompt` output -- so a metric series quoted as
    'error_rate_jpy_pct: start=0.1 end=99.7 ...' is a real citation even though
    that exact line appears nowhere in metrics.json. Checking both is the honest
    test of "did you copy this from what you were shown".
    """
    section = _ARTIFACT_SECTION.get(artifact)
    if section is None:
        return ""
    inc = loader.load_incident(incident_id)
    if section not in inc:
        return ""
    raw = inc[section]
    raw_text = raw if isinstance(raw, str) else json.dumps(raw, indent=1)
    try:
        rendered = loader.render_section(inc, section, metrics_style="summary")
    except Exception:  # noqa: BLE001
        rendered = ""
    return f"{raw_text}\n{rendered}"


def _norm(text: str) -> str:
    """Collapse whitespace and case. A quote is still a quote if the model
    reflowed it; it is not a quote if the words are different."""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def _artifact_of(location: str) -> str:
    """'logs.txt:412' -> 'logs.txt'."""
    head, _, tail = str(location).strip().rpartition(":")
    return head if head and tail.isdigit() else str(location).strip()


#: Shortest string we will accept as a citation. The corpus sets this bar, not
#: taste: its own `match` values include bare series names like "rss_mb", so a
#: longer minimum would score three verified corpus entries as hallucinations.
MIN_QUOTE_CHARS = 4

#: Models habitually elide the middle of a long quote with an ellipsis. Each
#: side is still a real substring, so the fragments are checked separately.
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.+|\u2026)\s*")


def evidence_is_real(incident_id: str, location: str, evidence: str) -> bool:
    """Does this quote literally occur in the artifact the finding named?

    An ellipsis splices two quotes into one string: 'first bit ... last bit'.
    Both halves are real citations, so every fragment is required to be present
    rather than the joined string, which as written exists nowhere. Anything
    else is a straight substring test: reflowed whitespace and changed case are
    forgiven, changed words are not.
    """
    haystack = _norm(_artifact_text(incident_id, _artifact_of(location)))
    if not haystack:
        return False
    fragments = [_norm(x) for x in _ELLIPSIS.split(str(evidence))]
    fragments = [f for f in fragments if len(f) >= MIN_QUOTE_CHARS]
    if not fragments:           # too short to be a citation of anything
        return False
    return all(f in haystack for f in fragments)


def score_evidence(trace: dict, gt: Any = None) -> dict:
    """{"cited_real": n, "hallucinated": n} for one run.

    A finding is `cited_real` when its `evidence` string is verbatim present in
    the artifact its `location` names, and `hallucinated` otherwise -- including
    when it quotes a real string but attributes it to the wrong artifact. This
    is the check no LLM-judge harness can make: it is decided by the corpus, not
    by another model.
    """
    incident_id = trace["input_id"]
    if gt is not None:
        incident_entry(gt, incident_id)   # fail loudly on an unknown incident
    real = sum(1 for f in trace.get("findings", [])
               if evidence_is_real(incident_id, f.get("location", ""), f.get("evidence", "")))
    total = len(trace.get("findings", []))
    return {"cited_real": real, "hallucinated": total - real}


# ------------------------------------------------------------- planted traps

def score_red_herrings(trace: dict, gt: Any = None) -> list[str]:
    """Ids of the planted red herrings this run chased.

    A herring counts as chased when its `match` string turns up in the stated
    root cause or in a finding's claim -- both are assertions by construction.
    The corpus says merely mentioning and dismissing a herring is not a
    penalty; a claim string is not the place a rung dismisses things, so this is
    close, but it is a substring test and not a reader. A run that writes
    "not dep-7720" will be scored as having chased dep-7720.
    """
    inc = incident_entry(gt, trace["input_id"])
    asserted = _norm(" ".join(
        [trace.get("root_cause", "")] + [f.get("claim", "") for f in trace.get("findings", [])]
    ))
    return [rh["id"] for rh in inc.get("red_herrings", []) if _norm(rh["match"]) in asserted]


def red_herring_penalty(trace: dict, gt: Any = None) -> float:
    """The corpus's own weighting of the herrings chased."""
    inc = incident_entry(gt, trace["input_id"])
    chased = set(score_red_herrings(trace, inc))
    return float(sum(rh.get("penalty", 1.0) for rh in inc.get("red_herrings", [])
                     if rh["id"] in chased))


# ------------------------------------------------------------------- lenses

def score_lenses(chosen_lenses: Iterable[str], gt: Any = None,
                 incident_id: str | None = None) -> dict:
    """Did the system pick the RIGHT lenses for THIS incident?

    Chapter 06's claim is that the graph is chosen per incident. That claim is
    only interesting if the choice changes with the incident, so this is the
    metric to watch: a system that proposes the same lens set everywhere scores
    well on the two or three incidents that set happens to fit, and badly on the
    rest. Lenses in neither list are neutral -- they neither help nor hurt --
    which is why precision counts hits over everything proposed while
    `unwarranted_hit` counts only the explicit false positives.
    """
    if incident_id is None and isinstance(gt, dict):
        incident_id = gt.get("id")
    inc = incident_entry(gt, incident_id) if incident_id else gt
    warranted = set(inc.get("lenses_warranted", []))
    forbidden = set(inc.get("lenses_not_warranted", []))
    proposed = set(chosen_lenses)

    hits = proposed & warranted
    misses = proposed & forbidden
    union = proposed | warranted
    return {
        "warranted_hit": len(hits),
        "unwarranted_hit": len(misses),
        "jaccard": len(hits) / len(union) if union else 1.0,
        "precision": len(hits) / len(proposed) if proposed else 0.0,
        "recall": len(hits) / len(warranted) if warranted else 0.0,
        "proposed": sorted(proposed),
        "missed_warranted": sorted(warranted - proposed),
        "false_positives": sorted(misses),
    }


def planted_evidence_hits(run: dict, truth: list[dict]) -> int:
    """How many PLANTED evidence items this run actually found.

    This is recall, and it is a different question from whether a run's quotes
    were real. `score_evidence` asks "is what it cited genuine?" -- a run can
    quote seven real log lines and still miss every line that mattered. This
    asks the other half: for each thing the corpus planted, did any finding
    surface it?

    A planted item counts as found when its `match` substring -- verified at
    corpus build time to exist in the artifact it names -- turns up in a
    finding's evidence or claim. String containment again, so a hit is a fact
    rather than a similarity estimate.

    Why not the meter's default claim-similarity matcher: this corpus states
    *why* each piece of evidence matters, in editorial prose that deliberately
    does not restate the evidence. Token overlap against that prose reads low
    for reasons unrelated to whether the finding was correct.
    """
    haystack = _norm(" ".join(
        f"{f.get('evidence', '')} {f.get('claim', '')}" for f in run.get("findings", [])
    ))
    if not haystack:
        return 0
    hits = 0
    for item in truth:
        needle = _norm(str(item.get("match") or item.get("claim") or ""))
        if len(needle) >= MIN_QUOTE_CHARS and needle in haystack:
            hits += 1
    return hits


def groundedness(run: dict) -> float:
    """Fraction of this run's citations that are verifiably real. 1.0 = nothing invented."""
    s = score_evidence(run)
    total = s["cited_real"] + s["hallucinated"]
    return s["cited_real"] / total if total else 0.0
