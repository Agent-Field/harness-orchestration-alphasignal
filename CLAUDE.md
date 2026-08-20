# blast-radius — working agreement

Companion repo for an AgentField webinar talk. It is a **takeaway artifact**: there is
no live demo. The repo has to do the persuading on its own, to someone who arrived from
a slide link and may never run a single cell.

## The rule that matters most

**Notebooks are committed WITH their outputs. Always.**

Most people meet this repo by scrolling it on GitHub, and GitHub renders a notebook's
*saved* outputs. An unexecuted notebook is a blank page to that reader — the DAGs, the
tables, the plot, the whole argument, gone. Outputs are the artifact here, not build
residue.

So: whenever a notebook or anything a notebook renders changes, and before any commit
that touches one:

```bash
make notebooks      # execute every notebook in place, save outputs
make check-outputs  # guard: fails on unexecuted cells or committed error outputs
```

`make check` runs the guard too. Never strip outputs, never add `nbstripout`, and never
let `clean` touch them.

Corollary: a notebook is not finished when the code works — it is finished when its
committed outputs show what a reader needs to see. A committed cell that errors is a bug
in the artifact even if the code is "correct".

## How notebook prose reads

The reader is learning, not auditing. Every chapter follows the same shape:

1. Title, then one sentence on what this chapter is.
2. A `> **You'll learn**` block — three bullets, verb-first, concrete.
3. Sections: **one idea per markdown cell, one to three sentences.** If a cell needs a
   paragraph to set up the code below it, the idea is too big for one cell.
4. A closing `## What you learned` — three bullets mirroring the top — and a
   **Next:** line naming the following chapter and its hook.

Gotchas belong in `docs/gotchas.md`, not in the flow. Inline, a trap gets one clause
and a link. A reader who is here to learn should never have to wade through an
operational footnote to reach the next idea.

Teach in the order the reader needs it, not the order we discovered it.

## Environment, and the traps in it

- **Python 3.13 only.** `agentfield` declares `>=3.10,<3.14`; this machine's default
  `python3` is 3.14 and resolves to no installable version. Everything goes through
  `.venv`, which `make setup` pins.
- **`AI_MODEL` must carry the `openrouter/` prefix**: `openrouter/deepseek/deepseek-v4-flash`.
  The bare slug does not fail — it silently routes to DeepSeek's *direct* API via
  litellm. It appears to work on any machine that also has `DEEPSEEK_API_KEY` set, and
  fails with a confusing provider name on machines that don't.
- **`deepseek/deepseek-v4-flash-latest` is not callable** — OpenRouter 400s on it. It is
  an alias row in `/models`, not a slug.
- **V4 Flash is a reasoning model.** Reasoning tokens are spent before any content, so a
  small `max_tokens` truncates structured output into a parse failure. Keep `>= 2000`.
- **Node default port is 8001**, not 8000. Use `app.serve(port=..., auto_port=True)` to
  avoid collisions with other nodes on this control plane.
- Set `dev_mode=False` (its event dump is unusable in a notebook cell) and
  `enable_did=False` (DID registration 404s on this control plane; noisy, non-fatal).

## Control plane facts the docs get wrong

- The workflow DAG is **`GET /api/v1/agentic/run/<run_id>`**. `/api/v1/workflows/<id>`
  and `/api/v1/workflows/<id>/dag` are 404 and do not exist.
- The DAG is a **flat `executions` list** with implicit `parent_execution_id` edges —
  not the nested `children` tree the docs describe.
- **Two different ids.** `GET /api/v1/executions/<id>` takes an *execution_id*;
  `/api/v1/agentic/run/<id>` and `af wait` take a *run_id*. Mixing them polls forever.
- **The target separator flips.** Discovery reports `agent:reasoner`; the execute
  endpoint demands `agent.reasoner` and 400s on the colon.
- **`af ls` is not a registration check** — it truncates to 20 rows by `last_run_at`, so
  a freshly registered node is invisible. Use `GET /api/v1/discovery/capabilities`, and
  ping the node's own `/health`: registrations outlive the process that made them, so a
  dead node still reports healthy.
- **`await app.call(...)` from a notebook's event loop is broken** — it binds a timeout
  to the wrong loop, silently falls back, and executes children **twice**. Serve the node
  in a daemon thread and drive it over HTTP through the control plane. This is also the
  repo's pedagogy: the notebook is the cockpit, the control plane is the runtime.
- **Cost and tokens are not in the control plane.** `CostTracker` is per-process and
  in-memory; surface `app.execution_cost` in a reasoner's return value if you want it.

## Honesty rules

- Fixture-derived numbers are labelled as fixtures, in the notebook, where the reader
  sees them. They demonstrate that the instrument works; they are not evidence for the
  claim it measures.
- When the real runs disagree with the expected story, the repo shows the real runs.
- No `Co-Authored-By` trailers in commits.
