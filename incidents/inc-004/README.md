# inc-004 — search-api got slow and nothing about it changed

21:35 UTC. `search-api` p95 latency crossed 1.2 seconds and stayed there. Search is not on the
checkout path, so it is a SEV3, but the product team will notice tomorrow morning and the
graphs look ugly. The service is a Go app on the shared `general-2` node pool. Container CPU
utilisation for search-api looks unremarkable, the Elasticsearch cluster behind it is doing a
scheduled index rebuild tonight, and someone flipped the log level to debug this afternoon.
Nothing in search-api itself has shipped in nine days. The latency is not uniform: some pods
are fine and some are terrible.
