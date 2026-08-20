# Bring your own incident

The corpus in this directory exists so the seven rungs are comparable. It is not the point.
The point is pointing this at *your* last bad night. This guide gets you there in about ten
minutes with no integration work — no Datadog API key, no Loki, no Grafana, no OpenTelemetry
collector. If you can paste, you can run it.

---

## Day one: the two-file incident

The minimum viable incident is **a directory with two files**.

```
incidents/
  byo-001/
    README.md     <- what you saw, in your own words, no answer
    logs.txt      <- whatever text you have
```

`load_incident("byo-001")` works immediately. Missing artifacts are reported to the model as
explicitly absent rather than silently skipped, which matters: a reasoner that does not know
`metrics.json` is missing will invent conclusions about metrics.

```python
from loader import load_incident, to_prompt
inc = load_incident("byo-001")
print(inc["missing"])            # ['alert', 'deploys', 'metrics', 'topology']
print(to_prompt(inc, token_budget=8000))
```

**`logs.txt` can be almost anything.** In descending order of how much you already have:

- a real log tail from `kubectl logs`, `journalctl`, a CloudWatch export, a Kibana copy-paste
- the Slack thread from the incident channel, pasted verbatim, timestamps and all
- the postmortem document
- the PagerDuty timeline plus three screenshots you describe in one line each

A Slack thread is a genuinely good input. It contains a timeline, the hypotheses people held,
the moment someone said "wait, when did that deploy?", and the eventual answer — which is
exactly the material a reasoner needs and exactly the material a monitoring integration would
not give you.

**`README.md` has one rule: no spoilers.** Write what the responder knew at minute zero, not
what you know now. If your README says "the cache namespace changed", every rung scores 100%
and you have learned nothing about any of them. Write the alert text, the time, what the graphs
looked like, and what people initially believed. Delete the answer. Keep the answer somewhere
else — see scoring, below.

---

## Redaction

You are going to paste this into a model. Before you do:

- Replace customer identifiers with synthetic ones. `sed -E 's/usr_[0-9]+/usr_XXXX/g'` gets
  most of it; check for emails, order ids, phone numbers, and internal hostnames if those are
  sensitive to you.
- Strip anything that looks like a token, key, or password. Logs are full of them.
- Keep timestamps exactly as they are. Timing is most of the signal; shifting or rounding
  timestamps destroys the thing you are trying to test.
- Keep service names, or rename them consistently across every file. Inconsistent renaming
  breaks the topology-to-log correlation that several lenses depend on.

Rewriting a real incident into a shareable one takes about twenty minutes and is, separately,
a good exercise. Every synthetic incident in this corpus was built the same way.

---

## Day two: add whatever else you have

Add files as you get them. Each one is optional and each one unlocks lenses that are otherwise
guessing. Rough order of value per minute spent:

| file | what it unlocks | cheapest way to produce it |
|---|---|---|
| `deploys.json` | `change_correlation`, `rollback_viability`, `long_horizon_change` | five minutes of `git log --since` or your CD tool's history, hand-typed |
| `metrics.json` | `traffic_demand`, `saturation_compute`, `memory_lifecycle`, `capacity_autoscaling` | eyeball the graph, type in ten numbers per series |
| `topology.json` | `blast_scope`, `dependency_health`, `resource_contention` | draw it from memory; you already know it |
| `alert.json` | `alert_validity`, and it frames the whole run | copy the page text |

`deploys.json` is the highest-value file in the set and the easiest to fake honestly. Most
incidents are caused by a change, and without a change feed the system cannot do the single
most productive thing an on-call engineer does. Ten hand-typed entries beat a perfect
integration you never build.

### Shapes

Nothing validates these schemas strictly. Extra keys are passed through to the model verbatim;
missing keys are simply absent. Match the corpus files closely enough that a reader can follow.

```jsonc
// deploys.json  — the only one you should really bother getting right
{"lookback_hours": 24, "events": [
  {"id": "d-1", "at": "2026-08-14T01:52:00Z", "kind": "deploy|config|maintenance|schedule|vendor_status|policy",
   "service": "checkout-api", "version": "3.8.2", "actor": "someone",
   "change": "one line a human would write",
   "diff_summary": "optional: files and line counts, or the one line that changed"}
]}
```

