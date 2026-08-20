"""blast_radius: measure how wide the gap gets between what you meant and what you got.

The ladder of autonomy runs the same task at seven altitudes of intent (r1..r7).
This module turns a pile of run traces into the numbers that argue the thesis:

  outcome_variance  -- same input, how much does the ANSWER move?
  process_variance  -- same input, how much does the PROCESS (the DAG) move?
  recall/precision  -- did it actually find the planted defects?
  cost/time/touch   -- what did the containment cost you?

The thesis lives in the gap between the first two: at low altitude both are
small because nothing much happens; in the improvised middle (r2-r3) both blow
up; with structure (r4+) outcome variance collapses while process variance is
allowed to stay high on purpose. Varying process + stable outcome = contained
autonomy.

Trace schema (one JSON object per run) -- see fixtures/runs.json:

    {
      "rung": "r3",                       # r1..r7, the altitude of intent
      "input_id": "svc-auth",             # what was analysed; repeated across runs
      "run_id": "r3/svc-auth/002",        # unique
      "findings": [
        {"id": "f1",
         "location": "auth/session.py:42",  # file:line, line matched with tolerance
         "claim": "session token never expires",
         "severity": "high"}               # low|medium|high|critical
      ],
      "cost_usd": 0.41,
      "tokens": 18342,
      "wall_time_s": 63.2,
      "human_touchpoints": 1,             # times a human had to look/decide
      "escalations": ["ambiguous scope"], # free-text, count is what matters
      "dag": {                            # the process actually executed
        "nodes": [{"id": "n0", "label": "plan"}, ...],
        "edges": [["n0", "n1"], ...]      # by node id
      }
    }

Ground truth (per input): {"svc-auth": [{"location": ..., "claim": ..., "severity": ...}]}
"""

from __future__ import annotations

import difflib
import itertools
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

RUNGS = ["r1", "r2", "r3", "r4", "r5", "r6", "r7"]
SEVERITY_WEIGHT = {"low": 1.0, "medium": 2.0, "high": 4.0, "critical": 8.0}

# How close two claims must read before we call them the same finding.
CLAIM_THRESHOLD = 0.45
# How far apart two line numbers may be and still be the same defect.
LINE_TOLERANCE = 6


# ---------------------------------------------------------------- loading

def load_runs(path) -> list[dict]:
    return json.loads(Path(path).read_text())


def load_ground_truth(path) -> dict[str, list[dict]]:
    return json.loads(Path(path).read_text())


REQUIRED = ("rung", "input_id", "run_id", "findings", "cost_usd", "tokens",
            "wall_time_s", "human_touchpoints", "escalations", "dag")


def validate_run(run: dict) -> list[str]:
    """Check one emitted trace against the schema. Returns a list of complaints.

    The seven rung implementations each emit these; call this in their tests so a
    rung cannot quietly drop a field and flatten its own numbers.
    """
    bad = [f"missing field: {k}" for k in REQUIRED if k not in run]
    if run.get("rung") not in RUNGS:
        bad.append(f"rung must be one of {RUNGS}, got {run.get('rung')!r}")
    for i, f in enumerate(run.get("findings") or []):
        for k in ("id", "location", "claim", "severity"):
            if k not in f:
                bad.append(f"findings[{i}] missing {k}")
        if f.get("severity") not in SEVERITY_WEIGHT:
            bad.append(f"findings[{i}] severity must be one of "
                       f"{list(SEVERITY_WEIGHT)}, got {f.get('severity')!r}")
    dag = run.get("dag") or {}
    ids = {n.get("id") for n in dag.get("nodes", [])}
    if any("label" not in n for n in dag.get("nodes", [])):
        bad.append("every dag node needs a label (labels are what get compared)")
    for s_, t in dag.get("edges", []):
        if s_ not in ids or t not in ids:
            bad.append(f"dag edge {s_}->{t} references an unknown node id")
    return bad


def altitude(rung: str) -> int:
    """r3 -> 3. The x-axis of the whole story: how high-level the intent was."""
    return int(str(rung).lstrip("rR"))


