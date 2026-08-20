# Investigative lenses

This file is three things at once. It is teaching material for the webinar. It is the source
the hand-written graph in chapter 04 is transcribed from. And it is the reference a dynamic
lens generator in chapter 06 is measured against: when the generator invents nodes for an
incident, the question is whether it invented these, and only these.

A **lens** is not a tool and not a data source. It is a standing question plus the discipline
of answering it: what it reads, what would confirm it, what would refute it, and when to put
it down. Two engineers looking at the same dashboard are running different lenses, and that,
not their tooling, is why one of them finds the cause in four minutes.

---

## 1. How on-call actually works

The mental model that makes the rest of this file legible.

**The first ninety seconds are not root-cause analysis.** They are triage: is this real, how
bad is it, who is hurt, does it need a page to someone else. A good engineer answers "should I
mitigate before I understand?" before answering "why?". Several incidents in this corpus have a
correct mitigation that does not require knowing the cause (inc-006: roll back; inc-001: turn
the flag off), and a system that insists on full diagnosis before acting is modelling on-call
badly.

**Four lenses run on every incident, unprompted.** Experienced responders do not choose these,
they arrive with them: *is the alert real*, *what is the blast scope*, *what is the timeline*,
*what changed*. In this corpus, `timeline` is warranted in 11 of 12 incidents and
`change_correlation` in 9. They are the floor, not the differentiator.

**The differentiating lens is chosen from the shape of the symptom, not from the name of the
service.** "Latency up, CPU flat" and "latency up, CPU pinned" are different investigations.
"Errors started at a round number on the clock" and "errors started four minutes after a
deploy" are different investigations. The routing table in section 4 encodes this.

**Depth is earned, not scheduled.** You do not open the retry-policy lens on every incident;
you open it when offered load rose and real demand did not. Cheap lenses run first and their
findings license the expensive ones. This is exactly the property a dynamic graph should
exhibit and a static graph cannot.

**Knowing when to stop is a skill.** The stop condition is not "I found something wrong" —
there is always something wrong. It is: *this mechanism explains the timing, the magnitude, and
the blast scope, and the alternatives do not*. Most bad root-cause analyses fail one of those
three, usually timing. In inc-004 the debug-logging change is genuinely a suspicious change; it
fails the timing test by five hours and the blast-scope test entirely.

**A cause you cannot act on is not a root cause yet.** "The database was overloaded" and "CPU
was saturated" are restatements of the alert. Push until the answer names something a person
did, decided, or failed to renew.

---

## 2. The four standing lenses

### alert_validity — *Is this real?*
Reads the monitor definition, its threshold, its firing history, and any recent change to the
monitor itself. Confirms with: the underlying signal moved, not just the monitor. Refutes with:
the threshold changed, the metric was re-tagged, a deploy renamed a series. Cheap, and it saves
whole nights. In this corpus it is never the answer, which is itself worth teaching: the corpus
is honest about the fact that the cheapest lens usually returns "yes, it's real, move on".

### blast_scope — *Who is affected and, more importantly, who is not?*
Reads per-pod, per-region, per-tenant, per-currency, per-endpoint, per-caller breakdowns. The
negative half is the powerful half. One pod of six failing (inc-011) means node-local. One
currency of five failing (inc-002) means input-dependent. One caller of three failing (inc-003)
means the edge, not the service. Three unrelated services failing together (inc-007) means
shared infrastructure. Scope is often a stronger localiser than any log line.

