# AgentField: Approvals, Triggers, Memory Scopes — demonstrated reference

Everything below was **executed live** on 2026-08-20 unless tagged UNVERIFIED. C/D/E/F omitted per scope update.

**Rig used for the demos** (reproduce it; two details are load-bearing):

```bash
# SDK
uv venv --python 3.13 && uv pip install agentfield==0.1.132

# An ISOLATED control plane, so the user's own CP is untouched.
# Both env vars matter — see the two gotchas in section A.
HOME=$PWD/cphome \
AGENTFIELD_WEBHOOK_ALLOWED_HOSTS=localhost,127.0.0.1 \
WBN_TOKEN=supersecret \
  af server --port 8077 --open=false --no-vc-execution
```

Agent node `wbn` on port 8140, four reasoners + one skill, `enable_did=False`, `vc_enabled=False`, no LLM calls (so nothing here depends on a model slug). Local CP needs **no API key** (`af auth status` → *"none — requests are sent unauthenticated"*); the approval endpoints accepted plain unauthenticated curl.

A bonus that unblocked section B: **`af server` prints its entire GIN route table at startup.** That is the authoritative route list — `af agent discover` is incomplete and omits every trigger route.

```bash
af server --port 8077 2>&1 | grep GIN-debug   # ground truth for routes
```

---

## A. Approvals / human-in-the-loop — FULL ROUND TRIP VERIFIED

### The reasoner

```python
from agentfield import Agent

app = Agent(
    node_id="wbn",
    agentfield_server="http://localhost:8077",
    callback_url="http://127.0.0.1:8140",   # 127.0.0.1, NOT localhost — see Gotcha 2
    enable_did=False,
    vc_enabled=False,
)

@app.reasoner()
async def gate(amount: float = 500.0) -> dict:
    """Pause mid-execution for a human decision."""
    res = await app.pause(
        approval_request_id=f"req-{int(amount)}",
        approval_request_url=f"http://localhost:9999/review/req-{int(amount)}",
        expires_in_hours=1,
        timeout=180.0,
    )
    return {"decision": res.decision, "approved": res.approved,
            "changes_requested": res.changes_requested, "feedback": res.feedback,
            "raw_response": res.raw_response}

app.serve(host="0.0.0.0", port=8140)
```

Signature (VERIFIED, `agent.py:4889`):

```python
async def pause(approval_request_id: str, approval_request_url: str = "",
                expires_in_hours: int = 72, timeout: Optional[float] = None,
                execution_id: Optional[str] = None) -> ApprovalResult
```

`app.serve()` auto-mounts `POST /webhooks/approval` on the agent (VERIFIED — curled it directly, returns 200). `pause()` raises `AgentFieldClientError("Agent is not serving...")` if `base_url` is unset.

### (1) What the caller blocks on, and for how long — VERIFIED

An `asyncio.Future`, **not** a poll loop. Sequence (`agent.py:4926-4995`, `agent_pause.py`):

1. Register an `asyncio.Future` in `_PauseManager` keyed by `approval_request_id` — **before** notifying the CP, so a fast callback cannot be lost.
2. `POST /api/v1/agents/{node}/executions/{id}/request-approval` with `{approval_request_id, callback_url, expires_in_hours, approval_request_url}`. CP callback URL is always `f"{self.base_url}/webhooks/approval"`.
3. Emit `app.note("Execution paused — waiting for approval <id>", tags=["approval","waiting"])`.
4. `await asyncio.wait_for(future, timeout=timeout or expires_in_hours*3600)`.

Duration: `timeout` if given, else `expires_in_hours * 3600` (default **72 h**). A `PauseClock` (`start_pause`/`end_pause`) tells the reasoner watchdog to **discount paused time from the active-time budget**, so a multi-hour human wait does not trip the reasoner timeout. Observed log line:

```
pause_cascade: registered pause_clock id=4471657664 for execution_id=exec_... reasoner=gate
```