# ------------------------------------------------- does this == that?

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "on", "and", "or",
         "it", "its", "this", "that", "be", "can", "for", "with", "not", "no"}


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def claim_similarity(a: str, b: str) -> float:
    """0..1. Paraphrase-tolerant, no embeddings: token overlap OR raw string ratio."""
    wa, wb = _words(a), _words(b)
    overlap = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    literal = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(overlap, literal)


def _split_location(loc: str) -> tuple[str, int | None]:
    loc = str(loc).strip().lower()
    if ":" in loc:
        head, _, tail = loc.rpartition(":")
        if tail.isdigit():
            return head, int(tail)
    return loc, None


def location_match(a: str, b: str) -> bool:
    """Same file, and line numbers within tolerance (a report may be off by a few)."""
    fa, la = _split_location(a)
    fb, lb = _split_location(b)
    if fa != fb:
        return False
    if la is None or lb is None:
        return True
    return abs(la - lb) <= LINE_TOLERANCE


def same_finding(a: dict, b: dict, threshold: float = CLAIM_THRESHOLD) -> bool:
    return (location_match(a["location"], b["location"])
            and claim_similarity(a["claim"], b["claim"]) >= threshold)


def _pair_up(left: list[dict], right: list[dict], threshold=CLAIM_THRESHOLD) -> int:
    """Greedy best-first matching between two finding lists. Returns pairs matched."""
    scored = []
    for i, x in enumerate(left):
        for j, y in enumerate(right):
            if location_match(x["location"], y["location"]):
                s = claim_similarity(x["claim"], y["claim"])
                if s >= threshold:
                    scored.append((s, i, j))
    scored.sort(reverse=True)
    used_l: set[int] = set()
    used_r: set[int] = set()
    matched = 0
    for _, i, j in scored:
        if i not in used_l and j not in used_r:
            used_l.add(i)
            used_r.add(j)
            matched += 1
    return matched


def finding_jaccard(left: list[dict], right: list[dict]) -> float:
    if not left and not right:
        return 1.0
    m = _pair_up(left, right)
    return m / (len(left) + len(right) - m)


# ------------------------------------------------------- outcome variance

def _cv(values) -> float:
    """Coefficient of variation. Scale-free dispersion, so counts and severity compare."""
    v = np.asarray(values, dtype=float)
    if len(v) < 2 or v.mean() == 0:
        return 0.0
    return float(v.std(ddof=1) / v.mean())


def outcome_variance(runs: list[dict]) -> dict:
    """How much the ANSWER moves across repeats of the same input.

    instability : 1 - mean pairwise Jaccard of the finding sets (set-level churn)
    count_cv    : dispersion in how many findings came back
    severity_cv : dispersion in total severity weight (a run can find the same
                  number of things but call them all critical)
    """
    by_input: dict[str, list[dict]] = {}
    for r in runs:
        by_input.setdefault(r["input_id"], []).append(r)

    instabilities, count_cvs, sev_cvs = [], [], []
    for group in by_input.values():
        if len(group) < 2:
            continue
        sims = [finding_jaccard(a["findings"], b["findings"])
                for a, b in itertools.combinations(group, 2)]
        instabilities.append(1.0 - float(np.mean(sims)))
        count_cvs.append(_cv([len(r["findings"]) for r in group]))
        sev_cvs.append(_cv([sum(SEVERITY_WEIGHT.get(f["severity"], 1.0)
                                for f in r["findings"]) for r in group]))
    return {"instability": float(np.mean(instabilities or [0.0])),
            "count_cv": float(np.mean(count_cvs or [0.0])),
            "severity_cv": float(np.mean(sev_cvs or [0.0]))}


# ------------------------------------------------------- process variance

def _shape(dag: dict) -> tuple[Counter, Counter]:
    """A DAG reduced to what it DOES, not what it named things.

    Node ids are arbitrary, so compare label multisets and label-to-label edges.
    Two structurally identical runs score 0 even if the ids differ.
    """
    label = {n["id"]: n.get("label", n["id"]) for n in dag.get("nodes", [])}
    nodes = Counter(label.values())
    edges = Counter((label.get(s, s), label.get(t, t)) for s, t in dag.get("edges", []))
    return nodes, edges