```jsonc
// metrics.json  — ten points per series is plenty; shape beats precision
{"service": "checkout-api",
 "window": {"start": "2026-08-14T02:20:00Z", "step_seconds": 60, "points": 30},
 "units": {"latency_p99_ms": "ms"},
 "series": {"latency_p99_ms": [640, 700, 810, 2300, 14000, 29500],
            "rps": [310, 320, 330, 340, 352, 344]},
 "annotations": [{"t": "2026-08-14T02:32:00Z", "text": "deploy X"}],
 "note": "free text for anything that has no series"}
```

The `note` field and the `extra` blocks are not a cop-out. "Redis memory dropped to zero with
no evictions recorded" is a sentence, not a time series, and it is the sentence that solves
inc-006. Write the sentences down.

```jsonc
// topology.json
{"root": "checkout-api",
 "nodes": [{"id": "checkout-api", "kind": "service", "team": "payments"},
           {"id": "postgres-orders", "kind": "database"}],
 "edges": [{"from": "checkout-api", "to": "postgres-orders", "protocol": "jdbc", "pool_max_size": 20}],
 "notes": "the thing you would say out loud while drawing this on a whiteboard"}
```

```jsonc
// alert.json
{"monitor_name": "checkout-api :: p99 > 8s (5m)", "severity": "SEV2",
 "fired_at": "2026-08-14T02:44:00Z", "service": "checkout-api",
 "threshold": {"metric": "http.server.duration.p99", "comparator": ">", "value": 8000, "unit": "ms"},
 "observed_value": 21400}
```

---

## Scoring your own incidents

Without a ground-truth entry you can still compare rungs qualitatively, but you cannot measure
blast radius, which is the whole exercise. Adding one entry takes about ten minutes and is
worth it for even two or three of your own incidents.

Copy any entry from `ground_truth.json` and fill it in. The fields that actually drive scoring:

- `root_cause.summary` and `root_cause_must_include` — recall.
- `required_evidence[].match` — a **literal substring that exists in the named artifact**, so a
  scorer can verify a citation is real. If you cannot produce three, your incident is probably
  under-documented rather than hard.
- `red_herrings[]` — the things people actually chased on the night. Read your Slack thread and
  write down every wrong theory someone held for more than five minutes. This is the most
  valuable and most frequently skipped field, and it is free: the record already exists.
- `lenses_warranted` / `lenses_not_warranted` — pick from `lenses.md` section 3. Warranted means
  a competent responder would have opened it, whether or not it paid off. Not-warranted is the
  explicit false-positive set; anything in neither list is neutral, so you do not have to
  classify all twenty-six.
- `oneshot_prediction` — write your guess *before* you run anything. Being wrong about this is
  the most interesting result you can get, and it stops you retrofitting an explanation.

Then:

```python
gt = load_ground_truth("byo-001")
answer = run_rung_01(to_prompt(load_incident("byo-001")))
# recall:    do gt["root_cause_must_include"] terms appear in the answer?
# precision: how many gt["required_evidence"][i]["match"] does it cite?
# penalty:   does it assert any gt["red_herrings"][i] as a cause?
# lenses:    proposed vs gt["lenses_warranted"] / gt["lenses_not_warranted"]
```

---

## Choosing which incidents to bring

Three incidents beat thirty. Pick for contrast, since contrast is what the seven-rung
comparison measures:

1. **One that was obvious in hindsight** — a deploy, a stack trace, a four-minute diagnosis.
   It is your control. If a fancier rung does *worse* on it, you have learned something real
   about the cost of machinery.
2. **One where the team chased the wrong thing for twenty minutes.** Your red herrings are
   already documented in the channel. This is where rung differences show up.
3. **One nobody solved that night** — mitigated by restart, root-caused two days later or
   never. This is the honest test, and the one that tells you whether the ceiling is the
   architecture or the evidence.

If all three of your incidents want the same lenses, add a fourth from a different failure
class. A corpus without lens diversity cannot distinguish a dynamic graph from a static one,
which is the single most important property of this dataset — and the same warning applies to
yours.

---

## Common mistakes

- **Spoilers in the README.** The most common one, and it silently invalidates every score.
- **A log tail with only the interesting lines.** Real logs are 95% noise; the skill being
  measured is finding signal in noise. If you filter to the errors first, you have already done
  the hard part and are measuring something else.
- **Timestamps that do not line up across files.** If the deploy feed and the log are in
  different timezones, every timing conclusion is wrong. Normalise to UTC once, at the start.
- **Perfect metrics, no change feed.** Understandable, since metrics are exportable and deploy
  history usually is not. It is still backwards: type the deploys in by hand.
- **Waiting for the integration.** The next incident will happen before the integration ships.
  Paste the thread.
