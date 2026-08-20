# Harness Orchestration

A harness is one agent loop with tools. **Harness orchestration** is what happens when
that loop stops being the whole program and becomes the atomic unit you program *with* —
composed, conditioned, and eventually written at runtime by the system itself, the way
functions compose into software.

The question this repo keeps asking: **as you hand over higher-level intent, how far does
one instruction reach?** That reach is the *blast radius*, and every chapter measures it.

Material accompanying the AlphaSignal talk on harness orchestration. Built on
[AgentField](https://agentfield.ai).

## Quickstart

```bash
make setup                   # venv pinned to Python 3.13 + install
cp .env.example .env         # add your OPENROUTER_API_KEY
make demo                    # control plane + node + JupyterLab
```

Nothing to install to read it — every notebook is committed with its outputs.

> [!IMPORTANT]
> **Python 3.13 only**, and `AI_MODEL` needs the `openrouter/` prefix. Both fail in
> confusing ways otherwise — see [docs/gotchas.md](docs/gotchas.md).

## By the end

You'll be able to build an agent system that decides its own shape at runtime — and
measure whether that was a good idea. Concretely: write a typed reasoner, compose
reasoners into a graph, have a reasoner *generate* the next graph, and run the whole
thing headless with a human approval gate.

## The chapters

Each adds one rung of autonomy and one AgentField primitive. Every notebook opens with
what you'll learn and closes with what you learned.

| | Notebook | What you learn |
|---|---|---|
| 00 | [bootstrap](notebooks/00_bootstrap.ipynb) | The notebook is the cockpit; the control plane is the runtime |
| 01 | one-shot | `app.ai(schema=…)` — an LLM call with a contract, and a `confident` flag |
| 02 | loop | `@app.reasoner()` — a goal plus a judge is already an agent |
| 03 | nested | `app.call()` — reasoners are APIs, and why three runs give three answers |
| 04 | graph | `AgentRouter` + `asyncio.gather` — write the process down, get the same DAG every run |
| 05 | graph-gen | Meta-prompting — a reasoner writes its child's prompt |
| 06 | JIT | Runtime fan-out, recursion, caps — a different graph for every incident |
| 07 | headless | `@on_event`, approvals, `af install` — it runs with no notebook attached |
| 08 | [the meter](notebooks/08_meter.ipynb) | How blast radius is measured, and what the numbers say |

The hinge is 04 → 06. Chapter 04's graph is hand-wired and identical every run;
chapter 06 decides its own shape at runtime. `lib/dag.py` renders both side by side.

**Domain:** incident triage — given a page, find the root cause.
[12 incidents](incidents/) with planted causes, a 26-lens
[taxonomy](incidents/lenses.md), and ground truth whose evidence citations are literal
substrings, so a finding can be proved rather than believed. Chosen because the warranted
lenses genuinely differ per incident — 13 of the 26 appear in exactly one — which gives
chapter 06 something real to decide. Bring your own incident:
[bring_your_own.md](incidents/bring_your_own.md).

## Layout

```
notebooks/    the chapters, committed WITH outputs
node/         main.py — the agent the notebooks drive
incidents/    12 incidents, ground truth, lens taxonomy, loader
meter/        blast-radius measurement + self-checks
lib/dag.py    fetch a run, render it as mermaid
traces/       self-contained HTML run traces (make traces)
docs/         gotchas, and a demonstrated approvals + triggers reference
```

`make check` verifies the environment, the control plane, and that every notebook still
carries its outputs. `make notebooks` re-executes them.

## License

<!-- TODO -->
