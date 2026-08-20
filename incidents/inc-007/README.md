# inc-007 — intermittent connection failures, several services, one availability zone

04:02 UTC. Three separate monitors fired within ninety seconds of each other: `orders-service`
error rate, `cart-api` error rate, and `notification-worker` job failures. The errors are
intermittent rather than total, roughly one call in ten, and they come and go. Most of the
error text points at `orders-service`, so the orders team has been paged and is looking at
their own dashboards, where everything appears healthy. They shipped a release yesterday
evening. Platform is in the middle of a rolling kernel patch across the fleet tonight.