### (2) What the human actually does — VERIFIED end to end

**There is no `af approve` CLI command.** `af execution` offers only `cancel | pause | resume | restart`, and none of them resolve an approval. The human-facing path is a raw REST call:

```bash
curl -X POST http://localhost:8077/api/v1/executions/$EXECUTION_ID/approval-response \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approved","response":{"feedback":"Reviewed by Santosh - ship it."}}'
```

Real response:

```json
{"decision":"approved","execution_id":"exec_20260820_115301_tpq85r2x",
 "new_status":"running","status":"processed"}
```

Five seconds later the reasoner returned:

```json
{"execution_id":"exec_20260820_115301_tpq85r2x","status":"succeeded","duration_ms":5107,
 "approval_request_id":"req-500","approval_status":"approved",
 "result":{"decision":"approved","approved":true,"changes_requested":false,
           "feedback":"","raw_response":null}}
```

No API key needed on a local CP. On a keyed CP send `X-API-Key` (`af auth login` stores it per-URL in `~/.agentfield/credentials.json`, mode 0600).

Decisions accepted: `approved`, `rejected`, `request_changes`, `expired` — all four VERIFIED to resume the execution. `POST /api/v1/webhooks/approval-response` is the HMAC-signed variant for an external review service (`X-Webhook-Signature` / `X-Hax-Signature` / `X-Hub-Signature-256`).

#### GOTCHA 1 — top-level `feedback` never reaches the reasoner. VERIFIED bug.

I sent `{"decision":"request_changes","feedback":"needs a second look"}`. The reasoner received `feedback: ""`.

Cause: the agent's handler reads `body.get("feedback","")` (`agent_server.py:325`), but the **CP does not forward that field** when it calls the agent's callback. Anything you put under `response` *does* survive, arriving as `ApprovalResult.raw_response`:

```bash
-d '{"decision":"rejected","response":{"feedback":"nested feedback"}}'
# reasoner sees: feedback='', raw_response={'feedback': 'nested feedback'}
```

**Teach `response`, read `result.raw_response`.** Do not demo `res.feedback` from the REST path — it will be empty on stage. (`res.feedback` *is* populated when the callback hits the agent directly with a top-level `feedback` key, e.g. from an external service posting to the agent — UNVERIFIED, not exercised.)

#### GOTCHA 2 — two setup traps that both produce silent-looking failures

**(a) `localhost` callbacks are rejected outright.** First attempt died in 3 ms:

```json
{"status":"failed","duration_ms":3,
 "error":"Approval request failed (400): {\"error\":\"invalid_callback_url\",
   \"message\":\"callback_url rejected: webhook url must not target private/internal host \\\"localhost\\\"\"}"}
```

SSRF guard. Fix: start the CP with `AGENTFIELD_WEBHOOK_ALLOWED_HOSTS=localhost,127.0.0.1` (env var VERIFIED working; the YAML key is `webhook_allowed_hosts`).

**(b) IPv6/IPv4 split-brain.** With the guard lifted, the approval was accepted, the CP marked it `approval_granted` — and the reasoner **never resumed**. CP log:

```
warn  approval callback delivery failed
      error: Post "http://localhost:8140/webhooks/approval": dial tcp [::1]:8140: connect: connection refused
```

The Go CP resolves `localhost` → `::1`; uvicorn on `0.0.0.0` is IPv4-only. **Set `callback_url="http://127.0.0.1:<port>"` explicitly.** With `localhost` you get a paused execution that says "approved" on the control plane and hangs forever in the agent — the worst possible failure to hit live on stage.

Also note `app.serve(port=8140)` **silently auto-bumps** to the next free port if 8140 is taken, while `callback_url` does not follow. Verify with `GET /api/v1/discovery/capabilities?agent_ids=<node>` and check `base_url` matches the port uvicorn actually bound. Do not use `af ls` — it truncates to 20 rows by `last_run_at`, so a never-run node is invisible.

