"""Synthesise run traces for all 7 rungs so the meter has something to measure.

These are HAND-TUNED, not sampled from real agents: each rung gets a stability
profile that encodes what we claim happens at that altitude. The point of the
fixtures is to prove the metrics can see the story, not to prove the story.

Task under test: a code auditor looking for planted security defects.
"""
from __future__ import annotations

import json
import random
import zlib
from pathlib import Path

HERE = Path(__file__).parent

DEFECTS = {
    "svc-auth": [
        ("auth/session.py:42", "session token is never expired on logout", "critical"),
        ("auth/login.py:88", "password compared with == allowing timing attack", "high"),
        ("auth/reset.py:23", "reset link reuses a predictable counter", "high"),
        ("auth/jwt.py:17", "jwt signature verification is skipped when alg is none", "critical"),
        ("auth/middleware.py:60", "admin route lacks a role check", "high"),
        ("auth/models.py:12", "password hash uses md5", "medium"),
        ("auth/config.py:5", "secret key is hardcoded in the repo", "critical"),
        ("auth/audit.py:31", "failed logins are not logged", "low"),
    ],
    "svc-billing": [
        ("billing/charge.py:55", "amount is parsed as float losing cents", "high"),
        ("billing/refund.py:19", "refund can exceed the original charge", "critical"),
        ("billing/webhook.py:44", "stripe webhook signature is not verified", "critical"),
        ("billing/invoice.py:71", "tax rate is read from user supplied input", "high"),
        ("billing/retry.py:30", "retry loop has no maximum and can bill twice", "high"),
        ("billing/export.py:9", "csv export interpolates user text enabling injection", "medium"),
        ("billing/cache.py:26", "price cache is never invalidated", "low"),
    ],
    "svc-ingest": [
        ("ingest/upload.py:33", "uploaded file path is joined without sanitising", "critical"),
        ("ingest/parse.py:64", "yaml is loaded with the unsafe loader", "critical"),
        ("ingest/queue.py:21", "queue consumer swallows every exception", "medium"),
        ("ingest/schema.py:48", "schema validation is skipped for large payloads", "high"),
        ("ingest/worker.py:15", "worker runs as root inside the container", "high"),
        ("ingest/dedupe.py:7", "dedupe key ignores the tenant id", "high"),
    ],
}

# False positives. A rung only draws from the first `fp_pool` of these: a fixed
# graph invents the same handful of non-issues every run, an improvised nest of
# agents invents fresh ones each time -- which is exactly what churns the set.
NOISE = [
    ("core/util.py:90", "function could be simplified with a comprehension", "low"),
    ("style/format.py:3", "line is longer than 100 characters", "low"),
    ("db/pool.py:66", "connection pool size is not configurable", "low"),
    ("tests/test_util.py:12", "test has no assertion", "low"),
    ("docs/readme.md:1", "readme is out of date", "low"),
    ("core/retry.py:44", "possible race condition in the shared counter", "medium"),
    ("api/routes.py:120", "endpoint is missing rate limiting", "medium"),
    ("api/serial.py:8", "response serialiser leaks internal ids", "medium"),
    ("core/log.py:52", "logger writes to stdout without a level", "low"),
    ("core/time.py:19", "naive datetime used without a timezone", "medium"),
    ("db/migrate.py:77", "migration is not reversible", "medium"),
    ("db/index.py:14", "query on an unindexed column", "low"),
    ("api/cors.py:6", "cors policy allows any origin", "high"),
    ("core/env.py:22", "environment variable read without a default", "low"),
    ("worker/pool.py:38", "thread pool size is hardcoded", "low"),
    ("api/health.py:4", "health check does not test the database", "low"),
    ("core/json.py:31", "json decode errors are not handled", "medium"),
    ("db/tx.py:59", "transaction is not rolled back on error", "high"),
    ("api/paginate.py:27", "pagination limit is unbounded", "medium"),
    ("core/hash.py:11", "hash function is not stable across versions", "low"),
    ("worker/sched.py:70", "scheduler drifts under load", "low"),
    ("api/auth_hdr.py:16", "auth header parsed case sensitively", "medium"),
    ("core/copy.py:45", "shallow copy where a deep copy is meant", "medium"),
    ("db/seed.py:2", "seed data ships to production", "medium"),
]

