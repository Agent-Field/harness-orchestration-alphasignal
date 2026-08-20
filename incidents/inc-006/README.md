# inc-006 — product-catalog database on fire at 04:12

04:16 UTC. The page is for `postgres-catalog`: CPU pinned at 100%, and `product-catalog-api`
p99 has gone from 40ms to several seconds. The database is a large managed instance that
normally sits at ten percent utilisation, so the graph is dramatic and the obvious reading is
that something is hammering the database. Overnight there is a bot crawler that ramps up around
this hour, and the DBA channel has a long-running thread about a missing index on `product_variant`.
There was a routine release at 04:10. Read volume at the API edge is close to flat.
