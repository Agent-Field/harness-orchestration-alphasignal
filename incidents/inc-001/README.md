# inc-001 — checkout-api p99 latency and 5xx, overnight

It is 02:44 UTC on a Friday. Your phone goes off: `checkout-api` p99 latency has been over
8 seconds for five straight minutes and the error rate is climbing past 4%. Checkout is the
last screen before money changes hands, so this is a SEV2 the moment it fires. The service
is a JVM app behind the edge proxy; it talks to the orders database, a tax vendor, and the
inventory service. Traffic right now is roughly a third of daytime peak, so nothing about
the load looks alarming on the dashboard. The team shipped things yesterday evening and
again a little before midnight, and there is a database maintenance window that runs most
nights. You have logs, the deploy feed, a metrics snapshot, and the dependency map.
