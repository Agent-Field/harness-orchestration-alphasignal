from banks import http_noise, jvm_noise, k8s_noise, kafka_noise
from gen import seg

SPECS = []

# ============================================================ inc-005 =========
SPECS.append({
"id": "inc-005", "seed": 1005,
"readme": """
# inc-005 — shipping-rates-api timing out at the checkout step

11:20 UTC on a Tuesday, the busiest hour of the European day. `shipping-rates-api` is returning
504 to about a fifth of calls, and because the checkout page blocks on a rate quote, customers
see a spinner and then an error. The service fans out to four carrier APIs and returns the
cheapest option. Its own CPU is high and its worker threads are all busy, which makes it look
saturated. A change went out this morning that touched the rate cache. The rate of incoming
requests is normal for the hour.
""",
"alert": {
  "alert_id": "alt-2026-07-21-1120-shipping",
  "monitor_name": "shipping-rates-api :: 504 rate > 5% (5m)",
  "monitor_id": "mon-1533", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-07-21T11:20:00Z", "detected_change_at": "2026-07-21T11:12:00Z",
  "threshold": {"metric": "http.server.504_rate", "comparator": ">", "value": 5.0, "unit": "%", "window": "5m"},
  "observed_value": 21.4,
  "service": "shipping-rates-api", "environment": "prod", "region": "eu-west-1",
  "notified": ["oncall-fulfilment"], "runbook": "https://runbooks.internal/shipping-rates/timeouts",
  "tags": ["tier:1", "team:fulfilment", "revenue-path"]
},
"deploys": {"lookback_hours": 24, "events": [
  {"id": "dep-5510", "at": "2026-07-21T08:55:00Z", "kind": "deploy", "service": "shipping-rates-api",
   "version": "3.3.1", "actor": "lmoreau", "change": "raise rate-cache TTL 60s -> 300s to cut carrier spend",
   "diff_summary": "RateCache.kt +9/-3; application.yml: cache.ttl 60 -> 300"},
  {"id": "dep-5514", "at": "2026-07-21T10:40:00Z", "kind": "deploy", "service": "web-frontend",
   "version": "2026.7.21-1", "actor": "jtan", "change": "shipping selector UI"},
  {"id": "vendor-note-88", "at": "2026-07-21T11:14:00Z", "kind": "vendor_status", "service": "carrier-b-api",
   "actor": "statuspage-webhook",
   "change": "carrier-b status page: 'Investigating elevated API latency in EU region' (investigating)"}
]},
"topology": {
  "root": "shipping-rates-api",
  "nodes": [
    {"id": "checkout-api", "kind": "service", "team": "payments"},
    {"id": "shipping-rates-api", "kind": "service", "team": "fulfilment", "runtime": "jvm-21", "replicas": 6,
     "worker_threads": 200, "request_timeout_ms": 9000},
    {"id": "carrier-a-api", "kind": "third_party", "vendor": "carrier-a", "share_of_quotes": 0.31, "timeout_ms": 6000},
    {"id": "carrier-b-api", "kind": "third_party", "vendor": "carrier-b", "share_of_quotes": 0.44, "timeout_ms": 6000,
     "retries": 3, "retry_backoff": "none"},
    {"id": "carrier-c-api", "kind": "third_party", "vendor": "carrier-c", "share_of_quotes": 0.18, "timeout_ms": 6000},
    {"id": "carrier-d-api", "kind": "third_party", "vendor": "carrier-d", "share_of_quotes": 0.07, "timeout_ms": 6000},
    {"id": "redis-rates", "kind": "cache", "team": "fulfilment"}
  ],
  "edges": [
    {"from": "checkout-api", "to": "shipping-rates-api", "protocol": "http", "timeout_ms": 10000},
    {"from": "shipping-rates-api", "to": "carrier-a-api", "protocol": "https", "circuit_breaker": True},
    {"from": "shipping-rates-api", "to": "carrier-b-api", "protocol": "https", "circuit_breaker": False,
     "note": "breaker disabled 2026-03 after false trips"},
    {"from": "shipping-rates-api", "to": "carrier-c-api", "protocol": "https", "circuit_breaker": True},
    {"from": "shipping-rates-api", "to": "carrier-d-api", "protocol": "https", "circuit_breaker": True},
    {"from": "shipping-rates-api", "to": "redis-rates", "protocol": "resp"}
  ],
  "notes": "A quote fans out to all four carriers and waits for all of them. One slow carrier stalls the whole quote."
},
"metrics": {"service": "shipping-rates-api", "start": "2026-07-21T10:50:00Z", "step_seconds": 60,
  "units": {"latency_p99_ms": "ms", "worker_threads_busy": "threads"},
  "series": {
    "latency_p50_ms": [seg(20, 210, 240), seg(6, 240, 5400), seg(14, 5400, 8700)],
    "latency_p99_ms": [seg(20, 700, 780), seg(6, 780, 9000), seg(14, 9000, 9600, 0.01)],
    "error_rate_504_pct": [seg(20, 0.2, 0.3), seg(6, 0.3, 12.0), seg(14, 12.0, 23.0)],
    "rps": [seg(20, 420, 440), seg(20, 440, 431)],
    "cpu_pct": [seg(20, 34, 37), seg(6, 37, 71), seg(14, 71, 78)],
    "mem_pct": [seg(20, 52, 53), seg(20, 53, 58)],
    "worker_threads_busy": [seg(20, 24, 30), seg(6, 30, 186), seg(14, 186, 200, 0.01)],
    "carrier_a_p99_ms": [seg(20, 430, 460), seg(20, 460, 470)],
    "carrier_b_p99_ms": [seg(20, 510, 560), seg(6, 560, 8900), seg(14, 8900, 12000)],
    "carrier_c_p99_ms": [seg(20, 380, 400), seg(20, 400, 410)],
    "carrier_d_p99_ms": [seg(20, 620, 640), seg(20, 640, 655)],
    "carrier_b_outbound_rps": [seg(20, 190, 196), seg(6, 196, 610), seg(14, 610, 780)],
    "rate_cache_hit_pct": [seg(20, 61, 74), seg(20, 74, 76)]
  },
  "annotations": [
    {"t": "2026-07-21T08:55:00Z", "text": "deploy dep-5510: rate cache TTL 60s -> 300s"},
    {"t": "2026-07-21T11:12:00Z", "text": "504s begin"},
    {"t": "2026-07-21T11:14:00Z", "text": "carrier-b status page: investigating elevated EU latency"}
  ]},
"log": {"svc": "shipping-rates-api", "format": "logfmt", "start": "2026-07-21T10:56:00Z", "end": "2026-07-21T11:26:00Z",
  "lines": 310,
  "phases": [
    {"until": 0.52, "noise": http_noise(["/v1/rates", "/v1/rates/bulk", "/healthz"],
        extra=[
          (14, "INFO", "quote returned", {"carriers": 4, "cheapest": "carrier-b", "duration_ms": "{ms}", "req_id": "{rid}"}),
          (5, "DEBUG", "rate cache hit", {"key": "rates:eu:{sku}", "ttl_left_s": "2{n}0"}),
          (4, "INFO", "carrier call ok", {"carrier": "carrier-a", "duration_ms": "4{n}0", "status": 200}),
          (4, "INFO", "carrier call ok", {"carrier": "carrier-b", "duration_ms": "5{n}0", "status": 200}),
          (3, "INFO", "carrier call ok", {"carrier": "carrier-c", "duration_ms": "3{n}0", "status": 200}),
        ])},
    {"until": 1.0, "noise": [
          (10, "INFO", "carrier call ok", {"carrier": "carrier-a", "duration_ms": "4{n}0", "status": 200}),
          (8, "INFO", "carrier call ok", {"carrier": "carrier-c", "duration_ms": "3{n}0", "status": 200}),
          (5, "INFO", "carrier call ok", {"carrier": "carrier-d", "duration_ms": "6{n}0", "status": 200}),
          (12, "WARN", "quote degraded", {"carriers_ok": 3, "carriers_failed": 1, "duration_ms": "9{n}01", "req_id": "{rid}"}),
          (5, "ERROR", "quote timed out", {"status": 504, "duration_ms": 9001, "req_id": "{rid}"}),
          (3, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
        ]}
  ],
  "signals": [
    {"at": 540, "level": "INFO", "msg": "rate cache configured", "kv": {"ttl_s": 300, "prev_ttl_s": 60, "build": "3.3.1"}},
    {"at": 960, "level": "WARN", "msg": "carrier call slow",
     "kv": {"carrier": "carrier-b", "duration_ms": "5{n}12", "status": 200, "endpoint": "https://api.carrier-b.example/v3/rates"},
     "repeat": 10, "every": 14},
    {"at": 1020, "level": "ERROR", "msg": "carrier call failed",
     "kv": {"carrier": "carrier-b", "duration_ms": 6001, "error": "read timeout after 6000ms",
            "endpoint": "https://api.carrier-b.example/v3/rates", "attempt": 1, "req_id": "{rid}"},
     "repeat": 24, "every": 24},
    {"at": 1030, "level": "WARN", "msg": "retrying carrier call immediately (no backoff configured)",
     "kv": {"carrier": "carrier-b", "attempt": 2, "max_attempts": 3, "req_id": "{rid}"}, "repeat": 20, "every": 27},
    {"at": 1080, "level": "WARN", "msg": "carrier returned 503",
     "kv": {"carrier": "carrier-b", "status": 503, "body_snippet": "upstream capacity exceeded, retry later",
            "retry_after_s": 30}, "repeat": 12, "every": 40},
    {"at": 1140, "level": "WARN", "msg": "worker pool saturated",
     "kv": {"busy": 198, "max": 200, "queue": "{n}2", "dominant_stack": "CarrierBClient.fetchRates"},
     "repeat": 8, "every": 60},
    {"at": 1200, "level": "INFO", "msg": "circuit breaker state",
     "kv": {"carrier-a": "closed", "carrier-b": "disabled", "carrier-c": "closed", "carrier-d": "closed"},
     "repeat": 3, "every": 150},
    {"at": 1260, "level": "ERROR", "msg": "quote timed out",
     "kv": {"status": 504, "waiting_on": "carrier-b", "elapsed_ms": 9001, "req_id": "{rid}"}, "repeat": 16, "every": 22},
  ]}
})

# ============================================================ inc-006 =========
SPECS.append({
"id": "inc-006", "seed": 1006,
"readme": """
# inc-006 — product-catalog database on fire at 04:12

04:16 UTC. The page is for `postgres-catalog`: CPU pinned at 100%, and `product-catalog-api`
p99 has gone from 40ms to several seconds. The database is a large managed instance that
normally sits at ten percent utilisation, so the graph is dramatic and the obvious reading is
that something is hammering the database. Overnight there is a bot crawler that ramps up around
this hour, and the DBA channel has a long-running thread about a missing index on `product_variant`.
There was a routine release at 04:10. Read volume at the API edge is close to flat.
""",
"alert": {
  "alert_id": "alt-2026-06-18-0416-catalogdb",
  "monitor_name": "postgres-catalog :: cpu > 90% (3m)",
  "monitor_id": "mon-0918", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-06-18T04:16:00Z", "detected_change_at": "2026-06-18T04:11:00Z",
  "threshold": {"metric": "rds.cpu_utilization", "comparator": ">", "value": 90, "unit": "%", "window": "3m"},
  "observed_value": 99.7,
  "secondary_conditions": [
    {"metric": "product-catalog-api.http.server.duration.p99", "comparator": ">", "value": 1000,
     "unit": "ms", "observed": 6400}
  ],
  "service": "product-catalog-api", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-catalog", "oncall-dba"], "runbook": "https://runbooks.internal/postgres/high-cpu",
  "tags": ["tier:1", "team:catalog"]
},
"deploys": {"lookback_hours": 24, "events": [
  {"id": "dep-8801", "at": "2026-06-17T16:22:00Z", "kind": "deploy", "service": "product-catalog-api",
   "version": "7.4.0", "actor": "abenali", "change": "add colour-family facet to product response"},
  {"id": "dep-8814", "at": "2026-06-18T04:10:00Z", "kind": "deploy", "service": "product-catalog-api",
   "version": "7.4.1", "actor": "abenali",
   "change": "chore: bump cache key namespace after response shape change",
   "diff_summary": "CacheKeys.kt: NAMESPACE = \"pcat:v7\" -> \"pcat:v8\"  (1 line)",
   "review_note": "approved as no-op, 1-line change, canary skipped"},
  {"id": "dep-8815", "at": "2026-06-18T04:14:00Z", "kind": "config", "service": "crawler-allowlist",
   "actor": "seo-bot", "change": "raise crawl budget for partner bot 40 rps -> 60 rps"}
]},
"topology": {
  "root": "product-catalog-api",
  "nodes": [
    {"id": "edge-proxy", "kind": "gateway", "team": "platform"},
    {"id": "product-catalog-api", "kind": "service", "team": "catalog", "runtime": "jvm-21", "replicas": 20},
    {"id": "redis-catalog", "kind": "cache", "team": "catalog", "maxmemory_gb": 32,
     "keyspace": "pcat:v7:* (14.2M keys)", "eviction": "allkeys-lru"},
    {"id": "postgres-catalog", "kind": "database", "team": "catalog", "instance": "db.r6g.4xlarge",
     "vcpu": 16, "baseline_cpu_pct": 11}
  ],
  "edges": [
    {"from": "edge-proxy", "to": "product-catalog-api", "protocol": "http", "timeout_ms": 8000, "retries": 2},
    {"from": "product-catalog-api", "to": "redis-catalog", "protocol": "resp", "timeout_ms": 120,
     "note": "read-through cache, no request coalescing"},
    {"from": "product-catalog-api", "to": "postgres-catalog", "protocol": "jdbc", "pool_max_size": 25,
     "note": "20 replicas x 25 = 500 possible connections"}
  ],
  "notes": "Steady state: 97% of catalog reads are served from redis-catalog and never reach postgres."
},
"metrics": {"service": "product-catalog-api", "start": "2026-06-18T03:56:00Z", "step_seconds": 60,
  "units": {"db_cpu_pct": "%", "cache_hit_pct": "%", "db_qps": "queries/s"},
  "series": {
    "edge_rps": [seg(14, 880, 940), seg(6, 940, 980), seg(20, 980, 1010)],
    "latency_p99_ms": [seg(14, 38, 44), seg(6, 44, 3900), seg(20, 3900, 7100)],
    "error_rate_pct": [seg(14, 0.02, 0.03), seg(6, 0.03, 2.2), seg(20, 2.2, 11.4)],
    "cache_hit_pct": [seg(14, 97.1, 97.4, 0.005), seg(2, 97.4, 3.0), seg(24, 3.0, 22.0)],
    "cache_keys_millions": [seg(14, 14.2, 14.2, 0.002), seg(2, 14.2, 0.02), seg(24, 0.02, 1.9)],
    "db_cpu_pct": [seg(14, 10, 12), seg(6, 12, 99), seg(20, 99, 100, 0.005)],
    "db_qps": [seg(14, 240, 260), seg(6, 260, 9400), seg(20, 9400, 11200)],
    "db_active_connections": [seg(14, 22, 26), seg(6, 26, 480), seg(20, 480, 500, 0.01)],
    "db_query_p99_ms": [seg(14, 6, 7), seg(6, 7, 2400), seg(20, 2400, 5100)],
    "crawler_rps": [seg(14, 38, 41), seg(6, 41, 58), seg(20, 58, 60, 0.02)],
    "app_cpu_pct": [seg(14, 29, 31), seg(6, 31, 62), seg(20, 62, 70)],
    "edge_retry_rps": [seg(14, 2, 3), seg(6, 3, 190), seg(20, 190, 420)]
  },
  "annotations": [
    {"t": "2026-06-18T04:10:00Z", "text": "deploy dep-8814: product-catalog-api 7.4.1"},
    {"t": "2026-06-18T04:14:00Z", "text": "config dep-8815: crawler budget 40 -> 60 rps"},
    {"t": "2026-06-18T04:16:00Z", "text": "alert fired"}
  ],
  "extra": {"note": "redis-catalog memory used dropped from 27.4GB to 0.3GB between 04:10 and 04:12 with "
                    "zero evictions recorded and no restart; it then began refilling under a new key prefix."}
},
"log": {"svc": "product-catalog-api", "format": "json", "start": "2026-06-18T04:00:00Z", "end": "2026-06-18T04:26:00Z",
  "lines": 350,
  "phases": [
    {"until": 0.38, "noise": http_noise(["/v1/products", "/v1/products/{sku}", "/v1/facets", "/healthz"],
        extra=[
          (18, "INFO", "product fetched", {"sku": "{sku}", "source": "cache", "duration_ms": "{n}", "trace_id": "{tid}"}),
          (3, "INFO", "product fetched", {"sku": "{sku}", "source": "db", "duration_ms": "{ms}", "trace_id": "{tid}"}),
          (3, "DEBUG", "cache get", {"key": "pcat:v7:sku:{sku}", "hit": "true"}),
          (2, "INFO", "crawler request", {"ua": "PartnerBot/1.4", "path": "/v1/products", "status": 200}),
        ])},
    {"until": 1.0, "noise": [
          (18, "INFO", "product fetched", {"sku": "{sku}", "source": "db", "duration_ms": "2{n}40", "trace_id": "{tid}"}),
          (8, "DEBUG", "cache get", {"key": "pcat:v8:sku:{sku}", "hit": "false"}),
          (6, "WARN", "db call slow", {"query": "select_product_by_sku", "duration_ms": "3{n}12", "sku": "{sku}"}),
          (4, "ERROR", "request failed", {"status": 503, "cause": "JdbcConnectionTimeout", "trace_id": "{tid}"}),
          (2, "INFO", "crawler request", {"ua": "PartnerBot/1.4", "path": "/v1/products", "status": 503}),
        ]}
  ],
  "signals": [
    {"at": 500, "level": "INFO", "msg": "rolling update started", "kv": {"version": "7.4.1", "strategy": "rolling",
     "max_surge": 4, "replicas": 20, "deploy_id": "dep-8814"}},
    {"at": 600, "level": "INFO", "msg": "cache namespace in use", "kv": {"namespace": "pcat:v8", "previous": "pcat:v7",
     "prewarm": "false"}, "repeat": 4, "every": 20},
    {"at": 660, "level": "WARN", "msg": "cache miss ratio above threshold",
     "kv": {"window_s": 60, "hit_pct": 3.1, "expected_pct": 97.0}, "repeat": 8, "every": 60},
    {"at": 690, "level": "WARN", "msg": "concurrent identical cache fills for same key",
     "kv": {"key": "pcat:v8:sku:{sku}", "inflight": "{n}8", "coalescing": "disabled"}, "repeat": 14, "every": 34},
    {"at": 720, "level": "WARN", "msg": "db call slow",
     "kv": {"query": "select_product_by_sku", "duration_ms": "1{n}40", "rows": 1, "sku": "{sku}"},
     "repeat": 20, "every": 22},
    {"at": 780, "level": "WARN", "msg": "seq scan detected by pg_stat_statements sampler",
     "kv": {"table": "product_variant", "calls_last_min": 4120, "mean_ms": 61,
            "note": "known missing index PCAT-1187, open since 2026-04"}, "repeat": 5, "every": 90},
    {"at": 840, "level": "ERROR", "msg": "connection pool timeout",
     "kv": {"pool": "catalog-pg", "active": 25, "idle": 0, "waiting": "{n}1", "timeout_ms": 5000},
     "repeat": 18, "every": 30},
    {"at": 900, "level": "WARN", "msg": "edge retry received for already-inflight request",
     "kv": {"path": "/v1/products", "retry_attempt": 2, "trace_id": "{tid}"}, "repeat": 16, "every": 28},
    {"at": 960, "level": "INFO", "msg": "redis info snapshot",
     "kv": {"used_memory_gb": 0.4, "keys": 118422, "evicted_keys_total": 0, "uptime_days": 63,
            "connected_clients": 220}, "repeat": 4, "every": 120},
    {"at": 1020, "level": "INFO", "msg": "crawler budget updated by config change",
     "kv": {"ua": "PartnerBot/1.4", "rps_limit": 60, "previous": 40}},
  ]}
})

# ============================================================ inc-007 =========
SPECS.append({
"id": "inc-007", "seed": 1007,
"readme": """
# inc-007 — intermittent connection failures, several services, one availability zone

04:02 UTC. Three separate monitors fired within ninety seconds of each other: `orders-service`
error rate, `cart-api` error rate, and `notification-worker` job failures. The errors are
intermittent rather than total, roughly one call in ten, and they come and go. Most of the
error text points at `orders-service`, so the orders team has been paged and is looking at
their own dashboards, where everything appears healthy. They shipped a release yesterday
evening. Platform is in the middle of a rolling kernel patch across the fleet tonight.
""",
"alert": {
  "alert_id": "alt-2026-08-09-0402-orders",
  "monitor_name": "orders-service :: client error rate > 3% (2m)",
  "monitor_id": "mon-1301", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-08-09T04:02:00Z", "detected_change_at": "2026-08-09T03:58:00Z",
  "threshold": {"metric": "client.request.error_rate", "comparator": ">", "value": 3.0, "unit": "%", "window": "2m"},
  "observed_value": 11.2,
  "correlated_alerts": [
    {"alert_id": "alt-2026-08-09-0402-cart", "monitor_name": "cart-api :: error rate > 3%", "fired_at": "2026-08-09T04:02:30Z"},
    {"alert_id": "alt-2026-08-09-0403-notif", "monitor_name": "notification-worker :: job failure rate > 5%", "fired_at": "2026-08-09T04:03:10Z"}
  ],
  "service": "orders-service", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-orders"], "runbook": "https://runbooks.internal/orders/error-rate",
  "tags": ["tier:1", "team:orders"]
},
"deploys": {"lookback_hours": 24, "events": [
  {"id": "dep-6602", "at": "2026-08-08T19:15:00Z", "kind": "deploy", "service": "orders-service",
   "version": "12.6.0", "actor": "kbrandt", "change": "add idempotency key to order submission"},
  {"id": "dep-6610", "at": "2026-08-09T03:40:00Z", "kind": "maintenance", "service": "node-pool/general-1",
   "actor": "platform-bot",
   "change": "rolling kernel patch: cordon+drain nodes one at a time (12 nodes, ~8 min each)",
   "diff_summary": "drained general-1-d at 03:50Z; general-1-e queued"},
  {"id": "dep-6611", "at": "2026-08-09T03:52:00Z", "kind": "config", "service": "cart-api",
   "actor": "ci-bot", "change": "bump HTTP client connect timeout 500ms -> 800ms"}
]},
"topology": {
  "root": "orders-service",
  "nodes": [
    {"id": "cart-api", "kind": "service", "team": "checkout", "zone_spread": ["us-east-1a", "us-east-1b", "us-east-1c"]},
    {"id": "orders-service", "kind": "service", "team": "orders", "replicas": 12,
     "zone_spread": ["us-east-1a", "us-east-1b", "us-east-1c"]},
    {"id": "notification-worker", "kind": "worker", "team": "growth"},
    {"id": "coredns", "kind": "platform", "team": "platform", "replicas_desired": 2, "replicas_ready": 1,
     "node_pool": "general-1", "anti_affinity": "requiredDuringScheduling (one per node)",
     "qps_limit_per_pod": 1000},
    {"id": "postgres-orders", "kind": "database", "team": "orders"},
    {"id": "node/general-1-d", "kind": "node", "zone": "us-east-1a", "state": "drained 03:50Z (kernel patch)"},
    {"id": "node/general-1-e", "kind": "node", "zone": "us-east-1a", "state": "Ready, cpu allocatable exhausted"}
  ],
  "edges": [
    {"from": "cart-api", "to": "orders-service", "protocol": "http", "resolves_via": "coredns",
     "dns_ndots": 5, "search_domains": ["prod.svc.cluster.local", "svc.cluster.local", "cluster.local", "ec2.internal"]},
    {"from": "notification-worker", "to": "orders-service", "protocol": "http", "resolves_via": "coredns"},
    {"from": "orders-service", "to": "postgres-orders", "protocol": "jdbc", "resolves_via": "coredns",
     "note": "connection established at startup, long-lived"}
  ],
  "notes": "coredns runs 2 replicas with required anti-affinity. Pods that already hold a connection are unaffected; "
           "new connections require a fresh lookup."
},
"metrics": {"service": "orders-service", "start": "2026-08-09T03:35:00Z", "step_seconds": 60,
  "units": {"error_rate_pct": "%", "dns_lookup_p99_ms": "ms", "coredns_ready_replicas": "pods"},
  "series": {
    "caller_error_rate_pct": [seg(15, 0.1, 0.15), seg(8, 0.15, 9.8), seg(17, 9.8, 12.6)],
    "server_error_rate_pct": [seg(15, 0.09, 0.11), seg(25, 0.11, 0.13)],
    "server_latency_p99_ms": [seg(15, 88, 94), seg(25, 94, 97)],
    "server_rps": [seg(15, 340, 348), seg(8, 348, 306), seg(17, 306, 298)],
    "cpu_pct": [seg(15, 27, 29), seg(25, 29, 26)],
    "mem_pct": [seg(15, 44, 45), seg(25, 45, 45)],
    "dns_lookup_p99_ms": [seg(15, 3, 4), seg(8, 4, 5100), seg(17, 5100, 5100, 0.01)],
    "dns_nxdomain_per_min": [seg(15, 0, 1), seg(8, 1, 640), seg(17, 640, 810)],
    "coredns_ready_replicas": [seg(15, 2, 2, 0.0), seg(1, 2, 1, 0.0), seg(24, 1, 1, 0.0)],
    "coredns_qps_per_pod": [seg(15, 470, 490), seg(1, 490, 1010), seg(24, 1010, 1040, 0.01)],
    "db_query_p99_ms": [seg(15, 6, 7), seg(25, 7, 7)]
  },
  "annotations": [
    {"t": "2026-08-09T03:50:00Z", "text": "node general-1-d cordoned and drained (kernel patch)"},
    {"t": "2026-08-09T03:52:00Z", "text": "config dep-6611: cart-api connect timeout 500 -> 800ms"},
    {"t": "2026-08-09T04:02:00Z", "text": "alerts fired (orders, cart, notification)"}
  ],
  "extra": {"note": "orders-service server-side metrics are healthy. The error rate is measured by its callers. "
                    "Requests that fail never reach orders-service at all."}
},
"log": {"svc": "cart-api", "format": "logfmt", "start": "2026-08-09T03:44:00Z", "end": "2026-08-09T04:10:00Z",
  "lines": 340,
  "phases": [
    {"until": 0.30, "noise": http_noise(["/v1/cart", "/v1/cart/items", "/healthz"],
        extra=[
          (14, "INFO", "downstream call ok", {"target": "orders-service", "duration_ms": "{ms}", "status": 200, "trace_id": "{tid}"}),
          (4, "DEBUG", "dns resolved", {"name": "orders-service.prod.svc.cluster.local", "ttl_s": 30, "duration_ms": 2}),
          (3, "INFO", "cart updated", {"user_id": "{uid}", "items": "{n}"}),
        ])},
    {"until": 1.0, "noise": [
          (14, "INFO", "downstream call ok", {"target": "orders-service", "duration_ms": "{ms}", "status": 200, "trace_id": "{tid}"}),
          (6, "ERROR", "downstream call failed", {"target": "orders-service", "error": "connect: no such host",
                                                  "duration_ms": "5{n}03", "trace_id": "{tid}"}),
          (4, "WARN", "retrying downstream call", {"target": "orders-service", "attempt": 2, "trace_id": "{tid}"}),
          (3, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
          (2, "INFO", "cart updated", {"user_id": "{uid}", "items": "{n}"}),
        ]}
  ],
  "signals": [
    {"at": 360, "level": "INFO", "msg": "node cordoned for maintenance", "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-1-d", "proc": "kubelet", "reason": "kernel-patch", "taint": "node.kubernetes.io/unschedulable"}},
    {"at": 375, "level": "INFO", "msg": "evicting pod", "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-1-d", "proc": "kubelet", "pod": "coredns-6f7b8c9d4-tq2xz", "grace_s": 30}},
    {"at": 395, "level": "WARN", "msg": "pod unschedulable", "format": "syslog", "svc": "kube-scheduler",
     "kv": {"host": "control-plane-1", "proc": "kube-scheduler", "pod": "coredns-6f7b8c9d4-9v4mn",
            "reason": "0/12 nodes are available: 3 node(s) didn't match pod anti-affinity rules, 9 Insufficient cpu"},
     "repeat": 9, "every": 62},
    {"at": 420, "level": "WARN", "msg": "dns lookup slow",
     "kv": {"name": "orders-service.prod.svc.cluster.local", "duration_ms": "1{n}04", "server": "10.96.0.10"},
     "repeat": 14, "every": 22},
    {"at": 600, "level": "ERROR", "msg": "dns lookup failed",
     "kv": {"name": "orders-service.prod.svc.cluster.local", "server": "10.96.0.10",
            "error": "i/o timeout after 5000ms", "search_attempts": 4, "trace_id": "{tid}"},
     "repeat": 26, "every": 26},
    {"at": 620, "level": "ERROR", "msg": "dial tcp: lookup orders-service.prod.svc.cluster.local on 10.96.0.10:53: no such host",
     "kv": {"target": "orders-service", "trace_id": "{tid}", "attempt": 3}, "repeat": 18, "every": 30},
    {"at": 700, "level": "WARN", "msg": "coredns request throttled", "format": "syslog", "svc": "coredns",
     "kv": {"host": "general-1-b", "proc": "coredns", "qps": 1024, "limit": 1000, "dropped": "{n}2"},
     "repeat": 12, "every": 55},
    {"at": 840, "level": "INFO", "msg": "http client connect timeout updated",
     "kv": {"from_ms": 500, "to_ms": 800, "source": "configmap cart-api-env"}},
    {"at": 900, "level": "INFO", "msg": "long-lived connection reused, no resolution needed",
     "kv": {"target": "postgres-orders", "age_s": "8{n}40"}, "repeat": 4, "every": 130},
    {"at": 960, "level": "ERROR", "msg": "job failed", "svc": "notification-worker",
     "kv": {"job": "order_confirmation", "error": "lookup orders-service.prod.svc.cluster.local: no such host",
            "attempt": 3, "order_id": "{oid}"}, "repeat": 10, "every": 42},
  ]}
})

