# Gotchas

Everything here cost someone an hour. Verified against `agentfield==0.1.132`,
litellm 1.96.2, control plane `v0.1.132`.

## Environment

- **Python 3.13 only.** `agentfield` requires `>=3.10,<3.14`. On a 3.14
  interpreter the install does not warn — it resolves to no candidate and fails.
  `make setup` pins it.
- **`AI_MODEL` needs the LiteLLM provider prefix**: `openrouter/deepseek/deepseek-v4-flash`.
  Dropping it does not fail loudly — litellm resolves the bare `deepseek/...`
  slug to provider `deepseek` and calls DeepSeek's **direct** API instead of
  OpenRouter. With a `DEEPSEEK_API_KEY` in the environment it even looks like it
  worked.
- **`deepseek/deepseek-v4-flash-latest` is not callable** — OpenRouter returns
  400. It is an alias row in `/models`, not a slug.
- **Reasoning tokens are spent before content.** A small `max_tokens` truncates
  structured output into a parse failure. Keep it `>= 2000`.
- **`app.harness()` skips all of this** — AForge ships with `af` and needs only
  `OPENROUTER_API_KEY`, no model slug.

## Control plane

- **The DAG lives at `GET /api/v1/agentic/run/{run_id}`.**
  `/api/v1/workflows/{id}` and `/api/v1/workflows/{id}/dag` are 404 and do not
  exist, whatever the docs say.
- **It is a flat `executions` list** with implicit `parent_execution_id` edges,
  not the nested `children` tree the docs describe.
- **`run_id` and `execution_id` are different ids.**
  `/api/v1/agentic/run/{id}` and `af wait` take a `run_id`;
  `/api/v1/executions/{id}` takes an `execution_id`. Crossing them polls
  forever. `lib/dag.py` accepts either.
- **The target separator flips.** Discovery reports `agent:reasoner`; the
  execute endpoint requires `agent.reasoner` and returns 400 on the colon.
- **Registration is not liveness.** Registrations outlive the process that made
  them, so a dead node still lists as healthy. `dag.node_alive()` pings the
  node's own `/health`. Don't verify with `af ls` either — it truncates to 20
  rows by `last_run_at`, hiding any node that has never run.
- **Cost and tokens are not in the control plane.** `CostTracker` is
  per-process and in-memory; surface `app.execution_cost` in a reasoner's return
  value if you want it recorded.

## Notebooks

- **Never drive an agent from the notebook's own event loop.** `await
  app.call(...)` against an app served in a notebook thread raises `Timeout
  context manager should be used inside a task`, silently falls back, and runs
  child reasoners **twice** — duplicate billed work, corrupted DAG, no error.
  Serve the node in a daemon thread and drive it over HTTP through the control
  plane.
- **Node default port is 8001**, not 8000. Use `app.serve(auto_port=True)` to
  avoid collisions with other nodes on the same control plane.
- Set `dev_mode=False` (its event dump is unusable in a cell) and
  `enable_did=False` (DID registration 404s here; noisy, non-fatal).

## Docker

- **`AGENT_CALLBACK_URL` must be the in-network DNS name**, `http://node:8001`.
  Registration is bidirectional: the node dials the control plane, and the
  control plane dials the node back to dispatch every call. Inside compose
  `localhost` is each container's own loopback, so a node that registers
  `http://localhost:8001` is telling the control plane to call itself.
  Executions then sit in `running` forever.

## Approvals and triggers

Full verified round-trips, with request/response bodies, are in
[approvals-triggers-memory.md](approvals-triggers-memory.md). The traps that will
cost you a live demo:

- **`localhost` callbacks are rejected** by an SSRF guard (`invalid_callback_url`).
  The control plane needs `AGENTFIELD_WEBHOOK_ALLOWED_HOSTS`.
- **Then it hangs anyway.** The Go control plane resolves `localhost` to `::1`;
  uvicorn is IPv4-only. Use `callback_url="http://127.0.0.1:<port>"`. The failure
  mode is the worst kind: the control plane reports the approval succeeded and the
  agent waits forever.
- **Top-level `feedback` never reaches the reasoner** — the control plane drops it.
  Send it nested under `response` and read `result.raw_response`.
- **A paused execution reports `status: "running"`** with
  `status_reason: "waiting_for_approval"`, not `status: "waiting"` as documented.
- **On timeout the execution SUCCEEDS** with `decision: "expired"`. The docs say it
  is cancelled; it is not.
- **The webhook ingress is `POST /sources/<trigger_id>`** — root level, no
  `/api/v1` prefix, undocumented and absent from `af agent discover`. `af server`
  prints its full route table at startup; that is the real endpoint inventory.
- **`secret_env` names an env var on the control plane**, not on your agent.
- **Trigger-fired runs use a `wf_` run_id prefix** instead of `run_`.
- **`POST /api/v1/triggers/<id>/test` fires without signing** — the cleanest path
  for a notebook demo.
- **A cron trigger keeps firing after its agent dies**, and code-managed triggers
  cannot be deleted through the API. `POST /triggers/<id>/pause` is the only clean
  off switch. Leave the machine quiet.
- **`MemoryConfig` is unrelated to the four memory scopes**, and
  `app.ai(memory_scope=...)` takes a **list**.
