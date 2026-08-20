"""Render an AgentField workflow run as a mermaid DAG inside a Jupyter cell.

This is the money visual of the talk: chapter 04's graph is hand-wired, so it
is byte-identical every run; chapter 06's graph is decided at runtime, so it is
different every run. `render_two()` puts them side by side.

Endpoint (verified live against a real run on 2026-08-20):
    GET /api/v1/agentic/run/{run_id}
      -> {"ok": true, "data": {"run_id", "agents", "executions": [...],
                               "notes", "summary"}}
    Each execution: execution_id, run_id, parent_execution_id (absent on root),
                    agent_node_id, reasoner_id, node_id, status, input,
                    started_at, completed_at, duration_ms, error
Edges come from parent_execution_id. That field is the whole DAG.

An execution_id can be passed instead of a run_id; it is resolved via
    GET /api/v1/executions/{execution_id}  ->  {"run_id": ...}
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx

RUN_ENDPOINT = "/api/v1/agentic/run/{run_id}"
EXEC_ENDPOINT = "/api/v1/executions/{execution_id}"
ACTIVE_ENDPOINT = "/api/v1/executions/active"

DEFAULT_SERVER = os.getenv("AGENTFIELD_SERVER", "http://localhost:8080")

#: status -> (mermaid class name, glyph)
_STATUS = {
    "succeeded": ("ok", "✓"),
    "running": ("run", "•"),
    "queued": ("wait", "·"),
    "pending": ("wait", "·"),
    "waiting": ("wait", "·"),
    "paused": ("wait", "‖"),
    "failed": ("bad", "✗"),
    "timeout": ("bad", "⏱"),
    "cancelled": ("bad", "⊘"),
}

_CLASSDEFS = """
  classDef ok   fill:#dcfce7,stroke:#16a34a,stroke-width:1px,color:#14532d;
  classDef run  fill:#dbeafe,stroke:#2563eb,stroke-width:1px,color:#1e3a8a;
  classDef wait fill:#f1f5f9,stroke:#94a3b8,stroke-width:1px,color:#334155;
  classDef bad  fill:#fee2e2,stroke:#dc2626,stroke-width:1px,color:#7f1d1d;
