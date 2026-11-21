-- The traffic pull now keeps a hostname without its port and only the zone's own hostnames (ops/traffic/pull.py): the
-- rows the first pulls kept under a Host header with a port, or naming another site, go. They are pulled again, folded.
DELETE FROM traffic_days WHERE host <> '' AND (host LIKE '%:%' OR NOT (host = zone OR host LIKE '%.' || zone));
DELETE FROM traffic_tops WHERE host <> '' AND (host LIKE '%:%' OR NOT (host = zone OR host LIKE '%.' || zone));