### (3) The execution record, before and after — VERIFIED

**While paused** — note it is **`running` + `status_reason`, NOT status `waiting`.** The docs' status table is wrong here.

```json
{"execution_id":"exec_20260820_115149_1abiwplw","run_id":"run_20260820_115149_qvbgqzrg",
 "status":"running","status_reason":"waiting_for_approval",
 "started_at":"2026-08-20T15:51:49Z","webhook_registered":false,
 "approval_request_id":"req-500","approval_status":"pending",
 "approval_request_url":"http://localhost:9999/review/req-500"}
```

Three fields appear only while an approval is outstanding: `approval_request_id`, `approval_status`, `approval_request_url`.

**Dedicated status endpoint** `GET /api/v1/executions/{id}/approval-status` — note it carries `expires_at`, which the execution record does not:

```json
{"status":"pending","request_url":"http://localhost:9999/review/req-500",
 "requested_at":"2026-08-20T15:51:49Z","expires_at":"2026-08-20T16:51:49Z"}
```

Before any `pause()`: `{"error":"no_approval_request","message":"No approval request exists for this execution"}`.

**Immediately after approval** — `status_reason` flips, still `running` while the reasoner finishes:

```json
{"status":"running","status_reason":"approval_granted","approval_status":"approved"}
```

**After completion:** `status:"succeeded"`, `approval_status:"approved"`, `result` = your reasoner's return value.

### (4) Timeout / expiry — VERIFIED, and the docs are wrong

Reasoner with `timeout=12.0`, nobody approves:

```json
{"execution_id":"exec_20260820_115410_9o5a82li","status":"succeeded","duration_ms":12004,
 "result":{"decision":"expired","feedback":"timed out waiting for approval"},
 "approval_request_id":"fast-9","approval_status":"pending"}
```

- The execution **succeeds**. It is not cancelled and not failed. The docs sentence *"the approval is resolved as `expired` and the execution is cancelled"* is **false** on this build.
- Timeout is data, not an exception: `asyncio.TimeoutError` is caught and converted to `ApprovalResult(decision="expired", feedback="timed out waiting for approval")` (`agent.py:4983`). Note `feedback` **is** populated on this path — it is set locally by the SDK, not delivered over the wire.
- CP-side `approval_status` stays `pending` forever. **The agent gives up; the control plane does not.** If you resolve that stale request later, nothing is listening.
- `timeout` and `expires_in_hours` are independent: `timeout` is the agent's wait, `expires_in_hours` is the CP's `expires_at`. Leave `timeout=None` to make them agree.

### (5) Does it show in the DAG? YES — VERIFIED

`GET /api/v1/agentic/run/{run_id}` carries the approval, in two places. The `app.note()` from `pause()` appears **both** per-execution and at run level:

```json
{"ok":true,"data":{
  "agents":["wbn"],
  "executions":[{
    "execution_id":"exec_20260820_115149_1abiwplw","reasoner_id":"gate","node_id":"wbn",
    "input":{"amount":500},
    "status":"running","status_reason":"approval_granted",
    "notes":[{"message":"Execution paused — waiting for approval req-500",
              "tags":["approval","waiting"],
              "timestamp":"2026-08-20T11:51:49.72006-04:00"}],
    "started_at":"2026-08-20T15:51:49.711148Z","updated_at":"2026-08-20T15:52:01.052203Z"}],
  "notes":[{"message":"Execution paused — waiting for approval req-500",
            "tags":["approval","waiting"],"timestamp":"2026-08-20T11:51:49.72006-04:00"}],
  "run_id":"run_20260820_115149_qvbgqzrg",
  "summary":{"status_counts":{"running":1},"total_executions":1,"unique_agents":1}}}
```

