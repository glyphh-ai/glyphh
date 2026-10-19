"""The receiver for rrotor's opt-in server-side logging (`RROTOR_SERVER_LOGS=on`, rrotor's docs/specs/cluster.md 7):
`POST /v1/otlp/v1/{logs,metrics,traces}`, OTLP over HTTP with protobuf, gzipped or not, the runtime's own token as
the bearer. `body.py` reads and decodes a request within its limits, `values.py` turns OTLP's values into plain ones
(dropping what must never be kept), `rows.py` and `points.py` make the rows, `keep.py` keeps them in the runtime's
org. Never logged: a body, or the caller's address (obs/logs.py drops the access line for these paths)."""
