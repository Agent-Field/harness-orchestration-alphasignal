"""Check that ground_truth.json is consistent with the generated artifacts."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
gt = json.load(open(os.path.join(ROOT, "ground_truth.json")))
vocab = {l["id"] for l in gt["lens_vocabulary"]}
bad = []
for inc in gt["incidents"]:
    d = os.path.join(ROOT, inc["id"])
    files = {n: open(os.path.join(d, n)).read()
             for n in ("logs.txt", "metrics.json", "deploys.json", "topology.json", "alert.json")}
    for e in inc["required_evidence"] + inc["red_herrings"]:
        if e["match"] not in files[e["artifact"]]:
            bad.append(f'{inc["id"]} {e["id"]}: not found in {e["artifact"]}: {e["match"][:60]!r}')
    for L in inc["lenses_warranted"] + inc["lenses_not_warranted"]:
        if L not in vocab:
            bad.append(f'{inc["id"]}: unknown lens {L}')
    if set(inc["lenses_warranted"]) & set(inc["lenses_not_warranted"]):
        bad.append(f'{inc["id"]}: lens appears in both lists')
sets = {i["id"]: frozenset(i["lenses_warranted"]) for i in gt["incidents"]}
if len(set(sets.values())) != len(sets):
    bad.append("two incidents have identical warranted-lens sets")
worst = max((len(sets[a] & sets[b]) / len(sets[a] | sets[b]), a, b)
            for a in sets for b in sets if a < b)
print(f"{len(gt['incidents'])} incidents, {len(vocab)} lenses, "
      f"max lens-set jaccard {worst[0]:.2f} ({worst[1]}/{worst[2]})")
print("PROBLEMS:", len(bad))
for b in bad:
    print("  ", b)
sys.exit(1 if bad else 0)