def _graph_distance(a: dict, b: dict) -> float:
    """Normalised edit distance: symmetric difference of node and edge multisets.

    0.0 = same process ran twice. 1.0 = nothing in common.
    """
    na, ea = _shape(a)
    nb, eb = _shape(b)
    diff = sum(((na - nb) + (nb - na)).values()) + sum(((ea - eb) + (eb - ea)).values())
    total = sum(na.values()) + sum(nb.values()) + sum(ea.values()) + sum(eb.values())
    return diff / total if total else 0.0


def process_variance(runs: list[dict]) -> float:
    """How much the PROCESS moves across repeats of the same input.

    r4 (hand-written graph) should be ~0: the same graph every time.
    r6 (JIT graph) should be well above 0 by design -- and that is fine, as long
    as outcome_variance stays low. That gap is the whole argument.
    """
    by_input: dict[str, list[dict]] = {}
    for r in runs:
        by_input.setdefault(r["input_id"], []).append(r)
    per_input = []
    for group in by_input.values():
        if len(group) < 2:
            continue
        per_input.append(float(np.mean([_graph_distance(a["dag"], b["dag"])
                                        for a, b in itertools.combinations(group, 2)])))
    return float(np.mean(per_input or [0.0]))


# ---------------------------------------------------------- vs ground truth

def recall_precision(runs: list[dict], ground_truth: dict[str, list[dict]],
                     hits_fn=None) -> dict:
    """Mean per-run recall and precision against the planted defects.

    `hits_fn(run, truth) -> int` overrides how a hit is counted. The default
    compares claims by token overlap, which is all you can do when ground truth is
    prose. When ground truth pins evidence to literal substrings -- as this repo's
    incident corpus does -- pass `meter.adapter.evidence_hits` instead and a hit
    becomes a fact about string containment rather than a similarity heuristic.
    """
    recalls, precisions = [], []
    for r in runs:
        truth = ground_truth.get(r["input_id"], [])
        found = r["findings"]
        hits = hits_fn(r, truth) if hits_fn else _pair_up(found, truth)
        recalls.append(hits / len(truth) if truth else 0.0)
        precisions.append(hits / len(found) if found else 0.0)
    return {"recall": float(np.mean(recalls or [0.0])),
            "precision": float(np.mean(precisions or [0.0]))}


# ------------------------------------------------------------ the ladder

def ladder_table(runs: list[dict], ground_truth: dict[str, list[dict]],
                 hits_fn=None) -> pd.DataFrame:
    """One row per rung: what you got, how much it wobbled, what it cost.

    `hits_fn` is passed through to `recall_precision` -- see its docstring.
    """
    rows = []
    for rung in sorted({r["rung"] for r in runs}, key=altitude):
        group = [r for r in runs if r["rung"] == rung]
        rp = recall_precision(group, ground_truth, hits_fn=hits_fn)
        ov = outcome_variance(group)
        rows.append({
            "rung": rung,
            "altitude": altitude(rung),
            "runs": len(group),
            "recall": rp["recall"],
            "precision": rp["precision"],
            "outcome_variance": ov["instability"],
            "count_cv": ov["count_cv"],
            "severity_cv": ov["severity_cv"],
            "process_variance": process_variance(group),
            "cost_usd": float(np.mean([r["cost_usd"] for r in group])),
            "wall_time_s": float(np.mean([r["wall_time_s"] for r in group])),
            "touchpoints": float(np.mean([r["human_touchpoints"] for r in group])),
            "escalations": float(np.mean([len(r.get("escalations", [])) for r in group])),
        })
    return pd.DataFrame(rows).set_index("rung")


DEFAULT_LABELS = {
    "r1": "r1\none-shot", "r2": "r2\nloop", "r3": "r3\nnested AI",
    "r4": "r4\nhand graph", "r5": "r5\nAI graph", "r6": "r6\nJIT graph",
    "r7": "r7\nheadless",
}


