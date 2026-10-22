-- A model's days for the platform's dashboard (glyphh_ada/days.py): its reads by kind and its decides' answers, by
-- UTC day, added by the minute tick from Redis; seen only by its org, as ada_usage is.
CREATE TABLE IF NOT EXISTS ada_model_days (
    org_id UUID NOT NULL,
    model TEXT NOT NULL,
    day DATE NOT NULL,
    metric TEXT NOT NULL,
    n BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (org_id, model, day, metric),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
