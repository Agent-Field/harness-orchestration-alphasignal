from banks import http_noise, jvm_noise, k8s_noise, kafka_noise
from gen import seg

SPECS = []

# ============================================================ inc-001 =========
SPECS.append({
"id": "inc-001", "seed": 1001,
"readme": """
# inc-001 — checkout-api p99 latency and 5xx, overnight

It is 02:44 UTC on a Friday. Your phone goes off: `checkout-api` p99 latency has been over
8 seconds for five straight minutes and the error rate is climbing past 4%. Checkout is the
last screen before money changes hands, so this is a SEV2 the moment it fires. The service
is a JVM app behind the edge proxy; it talks to the orders database, a tax vendor, and the
inventory service. Traffic right now is roughly a third of daytime peak, so nothing about
the load looks alarming on the dashboard. The team shipped things yesterday evening and
again a little before midnight, and there is a database maintenance window that runs most
nights. You have logs, the deploy feed, a metrics snapshot, and the dependency map.
""",
"alert": {
  "alert_id": "alt-2026-08-14-0244-checkout",
  "monitor_name": "checkout-api :: p99 latency > 8s (5m)",
  "monitor_id": "mon-1189",
  "severity": "SEV2", "state": "firing",
  "fired_at": "2026-08-14T02:44:00Z",
  "detected_change_at": "2026-08-14T02:38:00Z",
  "threshold": {"metric": "http.server.duration.p99", "comparator": ">", "value": 8000, "unit": "ms", "window": "5m"},
  "observed_value": 21400,
  "secondary_conditions": [
    {"metric": "http.server.error_rate", "comparator": ">", "value": 2.0, "unit": "%", "observed": 4.6}
  ],
  "service": "checkout-api", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-payments"], "runbook": "https://runbooks.internal/checkout-api/latency",
  "tags": ["tier:1", "team:payments", "revenue-path"]
},
"deploys": {"lookback_hours": 24, "events": [
  {"id": "dep-4463", "at": "2026-08-13T18:04:00Z", "kind": "deploy", "service": "inventory-service",
   "version": "1.22.4", "actor": "hkim", "change": "bump grpc-go, no behaviour change", "rollback_of": None},
  {"id": "dep-4468", "at": "2026-08-13T23:52:00Z", "kind": "deploy", "service": "checkout-api",
   "version": "3.8.2", "actor": "mrivera", "change": "add POST /v2/checkout/quote (tax preview before order create)",
   "diff_summary": "OrderQuoteService.java +214/-6; QuoteController.java +88/-0; application.yml +2/-0"},
  {"id": "dep-4470", "at": "2026-08-14T01:52:00Z", "kind": "config", "service": "checkout-api",
   "actor": "ci-bot", "change": "feature flag checkout_v2_quote rollout 5% -> 100%",
   "diff_summary": "flags/checkout.yaml: checkout_v2_quote.rollout 5 -> 100"},
  {"id": "dep-4471", "at": "2026-08-14T02:32:00Z", "kind": "deploy", "service": "web-frontend",
   "version": "2026.8.13-4", "actor": "jtan", "change": "checkout page CSS + copy tweaks, no API changes",
   "diff_summary": "checkout.module.css +40/-31; en-US.json +6/-6"}
]},
"topology": {
  "root": "checkout-api",
  "nodes": [
    {"id": "edge-proxy", "kind": "gateway", "team": "platform"},
    {"id": "checkout-api", "kind": "service", "team": "payments", "runtime": "jvm-21", "replicas": 6},
    {"id": "postgres-orders", "kind": "database", "team": "payments", "engine": "postgres-15", "max_connections": 400},
    {"id": "inventory-service", "kind": "service", "team": "fulfilment", "replicas": 8},
    {"id": "tax-vendor-api", "kind": "third_party", "vendor": "avalara-like", "sla_p99_ms": 900},
    {"id": "redis-session", "kind": "cache", "team": "platform"}
  ],
  "edges": [
    {"from": "edge-proxy", "to": "checkout-api", "protocol": "http", "timeout_ms": 30000},
    {"from": "checkout-api", "to": "postgres-orders", "protocol": "jdbc", "pool": "HikariPool-1",
     "pool_max_size": 20, "pool_min_idle": 4, "connection_timeout_ms": 30000},
    {"from": "checkout-api", "to": "tax-vendor-api", "protocol": "https", "timeout_ms": 4000, "retries": 2,
     "observed_p99_ms": 2100},
    {"from": "checkout-api", "to": "inventory-service", "protocol": "grpc", "timeout_ms": 1500},
    {"from": "checkout-api", "to": "redis-session", "protocol": "resp", "timeout_ms": 200}
  ],
  "notes": "checkout-api runs 6 replicas x 20 JDBC connections = 120 of 400 postgres slots."
},
"metrics": {"service": "checkout-api", "start": "2026-08-14T02:20:00Z", "step_seconds": 60,
  "units": {"latency_p50_ms": "ms", "latency_p99_ms": "ms", "error_rate_pct": "%", "rps": "req/s",
            "cpu_pct": "%", "mem_pct": "%", "db_pool_active": "connections", "db_pool_pending": "threads",
            "db_pool_wait_ms": "ms", "db_query_p99_ms": "ms", "tax_vendor_p99_ms": "ms"},
  "series": {
    "latency_p50_ms": [seg(18, 120, 190), seg(6, 190, 3100), seg(6, 3100, 6200)],
    "latency_p99_ms": [seg(18, 640, 2300), seg(6, 2300, 14000), seg(6, 14000, 29500)],
    "error_rate_pct": [seg(18, 0.1, 0.2), seg(6, 0.2, 3.1), seg(6, 3.1, 9.4)],
    "rps": [seg(18, 310, 340), seg(6, 340, 352), seg(6, 352, 344)],
    "cpu_pct": [seg(18, 22, 26), seg(6, 26, 19), seg(6, 19, 14)],
    "mem_pct": [seg(18, 61, 63), seg(6, 63, 66), seg(6, 66, 67)],
    "db_pool_active": [seg(18, 6, 14, 0.12), seg(6, 14, 20, 0.02), seg(6, 20, 20, 0.0)],
    "db_pool_pending": [seg(18, 0, 1, 0.2), seg(6, 1, 46), seg(6, 46, 128)],
    "db_pool_wait_ms": [seg(18, 2, 40), seg(6, 40, 9800), seg(6, 9800, 29800)],
    "db_query_p99_ms": [seg(18, 9, 12), seg(6, 12, 14), seg(6, 14, 13)],
    "tax_vendor_p99_ms": [seg(18, 1900, 2200), seg(6, 2200, 2400), seg(6, 2400, 2350)]
  },
  "annotations": [
    {"t": "2026-08-14T01:52:00Z", "text": "config dep-4470: checkout_v2_quote 5% -> 100%"},
    {"t": "2026-08-14T02:32:00Z", "text": "deploy dep-4471: web-frontend 2026.8.13-4"},
    {"t": "2026-08-14T02:44:00Z", "text": "alert alt-2026-08-14-0244-checkout fired"}
  ],
  "extra": {"note": "postgres-orders server-side metrics for the same window: active_backends 118 -> 121, "
                    "xact_rollback flat, checkpoints 1, autovacuum workers 1."}
},
"log": {"svc": "checkout-api", "format": "java", "start": "2026-08-14T02:20:00Z", "end": "2026-08-14T02:50:00Z",
  "lines": 330,
  "phases": [
    {"until": 0.55, "noise": http_noise(
        ["/v1/cart", "/v1/checkout/session", "/v1/checkout/address", "/healthz"],
        extra=jvm_noise() + [
          (10, "INFO", "quote computed", {"logger": "c.a.checkout.OrderQuoteService", "path": "/v2/checkout/quote",
                                          "status": 200, "duration_ms": "21{n}0", "tax_call_ms": "20{n}0",
                                          "tx": "open", "req_id": "{rid}"}),
          (3, "INFO", "inventory reservation ok", {"logger": "c.a.checkout.InventoryClient", "sku": "{sku}", "duration_ms": "{ms}"}),
          (2, "INFO", "session written", {"logger": "c.a.checkout.SessionStore", "backend": "redis-session", "duration_ms": 3}),
        ])},
    {"until": 1.0, "noise": http_noise(
        ["/v1/cart", "/v1/checkout/session", "/healthz"],
        extra=jvm_noise() + [
          (14, "WARN", "quote slow", {"logger": "c.a.checkout.OrderQuoteService", "path": "/v2/checkout/quote",
                                      "duration_ms": "1{n}430", "tax_call_ms": "21{n}0", "tx": "open", "req_id": "{rid}"}),
          (6, "WARN", "request exceeded soft deadline", {"logger": "c.a.common.Deadline", "path": "/v1/checkout/session",
                                                        "duration_ms": "9{n}12", "req_id": "{rid}"}),
          (4, "ERROR", "order create failed", {"logger": "c.a.checkout.OrderController", "status": 503,
                                               "order_id": "{oid}", "req_id": "{rid}"}),
        ])}
  ],
  "signals": [
    {"at": 300, "level": "INFO", "msg": "HikariPool-1 - After cleanup  stats (total=20, active=11, idle=9, waiting=0)",
     "kv": {"logger": "com.zaxxer.hikari.pool.HikariPool", "thread": "HikariPool-1 housekeeper"}},
    {"at": 900, "level": "INFO", "msg": "HikariPool-1 - After cleanup  stats (total=20, active=18, idle=2, waiting=0)",
     "kv": {"logger": "com.zaxxer.hikari.pool.HikariPool", "thread": "HikariPool-1 housekeeper"}},
    {"at": 1085, "level": "WARN", "msg": "HikariPool-1 - Thread starvation or clock leap detected (housekeeper delta=61s)",
     "kv": {"logger": "com.zaxxer.hikari.pool.HikariPool", "thread": "HikariPool-1 housekeeper"}},
    {"at": 1140, "level": "INFO", "msg": "HikariPool-1 - After cleanup  stats (total=20, active=20, idle=0, waiting=37)",
     "kv": {"logger": "com.zaxxer.hikari.pool.HikariPool", "thread": "HikariPool-1 housekeeper"}, "repeat": 3, "every": 30},
    {"at": 1160, "level": "ERROR",
     "msg": "HikariPool-1 - Connection is not available, request timed out after 30001ms (total=20, active=20, idle=0, waiting=63)",
     "kv": {"logger": "com.zaxxer.hikari.pool.HikariPool", "req_id": "{rid}"},
     "repeat": 22, "every": 41,
     "cont": ["\tat com.zaxxer.hikari.pool.HikariPool.createTimeoutException(HikariPool.java:696)",
              "\tat com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:197)",
              "\tat com.acme.checkout.OrderQuoteService.persistQuote(OrderQuoteService.java:141)",
              "\tat com.acme.checkout.OrderQuoteService.quote(OrderQuoteService.java:96)",
              "\tat com.acme.checkout.QuoteController.postQuote(QuoteController.java:52)"]},
    {"at": 1275, "level": "WARN",
     "msg": "autovacuum: VACUUM ANALYZE public.orders (to prevent wraparound) elapsed=214.8s",
     "kv": {"logger": "pg.forwarder", "thread": "pg-log-tail", "host": "postgres-orders-w1"}},
    {"at": 1290, "level": "INFO", "msg": "database maintenance window 02:00-04:00 UTC is active (informational)",
     "kv": {"logger": "c.a.platform.MaintenanceBanner", "thread": "scheduler-2"}},
    {"at": 1350, "level": "ERROR", "msg": "tax vendor call retried",
     "kv": {"logger": "c.a.checkout.TaxClient", "attempt": 2, "vendor_ms": 2180, "req_id": "{rid}"}, "repeat": 5, "every": 60},
    {"at": 1440, "level": "ERROR",
     "msg": "OrderQuoteService.quote holds transaction across TaxClient.fetch (span tax_call_ms=2140, tx_open_ms=2206)",
     "kv": {"logger": "c.a.common.TxAudit", "thread": "tx-audit-1", "req_id": "{rid}"}, "repeat": 4, "every": 90},
    {"at": 1500, "level": "ERROR", "msg": "POST /v2/checkout/quote failed",
     "kv": {"logger": "c.a.checkout.QuoteController", "status": 503,
            "cause": "CannotGetJdbcConnectionException", "req_id": "{rid}"}, "repeat": 12, "every": 24},
  ]}
})