For the mermaid cell: colour any node whose `status_reason == "waiting_for_approval"`, and render `notes[].tags` containing `"approval"` as the human gate. Both `status_reason` and per-execution `notes` are present **only** in the run-overview response — `GET /api/v1/executions/{id}` has `status_reason` but not `notes`.

### Types (VERIFIED — dataclasses, not Pydantic)

```python
@dataclass
class ApprovalResult:
    decision: str            # "approved"|"rejected"|"request_changes"|"expired"|"error"
    feedback: str = ""
    execution_id: str = ""
    approval_request_id: str = ""
    raw_response: Optional[Dict[str, Any]] = None
    @property
    def approved(self) -> bool: ...          # decision == "approved"
    @property
    def changes_requested(self) -> bool: ... # decision == "request_changes"

@dataclass
class ApprovalRequestResponse:  approval_request_id: str; approval_request_url: str

@dataclass
class ApprovalStatusResponse:
    status: str              # pending|approved|rejected|expired
    response: Optional[Dict[str, Any]] = None
    request_url: Optional[str] = None
    requested_at: Optional[str] = None
    responded_at: Optional[str] = None
```

Poll instead of block: `await app.client.get_approval_status(execution_id)`; `client.wait_for_approval(...)` polls with exponential backoff (`client.py:1967`).

**Crash recovery — UNVERIFIED (not exercised).** `await app.wait_for_resume(approval_request_id, execution_id=None, timeout=None)` reattaches to an already-pending approval without re-calling the CP, falling back to one `get_approval_status` poll on timeout (`agent.py:4998`).

### Suggested webinar beat

Start `gate` async → show `status_reason: "waiting_for_approval"` and `expires_at` → let it sit → `curl` the approval → show `succeeded` with `approved: true` and the note in the DAG. Total elapsed ~15 s. Use `response` for the feedback payload, `127.0.0.1` for the callback, and pre-set `AGENTFIELD_WEBHOOK_ALLOWED_HOSTS`.

---

## B. Triggers / headless execution — FIRED FOR REAL, BOTH KINDS

### THE ANSWER YOU NEEDED: the public webhook URL

```
POST http://<control-plane>/sources/<trigger_id>
```

**Root-level. No `/api/v1` prefix.** That is why it resists discovery: it is absent from `af agent discover`, absent from `llms-full.txt`, and returns 404 for every `/api/v1/...` shape. I found it in the CP's own startup route dump (`[GIN-debug] POST /sources/:trigger_id`) and then fired it.

The `trigger_id` is the row `id` from `GET /api/v1/triggers` — matching the SDK docstring *"trigger_id: … stable, == public URL slug."*

### Declaring triggers

```python
from agentfield import Agent, on_event, on_schedule, TriggerContext

@app.reasoner()                     # @app.reasoner MUST be outermost
@on_schedule("* * * * *", timezone="UTC")
async def tick(event: dict = None, trigger: TriggerContext = None) -> dict:
    return {"kind": "cron", "trigger_id": trigger.trigger_id,
            "event_type": trigger.event_type, "event": event}

@app.reasoner()
@on_event("generic_bearer", secret_env="WBN_TOKEN",
          config={"header": "Authorization", "scheme": "Bearer"})
async def hook(event: dict = None, trigger: TriggerContext = None) -> dict:
    return {"kind": "hook", "trigger_id": trigger.trigger_id,
            "idempotency_key": trigger.idempotency_key, "event": event}
```

Signatures (VERIFIED, `decorators.py`):

```python
def on_event(source: str, *, types: Optional[List[str]] = None,
             secret_env: Optional[str] = None,
             config: Optional[Dict[str, Any]] = None) -> Callable
def on_schedule(cron: str, *, timezone: str = "UTC") -> Callable
```

Equivalent canonical form: `@app.reasoner(triggers=[EventTrigger(...), ScheduleTrigger(...)])`. `@app.reasoner` also takes `accepts_webhook: bool | "warn" | None` (a UI guardrail flag). `EventTrigger.transform` must be **sync** (`TypeError` if a coroutine) and is not serialized — it runs client-side, replacing the reasoner's input with `transform(raw_event)`.

