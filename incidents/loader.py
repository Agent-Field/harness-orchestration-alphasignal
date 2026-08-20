"""blast-radius incident corpus loader. Standard library only, Python 3.9+.

    from loader import list_incidents, load_incident, load_ground_truth, to_prompt

    inc = load_incident("inc-001")
    print(to_prompt(inc))                                  # everything, budget-capped
    print(to_prompt(inc, sections=["alert", "deploys"]))   # one lens's slice
    print(to_prompt(inc, sections=["logs"], token_budget=1500, log_filter="problems"))

Chapter 01 feeds the whole thing to one call. Chapters 04-06 feed narrow slices to
individual lenses, which is what `sections` and `token_budget` are for.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

ROOT = os.path.dirname(os.path.abspath(__file__))

ARTIFACTS = {
    "readme": "README.md",
    "alert": "alert.json",
    "logs": "logs.txt",
    "deploys": "deploys.json",
    "metrics": "metrics.json",
    "topology": "topology.json",
}
ALL_SECTIONS = ["readme", "alert", "topology", "deploys", "metrics", "logs"]

# Rough but stable: ~4 characters per token. Good enough for budgeting, and it
# keeps the loader dependency-free.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


# --------------------------------------------------------------------- loading
def list_incidents(include_byo: bool = True) -> List[str]:
    """Incident ids, sorted. Corpus incidents are inc-NNN; anything the user drops
    in as byo-* (see bring_your_own.md) is listed after them."""
    entries = [d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d))]
    corpus = sorted(d for d in entries if re.fullmatch(r"inc-\d{3}", d))
    if not include_byo:
        return corpus
    byo = sorted(d for d in entries if d.startswith("byo-"))
    return corpus + byo


def load_incident(incident_id: str) -> Dict[str, Any]:
    """Every artifact for one incident, parsed.

    Returns keys: id, path, readme (str), logs (str), alert/deploys/metrics/topology (dict).
    """
    d = os.path.join(ROOT, incident_id)
    if not os.path.isdir(d):
        raise FileNotFoundError(f"no such incident: {incident_id} (have: {', '.join(list_incidents())})")
    out: Dict[str, Any] = {"id": incident_id, "path": d, "missing": []}
    for key, fname in ARTIFACTS.items():
        path = os.path.join(d, fname)
        if not os.path.exists(path):
            # Bring-your-own incidents are allowed to be partial. A README and a
            # log tail is already enough to be useful.
            out["missing"].append(key)
            continue
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        try:
            out[key] = json.loads(raw) if fname.endswith(".json") else raw
        except json.JSONDecodeError as exc:
            raise ValueError(f"{incident_id}/{fname} is not valid JSON: {exc}") from None
    if set(out["missing"]) == set(ARTIFACTS):
        raise FileNotFoundError(f"{incident_id} contains none of: {', '.join(ARTIFACTS.values())}")
    return out


def load_all() -> List[Dict[str, Any]]:
    return [load_incident(i) for i in list_incidents()]


def load_ground_truth(incident_id: Optional[str] = None) -> Dict[str, Any]:
    """The whole ground-truth file, or one incident's entry if an id is given."""
    with open(os.path.join(ROOT, "ground_truth.json"), encoding="utf-8") as fh:
        gt = json.load(fh)
    if incident_id is None:
        return gt
    for inc in gt["incidents"]:
        if inc["id"] == incident_id:
            return inc
    raise KeyError(incident_id)


def lens_vocabulary() -> List[Dict[str, str]]:
    return load_ground_truth()["lens_vocabulary"]


