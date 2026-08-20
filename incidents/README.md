# The incident corpus

Twelve synthetic production incidents, each with the artifacts an on-call engineer would
actually have at 3am, plus machine-readable ground truth. This is the fixed input set that
makes the seven rungs of `blast-radius` comparable and scoreable.

```
incidents/
  inc-001/ .. inc-012/    12 incidents, six artifacts each
    README.md             what the on-call engineer sees. No spoilers.
    alert.json            what paged: monitor, threshold, severity, firing time
    logs.txt              370-520 lines of realistic log tail, signal buried in noise
    deploys.json          deploy and config history, lookback varies by incident
    metrics.json          time series around the window (+ long-horizon data where it matters)
    topology.json         the dependency graph relevant to the affected service
  ground_truth.json       root causes, required evidence, red herrings, warranted lenses
  lenses.md               the investigative lens taxonomy: teaching material and graph seed
  loader.py               dependency-free loader and prompt renderer
  bring_your_own.md       how to point this at your own incident with no integrations
  _build/                 the generator that produced the artifacts (deterministic, seeded)
```

## Reading order

1. `lenses.md` — what a lens is, how on-call actually works, and the routing table.
2. Any incident's `README.md`, then its artifacts, without looking at ground truth.
3. `ground_truth.json` for that incident, to see what you missed.
4. `bring_your_own.md` when you want to run this on your own last bad night.

## Using it

```python
from loader import list_incidents, load_incident, load_ground_truth, to_prompt

list_incidents()                                     # ['inc-001', ... 'inc-012']
inc = load_incident("inc-004")

to_prompt(inc)                                       # everything, capped at 12k tokens
to_prompt(inc, token_budget=180_000)                 # everything, uncapped in practice
to_prompt(inc, sections=["alert", "deploys"])        # what a change-correlation lens needs
to_prompt(inc, sections=["logs"], log_filter="problems", token_budget=2000)
to_prompt(inc, sections=["metrics"], metrics_style="full")

load_ground_truth("inc-004")["lenses_warranted"]
```

`python3 loader.py` runs a self-check over the whole corpus and prints token sizes per
incident. A full incident renders to roughly 16k-24k tokens.

Bring-your-own incidents live alongside as `byo-*` directories and may contain any subset of
the six artifacts; missing ones are declared to the model rather than silently dropped.

## Ground truth at a glance

`ground_truth.json` carries a `how_to_score` block and, per incident: `root_cause`,
`root_cause_must_include`, `contributing_factors`, `required_evidence` (each with a literal
substring that provably exists in the named artifact, so citations can be verified rather than
trusted), `red_herrings` with penalties, `lenses_warranted`, `lenses_not_warranted`,
`correct_remediation`, `wrong_remediations`, and a pre-registered `oneshot_prediction`.

Lenses in neither the warranted nor the not-warranted list are neutral. All twelve warranted
lens sets are distinct, and no two overlap by more than half — that diversity is what lets
chapter 06 demonstrate that a dynamic graph grows different nodes for different incidents.

**Do not paste `ground_truth.json` into any rung.** It is the answer key.

## Regenerating

```
cd _build && python3 build.py
```

Deterministic: each incident is seeded, so the artifacts are byte-identical across runs. Edit
the specs in `_build/specs_*.py` to change an incident; keep `ground_truth.json` in step, and
re-run the evidence validator (every `required_evidence[].match` must still be a real substring
of its artifact).