PARAPHRASE = [
    "{c}", "{c}", "possible issue: {c}", "{c} (unverified)",
    "the code {c}", "I think {c}", "{c} — should be fixed",
    "security concern where {c}", "{c}, which is unsafe",
]

# rung -> stability profile.
#   recall       target mean recall
#   churn        share of the recalled defects that flicker run to run
#   fp           mean number of false positives
#   fp_jitter    how much the false-positive count itself moves
#   fp_pool      how many DIFFERENT non-issues this rung is capable of inventing
#   proc         which DAG generator to use
#   cost, secs, touch, esc
PROFILE = {
    "r1": dict(recall=0.34, churn=0.10, fp=0.7, fp_jitter=0.35, fp_pool=4, proc="oneshot",
               cost=0.05, secs=14, touch=1.0, esc=0.0),
    "r2": dict(recall=0.50, churn=0.62, fp=2.0, fp_jitter=1.3, fp_pool=9, proc="loop",
               cost=0.19, secs=48, touch=2.0, esc=0.3),
    "r3": dict(recall=0.61, churn=1.00, fp=5.0, fp_jitter=2.8, fp_pool=24, proc="nested",
               cost=0.72, secs=141, touch=3.0, esc=1.4),
    "r4": dict(recall=0.68, churn=0.16, fp=1.0, fp_jitter=0.5, fp_pool=4, proc="fixed",
               cost=0.31, secs=61, touch=1.0, esc=0.1),
    "r5": dict(recall=0.79, churn=0.12, fp=1.1, fp_jitter=0.5, fp_pool=4, proc="written",
               cost=0.44, secs=77, touch=1.0, esc=0.2),
    "r6": dict(recall=0.89, churn=0.09, fp=0.9, fp_jitter=0.4, fp_pool=3, proc="jit",
               cost=0.63, secs=96, touch=0.4, esc=0.4),
    "r7": dict(recall=0.92, churn=0.06, fp=0.8, fp_jitter=0.4, fp_pool=3, proc="jit_deep",
               cost=0.81, secs=118, touch=0.0, esc=0.6),
}


N_RUNS = 6


