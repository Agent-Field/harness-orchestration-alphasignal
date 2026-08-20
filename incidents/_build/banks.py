"""Reusable log-noise banks. Entries are (weight, level, message, extra_kv)."""

def http_noise(paths, extra=None, ok_weight=40):
    """Boring successful-request chatter."""
    bank = []
    for p in paths:
        bank.append((ok_weight / len(paths), "INFO",
                     "%s completed" % p, {"method": "GET", "path": p, "status": 200,
                                          "duration_ms": "{ms}", "trace_id": "{tid}", "req_id": "{rid}"}))
    bank += [
        (6, "INFO", "health check ok", {"path": "/healthz", "status": 200, "duration_ms": 2}),
        (3, "INFO", "readiness probe ok", {"path": "/readyz", "status": 200, "duration_ms": 1}),
        (2, "DEBUG", "metrics scrape served", {"path": "/metrics", "status": 200, "bytes": "{n}214"}),
        (2, "INFO", "auth token validated", {"user_id": "{uid}", "issuer": "identity-service"}),
        (2, "DEBUG", "feature flag evaluated", {"flag": "checkout_v2_layout", "value": "true", "user_id": "{uid}"}),
        (1, "INFO", "session refreshed", {"user_id": "{uid}", "ttl_s": 1800}),
    ]
    return bank + (extra or [])

def jvm_noise():
    return [
        (3, "INFO", "GC pause", {"logger": "o.a.g.G1Young", "collector": "G1 Young Generation",
                                 "duration_ms": "{n}", "heap_before_mb": "18{n}4", "heap_after_mb": "9{n}1"}),
        (1, "DEBUG", "thread pool stats", {"logger": "c.a.common.Pools", "active": "{n}", "queued": 0}),
    ]

def k8s_noise():
    return [
        (2, "INFO", "container probe succeeded", {"probe": "liveness", "container": "app"}),
        (1, "INFO", "kubelet synced pod status", {"phase": "Running"}),
        (1, "DEBUG", "cAdvisor housekeeping finished", {"duration_ms": "{n}"}),
    ]

def kafka_noise(topic, group):
    return [
        (8, "INFO", "offsets committed", {"topic": topic, "group": group, "partition": "{n}", "offset": "4{n}83221"}),
        (4, "DEBUG", "fetch response received", {"topic": topic, "partition": "{n}", "records": "{n}"}),
        (1, "INFO", "heartbeat sent to coordinator", {"group": group, "generation": 118}),
    ]