# ------------------------------------------------------------------- rendering
def _kv_lines(obj: Any, indent: str = "  ") -> List[str]:
    """Flatten a small JSON object into readable indented lines."""
    lines: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{indent}{k}:")
                lines.extend(_kv_lines(v, indent + "  "))
            else:
                lines.append(f"{indent}{k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                head = item.get("id") or item.get("at") or item.get("name") or ""
                lines.append(f"{indent}- {head}".rstrip())
                lines.extend(_kv_lines({k: v for k, v in item.items() if k != "id"}, indent + "    "))
            else:
                lines.append(f"{indent}- {item}")
    else:
        lines.append(f"{indent}{obj}")
    return lines


def _series_summary(name: str, values: Sequence[float]) -> str:
    if not values:
        return f"  {name}: (empty)"
    lo, hi = min(values), max(values)
    return (f"  {name}: start={values[0]} end={values[-1]} min={lo} max={hi} "
            f"points={len(values)}")


def render_metrics(metrics: Dict[str, Any], style: str = "summary") -> str:
    w = metrics.get("window", {})
    out = [f"Metric window {w.get('start')} .. {w.get('end')} "
           f"at {w.get('step_seconds')}s steps ({w.get('points')} points)."]
    if metrics.get("units"):
        out.append("Units: " + ", ".join(f"{k}={v}" for k, v in metrics["units"].items()))
    out.append("Series:")
    for name, vals in metrics.get("series", {}).items():
        if style == "full":
            out.append(f"  {name}: {vals}")
        else:
            out.append(_series_summary(name, vals))
    if metrics.get("annotations"):
        out.append("Annotations:")
        for a in metrics["annotations"]:
            out.append(f"  {a.get('t')}  {a.get('text')}")
    for extra_key in ("note", "long_window", "heap_snapshot_summary"):
        if extra_key in metrics:
            out.append(f"{extra_key}:")
            out.extend(_kv_lines(metrics[extra_key]))
    return "\n".join(out)


_LEVEL_RE = re.compile(r"\b(ERROR|WARN|WARNING|FATAL|SEVERE|CRITICAL)\b", re.I)
_JSON_LEVEL_RE = re.compile(r'"level"\s*:\s*"(error|warn|warning|fatal|critical)"', re.I)


def _is_problem_line(line: str) -> bool:
    return bool(_LEVEL_RE.search(line) or _JSON_LEVEL_RE.search(line)) or line.startswith(("\t", "    at "))


def render_logs(logs: str, log_filter: str = "all", max_lines: Optional[int] = None) -> str:
    """log_filter: 'all' | 'problems' (WARN/ERROR/FATAL plus stack frames) | 'head_tail'."""
    lines = logs.rstrip("\n").split("\n")
    if log_filter == "problems":
        lines = [l for l in lines if _is_problem_line(l)]
    elif log_filter == "head_tail":
        n = (max_lines or 120) // 2
        if len(lines) > 2 * n:
            lines = lines[:n] + [f"... [{len(lines) - 2 * n} lines elided] ..."] + lines[-n:]
    if max_lines is not None and len(lines) > max_lines:
        # Prefer problem lines, but never exceed max_lines: this has to be
        # monotonic in max_lines for the budget search in to_prompt to work.
        problems = [(i, l) for i, l in enumerate(lines) if _is_problem_line(l)]
        others = [(i, l) for i, l in enumerate(lines) if not _is_problem_line(l)]
        if len(problems) > max_lines:
            step = max(len(problems) // max_lines, 1)
            kept = dict(problems[::step][:max_lines])
        else:
            kept = dict(problems)
            room = max_lines - len(kept)
            if room and others:
                step = max(len(others) // room, 1)
                kept.update(dict(others[::step][:room]))
        elided = len(lines) - len(kept)
        lines = [kept[i] for i in sorted(kept)]
        if elided > 0:
            lines.append(f"... [{elided} lines elided by the loader; "
                         f"{len(lines)} of {len(lines) + elided} shown, problem lines preferred] ...")
    return "\n".join(lines)


_SECTION_TITLE = {
    "readme": "WHAT THE ON-CALL ENGINEER SEES",
    "alert": "THE ALERT",
    "topology": "SERVICE TOPOLOGY",
    "deploys": "RECENT CHANGES",
    "metrics": "METRICS",
    "logs": "LOG TAIL",
}


def render_section(incident: Dict[str, Any], section: str, *,
                   metrics_style: str = "summary",
                   log_filter: str = "all",
                   log_max_lines: Optional[int] = None) -> str:
    title = f"## {_SECTION_TITLE[section]}"
    if section == "readme":
        body = incident["readme"].strip()
    elif section == "logs":
        body = render_logs(incident["logs"], log_filter=log_filter, max_lines=log_max_lines)
    elif section == "metrics":
        body = render_metrics(incident["metrics"], style=metrics_style)
    else:
        body = "\n".join(_kv_lines(incident[section]))
    return f"{title}\n{body}"


def to_prompt(incident: Dict[str, Any],
              sections: Optional[Iterable[str]] = None,
              token_budget: int = 12000,
              *,
              metrics_style: str = "summary",
              log_filter: str = "all",
              header: bool = True) -> str:
    """Render an incident, or a chosen subset of its artifacts, as clean prose.

    Everything except the log tail is rendered in full; the log is the only
    section that scales, so it absorbs whatever budget is left over. If the
    budget is so small that even the non-log sections do not fit, sections are
    dropped from the end of `sections` and the omission is stated in the text
    rather than hidden.
    """
    sections = list(sections) if sections is not None else list(ALL_SECTIONS)
    unknown = [s for s in sections if s not in ALL_SECTIONS]
    if unknown:
        raise ValueError(f"unknown section(s): {unknown}; valid: {ALL_SECTIONS}")
    absent = [s for s in sections if s not in incident]
    sections = [s for s in sections if s in incident]

    head = (f"# INCIDENT {incident['id']}\n"
            f"(Artifacts included: {', '.join(sections)})\n") if header else ""

    fixed = [s for s in sections if s != "logs"]
    rendered: Dict[str, str] = {}
    for s in fixed:
        rendered[s] = render_section(incident, s, metrics_style=metrics_style)

    used = estimate_tokens(head) + sum(estimate_tokens(v) + 2 for v in rendered.values())
    dropped: List[str] = []
    while used > token_budget and fixed:
        drop = fixed.pop()
        used -= estimate_tokens(rendered.pop(drop)) + 2
        dropped.append(drop)

    parts = [head] if head else []
    for s in sections:
        if s in rendered:
            parts.append(rendered[s])
    if "logs" in sections:
        remaining = token_budget - used
        if remaining <= 40:
            dropped.append("logs")
        else:
            # Binary-search a line count that fits the remaining budget.
            lines = incident["logs"].rstrip("\n").split("\n")
            lo, hi, best = 1, len(lines), None
            while lo <= hi:
                mid = (lo + hi) // 2
                body = render_section(incident, "logs", log_filter=log_filter, log_max_lines=mid)
                if estimate_tokens(body) <= remaining:
                    best, lo = body, mid + 1
                else:
                    hi = mid - 1
            parts.append(best if best is not None
                         else render_section(incident, "logs", log_filter="problems", log_max_lines=20))
    if absent:
        parts.append("## NOT AVAILABLE\n" + ", ".join(absent) +
                     " (this incident has no such artifact; do not assume anything about it)")
    if dropped:
        parts.append("## OMITTED\n" + ", ".join(dropped) +
                     " (did not fit the token budget; ask for them explicitly if needed)")
    return "\n\n".join(p for p in parts if p).strip() + "\n"


# ------------------------------------------------------------------ self-check
if __name__ == "__main__":
    ids = list_incidents()
    gt = load_ground_truth()
    print(f"{len(ids)} incidents, {len(gt['incidents'])} ground-truth entries, "
          f"{len(gt['lens_vocabulary'])} lenses")
    for i in ids:
        inc = load_incident(i)
        full = to_prompt(inc, token_budget=200000)
        capped = to_prompt(inc, token_budget=3000)
        slim = to_prompt(inc, sections=["alert", "deploys"], token_budget=2000)
        g = load_ground_truth(i)
        print(f"  {i}  full={estimate_tokens(full):>6}tok  capped={estimate_tokens(capped):>5}tok  "
              f"slice={estimate_tokens(slim):>4}tok  lenses={len(g['lenses_warranted'])}  "
              f"{g['difficulty']:<6} {g['failure_class']}")
        assert estimate_tokens(capped) <= 3000, i
        assert estimate_tokens(slim) <= 2000, i
    print("ok")
