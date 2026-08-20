# inc-008 — notification-worker keeps getting killed

07:41 UTC. `notification-worker` pods have restarted eleven times in the last half hour and the
restart-loop monitor has paged. The exit reason is OOMKilled. Notification volume is at its
usual weekday-morning peak, roughly double the overnight floor, and the obvious story is that
the morning send is simply too big for the memory limit. A sibling service shipped this morning,
and a colleague has already suggested doubling the memory limit and moving on. The queue behind
the worker is backing up while it restarts.
