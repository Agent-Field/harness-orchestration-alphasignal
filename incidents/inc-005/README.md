# inc-005 — shipping-rates-api timing out at the checkout step

11:20 UTC on a Tuesday, the busiest hour of the European day. `shipping-rates-api` is returning
504 to about a fifth of calls, and because the checkout page blocks on a rate quote, customers
see a spinner and then an error. The service fans out to four carrier APIs and returns the
cheapest option. Its own CPU is high and its worker threads are all busy, which makes it look
saturated. A change went out this morning that touched the rate cache. The rate of incoming
requests is normal for the hour.
