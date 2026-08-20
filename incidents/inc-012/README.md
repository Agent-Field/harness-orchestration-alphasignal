# inc-012 — pricing-consumer has stopped keeping up

16:48 UTC. The lag monitor on the `pricing-consumer` group has crossed a hundred thousand
messages and is climbing at a steady rate. The consequence is that prices shown on the site are
going stale, which merchandising will notice before customers do. The consumer processes a
price feed published by another team. Kafka had a broker restart earlier this afternoon and the
consumer group rebalanced, which is the first thing everyone in the channel points at. Our team
shipped a dependency bump this morning. The consumer is not crash-looping; it is running and
committing offsets, just not producing much useful output.