# ============================================================ inc-008 =========
SPECS.append({
"id": "inc-008", "seed": 1008,
"readme": """
# inc-008 — notification-worker keeps getting killed

07:41 UTC. `notification-worker` pods have restarted eleven times in the last half hour and the
restart-loop monitor has paged. The exit reason is OOMKilled. Notification volume is at its
usual weekday-morning peak, roughly double the overnight floor, and the obvious story is that
the morning send is simply too big for the memory limit. A sibling service shipped this morning,
and a colleague has already suggested doubling the memory limit and moving on. The queue behind
the worker is backing up while it restarts.
""",
"alert": {
  "alert_id": "alt-2026-07-15-0741-notif",
  "monitor_name": "notification-worker :: container restarts > 3 in 30m",
  "monitor_id": "mon-1620", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-07-15T07:41:00Z", "detected_change_at": "2026-07-15T07:12:00Z",
  "threshold": {"metric": "kube.container.restarts", "comparator": ">", "value": 3, "unit": "count", "window": "30m"},
  "observed_value": 11,
  "secondary_conditions": [
    {"metric": "kube.container.last_terminated_reason", "comparator": "==", "value": "OOMKilled", "observed": "OOMKilled"}
  ],
  "service": "notification-worker", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-growth"], "runbook": "https://runbooks.internal/notification-worker/oom",
  "tags": ["tier:2", "team:growth"]
},
"deploys": {"lookback_hours": 336, "events": [
  {"id": "dep-2201", "at": "2026-07-06T13:05:00Z", "kind": "deploy", "service": "notification-worker",
   "version": "5.2.0", "actor": "pnwosu",
   "change": "per-recipient template personalisation; add render metrics hook",
   "diff_summary": "TemplateRenderer.ts +148/-22; metrics.ts +37/-0; RecipientContext.ts +64/-3",
   "review_note": "metrics hook registers a listener per render call on the shared emitter"},
  {"id": "dep-2244", "at": "2026-07-10T09:30:00Z", "kind": "config", "service": "notification-worker",
   "actor": "platform-bot", "change": "memory limit 1Gi -> 1.5Gi (capacity planning sweep)"},
  {"id": "dep-2301", "at": "2026-07-14T17:44:00Z", "kind": "deploy", "service": "template-service",
   "version": "2.8.0", "actor": "hkim", "change": "new promo template family"},
  {"id": "dep-2309", "at": "2026-07-15T06:55:00Z", "kind": "deploy", "service": "email-gateway",
   "version": "3.1.2", "actor": "release-train", "change": "switch SMTP pool to keepalive connections"}
]},
"topology": {
  "root": "notification-worker",
  "nodes": [
    {"id": "kafka/notifications", "kind": "queue", "team": "platform", "partitions": 24},
    {"id": "notification-worker", "kind": "worker", "team": "growth", "runtime": "node-22", "replicas": 6,
     "memory_limit": "1.5Gi", "memory_request": "768Mi", "restart_policy": "Always"},
    {"id": "template-service", "kind": "service", "team": "growth"},
    {"id": "email-gateway", "kind": "service", "team": "growth"},
    {"id": "postgres-users", "kind": "database", "team": "platform"}
  ],
  "edges": [
    {"from": "kafka/notifications", "to": "notification-worker", "protocol": "kafka", "consumer_group": "notif-w"},
    {"from": "notification-worker", "to": "template-service", "protocol": "http", "timeout_ms": 1500},
    {"from": "notification-worker", "to": "email-gateway", "protocol": "http", "timeout_ms": 4000},
    {"from": "notification-worker", "to": "postgres-users", "protocol": "pg", "pool_max_size": 10}
  ],
  "notes": "Worker is stateless per message. Steady-state RSS after a restart is ~410MB."
},
"metrics": {"service": "notification-worker", "start": "2026-07-15T07:00:00Z", "step_seconds": 60,
  "units": {"rss_mb": "MB", "messages_per_min": "msg/min", "consumer_lag": "messages"},
  "series": {
    "rss_mb": [seg(12, 1390, 1490, 0.008), seg(1, 1490, 420, 0.0), seg(9, 420, 1470, 0.008),
               seg(1, 1470, 415, 0.0), seg(9, 415, 1480, 0.008), seg(1, 1480, 430, 0.0),
               seg(9, 430, 1210, 0.008)],
    "messages_per_min": [seg(12, 3100, 3900), seg(10, 3900, 4200), seg(20, 4200, 2600)],
    "consumer_lag": [seg(12, 400, 2200), seg(10, 2200, 26000), seg(20, 26000, 71000)],
    "restarts_total": [seg(12, 0, 3, 0.0), seg(10, 3, 7, 0.0), seg(20, 7, 11, 0.0)],
    "cpu_pct": [seg(12, 38, 44), seg(30, 44, 41)],
    "gc_old_gen_pct": [seg(12, 88, 97), seg(30, 97, 96)],
    "template_service_p99_ms": [seg(12, 120, 128), seg(30, 128, 131)],
    "email_gateway_p99_ms": [seg(12, 300, 290), seg(30, 290, 280)]
  },
  "annotations": [
    {"t": "2026-07-15T06:55:00Z", "text": "deploy dep-2309: email-gateway 3.1.2"},
    {"t": "2026-07-15T07:12:00Z", "text": "first OOMKill of the morning"},
    {"t": "2026-07-15T07:41:00Z", "text": "alert fired"}
  ],
  "extra": {
    "long_window": {
      "description": "daily max RSS per pod, 14 days, MB (one point per day, 2026-07-01 .. 2026-07-14)",
      "rss_mb_daily_max": [402, 409, 398, 411, 405, 407, 512, 641, 763, 889, 1002, 1130, 1268, 1394],
      "memory_limit_mb_daily": [1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1024, 1536, 1536, 1536, 1536, 1536],
      "oomkills_daily": [0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0],
      "messages_per_day_millions": [4.1, 4.0, 4.2, 4.1, 3.9, 2.2, 2.1, 4.2, 4.1, 4.3, 4.2, 4.0, 4.1, 4.2]
    },
    "heap_snapshot_summary": {
      "taken_at": "2026-07-15T07:38:00Z",
      "top_retainers": [
        {"type": "EventEmitter[render]", "count": 1841203, "retained_mb": 812,
         "note": "listeners attached to the module-level metrics emitter"},
        {"type": "RecipientContext", "count": 1841203, "retained_mb": 402},
        {"type": "Buffer", "count": 9120, "retained_mb": 61}
      ]
    }
  }
},
"log": {"svc": "notification-worker", "format": "json", "start": "2026-07-15T07:10:00Z", "end": "2026-07-15T07:45:00Z",
  "lines": 330,
  "phases": [
    {"until": 0.45, "noise": kafka_noise("notifications", "notif-w") + [
          (16, "INFO", "notification sent", {"channel": "email", "template": "order_shipped",
                                             "user_id": "{uid}", "duration_ms": "{ms}"}),
          (5, "INFO", "notification sent", {"channel": "push", "template": "promo_summer",
                                            "user_id": "{uid}", "duration_ms": "{ms}"}),
          (3, "DEBUG", "template rendered", {"template": "order_shipped", "render_ms": "{n}", "personalised": "true"}),
          (2, "INFO", "smtp connection reused", {"gateway": "email-gateway", "keepalive": "true"}),
        ]},
    {"until": 1.0, "noise": kafka_noise("notifications", "notif-w") + [
          (14, "INFO", "notification sent", {"channel": "email", "template": "order_shipped",
                                             "user_id": "{uid}", "duration_ms": "{ms}"}),
          (6, "WARN", "event loop lag", {"lag_ms": "3{n}0"}),
          (4, "WARN", "consumer lag growing", {"topic": "notifications", "lag": "{n}0421"}),
          (3, "DEBUG", "template rendered", {"template": "promo_flash_sale", "render_ms": "{n}"}),
        ]}
  ],
  "signals": [
    {"at": 120, "level": "WARN", "msg": "heap usage high",
     "kv": {"rss_mb": "14{n}", "heap_used_mb": "13{n}", "heap_limit_mb": 1434, "pod": "notification-worker-84cf{pod}"},
     "repeat": 10, "every": 45},
    {"at": 160, "level": "WARN", "msg": "MaxListenersExceededWarning: 11 render listeners added to [EventEmitter]. Use emitter.setMaxListeners() to increase limit",
     "kv": {"emitter": "metricsEmitter", "source": "TemplateRenderer.ts:214", "listeners": "18{n}12"},
     "repeat": 8, "every": 62},
    {"at": 300, "level": "ERROR", "msg": "FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory",
     "kv": {"pod": "notification-worker-84cf{pod}", "rss_mb": 1492},
     "repeat": 3, "every": 480,
     "cont": ["    1: 0xb9a0e0 node::Abort() [node]",
              "    2: 0xaa77f4 node::FatalError(char const*, char const*) [node]",
              "    3: 0xd7b3ba v8::Utils::ReportOOMFailure(v8::internal::Isolate*, char const*, bool) [node]",
              "    4: 0x10f4a25 v8::internal::Heap::CollectGarbage(...) [node]",
              "    5: 0x14f2a19 v8::internal::TemplateRenderer::render(...) [node]"]},
    {"at": 310, "level": "ERROR", "msg": "container terminated", "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-3-b", "proc": "kubelet", "pod": "notification-worker-84cf-2k9dq",
            "reason": "OOMKilled", "exit_code": 137, "restart_count": 4}, "repeat": 3, "every": 480},
    {"at": 330, "level": "INFO", "msg": "worker started",
     "kv": {"version": "5.2.0", "build": "2026-07-06T12:58Z", "rss_mb": "41{n}", "node": "v22.14.0"},
     "repeat": 3, "every": 480},
    {"at": 600, "level": "INFO", "msg": "email-gateway keepalive pool active",
     "kv": {"version": "3.1.2", "pool_size": 32, "reused_pct": 94}, "repeat": 4, "every": 200},
    {"at": 900, "level": "WARN", "msg": "gc pressure",
     "kv": {"type": "mark-sweep", "duration_ms": "8{n}", "freed_mb": "{n}", "heap_after_mb": "13{n}0"},
     "repeat": 12, "every": 55},
    {"at": 1200, "level": "INFO", "msg": "retained object census (debug endpoint)",
     "kv": {"EventEmitter_render_listeners": 1841203, "RecipientContext": 1841203,
            "since_process_start_s": "8{n}1"}, "repeat": 2, "every": 300},
  ]}
})
