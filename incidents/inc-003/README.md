# inc-003 — authentication failures across every service, just after midnight

Just after midnight UTC the on-call channel lights up. `identity-service` is returning errors
to almost everything that calls it, and the symptom the customer sees is that logins and API
tokens stop working. The alert is on upstream 5xx from the edge proxy toward identity, and it
went from zero to sustained in under a minute. Nobody deployed anything tonight; the last
change to anything in the auth path was two days ago. The security channel has an open thread
about a burst of failed logins from a single netblock that started an hour before this. It is
a Saturday, the deploy freeze is on, and there is no obvious human to blame.
