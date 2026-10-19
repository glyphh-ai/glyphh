"""What the org's runtimes sent with server-side logging on, read for the platform and the connector: their log
records and audit events newest first, paged (`records.py`), their metrics' latest values (`metrics.py`); and
retention, the minute tick's purge (`retention.py`). Every read runs in the caller's org (row-level security)."""