# ============================================================ inc-002 =========
SPECS.append({
"id": "inc-002", "seed": 1002,
"readme": """
# inc-002 — payments-gateway 5xx spike

02:14 UTC. `payments-gateway` is throwing 5xx at about six percent of requests, well over the
one percent page threshold, and the graph went from flat to a step change with no ramp. The
service is the single front door for card authorisation, so the payments team owns it and the
finance dashboards will notice within the hour. The release train ran tonight. There is also
a scheduled Redis maintenance notice in the channel and someone in #infra is asking whether
the cache failover is related. Overall request volume is unchanged.
""",
"alert": {
  "alert_id": "alt-2026-07-09-0214-payg",
  "monitor_name": "payments-gateway :: 5xx rate > 1% (3m)",
  "monitor_id": "mon-0402", "severity": "SEV2", "state": "firing",
  "fired_at": "2026-07-09T02:14:00Z", "detected_change_at": "2026-07-09T02:11:00Z",
  "threshold": {"metric": "http.server.5xx_rate", "comparator": ">", "value": 1.0, "unit": "%", "window": "3m"},
  "observed_value": 6.2,
  "service": "payments-gateway", "environment": "prod", "region": "eu-west-1",
  "notified": ["oncall-payments"], "runbook": "https://runbooks.internal/payments-gateway/5xx",
  "tags": ["tier:1", "team:payments", "pci-scope"]
},
"deploys": {"lookback_hours": 24, "events": [
  {"id": "dep-7712", "at": "2026-07-08T14:31:00Z", "kind": "deploy", "service": "ledger-service",
   "version": "4.9.0", "actor": "release-train", "change": "batch settlement job tuning"},
  {"id": "dep-7719", "at": "2026-07-09T02:07:00Z", "kind": "deploy", "service": "payments-gateway",
   "version": "2.14.0", "actor": "release-train",
   "change": "multi-currency rounding refactor; add JPY/KRW support",
   "diff_summary": "MoneyRounding.java +96/-40; CurrencyRegistry.java +31/-4; AuthorizationHandler.java +12/-9",
   "canary": "skipped (release-train off-hours policy)"},
  {"id": "dep-7720", "at": "2026-07-09T02:09:00Z", "kind": "config", "service": "redis-ratelimit",
   "actor": "platform-bot", "change": "scheduled failover to replica for patching (announced)"}
]},
"topology": {
  "root": "payments-gateway",
  "nodes": [
    {"id": "edge-proxy", "kind": "gateway", "team": "platform"},
    {"id": "payments-gateway", "kind": "service", "team": "payments", "runtime": "jvm-21", "replicas": 12},
    {"id": "acquirer-api", "kind": "third_party", "vendor": "card-acquirer", "sla_p99_ms": 1200},
    {"id": "ledger-service", "kind": "service", "team": "finance", "replicas": 6},
    {"id": "redis-ratelimit", "kind": "cache", "team": "platform"},
    {"id": "postgres-payments", "kind": "database", "team": "payments"}
  ],
  "edges": [
    {"from": "edge-proxy", "to": "payments-gateway", "protocol": "http", "timeout_ms": 10000},
    {"from": "payments-gateway", "to": "acquirer-api", "protocol": "https", "timeout_ms": 8000},
    {"from": "payments-gateway", "to": "ledger-service", "protocol": "grpc", "timeout_ms": 2000},
    {"from": "payments-gateway", "to": "redis-ratelimit", "protocol": "resp", "timeout_ms": 150, "fail_open": True},
    {"from": "payments-gateway", "to": "postgres-payments", "protocol": "jdbc", "pool_max_size": 30}
  ],
  "notes": "Currency mix in eu-west-1: EUR 71%, GBP 19%, USD 4%, JPY 5.4%, other 0.6%."
},
"metrics": {"service": "payments-gateway", "start": "2026-07-09T01:55:00Z", "step_seconds": 60,
  "units": {"latency_p99_ms": "ms", "error_rate_pct": "%", "rps": "req/s"},
  "series": {
    "latency_p50_ms": [seg(12, 74, 78), seg(18, 78, 76)],
    "latency_p99_ms": [seg(12, 410, 430), seg(18, 430, 445)],
    "error_rate_pct": [seg(12, 0.08, 0.11, 0.3), seg(1, 0.11, 5.9), seg(17, 5.9, 6.3, 0.05)],
    "error_rate_jpy_pct": [seg(12, 0.1, 0.1, 0.3), seg(1, 0.1, 99.0), seg(17, 99.0, 100.0, 0.005)],
    "error_rate_eur_pct": [seg(12, 0.08, 0.1, 0.3), seg(18, 0.1, 0.12, 0.3)],
    "rps": [seg(12, 640, 655), seg(18, 655, 648)],
    "cpu_pct": [seg(12, 38, 40), seg(18, 40, 39)],
    "mem_pct": [seg(12, 55, 56), seg(18, 56, 57)],
    "redis_ratelimit_errors": [seg(12, 0, 0, 0.0), seg(2, 0, 34), seg(2, 34, 0), seg(14, 0, 0, 0.0)],
    "acquirer_p99_ms": [seg(12, 880, 910), seg(18, 910, 905)]
  },
  "annotations": [
    {"t": "2026-07-09T02:07:00Z", "text": "deploy dep-7719: payments-gateway 2.14.0"},
    {"t": "2026-07-09T02:09:00Z", "text": "config dep-7720: redis-ratelimit failover"},
    {"t": "2026-07-09T02:14:00Z", "text": "alert fired"}
  ]},
"log": {"svc": "payments-gateway", "format": "java", "start": "2026-07-09T01:58:00Z", "end": "2026-07-09T02:22:00Z",
  "lines": 300,
  "phases": [
    {"until": 0.40, "noise": http_noise(["/v1/authorize", "/v1/capture", "/v1/refund", "/healthz"],
        extra=jvm_noise() + [
          (14, "INFO", "authorization approved", {"logger": "c.a.pg.AuthorizationHandler", "currency": "EUR",
                                                  "amount_minor": "{n}499", "acquirer_ms": "{ms}", "req_id": "{rid}"}),
          (3, "INFO", "authorization approved", {"logger": "c.a.pg.AuthorizationHandler", "currency": "GBP",
                                                 "amount_minor": "{n}250", "acquirer_ms": "{ms}", "req_id": "{rid}"}),
          (2, "INFO", "authorization approved", {"logger": "c.a.pg.AuthorizationHandler", "currency": "JPY",
                                                 "amount_minor": "{n}800", "acquirer_ms": "{ms}", "req_id": "{rid}"}),
          (2, "DEBUG", "rate limit token consumed", {"logger": "c.a.pg.RateLimiter", "backend": "redis-ratelimit", "remaining": "{n}"}),
        ])},
    {"until": 1.0, "noise": http_noise(["/v1/authorize", "/v1/capture", "/healthz"],
        extra=jvm_noise() + [
          (16, "INFO", "authorization approved", {"logger": "c.a.pg.AuthorizationHandler", "currency": "EUR",
                                                  "amount_minor": "{n}499", "acquirer_ms": "{ms}", "req_id": "{rid}"}),
          (3, "INFO", "authorization approved", {"logger": "c.a.pg.AuthorizationHandler", "currency": "GBP",
                                                 "amount_minor": "{n}250", "acquirer_ms": "{ms}", "req_id": "{rid}"}),
          (2, "WARN", "rate limiter unavailable, failing open",
           {"logger": "c.a.pg.RateLimiter", "backend": "redis-ratelimit", "cause": "MOVED 5417"}),
        ])}
  ],
  "signals": [
    {"at": 540, "level": "INFO", "msg": "starting payments-gateway 2.14.0 (build 9f31c2a, released by release-train)",
     "kv": {"logger": "c.a.pg.Bootstrap", "thread": "main"}},
    {"at": 545, "level": "INFO", "msg": "CurrencyRegistry loaded 168 currencies (zero_decimal=[])",
     "kv": {"logger": "c.a.pg.CurrencyRegistry", "thread": "main"}},
    {"at": 660, "level": "WARN", "msg": "redis-ratelimit connection reset during failover, reconnecting",
     "kv": {"logger": "c.a.pg.RateLimiter", "thread": "lettuce-nioEventLoop-4"}, "repeat": 4, "every": 12},
    {"at": 780, "level": "ERROR", "msg": "authorization failed",
     "kv": {"logger": "c.a.pg.AuthorizationHandler", "currency": "JPY", "amount_minor": "{n}800",
            "status": 500, "cause": "java.lang.ArithmeticException: Rounding necessary", "req_id": "{rid}"},
     "repeat": 26, "every": 27,
     "cont": ["\tat java.base/java.math.BigDecimal.commonNeedIncrement(BigDecimal.java:4864)",
              "\tat java.base/java.math.BigDecimal.setScale(BigDecimal.java:3079)",
              "\tat com.acme.pg.MoneyRounding.toMinorUnits(MoneyRounding.java:77)",
              "\tat com.acme.pg.AuthorizationHandler.authorize(AuthorizationHandler.java:203)"]},
    {"at": 900, "level": "INFO", "msg": "redis-ratelimit failover complete, cluster topology refreshed",
     "kv": {"logger": "c.a.pg.RateLimiter", "thread": "lettuce-nioEventLoop-4"}},
    {"at": 960, "level": "WARN", "msg": "MoneyRounding.toMinorUnits assumes scale=2 for currency=JPY (registry scale=0)",
     "kv": {"logger": "c.a.pg.MoneyRounding", "req_id": "{rid}"}, "repeat": 6, "every": 45},
  ]}
})