### Registration is automatic — VERIFIED

No provisioning call. Starting the node created both rows, stamped `managed_by: "code"` with the source line:

```json
{"id":"exec_20260820_115108_kcakpnu9","source_name":"generic_bearer",
 "config":{"header":"Authorization","scheme":"Bearer"},"secret_env_var":"WBN_TOKEN",
 "target_node_id":"wbn","target_reasoner":"hook","event_types":[],
 "managed_by":"code","enabled":true,
 "code_origin":".../demo/node.py:64",
 "last_registered_at":"2026-08-20T15:51:08Z","orphaned":false,
 "event_count_24h":1,"dispatch_success_24h":1,"dispatch_failed_24h":0,
 "dispatch_buckets_24h":[0,0, ...24 hourly buckets... ]}
{"id":"exec_20260820_115108_w1jjfcwc","source_name":"cron",
 "config":{"expression":"* * * * *","timezone":"UTC"},"secret_env_var":"",
 "target_node_id":"wbn","target_reasoner":"tick","managed_by":"code",
 "code_origin":".../demo/node.py:46", ...}
```

Rows created via API/UI get `managed_by: "ui"` instead. `orphaned` flags a code trigger whose reasoner no longer registers.

### `secret_env` — the trap. VERIFIED.

**`secret_env` names an environment variable on the CONTROL PLANE process, not on your agent.** With `WBN_TOKEN` exported only in the agent's shell, every dispatch attempt failed:

```json
{"error":"secret environment variable \"WBN_TOKEN\" is not set"}
```

Restarting the CP with `WBN_TOKEN=supersecret` fixed it. The agent never sees the secret — the CP verifies the signature/token and only then dispatches.

### Firing it — VERIFIED, with auth enforcement

```bash
TID=exec_20260820_115108_kcakpnu9

curl -X POST http://localhost:8077/sources/$TID \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer supersecret' \
  -d '{"order_id":"A-77","total":42.5}'
# -> 200 {"duplicates":0,"received":1,"status":"ok"}

# wrong token -> 401 {"error":"generic_bearer: token mismatch"}
# no token    -> 401 {"error":"generic_bearer: missing auth header"}
```

`duplicates` is the idempotency counter — replays land here.

**Notebook-friendly alternative, no secret needed in the request:**

```bash
curl -X POST http://localhost:8077/api/v1/triggers/$TID/test \
  -H 'Content-Type: application/json' -d '{"event":{"probe":true}}'
# -> {"event_id":"exec_20260820_115438_ka7783ya","status":"accepted"}
```

`/test` still requires the CP-side secret env var to *exist* (it 400s with the "not set" error otherwise) but does not require you to sign the request. Best demo path.

### What the reasoner actually received — VERIFIED, real payloads

**Webhook** (`event` = your body verbatim; `event_type`/`idempotency_key` empty because `generic_bearer` was configured without `event_type_header`/`idempotency_header`):

```json
{"input": {"order_id":"A-77","total":42.5},
 "result": {"kind":"hook","source":"generic_bearer",
            "trigger_id":"exec_20260820_115108_kcakpnu9",
            "event_id":"exec_20260820_115357_wy1tl6l7",
            "event_type":"", "idempotency_key":"",
            "received_at":"2026-08-20 15:53:57+00:00",
            "event":{"order_id":"A-77","total":42.5}}}
```

**Cron** — fired on its own, three times, unattended:

```json
{"input": {"expression":"* * * * *","fired_at":"2026-08-20T15:48:00Z","timezone":"UTC"},
 "result": {"kind":"cron","source":"cron","event_type":"tick",
            "trigger_id":"exec_20260820_114723_u03b9119",
            "event_id":"exec_20260820_114800_p81baj00",
            "idempotency_key":"* * * * *@2026-08-20T15:48Z",
            "received_at":"2026-08-20 15:48:00+00:00","vc_id":null,
            "event":{"expression":"* * * * *","fired_at":"2026-08-20T15:48:00Z","timezone":"UTC"}}}
```

