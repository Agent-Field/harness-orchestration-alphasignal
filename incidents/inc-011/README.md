# inc-011 — booking-api rejecting valid tokens, but only sometimes

14:22 UTC. `booking-api` is rejecting roughly one in six authenticated requests with 401, and
the customers affected are not a coherent group: the same user succeeds on one attempt and
fails on the next. Support is escalating because partners using the signed-webhook callback are
also seeing rejections. The auth team rotated the JWT signing key three days ago and that is
the leading theory in the incident channel. Nothing has deployed in this region today. The
infrastructure team did live-migrate a batch of hypervisors last night.
