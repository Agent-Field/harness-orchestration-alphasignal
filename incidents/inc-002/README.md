# inc-002 — payments-gateway 5xx spike

02:14 UTC. `payments-gateway` is throwing 5xx at about six percent of requests, well over the
one percent page threshold, and the graph went from flat to a step change with no ramp. The
service is the single front door for card authorisation, so the payments team owns it and the
finance dashboards will notice within the hour. The release train ran tonight. There is also
a scheduled Redis maintenance notice in the channel and someone in #infra is asking whether
the cache failover is related. Overall request volume is unchanged.
