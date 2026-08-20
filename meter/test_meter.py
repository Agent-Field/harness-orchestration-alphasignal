"""Sanity checks. Run: python3.13 test_meter.py"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from meter import blast_radius as br

ok = 0
def check(name, cond):
    global ok
    assert cond, "FAIL: " + name
    ok += 1
    print("  ok  ", name)

def run(rung="rX", inp="i", rid="x", findings=(), dag=None):
    return {"rung": rung, "input_id": inp, "run_id": rid, "findings": list(findings),
            "cost_usd": 1.0, "tokens": 1, "wall_time_s": 1.0, "human_touchpoints": 0,
            "escalations": [], "dag": dag or {"nodes": [], "edges": []}}

def f(loc, claim, sev="high"):
    return {"id": loc, "location": loc, "claim": claim, "severity": sev}

print("fuzzy matcher")
check("paraphrase matches", br.same_finding(
    f("a/b.py:10", "session token is never expired on logout"),
    f("a/b.py:12", "I think session token is never expired on logout")))
check("line tolerance", br.location_match("a/b.py:10", "a/b.py:15"))
check("line beyond tolerance rejected", not br.location_match("a/b.py:10", "a/b.py:99"))
check("different file rejected", not br.location_match("a/b.py:10", "c/d.py:10"))
check("unrelated claim rejected", not br.same_finding(
    f("a/b.py:10", "session token is never expired on logout"),
    f("a/b.py:10", "readme is out of date")))
check("jaccard identical == 1", br.finding_jaccard([f("a:1","x y z")], [f("a:1","x y z")]) == 1.0)
check("jaccard disjoint == 0", br.finding_jaccard([f("a:1","x y z")], [f("b:1","q r s")]) == 0.0)
check("no double matching", br._pair_up(
    [f("a:1","token never expires"), f("a:2","token never expires")],
    [f("a:1","token never expires")]) == 1)

print("outcome variance")
same = [run(rid=str(i), findings=[f("a:1","token never expires")]) for i in range(4)]
ov = br.outcome_variance(same)
check("identical runs -> 0 instability", ov["instability"] == 0.0)
check("identical runs -> 0 count cv", ov["count_cv"] == 0.0)
wild = [run(rid=str(i), findings=[f(f"a:{i*20}", f"issue number {i}")]) for i in range(4)]
check("disjoint runs -> 1.0 instability", br.outcome_variance(wild)["instability"] == 1.0)
sev = [run(rid="0", findings=[f("a:1","x y z","low")]),
       run(rid="1", findings=[f("a:1","x y z","critical")])]
check("severity moves even when set is stable",
      br.outcome_variance(sev)["instability"] == 0.0 and br.outcome_variance(sev)["severity_cv"] > 0)

print("process variance")
g1 = {"nodes":[{"id":"n0","label":"plan"},{"id":"n1","label":"scan"}],"edges":[["n0","n1"]]}
g2 = {"nodes":[{"id":"z9","label":"plan"},{"id":"z8","label":"scan"}],"edges":[["z9","z8"]]}
g3 = {"nodes":[{"id":"n0","label":"plan"},{"id":"n1","label":"scan"},
               {"id":"n2","label":"verify"}],"edges":[["n0","n1"],["n1","n2"]]}
check("relabelled ids -> 0", br.process_variance([run(rid="a",dag=g1), run(rid="b",dag=g2)]) == 0.0)
check("extra node -> >0", br.process_variance([run(rid="a",dag=g1), run(rid="b",dag=g3)]) > 0)
check("different shape -> <=1", br.process_variance([run(rid="a",dag=g1), run(rid="b",dag=g3)]) <= 1.0)

print("recall / precision")
truth = {"i": [f("a:1","token never expires"), f("b:2","md5 is used for hashing")]}
r = br.recall_precision([run(findings=[f("a:3","the token never expires")])], truth)
check("recall 1 of 2", abs(r["recall"] - 0.5) < 1e-9)
check("precision 1 of 1", r["precision"] == 1.0)
r2 = br.recall_precision([run(findings=[f("zz:9","totally unrelated noise here")])], truth)
check("all-noise run scores 0", r2["recall"] == 0.0 and r2["precision"] == 0.0)

print("ladder over the real fixtures")
runs = br.load_runs(Path(__file__).parent / "fixtures/runs.json")
gt = br.load_ground_truth(Path(__file__).parent / "fixtures/ground_truth.json")
df = br.ladder_table(runs, gt)
check("all 7 rungs present", list(df.index) == br.RUNGS)
check("recall rises monotonically", df["recall"].is_monotonic_increasing)
check("outcome variance peaks at r3", df["outcome_variance"].idxmax() == "r3")
check("outcome variance falls monotonically after r3",
      df.loc["r4":, "outcome_variance"].is_monotonic_decreasing)
check("r1 quieter than the improvised middle",
      df.loc["r1","outcome_variance"] < df.loc["r2","outcome_variance"])
check("r4 hand-written graph is exactly reproducible", df.loc["r4","process_variance"] == 0.0)
check("r6 JIT graph genuinely varies", df.loc["r6","process_variance"] > 0.2)
check("THESIS: at r6 process varies more than outcome",
      df.loc["r6","process_variance"] > df.loc["r6","outcome_variance"])
check("THESIS: at r3 outcome varies more than at r6",
      df.loc["r3","outcome_variance"] > 3 * df.loc["r6","outcome_variance"])
check("structure is cheaper AND better than improvised nesting",
      df.loc["r4","cost_usd"] < df.loc["r3","cost_usd"]
      and df.loc["r4","recall"] > df.loc["r3","recall"])
check("cost climbs across the structured rungs",
      df.loc["r4":, "cost_usd"].is_monotonic_increasing)
check("touchpoints fall away by r7", df.loc["r7","touchpoints"] < df.loc["r3","touchpoints"])
check("schema: every run carries every field", all(
    set(r) >= {"rung","input_id","run_id","findings","cost_usd","tokens",
               "wall_time_s","human_touchpoints","escalations","dag"} for r in runs))

print(f"\n{ok} checks passed")

print("schema validator")
good = run(rung="r4", findings=[f("a:1","x y z")],
           dag={"nodes":[{"id":"n0","label":"plan"}],"edges":[]})
check("valid run passes", br.validate_run(good) == [])
check("bad rung caught", br.validate_run({**good, "rung": "r9"}))
check("missing field caught", br.validate_run({k: v for k, v in good.items() if k != "tokens"}))
check("bad severity caught", br.validate_run({**good, "findings":[f("a:1","x","urgent")]}))
check("dangling edge caught", br.validate_run(
    {**good, "dag":{"nodes":[{"id":"n0","label":"plan"}],"edges":[["n0","n7"]]}}))
check("unlabelled node caught", br.validate_run({**good, "dag":{"nodes":[{"id":"n0"}],"edges":[]}}))
check("every fixture run is schema-valid", all(not br.validate_run(r) for r in runs))
print(f"\n{ok} checks passed")
