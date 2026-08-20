# inc-009 — feed-api falls over every morning at the same time

08:06 UTC. `feed-api` is returning 503 and its p99 is over four seconds. This is the third
weekday in a row that it has misbehaved during the European morning ramp, though the previous
two days recovered on their own before anyone looked. The service is the read path for the
personalised home feed: heavy fan-out, lots of waiting on downstream calls, not much local
computation. There is a database index migration running this morning, which the DBA has
flagged in the channel. Request volume is climbing, as it does every weekday at this hour.
The obvious explanation on the table is "we need more capacity".