def ladder_plot(df: pd.DataFrame, labels: dict | None = None, title: str | None = None):
    """The slide: recall climbing, blast radius peaking at r3 and collapsing after r4."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = labels or DEFAULT_LABELS
    x = df["altitude"].to_numpy()
    fig, ax = plt.subplots(figsize=(15, 8.5))

    ax.axvspan(x.min() - 0.5, 3.5, color="#d94a3d", alpha=0.07, zorder=0)
    ax.axvspan(3.5, x.max() + 0.5, color="#2e7d5b", alpha=0.07, zorder=0)
    ax.text(2.0, 1.012, "IMPROVISED", ha="center", fontsize=15, weight="bold",
            color="#b03528", transform=ax.get_xaxis_transform())
    ax.text(5.5, 1.012, "STRUCTURED", ha="center", fontsize=15, weight="bold",
            color="#1f5c42", transform=ax.get_xaxis_transform())

    ax.plot(x, df["recall"], "-o", color="#1f5c42", lw=4.5, ms=13,
            label="recall vs planted defects", zorder=3)
    ax.set_ylabel("recall  (did it find the bugs?)", fontsize=19, color="#1f5c42",
                  weight="bold", labelpad=12)
    ax.set_ylim(0, 1.05)
    ax.tick_params(axis="y", labelsize=16, colors="#1f5c42")
    ax.tick_params(axis="x", labelsize=17)
    ax.set_xticks(x)
    ax.set_xticklabels([labels.get(r, r) for r in df.index], fontsize=16)
    ax.set_xlabel("altitude of intent  →", fontsize=20, weight="bold", labelpad=14)
    ax.set_xlim(x.min() - 0.5, x.max() + 0.5)
    ax.grid(axis="y", alpha=0.25, zorder=0)

    ax2 = ax.twinx()
    ax2.plot(x, df["outcome_variance"], "-o", color="#d94a3d", lw=4.5, ms=13,
             label="outcome variance  (blast radius)", zorder=3)
    ax2.plot(x, df["process_variance"], "--s", color="#3b6fb0", lw=3.2, ms=10,
             label="process variance  (the DAG itself)", zorder=3)
    ax2.set_ylabel("variance across identical runs", fontsize=19, color="#d94a3d",
                   weight="bold", labelpad=12)
    ax2.set_ylim(0, 1.05)
    ax2.tick_params(axis="y", labelsize=16, colors="#d94a3d")

    peak = int(df["outcome_variance"].to_numpy().argmax())
    ax2.annotate("BLAST RADIUS\nsame input, different answers",
                 xy=(x[peak], df["outcome_variance"].iloc[peak]),
                 xytext=(x[peak] + 0.35, 0.97), fontsize=17, weight="bold",
                 color="#b03528", ha="left", va="top",
                 arrowprops=dict(arrowstyle="-|>", lw=3, color="#b03528",
                                 shrinkA=0, shrinkB=10))

    if "r6" in df.index:
        i = df.index.get_loc("r6")
        ax2.annotate("CONTAINED AUTONOMY\nprocess still varies,\nthe answer doesn't",
                     xy=(x[i], df["outcome_variance"].iloc[i]),
                     xytext=(x[i] + 1.05, 0.70), fontsize=17, weight="bold",
                     color="#1f4d80", ha="right", va="center",
                     arrowprops=dict(arrowstyle="-|>", lw=3, color="#1f4d80",
                                     connectionstyle="arc3,rad=0.25",
                                     shrinkA=8, shrinkB=10))

    if "r4" in df.index:
        i = df.index.get_loc("r4")
        ax2.annotate("hand-written graph:\nthe same process, every run",
                     xy=(x[i], df["process_variance"].iloc[i]),
                     xytext=(x[i] + 0.15, 0.20), fontsize=15, style="italic",
                     color="#1f4d80", ha="left", va="bottom",
                     arrowprops=dict(arrowstyle="-|>", lw=2.2, color="#1f4d80",
                                     shrinkA=4, shrinkB=6))

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower center", fontsize=16, ncol=3,
              frameon=False, bbox_to_anchor=(0.5, 1.075))
    ax.set_title(title or "Blast radius across the ladder of autonomy",
                 fontsize=25, weight="bold", pad=95)
    fig.tight_layout()
    return fig


def save_plot(fig, path, scale=2):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100 * scale, bbox_inches="tight", facecolor="white")
    return path