Settled facts: cron `event_type` is **`tick`** (the `TriggerContext` docstring's `""` is wrong). The cron idempotency key is `<expression>@<scheduled-minute-UTC>`. `vc_id` is `null` with DID disabled.

**Trigger-fired runs get a `wf_` run_id prefix, not `run_`** (`wf_20260820_115357_e84yp060`). Direct calls get `run_`. Free signal for "this ran with no notebook attached" — and worth knowing before you write a regex.

Wire envelope the CP POSTs, which the SDK unwraps (`agent.py:2297`):

```json
{"event": { /* provider payload verbatim */ },
 "_meta": {"trigger_id":"...","source":"generic_bearer","event_type":"...",
           "event_id":"...","idempotency_key":"...","received_at":"...","vc_id":null}}
```

`event` becomes the reasoner's input; `_meta` becomes `TriggerContext`. Injected-by-name params are exactly `{"trigger","webhook","execution_context"}` (`agent.py:489`). `ctx.trigger` is `None` on a direct `app.call(...)`.

```python
@dataclass(frozen=True)
class TriggerContext:
    trigger_id: str; source: str; event_type: str; event_id: str
    idempotency_key: str; received_at: datetime; vc_id: Optional[str] = None
```

### Inspecting triggers

```bash
curl -s $S/api/v1/triggers                       # all rows + 24h counters
curl -s $S/api/v1/triggers/$TID/events           # per-event audit log
```

Real event row — a complete delivery receipt:

```json
{"events":[{"id":"exec_20260820_115357_wy1tl6l7","trigger_id":"exec_20260820_115108_kcakpnu9",
  "source_name":"generic_bearer","event_type":"",
  "raw_payload":{"order_id":"A-77","total":42.5},
  "normalized_payload":{"order_id":"A-77","total":42.5},
  "idempotency_key":"","status":"dispatched",
  "received_at":"2026-08-20T15:53:57.935652Z","processed_at":"2026-08-20T15:53:57.939101Z",
  "dispatched_workflow_id":"wf_20260820_115357_e84yp060"}]}
```

`dispatched_workflow_id` links straight to `GET /api/v1/agentic/run/<id>` — inbound event to DAG in one hop. That is your "prove it ran headless" cell.

### Trigger lifecycle — code-managed rows are sticky. VERIFIED.

A trigger created by `@on_event`/`@on_schedule` (`managed_by:"code"`) **cannot be deleted through the API while its reasoner still registers**:

```bash
curl -X DELETE $S/api/v1/triggers/$TID
# -> {"error":"code-managed trigger cannot be deleted via UI"}

curl -X POST $S/api/v1/triggers/$TID/convert-to-ui
# -> {"error":"trigger is not orphaned; only orphaned code-managed rows can be converted"}
```

The disable path that does work:

```bash
curl -X POST $S/api/v1/triggers/$TID/pause      # -> {"status":"paused"}
# row becomes: "enabled": false, "manual_override_enabled": true, "manual_override_at": "..."
curl -X POST $S/api/v1/triggers/$TID/resume     # undo
```

Consequences worth demoing, and worth knowing before you leave a laptop running:

- **A cron trigger keeps firing after its agent dies.** After I stopped node `wbn`, the `* * * * *` trigger went on ticking against a dead agent: `event_count_24h: 10, dispatch_success_24h: 4, dispatch_failed_24h: 6`. The failure counter is the tell.
- `pause` is the only clean off switch. `enabled:false` + `manual_override_enabled:true` means "a human overrode what the code declared", and it survives the code re-registering.
- The delete path is: stop the agent, let the row go `orphaned:true`, `convert-to-ui`, then `DELETE`. UNVERIFIED — my rows never flipped to `orphaned` within the observation window, so the orphan detector is presumably on a longer TTL.
- Removing the decorator from your source does **not** remove the row. Triggers outlive the code that declared them.

### Complete trigger route table — VERIFIED from the CP's own route dump

```
POST   /sources/:trigger_id                           <-- PUBLIC INGRESS
GET    /api/v1/sources                                 list source plugins + config JSON-Schema
GET    /api/v1/sources/:name
GET    /api/v1/triggers                                list + 24h counters
POST   /api/v1/triggers                                create (source_name, target_node_id, target_reasoner required)
GET    /api/v1/triggers/metrics
GET    /api/v1/triggers/:trigger_id
PUT    /api/v1/triggers/:trigger_id
DELETE /api/v1/triggers/:trigger_id                    -> {"status":"deleted"}
POST   /api/v1/triggers/:trigger_id/test               fire without signing
POST   /api/v1/triggers/:trigger_id/pause | /resume
POST   /api/v1/triggers/:trigger_id/convert-to-ui
GET    /api/v1/triggers/:trigger_id/secret-status      check the CP env var without revealing it
GET    /api/v1/triggers/:trigger_id/events
GET    /api/v1/triggers/:trigger_id/events/:event_id
GET    /api/v1/triggers/:trigger_id/events/stream      SSE
POST   /api/v1/triggers/:trigger_id/events/:event_id/replay
```

`GET /api/v1/triggers/:id/secret-status` is the pre-flight for the `secret_env` trap. UNVERIFIED (not called), but it is the obvious remedy for the failure above.

### Sources on this build — VERIFIED live

`cron` (kind `loop`, no secret), `databricks`, `generic_bearer`, `generic_hmac`, `github`, `linear`, `sentry` (all kind `http`, `secret_required: true`); docs add `stripe`, `slack`, `hubspot`, `calendly`, `pagerduty`. `GET /api/v1/sources` returns a JSON-Schema per source:

```json
{"name":"generic_hmac","kind":"http","secret_required":true,
 "config_schema":{"type":"object","properties":{
   "signature_header":{"type":"string","default":"X-Signature"},
   "signature_prefix":{"type":"string","default":""},
   "timestamp_header":{"type":"string","default":""},
   "tolerance_seconds":{"type":"integer","minimum":0,"default":300},
   "event_type_header":{"type":"string","default":""},
   "idempotency_header":{"type":"string","default":""}}}}
```

Cron syntax: `*`, integers, ranges `9-17`, lists `1,2,3`, steps `*/5`, `9-17/2`. **Not** supported: seconds, year field, named months/weekdays, `@hourly`.

Event-type matching (`agent.py:2340`): binding matches when `source` matches **and** (`types` is empty **or** `event_type` exact- or prefix-matches). A failing `transform` logs a warning and falls back to raw input rather than failing the execution.

---

## G. Memory scopes — brief

Four scopes, `memory.py:727`:

```python
_VALID_SCOPES = ("global", "session", "actor", "workflow")
```

| Scope | Lifetime | Use for | Py/TS | Go |
|---|---|---|---|---|
| Global | until explicitly deleted | shared config, knowledge bases | `global` | `global` |
| Session | until the session ends | conversation context | `session` | `session` |
| Actor | persists **across** sessions | per-user learned data | `actor` | **`user`** |
| Workflow | until the run completes | intermediate per-run state | `workflow` | `workflow` |

`memory.get("k")` with no scope searches **workflow → session → actor → global**, first hit wins; narrower shadows broader. An invalid scope raises with the valid list. Go's `Memory.Get()` defaults to **session** — use `GlobalScope()`, `SessionScope()`, `UserScope()`, `WorkflowScope()`.

```python
await app.memory.set("ticket:T-123.sentiment", {"mood": "angry"})   # auto-scoped
v = await app.memory.get("ticket:T-123.sentiment")                  # hierarchical
await app.memory.set("cfg", val, scope="global")                    # explicit
await app.memory.set_vector("doc:1", emb, metadata={"src": "contracts.pdf"})
hits = await app.memory.similarity_search(q, top_k=5)

@app.on_change("ticket:*:sentiment")
async def react(event): await app.call("notify.alert", key=event.key, change=event.data)
```

Change event: `{"key","scope","scope_id","action","data","previous_data"}`. Scoped accessors: `memory.session(id)`, `memory.actor(id)`, `memory.workflow(id)`, `memory.global_scope`. REST: `POST /api/v1/memory/{set,get,delete}`, `GET /api/v1/memory/list`, vector CRUD + `/vector/search`, and `GET /api/v1/memory/events/{sse,ws,history}`.

### Two naming traps

**`MemoryConfig` is unrelated to the four scopes.** It is auto-injection + retention, constructor-only (`agent.py:651`):

```python
MemoryConfig(auto_inject: List[str], memory_retention: str, cache_results: bool)
app = Agent(node_id="x", memory_config=MemoryConfig(
    auto_inject=["user_context"], memory_retention="persistent", cache_results=True))
```

It is **not** a `@app.reasoner()` kwarg — `ReasonerDefinition.memory_config` exists in `types.py:57` but is marked *"Optional for now, can be added later."*

**`memory_scope` on `app.ai` is a `List[str]`**, not a single scope: the SDK fetches those scopes and appends their contents to the system prompt.

```python
answer = await app.ai(system="...", user=q, memory_scope=["workflow", "session"])
```

The SDK docstring's own example says `['workflow','session','reasoner']` — but `'reasoner'` is **not** in `_VALID_SCOPES`. UNVERIFIED whether it is a real fifth injection scope or a stale docstring; teach `["workflow","session"]`.

---

## Corrections to the published docs, all VERIFIED

| Docs say | Reality on this build |
|---|---|
| Paused execution has status `waiting` | `status:"running"` + `status_reason:"waiting_for_approval"` |
| On expiry "the execution is cancelled" | Execution **succeeds** with `decision:"expired"`; CP-side `approval_status` stays `pending` |
| CP "provisions one public webhook URL per trigger and prints them" | Nothing is printed and no URL field is returned; the URL is `POST /sources/<trigger_id>`, derivable only from the CP route dump |
| `TriggerContext.event_type` is `""` for cron | It is `"tick"` |
| `af agent discover` is the endpoint inventory | Incomplete — omits all trigger routes and `/sources/:trigger_id`. Use `af server 2>&1 \| grep GIN-debug` |
| Docs pages show Python/curl examples | Code fences are **stripped** on the HITL, triggers, tracing, async, VC and webhook pages in both `llms-full.txt` and `/llm/docs/<slug>` |

## Remaining honest gaps

- **`ApprovalResult.feedback` from the REST path is always `""`** — CP does not forward top-level `feedback`. Use `response` → `raw_response`.
- `wait_for_resume()` crash recovery: not exercised.
- `/api/v1/webhooks/approval-response` (HMAC variant) and `AGENTFIELD_APPROVAL_WEBHOOK_SECRET`: route confirmed to exist, signing not exercised.
- `GET /api/v1/triggers/:id/secret-status`, `/events/:id/replay`, `/pause`, `/resume`, `PUT /triggers/:id`: routes confirmed in the route table, not called.
- `'reasoner'` as an `app.ai(memory_scope=...)` value: contradicted by `_VALID_SCOPES`, untested.
- Bare-dict async input (`{"amount":222}` instead of `{"input":{"amount":222}}`) **silently fell back to the parameter default** in my test. Always wrap in `{"input":{...}}`.
- All of this is CP **0.1.127** + SDK **0.1.132**. The CP is one minor behind; the DID/VC route group is not mounted on it at all.
