# inc-010 — auth-service went down for a minute and has been down for half an hour

09:04 UTC. `auth-service` is failing about a third of token verifications and has been for
twenty-five minutes. What makes this odd is the shape of it: there was a short, sharp blip at
09:00 that lasted well under a minute, everything looked like it was recovering, and then the
service got worse and stayed worse. Nobody has touched auth-service in four days. Platform
rebooted a node at 09:00 as part of routine patching, and one auth-service pod went with it.
Every service in the company calls this one. The team has already restarted the pods twice;
each restart helps for about ninety seconds.
