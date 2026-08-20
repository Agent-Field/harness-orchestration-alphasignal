from banks import http_noise, jvm_noise, k8s_noise, kafka_noise
from gen import seg

SPECS = []

# ============================================================ inc-009 =========
SPECS.append({
"id": "inc-009", "seed": 1009,
"readme": """
# inc-009 — feed-api falls over every morning at the same time

08:06 UTC. `feed-api` is returning 503 and its p99 is over four seconds. This is the third
weekday in a row that it has misbehaved during the European morning ramp, though the previous
two days recovered on their own before anyone looked. The service is the read path for the
personalised home feed: heavy fan-out, lots of waiting on downstream calls, not much local
computation. There is a database index migration running this morning, which the DBA has
flagged in the channel. Request volume is climbing, as it does every weekday at this hour.
The obvious explanation on the table is "we need more capacity".
""",
"alert": {
  "alert_id": "alt-2026-08-12-0806-feed",
  "monitor_name": "feed-api :: 503 rate > 2% (5m)",
  "monitor_id": "mon-1877", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-08-12T08:06:00Z", "detected_change_at": "2026-08-12T07:58:00Z",
  "threshold": {"metric": "http.server.503_rate", "comparator": ">", "value": 2.0, "unit": "%", "window": "5m"},
  "observed_value": 9.1,
  "history": ["fired 2026-08-10T08:11Z, auto-resolved 08:38Z",
              "fired 2026-08-11T08:04Z, auto-resolved 08:31Z"],
  "service": "feed-api", "environment": "prod", "region": "eu-west-1",
  "notified": ["oncall-feed"], "runbook": "https://runbooks.internal/feed-api/503",
  "tags": ["tier:1", "team:feed"]
},
"deploys": {"lookback_hours": 120, "events": [
  {"id": "dep-4102", "at": "2026-08-07T11:20:00Z", "kind": "deploy", "service": "feed-api",
   "version": "9.1.2", "actor": "tokafor", "change": "ranking model refresh"},
  {"id": "dep-4130", "at": "2026-08-09T16:12:00Z", "kind": "config", "service": "feed-api",
   "actor": "platform-bot",
   "change": "HPA standardisation sweep: switch all services to cpu target 70%, min 3 / max 40",
   "diff_summary": "hpa.yaml: metrics[0] Pods/http_requests_per_second target 120 -> Resource/cpu target 70; "
                   "minReplicas 12 -> 3; behavior.scaleDown.stabilizationWindowSeconds 300 -> 60; "
                   "behavior.scaleUp.stabilizationWindowSeconds 0 -> 180"},
  {"id": "dep-4141", "at": "2026-08-12T07:30:00Z", "kind": "maintenance", "service": "postgres-feed",
   "actor": "dba-bot", "change": "CREATE INDEX CONCURRENTLY on feed_item(user_id, created_at) - running"}
]},
"topology": {
  "root": "feed-api",
  "nodes": [
    {"id": "edge-proxy", "kind": "gateway", "team": "platform"},
    {"id": "feed-api", "kind": "service", "team": "feed", "runtime": "go-1.24",
     "replicas_min": 3, "replicas_max": 40, "profile": "io-bound: ~85% of wall time waiting on downstreams",
     "cpu_at_full_load_pct": 22, "max_inflight_per_replica": 120},
    {"id": "ranking-service", "kind": "service", "team": "ml", "timeout_ms": 700},
    {"id": "profile-service", "kind": "service", "team": "identity", "timeout_ms": 400},
    {"id": "postgres-feed", "kind": "database", "team": "feed"},
    {"id": "redis-feed", "kind": "cache", "team": "feed"}
  ],
  "edges": [
    {"from": "edge-proxy", "to": "feed-api", "protocol": "http", "timeout_ms": 5000},
    {"from": "feed-api", "to": "ranking-service", "protocol": "grpc", "fanout": 4},
    {"from": "feed-api", "to": "profile-service", "protocol": "grpc", "fanout": 1},
    {"from": "feed-api", "to": "postgres-feed", "protocol": "pg", "pool_max_size": 20},
    {"from": "feed-api", "to": "redis-feed", "protocol": "resp"}
  ],
  "notes": "feed-api spends most of its time blocked on IO, so CPU is a poor proxy for how loaded it is."
},
"metrics": {"service": "feed-api", "start": "2026-08-12T07:20:00Z", "step_seconds": 60,
  "units": {"replicas": "pods", "cpu_pct": "%", "inflight_per_replica": "requests"},
  "series": {
    "rps": [seg(10, 900, 1400), seg(10, 1400, 2900), seg(10, 2900, 4100), seg(20, 4100, 4600)],
    "rps_same_time_yesterday": [seg(10, 890, 1390), seg(10, 1390, 2880), seg(10, 2880, 4050), seg(20, 4050, 4580)],
    "replicas": [seg(6, 12, 12, 0.0), seg(4, 12, 6, 0.0), seg(6, 6, 3, 0.0), seg(14, 3, 3, 0.0),
                 seg(10, 3, 4, 0.0), seg(10, 4, 7, 0.0)],
    "cpu_pct": [seg(10, 14, 17), seg(10, 17, 33), seg(10, 33, 61), seg(20, 61, 74)],
    "mem_pct": [seg(10, 41, 43), seg(40, 43, 52)],
    "inflight_per_replica": [seg(10, 21, 34), seg(10, 34, 96), seg(10, 96, 120, 0.01), seg(20, 120, 120, 0.0)],
    "latency_p99_ms": [seg(10, 210, 240), seg(10, 240, 900), seg(10, 900, 3800), seg(20, 3800, 4600)],
    "error_rate_503_pct": [seg(20, 0.05, 0.08), seg(10, 0.08, 4.2), seg(20, 4.2, 10.1)],
    "hpa_desired_replicas": [seg(6, 12, 12, 0.0), seg(4, 12, 6, 0.0), seg(6, 6, 3, 0.0), seg(14, 3, 3, 0.0),
                             seg(10, 3, 4, 0.0), seg(10, 4, 8, 0.0)],
    "db_query_p99_ms": [seg(10, 8, 9), seg(40, 9, 12)],
    "ranking_service_p99_ms": [seg(10, 180, 190), seg(40, 190, 210)]
  },
  "annotations": [
    {"t": "2026-08-12T07:30:00Z", "text": "postgres-feed CREATE INDEX CONCURRENTLY started"},
    {"t": "2026-08-12T07:36:00Z", "text": "HPA scaled feed-api 12 -> 6"},
    {"t": "2026-08-12T07:44:00Z", "text": "HPA scaled feed-api 6 -> 3 (minReplicas)"},
    {"t": "2026-08-12T08:06:00Z", "text": "alert fired"}
  ],
  "extra": {"note": "Traffic today tracks yesterday within 2%. The overnight replica count used to floor at 12."}
},
"log": {"svc": "feed-api", "format": "logfmt", "start": "2026-08-12T07:24:00Z", "end": "2026-08-12T08:12:00Z",
  "lines": 340,
  "phases": [
    {"until": 0.40, "noise": http_noise(["/v1/feed", "/v1/feed/refresh", "/healthz"],
        extra=[
          (16, "INFO", "feed built", {"user_id": "{uid}", "items": "{n}", "duration_ms": "{ms}", "replica": "feed-api{pod}"}),
          (4, "DEBUG", "ranking fanout complete", {"shards": 4, "duration_ms": "1{n}0"}),
          (3, "DEBUG", "feed cache hit", {"user_id": "{uid}"}),
        ])},
    {"until": 1.0, "noise": [
          (14, "INFO", "feed built", {"user_id": "{uid}", "items": "{n}", "duration_ms": "3{n}40", "replica": "feed-api{pod}"}),
          (8, "WARN", "request queued", {"queue_depth": "1{n}", "inflight": 120, "max_inflight": 120}),
          (6, "ERROR", "request rejected", {"status": 503, "reason": "max_inflight_exceeded", "user_id": "{uid}"}),
          (3, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
        ]}
  ],
  "signals": [
    {"at": 360, "level": "INFO", "msg": "postgres index build progress",
     "kv": {"index": "feed_item_user_id_created_at_idx", "phase": "building index", "pct": "{n}",
            "blocks_done": "1{n}0421"}, "repeat": 6, "every": 240},
    {"at": 720, "level": "INFO", "msg": "horizontal pod autoscaler scaled deployment",
     "format": "syslog", "svc": "kube-controller-manager",
     "kv": {"host": "control-plane-2", "proc": "kube-controller-manager", "deployment": "feed-api",
            "from": 12, "to": 6, "metric": "resource/cpu", "current_pct": 17, "target_pct": 70}},
    {"at": 1200, "level": "INFO", "msg": "horizontal pod autoscaler scaled deployment",
     "format": "syslog", "svc": "kube-controller-manager",
     "kv": {"host": "control-plane-2", "proc": "kube-controller-manager", "deployment": "feed-api",
            "from": 6, "to": 3, "metric": "resource/cpu", "current_pct": 21, "target_pct": 70,
            "note": "clamped at minReplicas=3"}},
    {"at": 1500, "level": "WARN", "msg": "inflight limit reached, shedding",
     "kv": {"replica": "feed-api-6b9{pod}", "inflight": 120, "max_inflight": 120, "cpu_pct": "3{n}"},
     "repeat": 18, "every": 40},
    {"at": 1560, "level": "WARN", "msg": "hpa scale-up suppressed by stabilization window",
     "format": "syslog", "svc": "kube-controller-manager",
     "kv": {"host": "control-plane-2", "proc": "kube-controller-manager", "deployment": "feed-api",
            "desired": 8, "current": 3, "stabilization_window_s": 180, "seconds_remaining": "1{n}0"},
     "repeat": 7, "every": 90},
    {"at": 1800, "level": "ERROR", "msg": "request rejected",
     "kv": {"status": 503, "reason": "max_inflight_exceeded", "cpu_pct": "4{n}", "replica": "feed-api-6b9{pod}"},
     "repeat": 20, "every": 30},
    {"at": 2100, "level": "INFO", "msg": "capacity summary",
     "kv": {"replicas": 3, "rps": "4{n}00", "rps_per_replica": "15{n}0", "cpu_pct": 68,
            "designed_rps_per_replica": 400}, "repeat": 3, "every": 200},
  ]}
})

# ============================================================ inc-010 =========
SPECS.append({
"id": "inc-010", "seed": 1010,
"readme": """
# inc-010 — auth-service went down for a minute and has been down for half an hour

09:04 UTC. `auth-service` is failing about a third of token verifications and has been for
twenty-five minutes. What makes this odd is the shape of it: there was a short, sharp blip at
09:00 that lasted well under a minute, everything looked like it was recovering, and then the
service got worse and stayed worse. Nobody has touched auth-service in four days. Platform
rebooted a node at 09:00 as part of routine patching, and one auth-service pod went with it.
Every service in the company calls this one. The team has already restarted the pods twice;
each restart helps for about ninety seconds.
""",
"alert": {
  "alert_id": "alt-2026-07-28-0904-auth",
  "monitor_name": "auth-service :: verify error rate > 5% (3m)",
  "monitor_id": "mon-0333", "severity": "SEV1", "state": "firing",
  "fired_at": "2026-07-28T09:04:00Z", "detected_change_at": "2026-07-28T09:00:12Z",
  "threshold": {"metric": "auth.verify.error_rate", "comparator": ">", "value": 5.0, "unit": "%", "window": "3m"},
  "observed_value": 33.6,
  "service": "auth-service", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-platform"], "runbook": "https://runbooks.internal/auth-service/errors",
  "tags": ["tier:0", "team:platform", "fan-in:everything"]
},
"deploys": {"lookback_hours": 168, "events": [
  {"id": "dep-1180", "at": "2026-07-24T13:00:00Z", "kind": "deploy", "service": "auth-service",
   "version": "8.4.1", "actor": "mchen", "change": "cache introspection results 30s"},
  {"id": "dep-1201", "at": "2026-07-27T15:22:00Z", "kind": "deploy", "service": "web-bff",
   "version": "2026.7.27-2", "actor": "jtan",
   "change": "harden auth calls: retry 5x on any 5xx or timeout",
   "diff_summary": "authClient.ts: maxRetries 1 -> 5; backoff 'none'; timeout_ms 2000 -> 400"},
  {"id": "dep-1206", "at": "2026-07-28T08:58:00Z", "kind": "maintenance", "service": "node-pool/general-4",
   "actor": "platform-bot", "change": "routine node reboot general-4-c (1 of 12)",
   "diff_summary": "auth-service-5f7c-w9k terminated 09:00:04Z, rescheduled 09:00:41Z, Ready 09:00:52Z"}
]},
"topology": {
  "root": "auth-service",
  "nodes": [
    {"id": "auth-service", "kind": "service", "team": "platform", "replicas": 9,
     "capacity_rps_per_replica": 900, "verify_p50_ms": 4},
    {"id": "web-bff", "kind": "service", "team": "web", "calls_auth": True,
     "retry_policy": {"max_attempts": 5, "backoff": "none", "jitter": False, "timeout_ms": 400}},
    {"id": "mobile-bff", "kind": "service", "team": "mobile", "calls_auth": True,
     "retry_policy": {"max_attempts": 3, "backoff": "exponential", "jitter": True, "timeout_ms": 1500}},
    {"id": "checkout-api", "kind": "service", "team": "payments", "calls_auth": True,
     "retry_policy": {"max_attempts": 3, "backoff": "none", "jitter": False, "timeout_ms": 800}},
    {"id": "orders-service", "kind": "service", "team": "orders", "calls_auth": True,
     "retry_policy": {"max_attempts": 3, "backoff": "none", "jitter": False, "timeout_ms": 800}},
    {"id": "redis-auth", "kind": "cache", "team": "platform"}
  ],
  "edges": [
    {"from": "web-bff", "to": "auth-service", "protocol": "grpc", "share_of_traffic": 0.44},
    {"from": "mobile-bff", "to": "auth-service", "protocol": "grpc", "share_of_traffic": 0.31},
    {"from": "checkout-api", "to": "auth-service", "protocol": "grpc", "share_of_traffic": 0.15},
    {"from": "orders-service", "to": "auth-service", "protocol": "grpc", "share_of_traffic": 0.10},
    {"from": "auth-service", "to": "redis-auth", "protocol": "resp"}
  ],
  "notes": "Total steady-state verify load is ~5400 rps against 9 replicas x 900 rps = 8100 rps of capacity. "
           "auth-service has no admission control or load shedding."
},
"metrics": {"service": "auth-service", "start": "2026-07-28T08:50:00Z", "step_seconds": 60,
  "units": {"verify_rps": "req/s", "unique_sessions_per_min": "sessions", "error_rate_pct": "%"},
  "series": {
    "verify_rps": [seg(10, 5300, 5450), seg(1, 5450, 7100), seg(3, 7100, 24000), seg(26, 24000, 31000)],
    "verify_rps_first_attempt": [seg(10, 5300, 5450), seg(1, 5450, 5400), seg(3, 5400, 5380), seg(26, 5380, 5420)],
    "unique_sessions_per_min": [seg(10, 41000, 41500), seg(30, 41500, 41200)],
    "error_rate_pct": [seg(10, 0.2, 0.3), seg(1, 0.3, 12.0), seg(1, 12.0, 1.1), seg(3, 1.1, 22.0),
                       seg(25, 22.0, 36.0)],
    "healthy_replicas": [seg(10, 9, 9, 0.0), seg(1, 9, 8, 0.0), seg(1, 8, 9, 0.0), seg(28, 9, 9, 0.0)],
    "cpu_pct": [seg(10, 34, 36), seg(1, 36, 52), seg(3, 52, 98), seg(26, 98, 99, 0.005)],
    "queue_depth": [seg(10, 2, 3), seg(1, 3, 40), seg(3, 40, 4200), seg(26, 4200, 9100)],
    "verify_p99_ms": [seg(10, 22, 24), seg(1, 24, 310), seg(3, 310, 2900), seg(26, 2900, 4100)],
    "client_retry_rps_web_bff": [seg(10, 4, 6), seg(1, 6, 900), seg(3, 900, 14000), seg(26, 14000, 18500)],
    "client_retry_rps_mobile_bff": [seg(10, 3, 4), seg(1, 4, 210), seg(3, 210, 1900), seg(26, 1900, 2400)],
    "redis_auth_p99_ms": [seg(10, 1.1, 1.2), seg(30, 1.2, 1.4)]
  },
  "annotations": [
    {"t": "2026-07-28T09:00:04Z", "text": "auth-service-5f7c-w9k terminated (node reboot)"},
    {"t": "2026-07-28T09:00:52Z", "text": "replacement pod Ready; healthy_replicas back to 9"},
    {"t": "2026-07-28T09:04:00Z", "text": "alert fired"},
    {"t": "2026-07-28T09:14:00Z", "text": "team restarted all auth-service pods (no lasting effect)"}
  ],
  "extra": {"note": "unique_sessions_per_min is flat throughout: the population of real users did not change. "
                    "verify_rps_first_attempt is also flat. All growth is in retried attempts."}
},
"log": {"svc": "auth-service", "format": "logfmt", "start": "2026-07-28T08:56:00Z", "end": "2026-07-28T09:26:00Z",
  "lines": 350,
  "phases": [
    {"until": 0.13, "noise": [
          (24, "INFO", "verify ok", {"client": "web-bff", "session": "{uid}", "duration_ms": "{n}", "attempt": 1}),
          (12, "INFO", "verify ok", {"client": "mobile-bff", "session": "{uid}", "duration_ms": "{n}", "attempt": 1}),
          (6, "INFO", "verify ok", {"client": "checkout-api", "session": "{uid}", "duration_ms": "{n}", "attempt": 1}),
          (3, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
          (2, "DEBUG", "introspection cache hit", {"ttl_left_s": "{n}"}),
        ]},
    {"until": 1.0, "noise": [
          (18, "INFO", "verify ok", {"client": "web-bff", "session": "{uid}", "duration_ms": "2{n}00", "attempt": "{n}"}),
          (10, "ERROR", "verify failed", {"client": "web-bff", "session": "{uid}", "error": "DEADLINE_EXCEEDED",
                                          "deadline_ms": 400, "attempt": "{n}"}),
          (6, "ERROR", "verify failed", {"client": "checkout-api", "session": "{uid}", "error": "RESOURCE_EXHAUSTED",
                                         "queue_depth": "{n}021"}),
          (5, "WARN", "request queued", {"queue_depth": "{n}021", "workers_busy": 256, "workers_max": 256}),
          (3, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
        ]}
  ],
  "signals": [
    {"at": 240, "level": "WARN", "msg": "pod terminated by node drain", "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-4-c", "proc": "kubelet", "pod": "auth-service-5f7c-w9k", "reason": "NodeReboot"}},
    {"at": 250, "level": "ERROR", "msg": "verify failed",
     "kv": {"client": "web-bff", "error": "UNAVAILABLE: connection reset", "replica": "auth-service-5f7c-w9k",
            "session": "{uid}", "attempt": 1}, "repeat": 14, "every": 3},
    {"at": 288, "level": "INFO", "msg": "replacement pod ready, endpoints updated",
     "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-4-h", "proc": "kubelet", "pod": "auth-service-5f7c-2bd", "ready": "true",
            "healthy_replicas": 9}},
    {"at": 300, "level": "WARN", "msg": "retry received for request whose original is still inflight",
     "kv": {"client": "web-bff", "trace_id": "{tid}", "attempt": 3, "max_attempts": 5, "backoff": "none",
            "original_age_ms": "1{n}0"}, "repeat": 30, "every": 18},
    {"at": 330, "level": "WARN", "msg": "inbound rate exceeds capacity",
     "kv": {"inbound_rps": "2{n}400", "capacity_rps": 8100, "shedding": "not_configured"},
     "repeat": 14, "every": 70},
    {"at": 400, "level": "INFO", "msg": "attempt histogram (last 60s)",
     "kv": {"attempt_1": 5411, "attempt_2": 5203, "attempt_3": 5011, "attempt_4": 4802, "attempt_5": 4611,
            "distinct_trace_ids": 5388}, "repeat": 8, "every": 120},
    {"at": 600, "level": "ERROR", "msg": "verify failed",
     "kv": {"client": "web-bff", "error": "DEADLINE_EXCEEDED", "deadline_ms": 400, "server_processing_ms": "3{n}0",
            "attempt": "{n}", "trace_id": "{tid}"}, "repeat": 26, "every": 24},
    {"at": 900, "level": "WARN", "msg": "operator initiated rolling restart of auth-service",
     "kv": {"actor": "oncall-platform", "replicas": 9, "reason": "manual mitigation"}},
    {"at": 1000, "level": "INFO", "msg": "post-restart recovery window",
     "kv": {"error_rate_pct": 1.4, "duration_s": 88, "then": "error rate returned to 31%"}},
    {"at": 1200, "level": "WARN", "msg": "goodput vs offered load",
     "kv": {"offered_rps": "2{n}800", "goodput_rps": "52{n}0", "wasted_pct": 79}, "repeat": 5, "every": 130},
  ]}
})

# ============================================================ inc-011 =========
SPECS.append({
"id": "inc-011", "seed": 1011,
"readme": """
# inc-011 — booking-api rejecting valid tokens, but only sometimes

14:22 UTC. `booking-api` is rejecting roughly one in six authenticated requests with 401, and
the customers affected are not a coherent group: the same user succeeds on one attempt and
fails on the next. Support is escalating because partners using the signed-webhook callback are
also seeing rejections. The auth team rotated the JWT signing key three days ago and that is
the leading theory in the incident channel. Nothing has deployed in this region today. The
infrastructure team did live-migrate a batch of hypervisors last night.
""",
"alert": {
  "alert_id": "alt-2026-06-30-1422-booking",
  "monitor_name": "booking-api :: 401 rate > 5% (5m)",
  "monitor_id": "mon-2410", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-06-30T14:22:00Z", "detected_change_at": "2026-06-30T14:08:00Z",
  "threshold": {"metric": "http.server.401_rate", "comparator": ">", "value": 5.0, "unit": "%", "window": "5m"},
  "observed_value": 16.8,
  "service": "booking-api", "environment": "prod", "region": "eu-central-1",
  "notified": ["oncall-booking", "oncall-platform"],
  "runbook": "https://runbooks.internal/booking-api/401",
  "tags": ["tier:1", "team:booking"]
},
"deploys": {"lookback_hours": 96, "events": [
  {"id": "dep-7020", "at": "2026-06-27T10:00:00Z", "kind": "config", "service": "identity-service",
   "actor": "spatel", "change": "JWT signing key rotation kid=2026-06 (old kid retained in JWKS for 30d)"},
  {"id": "dep-7044", "at": "2026-06-29T14:10:00Z", "kind": "deploy", "service": "booking-api",
   "version": "4.7.3", "actor": "amaier", "change": "availability calendar caching"},
  {"id": "dep-7051", "at": "2026-06-29T23:10:00Z", "kind": "maintenance", "service": "hypervisor-fleet/eu-central-1",
   "actor": "infra-bot",
   "change": "live-migrate 40 VMs to new hardware generation (completed 02:40Z)",
   "diff_summary": "nodes migrated: eu-c1-n03, eu-c1-n07, eu-c1-n11, eu-c1-n14, ... (40 total)"}
]},
"topology": {
  "root": "booking-api",
  "nodes": [
    {"id": "edge-proxy", "kind": "gateway", "team": "platform"},
    {"id": "booking-api", "kind": "service", "team": "booking", "runtime": "jvm-21", "replicas": 6,
     "jwt_clock_skew_leeway_s": 30,
     "pods": [
       {"name": "booking-api-77bd-a1", "node": "eu-c1-n02"},
       {"name": "booking-api-77bd-b2", "node": "eu-c1-n05"},
       {"name": "booking-api-77bd-c3", "node": "eu-c1-n07"},
       {"name": "booking-api-77bd-d4", "node": "eu-c1-n09"},
       {"name": "booking-api-77bd-e5", "node": "eu-c1-n12"},
       {"name": "booking-api-77bd-f6", "node": "eu-c1-n15"}]},
    {"id": "identity-service", "kind": "service", "team": "platform", "region": "us-east-1",
     "note": "mints tokens; iat/nbf stamped at mint time"},
    {"id": "partner-webhook-verifier", "kind": "component", "team": "booking",
     "note": "HMAC signature with 60s timestamp window"},
    {"id": "postgres-booking", "kind": "database", "team": "booking"}
  ],
  "edges": [
    {"from": "edge-proxy", "to": "booking-api", "protocol": "http", "load_balancing": "round-robin across 6 pods"},
    {"from": "booking-api", "to": "identity-service", "protocol": "https", "note": "JWKS fetch, cached 1h"},
    {"from": "booking-api", "to": "postgres-booking", "protocol": "jdbc"}
  ],
  "notes": "Round-robin means a single user's consecutive requests land on different pods."
},
"metrics": {"service": "booking-api", "start": "2026-06-30T13:50:00Z", "step_seconds": 60,
  "units": {"error_rate_401_pct": "%", "clock_offset_s": "s"},
  "series": {
    "error_rate_401_pct": [seg(14, 0.4, 0.5), seg(6, 0.5, 14.0), seg(20, 14.0, 17.4)],
    "error_rate_401_pct_pod_a1": [seg(14, 0.4, 0.5), seg(26, 0.5, 0.6)],
    "error_rate_401_pct_pod_c3": [seg(14, 0.5, 0.6), seg(6, 0.6, 92.0), seg(20, 92.0, 99.0)],
    "rps": [seg(14, 260, 275), seg(26, 275, 268)],
    "latency_p99_ms": [seg(14, 190, 200), seg(26, 200, 198)],
    "cpu_pct": [seg(14, 33, 35), seg(26, 35, 34)],
    "jwks_fetch_failures": [seg(40, 0, 0, 0.0)],
    "jwt_kid_2026_06_pct": [seg(40, 100, 100, 0.0)],
    "node_clock_offset_s_eu_c1_n02": [seg(40, 0.002, 0.004, 0.4)],
    "node_clock_offset_s_eu_c1_n07": [seg(6, 0.003, 0.004, 0.3), seg(8, 0.004, 31.0), seg(6, 31.0, 78.0),
                                      seg(20, 78.0, 94.0)],
    "webhook_signature_failures_per_min": [seg(14, 0, 1), seg(6, 1, 24), seg(20, 24, 31)]
  },
  "annotations": [
    {"t": "2026-06-29T23:10:00Z", "text": "hypervisor live-migration window (completed 02:40Z)"},
    {"t": "2026-06-30T14:08:00Z", "text": "401 rate begins climbing"},
    {"t": "2026-06-30T14:22:00Z", "text": "alert fired"}
  ],
  "extra": {"note": "JWKS is reachable and every rejected token carries kid=2026-06, the current key. "
                    "Signature verification itself succeeds on rejected tokens; the claim check is what fails."}
},
"log": {"svc": "booking-api", "format": "logfmt", "start": "2026-06-30T13:58:00Z", "end": "2026-06-30T14:28:00Z",
  "lines": 330,
  "phases": [
    {"until": 0.33, "noise": http_noise(["/v1/bookings", "/v1/availability", "/healthz"],
        extra=[
          (16, "INFO", "booking created", {"user_id": "{uid}", "pod": "booking-api-77bd-b2", "duration_ms": "{ms}"}),
          (6, "DEBUG", "jwt verified", {"kid": "2026-06", "user_id": "{uid}", "pod": "booking-api-77bd-a1"}),
          (4, "DEBUG", "jwks cache hit", {"kid": "2026-06", "age_s": "2{n}0"}),
          (3, "INFO", "webhook signature ok", {"partner": "{tenant}", "skew_s": 1}),
        ])},
    {"until": 1.0, "noise": [
          (14, "INFO", "booking created", {"user_id": "{uid}", "pod": "booking-api-77bd-d4", "duration_ms": "{ms}"}),
          (8, "DEBUG", "jwt verified", {"kid": "2026-06", "user_id": "{uid}", "pod": "booking-api-77bd-e5"}),
          (6, "WARN", "request unauthenticated", {"status": 401, "user_id": "{uid}", "pod": "booking-api-77bd-c3"}),
          (3, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
          (2, "INFO", "webhook signature ok", {"partner": "{tenant}", "skew_s": 1}),
        ]}
  ],
  "signals": [
    {"at": 400, "level": "INFO", "msg": "jwks refreshed", "kv": {"keys": 2, "kids": "2026-05,2026-06", "source": "identity-service"}},
    {"at": 598, "level": "ERROR", "msg": "jwt validation failed",
     "kv": {"reason": "token used before issued", "kid": "2026-06", "signature": "valid",
            "iat": "2026-06-30T14:09:41Z", "now_local": "2026-06-30T14:11:14Z", "skew_s": 93,
            "leeway_s": 30, "pod": "booking-api-77bd-c3", "user_id": "{uid}"}},
    {"at": 600, "level": "ERROR", "msg": "jwt validation failed",
     "kv": {"reason": "token used before issued", "kid": "2026-06", "signature": "valid",
            "skew_s": "9{d}", "leeway_s": 30, "pod": "booking-api-77bd-c3", "user_id": "{uid}"},
     "repeat": 25, "every": 26},
    {"at": 620, "level": "ERROR", "msg": "webhook signature rejected",
     "kv": {"partner": "{tenant}", "reason": "timestamp outside 60s window", "delta_s": -93,
            "pod": "booking-api-77bd-c3"}, "repeat": 12, "every": 55},
    {"at": 700, "raw": True, "level": "ERROR",
     "msg": 'ts=2026-06-30T14:11:47.220Z level=error svc=booking-api pod=booking-api-77bd-c3 msg="jwt validation failed" reason="token used before issued" user_id={uid}'},
    {"at": 701, "raw": True, "level": "INFO",
     "msg": 'ts=2026-06-30T14:10:14.882Z level=info svc=booking-api pod=booking-api-77bd-b2 msg="booking created" user_id={uid} duration_ms=64'},
    {"at": 702, "raw": True, "level": "ERROR",
     "msg": 'ts=2026-06-30T14:11:48.004Z level=error svc=booking-api pod=booking-api-77bd-c3 msg="jwt validation failed" reason="token used before issued" user_id={uid}'},
    {"at": 703, "raw": True, "level": "INFO",
     "msg": 'ts=2026-06-30T14:10:15.331Z level=info svc=booking-api pod=booking-api-77bd-d4 msg="booking created" user_id={uid} duration_ms=71'},
    {"at": 780, "level": "WARN", "msg": "System clock unsynchronised", "format": "syslog", "svc": "chronyd",
     "kv": {"host": "eu-c1-n07", "proc": "chronyd", "detail": "no reachable sources; last update 15h ago; "
            "drift +6.2ppm; local stratum 10"}, "repeat": 6, "every": 120},
    {"at": 800, "level": "WARN", "msg": "timekeeping: kvm-clock source changed after live migration",
     "format": "syslog", "svc": "kernel",
     "kv": {"host": "eu-c1-n07", "proc": "kernel", "detail": "clocksource watchdog: tsc unstable, "
            "switching to hpet; ntp sync lost"}},
    {"at": 1000, "level": "INFO", "msg": "per-pod 401 breakdown (last 5m)",
     "kv": {"a1": 3, "b2": 5, "c3": 1418, "d4": 4, "e5": 6, "f6": 2}, "repeat": 3, "every": 200},
    {"at": 1200, "level": "INFO", "msg": "key rotation status",
     "kv": {"active_kid": "2026-06", "previous_kid": "2026-05", "tokens_with_active_kid_pct": 100,
            "verification_failures_due_to_signature": 0}},
  ]}
})

# ============================================================ inc-012 =========
SPECS.append({
"id": "inc-012", "seed": 1012,
"readme": """
# inc-012 — pricing-consumer has stopped keeping up

16:48 UTC. The lag monitor on the `pricing-consumer` group has crossed a hundred thousand
messages and is climbing at a steady rate. The consequence is that prices shown on the site are
going stale, which merchandising will notice before customers do. The consumer processes a
price feed published by another team. Kafka had a broker restart earlier this afternoon and the
consumer group rebalanced, which is the first thing everyone in the channel points at. Our team
shipped a dependency bump this morning. The consumer is not crash-looping; it is running and
committing offsets, just not producing much useful output.
""",
"alert": {
  "alert_id": "alt-2026-08-18-1648-pricing",
  "monitor_name": "kafka consumer group pricing-consumer :: lag > 100k (10m)",
  "monitor_id": "mon-1955", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-08-18T16:48:00Z", "detected_change_at": "2026-08-18T16:12:00Z",
  "threshold": {"metric": "kafka.consumer_group.lag", "comparator": ">", "value": 100000,
                "unit": "messages", "window": "10m"},
  "observed_value": 214000,
  "service": "pricing-consumer", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-pricing"], "runbook": "https://runbooks.internal/kafka/consumer-lag",
  "tags": ["tier:2", "team:pricing", "data-pipeline"]
},
"deploys": {"lookback_hours": 24, "events": [
  {"id": "dep-9110", "at": "2026-08-18T09:15:00Z", "kind": "deploy", "service": "pricing-consumer",
   "version": "2.6.4", "actor": "ci-bot", "change": "dependency bump: kafka client 3.6.1 -> 3.7.0, jackson 2.16 -> 2.17",
   "diff_summary": "pom.xml +2/-2"},
  {"id": "dep-9133", "at": "2026-08-18T15:02:00Z", "kind": "maintenance", "service": "kafka/cluster-main",
   "actor": "platform-bot", "change": "rolling broker restart for patch (brokers 1-5, completed 15:38Z)"},
  {"id": "dep-9140", "at": "2026-08-18T16:05:00Z", "kind": "deploy", "service": "pricing-publisher",
   "version": "5.0.0", "actor": "team-merch",
   "change": "price feed v5: promotional pricing support",
   "diff_summary": "PriceEvent.avsc: add field 'promotion' (record, nullable); "
                   "change 'price_cents' from int to string (decimal-as-string); "
                   "schema registry subject catalog.price.v1-value new version 7 registered, "
                   "compatibility check set to NONE for this release",
   "note": "cross-team change; pricing-consumer is a registered downstream of this subject"}
]},
"topology": {
  "root": "pricing-consumer",
  "nodes": [
    {"id": "pricing-publisher", "kind": "service", "team": "merchandising",
     "note": "sole producer to catalog.price.v1"},
    {"id": "kafka/catalog.price.v1", "kind": "topic", "team": "platform", "partitions": 12,
     "retention_h": 72, "schema_subject": "catalog.price.v1-value", "latest_schema_version": 7},
    {"id": "schema-registry", "kind": "platform", "team": "platform",
     "note": "compatibility mode for catalog.price.v1-value: NONE (changed 2026-08-18T16:04Z)"},
    {"id": "pricing-consumer", "kind": "worker", "team": "pricing", "replicas": 4,
     "consumer_group": "pricing-consumer", "reader_schema_version": 6},
    {"id": "kafka/pricing.dlq", "kind": "topic", "team": "pricing", "partitions": 3},
    {"id": "postgres-pricing", "kind": "database", "team": "pricing"},
    {"id": "product-catalog-api", "kind": "service", "team": "catalog",
     "note": "reads prices written by pricing-consumer"}
  ],
  "edges": [
    {"from": "pricing-publisher", "to": "kafka/catalog.price.v1", "protocol": "kafka"},
    {"from": "kafka/catalog.price.v1", "to": "pricing-consumer", "protocol": "kafka"},
    {"from": "pricing-consumer", "to": "kafka/pricing.dlq", "protocol": "kafka", "note": "poison messages"},
    {"from": "pricing-consumer", "to": "postgres-pricing", "protocol": "jdbc"},
    {"from": "postgres-pricing", "to": "product-catalog-api", "protocol": "read"}
  ],
  "notes": "Consumer deserialises with reader schema v6. Schema registry compatibility was relaxed to NONE "
           "immediately before the producer release."
},
"metrics": {"service": "pricing-consumer", "start": "2026-08-18T15:30:00Z", "step_seconds": 60,
  "units": {"consumer_lag": "messages", "processed_per_min": "msg/min", "dlq_per_min": "msg/min"},
  "series": {
    "consumer_lag": [seg(30, 900, 1400), seg(6, 1400, 22000), seg(44, 22000, 260000)],
    "processed_per_min": [seg(30, 11800, 12100), seg(6, 12100, 11900), seg(44, 11900, 12000)],
    "committed_per_min": [seg(30, 11800, 12100), seg(6, 12100, 11900), seg(44, 11900, 12000)],
    "successful_writes_per_min": [seg(30, 11750, 12050), seg(6, 12050, 3100), seg(44, 3100, 210)],
    "dlq_per_min": [seg(30, 2, 3), seg(6, 3, 8800), seg(44, 8800, 11800)],
    "deserialization_errors_per_min": [seg(30, 0, 1), seg(6, 1, 8800), seg(44, 8800, 11800)],
    "rebalance_events": [seg(30, 0, 0, 0.0), seg(6, 0, 0, 0.0), seg(44, 0, 0, 0.0)],
    "cpu_pct": [seg(30, 44, 46), seg(50, 46, 39)],
    "mem_pct": [seg(30, 51, 52), seg(50, 52, 53)],
    "produce_rate_publisher_per_min": [seg(30, 11900, 12200), seg(50, 12200, 12100)]
  },
  "annotations": [
    {"t": "2026-08-18T15:02:00Z", "text": "kafka rolling broker restart begins"},
    {"t": "2026-08-18T15:38:00Z", "text": "broker restart complete; consumer group rebalanced and recovered"},
    {"t": "2026-08-18T16:05:00Z", "text": "deploy dep-9140: pricing-publisher 5.0.0 (price feed v5)"},
    {"t": "2026-08-18T16:48:00Z", "text": "alert fired"}
  ],
  "extra": {"note": "The consumer is reading and committing at full rate. What collapsed is the number of "
                    "messages that survive deserialisation and reach postgres-pricing."}
},
"log": {"svc": "pricing-consumer", "format": "json", "start": "2026-08-18T15:44:00Z", "end": "2026-08-18T16:52:00Z",
  "lines": 340,
  "phases": [
    {"until": 0.30, "noise": kafka_noise("catalog.price.v1", "pricing-consumer") + [
          (16, "INFO", "price applied", {"sku": "{sku}", "price_cents": "{n}499", "schema_version": 6}),
          (4, "DEBUG", "batch processed", {"records": "{n}0", "duration_ms": "{ms}"}),
          (2, "INFO", "postgres upsert", {"table": "price_current", "rows": "{n}0"}),
        ]},
    {"until": 1.0, "noise": kafka_noise("catalog.price.v1", "pricing-consumer") + [
          (10, "ERROR", "record sent to dlq", {"topic": "catalog.price.v1", "partition": "{n}",
                                               "offset": "4{n}83221", "reason": "deserialization"}),
          (6, "INFO", "price applied", {"sku": "{sku}", "price_cents": "{n}499", "schema_version": 6}),
          (4, "WARN", "batch partially failed", {"records": "{n}0", "failed": "{n}0"}),
          (2, "DEBUG", "batch processed", {"records": "{n}0", "duration_ms": "{ms}"}),
        ]}
  ],
  "signals": [
    {"at": 120, "level": "WARN", "msg": "coordinator unavailable, rejoining group",
     "kv": {"group": "pricing-consumer", "broker": "kafka-3", "cause": "broker restart"}, "repeat": 5, "every": 20},
    {"at": 240, "level": "INFO", "msg": "group rebalance complete, partitions assigned",
     "kv": {"group": "pricing-consumer", "assigned": 12, "members": 4, "generation": 119}},
    {"at": 320, "level": "INFO", "msg": "lag recovered after rebalance", "kv": {"lag": 1180, "group": "pricing-consumer"}},
    {"at": 1260, "level": "INFO", "msg": "schema registry lookup",
     "kv": {"subject": "catalog.price.v1-value", "writer_version": 7, "reader_version": 6,
            "compatibility": "NONE"}, "repeat": 4, "every": 120},
    {"at": 1300, "level": "ERROR", "msg": "failed to deserialize record",
     "kv": {"topic": "catalog.price.v1", "partition": "{n}", "offset": "4{n}83244",
            "error": "Cannot deserialize value of type `int` from String \"12.99\": not a valid Integer value",
            "field": "price_cents", "writer_schema": 7, "reader_schema": 6},
     "repeat": 30, "every": 22,
     "cont": ["\tat com.fasterxml.jackson.databind.exc.InvalidFormatException.from(InvalidFormatException.java:67)",
              "\tat com.acme.pricing.PriceEventDeserializer.deserialize(PriceEventDeserializer.java:58)",
              "\tat com.acme.pricing.PricingConsumer.poll(PricingConsumer.java:131)"]},
    {"at": 1340, "level": "WARN", "msg": "unknown field in payload, ignoring",
     "kv": {"field": "promotion", "topic": "catalog.price.v1", "reader_schema": 6}, "repeat": 12, "every": 40},
    {"at": 1400, "level": "ERROR", "msg": "record sent to dlq",
     "kv": {"topic": "catalog.price.v1", "dlq": "pricing.dlq", "reason": "deserialization",
            "sample_payload": "{\"sku\":\"SKU-40218\",\"price_cents\":\"12.99\",\"currency\":\"USD\",\"promotion\":null}"},
     "repeat": 20, "every": 30},
    {"at": 1500, "level": "INFO", "msg": "offsets committed despite failures (dlq policy = commit_and_continue)",
     "kv": {"group": "pricing-consumer", "committed": "4{n}83400", "failed_in_batch": "{n}0"},
     "repeat": 8, "every": 90},
    {"at": 2000, "level": "WARN", "msg": "downstream freshness degraded",
     "kv": {"table": "price_current", "rows_updated_last_10m": 2140, "expected": 120000,
            "oldest_stale_sku_age_min": "{n}"}, "repeat": 5, "every": 200},
    {"at": 2400, "level": "INFO", "msg": "producer identity for recent offsets",
     "kv": {"topic": "catalog.price.v1", "producer_app": "pricing-publisher", "producer_version": "5.0.0",
            "first_seen": "2026-08-18T16:06:11Z"}, "repeat": 2, "every": 300},
  ]}
})