"""


# --------------------------------------------------------------------- fetch


def _headers() -> Dict[str, str]:
    key = os.getenv("AGENTFIELD_API_KEY")
    return {"X-API-Key": key} if key else {}


def _unwrap(payload: Any) -> Dict[str, Any]:
    """Control plane wraps agentic responses as {"ok":..,"data":..}."""
    if isinstance(payload, dict) and "data" in payload and "ok" in payload:
        return payload["data"] or {}
    return payload or {}


def resolve_run_id(any_id: str, server: str = DEFAULT_SERVER) -> str:
    """Accept a run_id or an execution_id, return a run_id."""
    with httpx.Client(base_url=server, headers=_headers(), timeout=15) as c:
        r = c.get(RUN_ENDPOINT.format(run_id=any_id))
        if r.status_code == 200:
            return any_id
        r2 = c.get(EXEC_ENDPOINT.format(execution_id=any_id))
        if r2.status_code == 200:
            run_id = _unwrap(r2.json()).get("run_id")
            if run_id:
                return run_id
    raise LookupError(f"{any_id!r} is neither a run_id nor a known execution_id on {server}")


def fetch_run(any_id: str, server: str = DEFAULT_SERVER) -> Dict[str, Any]:
    """Fetch the full run overview (executions + summary) for a run/execution id."""
    run_id = resolve_run_id(any_id, server)
    with httpx.Client(base_url=server, headers=_headers(), timeout=15) as c:
        r = c.get(RUN_ENDPOINT.format(run_id=run_id))
        r.raise_for_status()
        return _unwrap(r.json())


def recent_runs(server: str = DEFAULT_SERVER, limit: int = 10) -> List[Dict[str, Any]]:
    """In-flight runs, newest first. Handy for grabbing an id to render."""
    with httpx.Client(base_url=server, headers=_headers(), timeout=15) as c:
        r = c.get(ACTIVE_ENDPOINT)
        r.raise_for_status()
        runs = _unwrap(r.json()).get("runs") or r.json().get("runs") or []
    return sorted(runs, key=lambda x: x.get("started_at", ""), reverse=True)[:limit]


# ------------------------------------------------------------------ shaping


def _safe(text: str) -> str:
    """Make a string safe inside a mermaid ["..."] label."""
    return (
        str(text)
        .replace("\\", "/")
        .replace('"', "'")
        .replace("\n", " ")
        .strip()
    ) or "?"


def stats(data: Dict[str, Any]) -> Dict[str, int]:
    """Blast-radius numbers: how far did one call actually reach?"""
    execs = data.get("executions") or []
    by_id = {e["execution_id"]: e for e in execs}
    children: Dict[Optional[str], int] = {}
    for e in execs:
        children[e.get("parent_execution_id")] = children.get(e.get("parent_execution_id"), 0) + 1

    def depth(e: Dict[str, Any], seen: frozenset = frozenset()) -> int:
        pid = e.get("parent_execution_id")
        if not pid or pid not in by_id or pid in seen:
            return 1
        return 1 + depth(by_id[pid], seen | {pid})

    return {
        "executions": len(execs),
        "agents": len(data.get("agents") or []),
        "max_depth": max((depth(e) for e in execs), default=0),
        "max_fanout": max((v for k, v in children.items() if k), default=0),
    }


def to_mermaid(
    data: Dict[str, Any],
    *,
    direction: str = "TD",
    show_agent: bool = False,
    _prefix: str = "n",
    _bare: bool = False,
) -> str:
    """Build a mermaid flowchart from a run overview.

    _bare/_prefix are used by render_two() to inline two graphs into one chart.
    """
    execs = data.get("executions") or []
    ids = {e["execution_id"]: f"{_prefix}{i}" for i, e in enumerate(execs)}

    lines: List[str] = [] if _bare else [f"flowchart {direction}"]
    pad = "    " if _bare else "  "

    if not execs:
        lines.append(f'{pad}{_prefix}empty["(no executions for this run)"]')
        return "\n".join(lines)

    classed: Dict[str, List[str]] = {}
    for e in execs:
        nid = ids[e["execution_id"]]
        cls, glyph = _STATUS.get(str(e.get("status", "")).lower(), ("wait", "·"))
        label = _safe(e.get("reasoner_id") or e.get("node_id") or "?")
        if show_agent and e.get("agent_node_id"):
            label = f"{_safe(e['agent_node_id'])}<br/>{label}"
        ms = e.get("duration_ms")
        sub = f"<br/><small>{glyph} {e.get('status','?')}"
        sub += f" · {ms/1000:.1f}s</small>" if isinstance(ms, (int, float)) and ms else f"</small>"
        lines.append(f'{pad}{nid}["{label}{sub}"]')
        classed.setdefault(cls, []).append(nid)

    for e in execs:
        pid = e.get("parent_execution_id")
        if pid and pid in ids:
            lines.append(f"{pad}{ids[pid]} --> {ids[e['execution_id']]}")

    for cls, nodes in classed.items():
        lines.append(f"{pad}class {','.join(nodes)} {cls};")

    if not _bare:
        lines.append(_CLASSDEFS.strip("\n"))
    return "\n".join(lines)


# ----------------------------------------------------------------- display


def _md(mermaid: str):
    from IPython.display import Markdown

    return Markdown(f"```mermaid\n{mermaid}\n```")


def _html(mermaid_blocks: Sequence[Tuple[str, str]]):
    """CDN-backed fallback for front-ends that do not render markdown mermaid."""
    from IPython.display import HTML

    cells = "".join(
        f'<div style="flex:1;min-width:320px">'
        f'<div style="font:600 13px/1.4 ui-sans-serif,system-ui;margin:0 0 6px">{t}</div>'
        f'<pre class="mermaid">{m}</pre></div>'
        for t, m in mermaid_blocks
    )
    return HTML(
        f'<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start">{cells}</div>'
        '<script type="module">'
        'import m from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";'
        'm.initialize({startOnLoad:true});m.run();</script>'
    )


def render(
    any_id: str,
    *,
    server: str = DEFAULT_SERVER,
    direction: str = "TD",
    show_agent: bool = False,
    title: Optional[str] = None,
    html: bool = False,
):
    """Fetch a run and render its DAG as mermaid in the current cell.

    JupyterLab 4 renders ```mermaid fences natively, so the default needs no
    network. Pass html=True for front-ends that do not (loads mermaid from CDN).
    """
    data = fetch_run(any_id, server)
    chart = to_mermaid(data, direction=direction, show_agent=show_agent)
    s = stats(data)
    head = title or f"run {data.get('run_id', any_id)}"
    caption = (
        f"**{head}** — {s['executions']} executions · "
        f"depth {s['max_depth']} · max fan-out {s['max_fanout']} · {s['agents']} agent(s)"
    )
    if html:
        return _html([(caption, chart)])
    from IPython.display import Markdown

    return Markdown(f"{caption}\n\n```mermaid\n{chart}\n```")


def render_two(
    run_a: str,
    run_b: str,
    *,
    server: str = DEFAULT_SERVER,
    labels: Tuple[str, str] = ("run A", "run B"),
    direction: str = "TD",
    html: bool = False,
):
    """Two runs side by side -- the chapter 04 vs chapter 06 money shot.

    Both graphs go into ONE mermaid chart as two disconnected subgraphs, so
    mermaid lays them out horizontally and the native renderer still works.
    """
    a, b = fetch_run(run_a, server), fetch_run(run_b, server)
    sa, sb = stats(a), stats(b)

    def block(data, prefix, label, s):
        body = to_mermaid(data, _prefix=prefix, _bare=True)
        title = f"{_safe(label)} — {s['executions']} exec · depth {s['max_depth']} · fan-out {s['max_fanout']}"
        return f'  subgraph {prefix}g["{title}"]\n  direction {direction}\n{body}\n  end'

    if html:
        return _html(
            [
                (f"{labels[0]} — {sa['executions']} exec · depth {sa['max_depth']}",
                 to_mermaid(a, direction=direction)),
                (f"{labels[1]} — {sb['executions']} exec · depth {sb['max_depth']}",
                 to_mermaid(b, direction=direction)),
            ]
        )

    chart = "\n".join(
        [
            "flowchart LR",
            block(a, "a", labels[0], sa),
            block(b, "b", labels[1], sb),
            _CLASSDEFS.strip("\n"),
        ]
    )
    return _md(chart)


def mermaid(any_id: str, *, server: str = DEFAULT_SERVER, **kw) -> str:
    """Escape hatch: return the raw mermaid source as a string."""
    return to_mermaid(fetch_run(any_id, server), **kw)


# ------------------------------------------------------------- diagnostics


def nodes(server: str = DEFAULT_SERVER) -> List[Dict[str, Any]]:
    """Registered agents. This -- not `af ls` -- is the way to check registration.

    `af ls` truncates to 20 rows sorted by last_run_at, so a freshly registered
    node that has never run is invisible and looks like a failure.
    """
    with httpx.Client(base_url=server, headers=_headers(), timeout=15) as c:
        r = c.get("/api/v1/discovery/capabilities")
        r.raise_for_status()
        return r.json().get("capabilities", [])


def node_alive(agent_id: str, server: str = DEFAULT_SERVER) -> bool:
    """Is the node's OWN http server actually answering?

    Registrations persist after a node process dies, so a dead node still shows
    up in capabilities with a healthy-looking status. Only its own /health tells
    the truth. Always check this before dispatching, or the call 504s.
    """
    for c in nodes(server):
        if c.get("agent_id") == agent_id:
            base = c.get("base_url")
            if not base:
                return False
            try:
                return httpx.get(f"{base}/health", timeout=3).status_code == 200
            except Exception:
                return False
    return False


OWN_NODE = "blast-radius"


def print_nodes(server: str = DEFAULT_SERVER, only: str | None = OWN_NODE) -> None:
    """List registered agents. Defaults to this repo's own node.

    A shared control plane holds whatever else its owner is running, and those
    names would otherwise be baked into this repo's committed notebook outputs.
    Pass `only=None` to see everything on the control plane.
    """
    try:
        caps = nodes(server)
    except Exception as e:  # noqa: BLE001
        print(f"   (capabilities probe failed: {e})")
        return
    if only:
        others = [c for c in caps if c.get("agent_id") != only]
        caps = [c for c in caps if c.get("agent_id") == only]
        if others:
            print(f"   ({len(others)} unrelated agent(s) on this control plane, not shown)")
    if not caps:
        print("   none registered")
        return
    print(f"   {len(caps)} agent(s) registered:")
    for c in caps[:10]:
        print(
            f"     - {c.get('agent_id')} "
            f"[{c.get('health_status','?')}] "
            f"{len(c.get('reasoners') or [])} reasoner(s) @ {c.get('base_url','?')}"
        )
    print("   NOTE: registrations outlive the process. health_status can lie;")
    print("         dag.node_alive(<agent_id>) pings the node itself.")


if __name__ == "__main__":
    print_nodes()
