# blast-radius

> Companion repo for the AgentField webinar. Seven notebooks, seven rungs of
> autonomy, one primitive per rung — ending with a graph the code never drew.

## Quickstart

```bash
make setup                      # uv venv pinned to Python 3.13 + install
cp .env.example .env            # add your OPENROUTER_API_KEY
make up                         # control plane + agent node
make demo                       # JupyterLab -> start with 00_bootstrap.ipynb
```

> [!WARNING]
> **Python 3.13 only.** `agentfield==0.1.132` requires `>=3.10,<3.14`. On a 3.14
> interpreter the install does not warn — it resolves to no candidate and fails.
> `make setup` pins 3.13 for you; if you build a venv by hand, pin it yourself.
> Verify with cell 1 of `00_bootstrap.ipynb`.

## The climb

Each chapter adds exactly one primitive and one rung of autonomy. The question
the repo keeps asking: **when the model decides more, how much further does one
call reach?** That reach is the blast radius.

| # | Chapter | Rung | Primitive introduced | Who decides the shape |
|---|---|---|---|---|
| 01 | `01_one_shot` | one-shot | `app.ai(schema=...)` + `confident` flag | you |
| 02 | `02_loop` | loop | `@app.reasoner()`, `@app.skill()` | you |
| 03 | `03_nested` | nested | `app.call()`, depth >= 3 | you |
| 04 | `04_graph` | graph | `AgentRouter` + `asyncio.gather` fan-out | you |
| 05 | `05_graph_gen` | graph-gen | meta-prompting: a reasoner writes a child's prompt | you, then the model |
| 06 | `06_jit` | JIT | runtime fan-out width, recursion, caps | the model |
| 07 | `07_headless` | headless | `@on_event` / `EventTrigger`, approvals, `af install` | the model, unattended |

The hinge is 04 -> 06. Chapter 04's DAG is hand-wired, so it is identical every
run. Chapter 06 decides its own width and depth at runtime, so it is different
every run. `lib/dag.py` renders both side by side:

```python
import dag
dag.render_two(run_04, run_06, labels=("04 — static graph", "06 — JIT graph"))
```

<!-- TODO: blast-radius plot — executions/depth/fan-out per chapter, 01 -> 07. -->
![blast radius per rung](assets/blast-radius.png)

## Domain

Incident triage: given a page, find the root cause.

<!-- TODO: why this domain — it has a natural branching factor that the model,
     not the author, should be choosing. -->

## What's in here

```
notebooks/   00_bootstrap + the seven chapters (committed WITH outputs)
node/        main.py — the agent the notebooks drive, and its Dockerfile
lib/dag.py   fetch a run from the control plane, render it as mermaid
traces/      self-contained HTML run traces (make traces)
```

Notebook outputs are committed on purpose. This repo is a **takeaway**, not a
live demo: someone who never runs a cell should still be able to read the whole
story on GitHub. Nothing in `make` or `.gitignore` strips outputs.

## Make targets

| Target | Does |
|---|---|
| `make setup` | uv venv pinned to 3.13, install `requirements.txt`, seed `.env` |
| `make up` | start the control plane (if not already up) and the node |
| `make demo` | `setup` + `up` + JupyterLab |
| `make down` | stop what `make up` started |
| `make check` | python / SDK / control plane / `lib/dag.py` / registrations |
| `make traces RUNS="<run_id> ..."` | export self-contained HTML traces |
| `make clean` | remove the venv and run artifacts (never notebook outputs) |

## Docker

```bash
docker compose up --build
```

Two services: `control-plane` (`agentfield/control-plane:v0.1.132`) and `node`.

The one thing that bites everyone: **`AGENT_CALLBACK_URL` must be the in-network
DNS name**, `http://node:8001`. Registration is bidirectional — the node dials
the control plane, and the control plane dials the node back to dispatch every
call. Inside compose `localhost` is each container's own loopback, so a node
that registers `http://localhost:8001` is telling the control plane to call
itself. Executions then sit in `running` forever and never dispatch.

## Gotchas worth knowing

- **Model slug** — `AI_MODEL` needs the LiteLLM provider prefix:
  `openrouter/deepseek/deepseek-v4-flash`. The bare OpenRouter slug will not
  route, and `deepseek/deepseek-v4-flash-latest` is not a callable model id at
  all (OpenRouter returns 400).
- **Reasoning tokens** — DeepSeek V4 Flash spends reasoning tokens before
  emitting content, so a small `max_tokens` truncates structured output into a
  parse failure. Keep it >= 2000.
- **`run_id` vs `execution_id`** — different ids. `GET /api/v1/agentic/run/{id}`
  takes a `run_id`; `GET /api/v1/executions/{id}` takes an `execution_id`.
  Crossing them fails silently-ish and forever. `lib/dag.py` accepts either.
- **Execute target separator** — discovery reports `agent:reasoner`, but the
  execute endpoint requires `agent.reasoner`. The colon form returns HTTP 400.
- **Registration is not liveness** — registrations outlive the process that made
  them, so a dead node still lists as healthy. `dag.node_alive()` pings the
  node's own `/health`. Also: don't verify with `af ls`, which truncates to 20
  rows sorted by `last_run_at`, hiding any node that has never run.
- **Don't drive an agent from the notebook's own event loop** — `await
  app.call(...)` against an app served in a notebook thread raises `Timeout
  context manager should be used inside a task`, silently falls back, and runs
  child reasoners **twice**. Drive over HTTP through the control plane instead.

## The narrative

<!-- TODO: the argument the talk makes, in prose. -->
<!-- TODO: what "blast radius" means and why it is the right unit. -->
<!-- TODO: where this stops being a good idea — caps, approvals, and why 07
     exists at all. -->

## License

<!-- TODO -->