### timeline — *What is the true start, and does the candidate cause precede it?*
Reads first-bad timestamps against alert time against change times. Alerts fire late by design
(a 5m window means 5m of lag), so the alert time is never the incident time. Two traps this
lens exists to catch: a change that happened *after* the symptom started cannot have caused it
(inc-007's timeout bump), and a trigger that ended before the symptom did cannot be the whole
story (inc-010's node reboot).

### change_correlation — *What changed?*
Reads the deploy and config feed inside the alert window. The default and correct first
hypothesis: most incidents are caused by a human action. The failure modes are recency bias
(blaming the newest change because it is newest — inc-001) and diff-size bias (dismissing a
one-line change as safe — inc-006). Ask "does this diff touch the failing path?", not "is this
diff recent?".

---

## 3. The full catalogue

Each entry: the question, what it reads, what confirms, what refutes, and the false positive it
characteristically produces.

| id | question | reads | confirmed by | refuted by | classic false positive |
|---|---|---|---|---|---|
| `alert_validity` | Is the alert real? | monitor def, threshold history, monitor changes | raw signal moved | monitor or tagging changed | dismissing a real incident as a monitor bug |
| `blast_scope` | Who is affected, who is not? | per-dimension error/latency breakdowns | a clean split along one dimension | uniform degradation everywhere | reading an aggregate as if it were uniform |
| `timeline` | When did it truly start? | first-bad vs alert vs change times | candidate precedes symptom | candidate postdates symptom | using alert time as incident time |
| `change_correlation` | What changed in the window? | `deploys.json` inside the window | diff touches the failing path | change is on an unrelated path | blaming the most recent change |
| `long_horizon_change` | What changed days or weeks ago? | deploy feed beyond the window, slow metrics | a slow metric inflects at an old change | metric was already trending | never opening it at all |
| `rollback_viability` | Can we undo this safely? | diff, migration state, data written since | stateless, reversible change | schema migration, data written | rolling back a change that is not the cause |
| `config_drift` | Is running config what we think? | config events, effective config in logs | runtime value differs from intent | they agree | trusting the repo over the process |
| `dependency_health` | Are our downstreams healthy? | per-dependency latency/error series | one dependency diverges | all flat | blaming a dependency that is merely slow-and-always-was |
| `external_vendor` | Is a third party degraded? | vendor status, per-vendor latency, error bodies | vendor-specific divergence + status page | vendor flat | assuming vendor fault because the call is external |
| `saturation_compute` | Are we out of CPU, memory, threads? | utilisation vs limit, pool occupancy | resource at ceiling *and* demand explains it | resource at ceiling as a consequence | treating saturation as cause when it is symptom |
| `connection_pool` | Is a bounded pool exhausted? | pool active/idle/pending, acquisition wait | pool pinned at max with a wait queue | pool has idle capacity | raising the pool size |
| `queue_backpressure` | Is work arriving faster than it leaves? | lag, produce vs consume, DLQ rate | lag grows with consume rate flat | consume rate dropped | scaling consumers that are not the bottleneck |
| `cache_behavior` | Is the cache doing its job? | hit ratio, key count, memory, eviction, namespace | hit ratio collapse without demand change | hit ratio steady | assuming eviction when the keyspace moved |
| `database_health` | Is the database itself the problem? | query latency, plans, locks, vacuum, backends | query latency rises before app latency | query latency flat while app latency rises | naming the DB because the DB alert fired |
| `retry_amplification` | Are we creating our own load? | attempt histograms, retry config, first-attempt rate | total rate ≫ first-attempt rate | they track each other | adding capacity to absorb retries |
| `capacity_autoscaling` | Do we have the replicas we should? | replica count, HPA decisions, per-replica load | replicas fell or failed to rise | replica count tracked demand | "add capacity" without asking why capacity left |
| `resource_contention` | Is a neighbour stealing from us? | node-level utilisation, cgroup throttling, scheduling | node saturated, per-pod divergence | all pods equal, node has headroom | raising the victim's limit on a full node |
| `dns_service_discovery` | Can we even find the callee? | lookup latency, NXDOMAIN, resolver health | resolution fails before connection | lookups fast, connections fail | blaming the callee named in the error string |
| `network_path` | Is the path between us broken? | handshake errors, resets, per-hop attribution | failure at connect/TLS layer | failures are application-level | inferring "network" from any timeout |
| `credential_expiry` | Did something expire or rotate? | notAfter dates, rotation events, TLS alerts | expiry timestamp matches the cliff | credentials valid, failures elsewhere | blaming a rotation that predates the symptom |
| `security_abuse` | Is this hostile traffic? | source concentration, WAF events, failed auth rate | abuse volume changes when the symptom does | abuse is flat background | promoting ever-present background abuse to cause |
| `clock_time` | Is time itself wrong? | NTP offset, log ordering, boundary times | per-host offset, out-of-order logs | clocks agree | widening the leeway instead of fixing the clock |
| `data_contract` | Did the shape of the data change? | schema versions, deserialisation errors, DLQ payloads | writer/reader version mismatch | schema stable | blaming your own library upgrade |
| `memory_lifecycle` | Is allocation growing without bound? | RSS over days, GC, heap retainers, OOM kills | monotonic growth with flat workload | sawtooth around a stable floor | raising the memory limit |
| `traffic_demand` | Is demand actually different? | rate vs same hour yesterday, unique actors | today diverges from yesterday | today matches yesterday | calling a normal daily ramp a spike |
| `observability_gap` | What can we not see? | absent series, unsampled paths | the deciding question has no artifact | evidence exists and was not read | using it as an excuse to stop early |

---

## 4. Routing: symptom shape to lens set

This is the table chapter 04 hardcodes as a graph and chapter 06 should reconstruct on the fly.
It routes on the shape of the symptom, not on the service name.

| symptom shape | open first | open if the first pass points that way | almost never relevant |
|---|---|---|---|
| latency up, own CPU **flat or low** | `connection_pool`, `dependency_health`, `resource_contention` | `external_vendor`, `database_health` | `memory_lifecycle`, `data_contract` |
| latency up, own CPU **pinned** | `saturation_compute`, `traffic_demand`, `capacity_autoscaling` | `resource_contention`, `retry_amplification` | `credential_expiry`, `clock_time` |
| 5xx step change right after a deploy | `change_correlation`, `rollback_viability`, `blast_scope` | `config_drift` | `dns_service_discovery`, `clock_time`, `memory_lifecycle` |
| auth / 401 / 403 spike | `credential_expiry`, `security_abuse`, `clock_time`, `blast_scope` | `network_path`, `config_drift` | `cache_behavior`, `queue_backpressure` |
| errors start at a round clock boundary, no deploy | `credential_expiry`, `clock_time`, `timeline` | `config_drift` | `capacity_autoscaling`, `data_contract` |
| database CPU or IO saturated | `cache_behavior`, `traffic_demand`, `database_health`, `retry_amplification` | `change_correlation` | `dns_service_discovery`, `credential_expiry` |
| intermittent errors across **several** services | `dns_service_discovery`, `network_path`, `blast_scope` | `resource_contention`, `capacity_autoscaling` | `data_contract`, `memory_lifecycle` |
| restart loop / OOM kill | `memory_lifecycle`, `long_horizon_change`, `traffic_demand` | `change_correlation` | `dns_service_discovery`, `external_vendor` |
| queue lag growing, consumer alive | `data_contract`, `queue_backpressure`, `dependency_health` | `change_correlation` (including **other teams'** deploys) | `credential_expiry`, `clock_time` |
| brief blip that never recovered | `retry_amplification`, `timeline`, `traffic_demand` | `saturation_compute` | `data_contract`, `cache_behavior` |
| one dependency slow, others fine | `external_vendor`, `dependency_health`, `retry_amplification` | `network_path` | `cache_behavior`, `memory_lifecycle` |
| symptom differs per pod / per node | `resource_contention`, `clock_time`, `blast_scope` | `config_drift` | `external_vendor`, `data_contract` |

Read the last column as carefully as the first. A dynamic generator that grows a lens for every
plausible topic is not selecting; it is enumerating, and it will score badly on lens precision
even while it happens to find the cause.

---

## 5. Which lenses depend on which

Depth in the graph should come from findings, not from a fixed nesting. These are the edges
that matter, expressed as "if the first lens returns X, then the second is now worth opening".

- `blast_scope` finds **per-pod divergence** → open `resource_contention`, then `clock_time`.
- `blast_scope` finds **one caller of many affected** → open `network_path`, `credential_expiry`.
- `blast_scope` finds **many services affected together** → open `dns_service_discovery`.
- `saturation_compute` finds **at limit but node also at limit** → open `resource_contention`.
- `saturation_compute` finds **at limit with flat demand** → open `retry_amplification`.
- `traffic_demand` finds **demand unchanged** → open `retry_amplification`, `cache_behavior`, `capacity_autoscaling`.
- `database_health` finds **query latency flat** → close it, open `connection_pool` or `cache_behavior`.
- `change_correlation` finds **nothing in the window** → open `long_horizon_change`, `credential_expiry`, `clock_time`, `external_vendor`.
- `dependency_health` finds **one dependency diverging** → open `external_vendor`, `retry_amplification`.
- `queue_backpressure` finds **consume rate healthy, output collapsed** → open `data_contract`.
- `memory_lifecycle` finds **growth with flat workload** → open `long_horizon_change`.
- Any lens finds **a cause that explains timing but not scope** → do not stop; the scope
  mismatch is usually where the real cause is hiding.

---

## 6. Stop conditions

Stop when all four hold:

1. **Timing.** The mechanism started when the symptom started, not before, not after.
2. **Magnitude.** The mechanism is large enough. Twenty extra requests per second do not
   explain a 40x change (inc-006).
3. **Scope.** The mechanism affects exactly who is affected and nobody else.
4. **Counterfactual.** Undoing the mechanism would plausibly end the incident. If the fix that
   follows from your answer is "add capacity" and demand did not change, you are not done.

Stop *early*, deliberately, when a mitigation is available and safe. Write down that you
stopped early and why. That is a different thing from stopping because you ran out of ideas,
and a system that cannot tell those apart will report false confidence.

---

## 7. Using this file across the seven rungs

- **01 one-shot** — do not paste this file. The point of rung 01 is what a single call does
  with the artifacts alone.
- **02 loop** — the four standing lenses in section 2 make a reasonable termination checklist.
- **03 nested** — the dependency edges in section 5 are the sub-call structure.
- **04 hand-written graph** — section 4's routing table transcribed into fixed nodes. It will
  do well on incidents whose shape you anticipated and badly on the ones you did not; that is
  the lesson, so do not quietly widen it after seeing the scores.
- **05 AI-written graph** — give the model section 3 and the corpus, not section 4. See whether
  it derives the routing.
- **06 dynamic graph** — give it section 3 as vocabulary only. Score with
  `ground_truth.json:lenses_warranted` / `lenses_not_warranted`. The test is not "did it find
  the cause", it is "did it grow *different* nodes for inc-003 than for inc-011", two incidents
  that look identical from the alert (auth failures) and share only two of six lenses.
- **07 headless** — the stop conditions in section 6 are the only thing standing between an
  unattended system and a confident wrong answer. Make them explicit and logged.
