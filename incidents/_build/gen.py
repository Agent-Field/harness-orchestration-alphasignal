"""Corpus generator for the blast-radius incident triage teaching repo.

Renders realistic synthetic incident artifacts from compact, hand-authored specs.
Deterministic: seeded per-incident so regenerating produces byte-identical output.
"""
import json, os, random, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- time helpers
def T(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)

def iso(t, ms=True):
    if ms:
        return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")

# ------------------------------------------------------------ token fill-ins
HEX = "0123456789abcdef"

def _tok(rng, n):
    return "".join(rng.choice(HEX) for _ in range(n))

def fill(rng, msg, kv):
    ctx = {
        "rid": "req_" + _tok(rng, 12),
        "tid": _tok(rng, 32),
        "span": _tok(rng, 16),
        "uid": f"usr_{rng.randint(100000, 999999)}",
        "oid": f"ord_{rng.randint(10**9, 10**10 - 1)}",
        "ip": f"10.{rng.randint(4,60)}.{rng.randint(0,255)}.{rng.randint(2,254)}",
        "pod": f"-{_tok(rng,5)}-{_tok(rng,5)}",
        "ms": rng.randint(8, 240),
        "n": rng.randint(1, 40), "d": rng.randint(0, 9),
        "sku": f"SKU-{rng.randint(10000,99999)}",
        "tenant": rng.choice(["acme", "globex", "initech", "umbrella", "hooli", "soylent"]),
    }
    def f(v):
        if not isinstance(v, str) or "{" not in v:
            return v
        try:
            return v.format(**ctx)
        except (KeyError, IndexError, ValueError):
            return v
    out_kv = {k: f(v) for k, v in (kv or {}).items()}
    return f(msg), out_kv

# ------------------------------------------------------------- line renderers
LOGGERS = {}

def render(fmt, t, level, svc, msg, kv, rng):
    if fmt == "json":
        rec = {"ts": iso(t), "level": level.lower(), "service": svc, "msg": msg}
        rec.update(kv)
        return json.dumps(rec, separators=(",", ":"))
    if fmt == "logfmt":
        parts = [f"ts={iso(t)}", f"level={level.lower()}", f"svc={svc}"]
        parts.append('msg="%s"' % msg.replace('"', "'"))
        for k, v in kv.items():
            v = str(v)
            parts.append(f'{k}="{v}"' if (" " in v or "=" in v) else f"{k}={v}")
        return " ".join(parts)
    if fmt == "java":
        logger = kv.pop("logger", None) or LOGGERS.get(svc, "c.a." + svc.replace("-", ".") + ".Handler")
        thr = kv.pop("thread", None) or "http-nio-8080-exec-%d" % rng.randint(1, 24)
        tail = " ".join(f"{k}={v}" for k, v in kv.items())
        stamp = t.strftime("%Y-%m-%d %H:%M:%S,") + f"{t.microsecond // 1000:03d}"
        return f"{stamp} {level:<5} [{thr}] {logger} - {msg}{(' ' + tail) if tail else ''}"
    if fmt == "syslog":
        host = kv.pop("host", None) or "node-01"
        proc = kv.pop("proc", None) or svc
        tail = " ".join(f"{k}={v}" for k, v in kv.items())
        stamp = t.strftime("%b %d %H:%M:%S")
        return f"{stamp} {host} {proc}[{abs(hash(proc)) % 9000 + 700}]: {level.upper()} {msg}{(' ' + tail) if tail else ''}"
    raise ValueError(fmt)