# ============================================================ inc-003 =========
SPECS.append({
"id": "inc-003", "seed": 1003,
"readme": """
# inc-003 — authentication failures across every service, just after midnight

Just after midnight UTC the on-call channel lights up. `identity-service` is returning errors
to almost everything that calls it, and the symptom the customer sees is that logins and API
tokens stop working. The alert is on upstream 5xx from the edge proxy toward identity, and it
went from zero to sustained in under a minute. Nobody deployed anything tonight; the last
change to anything in the auth path was two days ago. The security channel has an open thread
about a burst of failed logins from a single netblock that started an hour before this. It is
a Saturday, the deploy freeze is on, and there is no obvious human to blame.
""",
"alert": {
  "alert_id": "alt-2026-08-01-0002-identity",
  "monitor_name": "edge-proxy :: upstream_5xx{upstream=identity-service} > 5% (2m)",
  "monitor_id": "mon-0771", "severity": "SEV1", "state": "firing",
  "fired_at": "2026-08-01T00:02:00Z", "detected_change_at": "2026-08-01T00:00:14Z",
  "threshold": {"metric": "nginx.upstream.5xx_rate", "comparator": ">", "value": 5.0, "unit": "%", "window": "2m"},
  "observed_value": 97.8,
  "service": "identity-service", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-platform", "oncall-security"],
  "runbook": "https://runbooks.internal/identity/upstream-errors",
  "tags": ["tier:0", "team:platform", "auth"]
},
"deploys": {"lookback_hours": 96, "events": [
  {"id": "dep-9901", "at": "2026-07-28T16:20:00Z", "kind": "deploy", "service": "identity-service",
   "version": "6.1.3", "actor": "spatel", "change": "add device-binding claim to access tokens"},
  {"id": "dep-9930", "at": "2026-07-30T11:05:00Z", "kind": "config", "service": "identity-service",
   "actor": "spatel", "change": "IAM: tighten session policy, reduce refresh token TTL 30d -> 7d",
   "diff_summary": "policies/session.hcl: refresh_ttl 720h -> 168h"},
  {"id": "dep-9941", "at": "2026-07-31T09:40:00Z", "kind": "config", "service": "waf",
   "actor": "security-bot", "change": "add rate-limit rule for /oauth/token from 203.0.113.0/24"},
  {"id": "freeze-08", "at": "2026-07-31T18:00:00Z", "kind": "policy", "service": "*",
   "actor": "release-eng", "change": "weekend change freeze in effect until 2026-08-03T08:00Z"}
]},
"topology": {
  "root": "identity-service",
  "nodes": [
    {"id": "edge-proxy", "kind": "gateway", "team": "platform", "tls": "public-cert (LE, auto-renewed)"},
    {"id": "identity-service", "kind": "service", "team": "platform", "replicas": 10,
     "client_auth": "mTLS required on :8443"},
    {"id": "internal-ca", "kind": "pki", "team": "security", "note": "issues client certs, 1y lifetime, manual renewal"},
    {"id": "postgres-identity", "kind": "database", "team": "platform"},
    {"id": "redis-session", "kind": "cache", "team": "platform"},
    {"id": "checkout-api", "kind": "service", "team": "payments", "calls_identity": True},
    {"id": "mobile-bff", "kind": "service", "team": "mobile", "calls_identity": True}
  ],
  "edges": [
    {"from": "edge-proxy", "to": "identity-service", "protocol": "https", "client_cert": "edge-proxy-client",
     "cert_serial": "0x3f9a21", "cert_not_after": "2026-07-31T23:59:59Z"},
    {"from": "checkout-api", "to": "identity-service", "protocol": "https", "client_cert": "svc-checkout-client",
     "cert_not_after": "2026-11-14T00:00:00Z"},
    {"from": "mobile-bff", "to": "identity-service", "protocol": "https", "client_cert": "svc-mobile-client",
     "cert_not_after": "2027-02-02T00:00:00Z"},
    {"from": "identity-service", "to": "postgres-identity", "protocol": "jdbc"},
    {"from": "identity-service", "to": "redis-session", "protocol": "resp"}
  ],
  "notes": "Public-facing TLS is auto-renewed. Internal mTLS client certs are issued by internal-ca and renewed by hand."
},
"metrics": {"service": "identity-service", "start": "2026-07-31T23:40:00Z", "step_seconds": 60,
  "units": {"upstream_5xx_pct": "%", "tls_handshake_failures": "count/min", "login_success_rps": "req/s"},
  "series": {
    "upstream_5xx_pct_via_edge": [seg(20, 0.02, 0.03, 0.4), seg(1, 0.03, 97.0), seg(19, 97.0, 98.6, 0.01)],
    "upstream_5xx_pct_via_checkout": [seg(20, 0.02, 0.03, 0.4), seg(20, 0.03, 0.04, 0.4)],
    "tls_handshake_failures": [seg(20, 0, 0, 0.0), seg(1, 0, 810), seg(19, 810, 940, 0.05)],
    "login_success_rps": [seg(20, 118, 96), seg(1, 96, 2), seg(19, 2, 0.4)],
    "failed_login_rps": [seg(8, 1, 9), seg(12, 9, 11, 0.3), seg(20, 11, 10, 0.3)],
    "cpu_pct": [seg(20, 31, 28), seg(20, 28, 11)],
    "mem_pct": [seg(20, 48, 48), seg(20, 48, 47)],
    "db_query_p99_ms": [seg(20, 7, 8), seg(20, 8, 6)]
  },
  "annotations": [
    {"t": "2026-07-31T23:00:00Z", "text": "security: elevated failed logins from 203.0.113.0/24 (ongoing since 23:02)"},
    {"t": "2026-08-01T00:00:14Z", "text": "edge-proxy upstream errors begin"},
    {"t": "2026-08-01T00:02:00Z", "text": "alert fired"}
  ],
  "extra": {"note": "identity-service internal request rate collapsed but its own CPU and DB latency are healthy; "
                    "traffic arriving from checkout-api and mobile-bff is unaffected."}
},
"log": {"svc": "identity-service", "format": "logfmt", "start": "2026-07-31T23:44:00Z", "end": "2026-08-01T00:12:00Z",
  "lines": 320,
  "phases": [
    {"until": 0.57, "noise": http_noise(["/oauth/token", "/oauth/introspect", "/v1/userinfo", "/healthz"],
        extra=[
          (10, "INFO", "token issued", {"grant": "refresh_token", "user_id": "{uid}", "client": "web", "ttl_s": 900}),
          (6, "INFO", "token introspected", {"client": "checkout-api", "active": "true"}),
          (5, "WARN", "login failed", {"reason": "invalid_credentials", "user_id": "{uid}",
                                       "src_ip": "203.0.113.{n}", "ua": "python-requests/2.32"}),
          (2, "INFO", "mTLS peer verified", {"peer": "svc-checkout-client", "serial": "0x7c22be"}),
          (2, "INFO", "mTLS peer verified", {"peer": "edge-proxy-client", "serial": "0x3f9a21"}),
        ])},
    {"until": 1.0, "noise": [
          (10, "INFO", "token introspected", {"client": "checkout-api", "active": "true"}),
          (6, "INFO", "token issued", {"grant": "client_credentials", "client": "mobile-bff", "ttl_s": 900}),
          (5, "WARN", "login failed", {"reason": "invalid_credentials", "user_id": "{uid}",
                                       "src_ip": "203.0.113.{n}", "ua": "python-requests/2.32"}),
          (4, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
          (2, "INFO", "mTLS peer verified", {"peer": "svc-mobile-client", "serial": "0x91aa03"}),
        ]}
  ],
  "signals": [
    {"at": 720, "level": "WARN", "msg": "client certificate approaching expiry",
     "kv": {"peer": "edge-proxy-client", "serial": "0x3f9a21", "not_after": "2026-07-31T23:59:59Z", "remaining_h": 0}},
    {"at": 960, "level": "ERROR", "msg": "tls: failed to verify client certificate",
     "kv": {"peer_addr": "10.4.11.{n}", "peer_cn": "edge-proxy-client", "serial": "0x3f9a21",
            "error": "x509: certificate has expired or is not yet valid: current time 2026-08-01T00:00:14Z is after 2026-07-31T23:59:59Z"},
     "repeat": 30, "every": 22},
    {"at": 968, "level": "ERROR", "msg": "handshake aborted",
     "kv": {"listener": "0.0.0.0:8443", "peer_addr": "10.4.11.{n}", "alert": "certificate_expired(45)"},
     "repeat": 18, "every": 36},
    {"at": 1000, "level": "WARN", "msg": "waf rule oauth-token-ratelimit tripped",
     "kv": {"src_ip": "203.0.113.{n}", "rule_id": "wf-2291", "action": "throttle", "count": "{n}"},
     "repeat": 6, "every": 60},
    {"at": 1080, "level": "INFO", "msg": "internal-ca renewal reminder digest (weekly)",
     "kv": {"expiring_30d": 3, "expired": 1, "detail": "edge-proxy-client expired 2026-07-31T23:59:59Z"}},
    {"at": 1140, "level": "INFO", "msg": "peer connection counts",
     "kv": {"edge-proxy": 0, "checkout-api": 41, "mobile-bff": 27}, "repeat": 3, "every": 120},
  ]}
})

# ============================================================ inc-004 =========
SPECS.append({
"id": "inc-004", "seed": 1004,
"readme": """
# inc-004 — search-api got slow and nothing about it changed

21:35 UTC. `search-api` p95 latency crossed 1.2 seconds and stayed there. Search is not on the
checkout path, so it is a SEV3, but the product team will notice tomorrow morning and the
graphs look ugly. The service is a Go app on the shared `general-2` node pool. Container CPU
utilisation for search-api looks unremarkable, the Elasticsearch cluster behind it is doing a
scheduled index rebuild tonight, and someone flipped the log level to debug this afternoon.
Nothing in search-api itself has shipped in nine days. The latency is not uniform: some pods
are fine and some are terrible.
""",
"alert": {
  "alert_id": "alt-2026-08-05-2135-search",
  "monitor_name": "search-api :: p95 latency > 1200ms (10m)",
  "monitor_id": "mon-2044", "severity": "SEV3", "state": "firing",
  "fired_at": "2026-08-05T21:35:00Z", "detected_change_at": "2026-08-05T21:22:00Z",
  "threshold": {"metric": "http.server.duration.p95", "comparator": ">", "value": 1200, "unit": "ms", "window": "10m"},
  "observed_value": 3180,
  "service": "search-api", "environment": "prod", "region": "us-east-1",
  "notified": ["oncall-discovery"], "runbook": "https://runbooks.internal/search-api/latency",
  "tags": ["tier:2", "team:discovery"]
},
"deploys": {"lookback_hours": 240, "events": [
  {"id": "dep-3301", "at": "2026-07-27T10:12:00Z", "kind": "deploy", "service": "search-api",
   "version": "1.9.7", "actor": "dwu", "change": "query parser: support quoted phrases"},
  {"id": "dep-3388", "at": "2026-08-05T15:48:00Z", "kind": "config", "service": "search-api",
   "actor": "dwu", "change": "LOG_LEVEL info -> debug for query-parser investigation",
   "diff_summary": "configmap search-api-env: LOG_LEVEL info -> debug"},
  {"id": "dep-3390", "at": "2026-08-05T20:00:00Z", "kind": "schedule", "service": "elasticsearch-catalog",
   "actor": "platform-bot", "change": "nightly force-merge / index rebuild window 20:00-23:00 UTC (recurring)"},
  {"id": "dep-3391", "at": "2026-08-05T21:04:00Z", "kind": "deploy", "service": "ml-featurizer",
   "version": "0.4.0", "actor": "rgupta",
   "change": "nightly embedding backfill job; moved from batch-pool to default scheduling",
   "diff_summary": "cronjob.yaml: nodeSelector pool=batch-1 REMOVED; resources.limits.cpu REMOVED; parallelism 4 -> 16"}
]},
"topology": {
  "root": "search-api",
  "nodes": [
    {"id": "search-api", "kind": "service", "team": "discovery", "runtime": "go-1.24", "replicas": 8,
     "node_pool": "general-2", "cpu_request": "500m", "cpu_limit": "1000m"},
    {"id": "elasticsearch-catalog", "kind": "datastore", "team": "platform", "nodes": 6, "node_pool": "data-1"},
    {"id": "redis-suggest", "kind": "cache", "team": "discovery", "node_pool": "general-2"},
    {"id": "ml-featurizer", "kind": "batch_job", "team": "ml", "node_pool": "general-2 (since 2026-08-05)",
     "cpu_request": "200m", "cpu_limit": None, "parallelism": 16},
    {"id": "node/general-2-a", "kind": "node", "cpu_cores": 8, "pods": ["search-api-7d4c9-xk2", "search-api-7d4c9-pl9", "ml-featurizer-*"]},
    {"id": "node/general-2-b", "kind": "node", "cpu_cores": 8, "pods": ["search-api-7d4c9-r8m", "redis-suggest-0"]},
    {"id": "node/general-2-c", "kind": "node", "cpu_cores": 8, "pods": ["search-api-7d4c9-w2t", "ml-featurizer-*"]}
  ],
  "edges": [
    {"from": "search-api", "to": "elasticsearch-catalog", "protocol": "http", "timeout_ms": 2000},
    {"from": "search-api", "to": "redis-suggest", "protocol": "resp", "timeout_ms": 100},
    {"from": "ml-featurizer", "to": "elasticsearch-catalog", "protocol": "http", "note": "bulk writes"}
  ],
  "notes": "general-2 is a shared pool. Only pods scheduled onto general-2-a and general-2-c share nodes with ml-featurizer."
},
"metrics": {"service": "search-api", "start": "2026-08-05T20:40:00Z", "step_seconds": 60,
  "units": {"latency_p95_ms": "ms", "container_cpu_pct_of_limit": "%", "node_cpu_pct": "%",
            "cpu_throttled_seconds_per_min": "s", "es_query_p99_ms": "ms"},
  "series": {
    "latency_p95_ms": [seg(24, 280, 300), seg(6, 300, 2400), seg(20, 2400, 3300)],
    "latency_p95_ms_pod_r8m": [seg(24, 275, 295), seg(6, 295, 320), seg(20, 320, 340)],
    "latency_p95_ms_pod_xk2": [seg(24, 285, 305), seg(6, 305, 3900), seg(20, 3900, 5200)],
    "error_rate_pct": [seg(24, 0.05, 0.06), seg(6, 0.06, 0.4), seg(20, 0.4, 0.9)],
    "rps": [seg(24, 210, 205), seg(26, 205, 202)],
    "container_cpu_pct_of_limit": [seg(24, 41, 44), seg(6, 44, 99), seg(20, 99, 100, 0.005)],
    "cpu_throttled_seconds_per_min": [seg(24, 0.0, 0.02, 0.5), seg(6, 0.02, 31.0), seg(20, 31.0, 47.0)],
    "node_cpu_pct_general_2_a": [seg(24, 46, 51), seg(6, 51, 98), seg(20, 98, 99, 0.01)],
    "node_cpu_pct_general_2_b": [seg(24, 44, 48), seg(26, 48, 52)],
    "mem_pct": [seg(24, 57, 58), seg(26, 58, 59)],
    "es_query_p99_ms": [seg(24, 88, 96), seg(6, 96, 130), seg(20, 130, 141)],
    "gc_pause_ms": [seg(24, 1.1, 1.3), seg(26, 1.3, 1.4)]
  },
  "annotations": [
    {"t": "2026-08-05T20:00:00Z", "text": "elasticsearch-catalog nightly force-merge window opens"},
    {"t": "2026-08-05T21:04:00Z", "text": "deploy dep-3391: ml-featurizer 0.4.0"},
    {"t": "2026-08-05T21:35:00Z", "text": "alert fired"}
  ],
  "extra": {"note": "container_cpu_pct_of_limit is measured against the 1000m limit; the pods are at their limit "
                    "while the node itself has no headroom left."}
},
"log": {"svc": "search-api", "format": "json", "start": "2026-08-05T20:50:00Z", "end": "2026-08-05T21:40:00Z",
  "lines": 340,
  "phases": [
    {"until": 0.42, "noise": http_noise(["/v1/search", "/v1/suggest", "/healthz"],
        extra=[
          (16, "INFO", "query served", {"pod": "search-api-7d4c9{pod}", "took_ms": "{ms}", "hits": "{n}4",
                                        "index": "catalog-v7", "trace_id": "{tid}"}),
          (8, "DEBUG", "parsed query", {"pod": "search-api-7d4c9{pod}", "terms": "{n}", "phrases": 1}),
          (4, "DEBUG", "suggest cache hit", {"pod": "search-api-7d4c9{pod}", "key": "sug:{sku}"}),
          (2, "INFO", "es bulk read", {"index": "catalog-v7", "took_ms": "{n}"}),
        ])},
    {"until": 1.0, "noise": [
          (12, "INFO", "query served", {"pod": "search-api-7d4c9-r8m", "took_ms": "3{n}0", "hits": "{n}4",
                                        "index": "catalog-v7", "trace_id": "{tid}"}),
          (14, "WARN", "query slow", {"pod": "search-api-7d4c9-xk2", "took_ms": "3{n}12", "es_ms": "1{n}1",
                                      "local_ms": "3{n}80", "index": "catalog-v7", "trace_id": "{tid}"}),
          (8, "WARN", "query slow", {"pod": "search-api-7d4c9-w2t", "took_ms": "2{n}44", "es_ms": "1{n}6",
                                     "local_ms": "2{n}20", "index": "catalog-v7", "trace_id": "{tid}"}),
          (8, "DEBUG", "parsed query", {"pod": "search-api-7d4c9-xk2", "terms": "{n}", "phrases": 1}),
          (3, "INFO", "health check ok", {"path": "/healthz", "status": 200}),
        ]}
  ],
  "signals": [
    {"at": 300, "level": "INFO", "msg": "elasticsearch force-merge started on catalog-v7 (scheduled)",
     "kv": {"segments_before": 214, "target_segments": 1, "es_node": "es-data-3"}},
    {"at": 840, "level": "INFO", "msg": "pod scheduled onto node",
     "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-2-a", "proc": "kubelet", "pod": "ml-featurizer-28104-b7q", "node": "general-2-a",
            "qos": "Burstable", "cpu_request": "200m", "cpu_limit": "none"}, "repeat": 5, "every": 9},
    {"at": 850, "level": "INFO", "msg": "pod scheduled onto node",
     "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-2-c", "proc": "kubelet", "pod": "ml-featurizer-28104-j4d", "node": "general-2-c",
            "qos": "Burstable", "cpu_request": "200m", "cpu_limit": "none"}, "repeat": 5, "every": 11},
    {"at": 1020, "level": "WARN", "msg": "cgroup cpu throttling observed",
     "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-2-a", "proc": "kubelet", "cgroup": "/kubepods/burstable/search-api-7d4c9-xk2",
            "nr_periods": 6000, "nr_throttled": 5412, "throttled_time_s": 41.2},
     "repeat": 12, "every": 60},
    {"at": 1050, "level": "WARN", "msg": "node under cpu pressure",
     "format": "syslog", "svc": "kubelet",
     "kv": {"host": "general-2-a", "proc": "kubelet", "load1": 31.4, "cores": 8, "runnable": 44},
     "repeat": 8, "every": 90},
    {"at": 1080, "level": "INFO", "msg": "es query completed", "kv": {"index": "catalog-v7", "took_ms": "1{n}2",
     "shard_hits": "{n}4", "note": "force-merge in progress"}, "repeat": 6, "every": 70},
    {"at": 1500, "level": "WARN", "msg": "goroutine scheduling latency elevated",
     "kv": {"pod": "search-api-7d4c9-xk2", "sched_latency_p99_ms": "2{n}0", "goroutines": 412,
            "gomaxprocs": 8, "cpu_quota_cores": 1.0}, "repeat": 5, "every": 100},
  ]}
})