def make_dag(kind: str, rng: random.Random, n_found: int) -> dict:
    """Each rung executes a differently-shaped process. Only some are reproducible."""
    if kind == "oneshot":
        chain = ["audit"]
    elif kind == "loop":                       # loop count drifts run to run
        chain = ["plan"] + ["scan", "critique"] * rng.randint(2, 4) + ["report"]
    elif kind == "nested":                     # improvised subagents: shape is a coin flip
        chain = ["dispatch"]
        for _ in range(rng.randint(2, 5)):
            chain.append(rng.choice(["subagent_scan", "subagent_review", "subagent_fix",
                                     "subagent_research", "subagent_replan"]))
            if rng.random() < 0.5:
                chain.append(rng.choice(["nested_scan", "nested_verify", "nested_expand"]))
        chain.append("merge")
    elif kind == "fixed":                      # hand-written: identical every time
        chain = ["load", "scan_auth", "scan_input", "scan_crypto", "rank", "report"]
    elif kind == "written":                    # AI wrote the graph; rarely rewrites it
        chain = ["load", "scan_auth", "scan_input", "scan_crypto", "scan_deps", "rank", "report"]
        if rng.random() < 0.2:
            chain.insert(5, "scan_config")
    elif kind in ("jit", "jit_deep"):          # graph is grown from what it finds
        chain = ["load", "triage"]
        for _ in range(max(2, n_found // 2)):
            chain.append(rng.choice(["expand_auth", "expand_input", "expand_crypto",
                                     "expand_config", "expand_deps"]))
        chain += ["verify"] * rng.randint(1, 3)
        if kind == "jit_deep":
            chain += ["self_check", "retry"] * rng.randint(0, 2)
        chain.append("report")
    else:
        raise ValueError(kind)
    nodes = [{"id": f"n{i}", "label": lab} for i, lab in enumerate(chain)]
    edges = [[f"n{i}", f"n{i+1}"] for i in range(len(chain) - 1)]
    return {"nodes": nodes, "edges": edges}


def jitter_location(loc: str, rng: random.Random) -> str:
    """Real reports point a few lines off. The matcher must tolerate it."""
    path, _, line = loc.rpartition(":")
    return f"{path}:{max(1, int(line) + rng.randint(-3, 3))}"


def build():
    runs, ground_truth = [], {}
    for inp, defects in DEFECTS.items():
        ground_truth[inp] = [{"location": l, "claim": c, "severity": s}
                             for l, c, s in defects]

    for rung, p in PROFILE.items():
        for inp, defects in DEFECTS.items():
            n = len(defects)
            n_recalled = round(n * p["recall"])
            n_flaky = round(n_recalled * p["churn"])
            n_stable = n_recalled - n_flaky
            # stable core first (easy defects), flaky pool drawn from the rest
            stable = defects[:n_stable]
            pool = defects[n_stable:]
            for k in range(N_RUNS):
                # crc32, not hash(): Python randomises str hashing per process and
                # these fixtures must be byte-identical on every machine.
                rng = random.Random(zlib.crc32(f"{rung}/{inp}/{k}".encode()))
                picked = list(stable)
                # flaky ones: pick n_flaky at random each run -> set churns
                if n_flaky:
                    picked += rng.sample(pool, min(n_flaky, len(pool)))
                findings = []
                for i, (loc, claim, sev) in enumerate(picked):
                    findings.append({
                        "id": f"f{i}",
                        "location": jitter_location(loc, rng),
                        "claim": rng.choice(PARAPHRASE).format(c=claim),
                        "severity": sev if rng.random() > p["churn"] * 0.35
                                    else rng.choice(["low", "medium", "high", "critical"]),
                    })
                n_fp = max(0, round(rng.gauss(p["fp"], p["fp_jitter"])))
                for j, (loc, claim, sev) in enumerate(rng.sample(NOISE[:p["fp_pool"]], min(n_fp, p["fp_pool"]))):
                    findings.append({"id": f"n{j}", "location": loc,
                                     "claim": claim, "severity": sev})
                rng.shuffle(findings)
                esc = ["ambiguous scope", "tool failure", "needs human call"]
                n_esc = min(3, max(0, round(rng.gauss(p["esc"], 0.5))))
                runs.append({
                    "rung": rung,
                    "input_id": inp,
                    "run_id": f"{rung}/{inp}/{k:03d}",
                    "findings": findings,
                    "cost_usd": round(p["cost"] * rng.uniform(0.8, 1.25), 4),
                    "tokens": int(p["cost"] * 42000 * rng.uniform(0.8, 1.25)),
                    "wall_time_s": round(p["secs"] * rng.uniform(0.75, 1.3), 1),
                    "human_touchpoints": max(0, round(rng.gauss(p["touch"], 0.35))),
                    "escalations": rng.sample(esc, n_esc),
                    "dag": make_dag(p["proc"], rng, len(findings)),
                })

    (HERE / "runs.json").write_text(json.dumps(runs, indent=1))
    (HERE / "ground_truth.json").write_text(json.dumps(ground_truth, indent=1))
    print(f"{len(runs)} runs, {len(ground_truth)} inputs, "
          f"{sum(len(v) for v in ground_truth.values())} planted defects")


if __name__ == "__main__":
    build()