# ------------------------------------------------------------------ log build
def build_log(spec, rng):
    fmt = spec["format"]
    svc = spec["svc"]
    start, end = T(spec["start"]), T(spec["end"])
    span = (end - start).total_seconds()
    n = spec["lines"]

    rows = []
    for _ in range(n):
        off = rng.random() * span
        t = start + dt.timedelta(seconds=off)
        frac = off / span
        bank = None
        for ph in spec["phases"]:
            if frac <= ph["until"]:
                bank = ph["noise"]
                break
        bank = bank or spec["phases"][-1]["noise"]
        level, msg, kv = pick(rng, bank)
        msg, kv = fill(rng, msg, kv)
        rows.append((t, render(fmt, t, level, svc, msg, dict(kv), rng)))

    for sig in spec.get("signals", []):
        base = start + dt.timedelta(seconds=sig["at"])
        reps = sig.get("repeat", 1)
        every = sig.get("every", 1.0)
        jitter = sig.get("jitter", 0.35)
        for i in range(reps):
            t = base + dt.timedelta(seconds=i * every + rng.uniform(0, jitter))
            level, msg, kv = sig["level"], sig["msg"], dict(sig.get("kv", {}))
            msg, kv = fill(rng, msg, kv)
            if sig.get("raw"):
                line = msg
            else:
                line = render(sig.get("format", fmt), t, level, sig.get("svc", svc), msg, kv, rng)
            rows.append((t, line))
            for j, cont in enumerate(sig.get("cont", [])):
                rows.append((t + dt.timedelta(microseconds=100 + j), cont))

    rows.sort(key=lambda r: r[0])
    return "\n".join(r[1] for r in rows) + "\n"

def pick(rng, bank):
    total = sum(w for w, *_ in bank)
    x = rng.random() * total
    for w, level, msg, kv in bank:
        x -= w
        if x <= 0:
            return level, msg, kv
    w, level, msg, kv = bank[-1]
    return level, msg, kv

# -------------------------------------------------------------- metric series
def seg(n, a, b, jitter=0.04, floor=None, ceil=None):
    return {"n": n, "a": a, "b": b, "j": jitter, "floor": floor, "ceil": ceil}

def series(rng, segs, nd=1):
    out = []
    for s in segs:
        n = s["n"]
        for i in range(n):
            f = (i / max(n - 1, 1)) if n > 1 else 1.0
            v = s["a"] + (s["b"] - s["a"]) * f
            v *= 1 + rng.uniform(-s["j"], s["j"])
            if s["floor"] is not None:
                v = max(v, s["floor"])
            if s["ceil"] is not None:
                v = min(v, s["ceil"])
            out.append(round(v, nd) if nd else int(round(v)))
    return out

def build_metrics(spec, rng):
    start = T(spec["start"])
    step = spec.get("step_seconds", 60)
    out = {
        "service": spec["service"],
        "window": {"start": iso(start, False), "step_seconds": step,
                   "points": len(series(random.Random(0), list(spec["series"].values())[0]))},
        "units": spec.get("units", {}),
        "series": {},
    }
    for k, segs in spec["series"].items():
        nd = 0 if k.endswith(("_count", "_depth", "_active", "_idle", "_total", "_rps", "_replicas")) else 1
        out["series"][k] = series(rng, segs, nd)
    out["window"]["end"] = iso(start + dt.timedelta(seconds=step * out["window"]["points"]), False)
    out["annotations"] = spec.get("annotations", [])
    if "extra" in spec:
        out.update(spec["extra"])
    return out

# ------------------------------------------------------------------- emitting
def write_incident(spec):
    rng = random.Random(spec["seed"])
    d = os.path.join(ROOT, spec["id"])
    os.makedirs(d, exist_ok=True)

    with open(os.path.join(d, "alert.json"), "w") as f:
        json.dump(spec["alert"], f, indent=2)
        f.write("\n")
    with open(os.path.join(d, "deploys.json"), "w") as f:
        json.dump(spec["deploys"], f, indent=2)
        f.write("\n")
    with open(os.path.join(d, "topology.json"), "w") as f:
        json.dump(spec["topology"], f, indent=2)
        f.write("\n")
    with open(os.path.join(d, "metrics.json"), "w") as f:
        json.dump(build_metrics(spec["metrics"], rng), f, indent=2)
        f.write("\n")
    with open(os.path.join(d, "logs.txt"), "w") as f:
        f.write(build_log(spec["log"], rng))
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write(spec["readme"].strip() + "\n")
    return d
