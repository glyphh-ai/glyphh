"""An org's own schema, `ada_<org id>`: made with its first model, migrated by every worker at start (each pending
migration once, under the schema's advisory lock, recorded in its `ada_schema` table), and fenced by row-level
security that fails closed.

The server's tables in it: `models`, `spec_versions`, `jobs`, `requests` (what makes a write happen once: the
caller's Idempotency-Key or the message's id, with its answer, kept a day) and `files` (imports' uploads and exports'
archives, in chunks, kept while their links work). The kernel's own (glyphh_postgres:
`precedents`, partitioned by model, `outcomes`, `meta`, `counts`) are made by PostgresStore beside them.

Every table in the schema, the kernel's partitions included, gets the policy `tenant`: a row is seen or written only
by a session whose `glyphh.org_id` is this org. Unlike the public schema's policies (db/tenancy.py), a session with no
org set sees nothing, so a statement that names the wrong schema, or none, finds no row."""

import psycopg
from psycopg import sql

from glyphh_ada.pg import org_of, schema_for

MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS {s}.models (
        id uuid PRIMARY KEY, name text NOT NULL, active_version integer NOT NULL DEFAULT 1,
        created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz);
    CREATE UNIQUE INDEX IF NOT EXISTS models_live_name ON {s}.models (name) WHERE deleted_at IS NULL;
    CREATE TABLE IF NOT EXISTS {s}.spec_versions (
        model_id uuid NOT NULL REFERENCES {s}.models (id) ON DELETE CASCADE, version integer NOT NULL,
        spec jsonb NOT NULL, note text NOT NULL DEFAULT '', made_by text NOT NULL,
        made_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (model_id, version));
    CREATE TABLE IF NOT EXISTS {s}.jobs (
        id uuid PRIMARY KEY, model_id uuid NOT NULL REFERENCES {s}.models (id) ON DELETE CASCADE,
        kind text NOT NULL, state text NOT NULL DEFAULT 'queued', percent real NOT NULL DEFAULT 0,
        args jsonb NOT NULL DEFAULT '{{}}', result jsonb, error jsonb, made_by text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz);
    CREATE TABLE IF NOT EXISTS {s}.requests (
        key text PRIMARY KEY, body text NOT NULL, reply jsonb NOT NULL, at timestamptz NOT NULL DEFAULT now());
    CREATE INDEX IF NOT EXISTS requests_at ON {s}.requests (at);
    """,
    # Step 3: files (an import's upload, an export's archive), a chunk a row, named by their job's id. Step 4: each
    # version names the store (the kernel's partition) it reads, keeps the learned weights and temperatures it went
    # live with, the backtest it was chosen by, when it stopped being active, and whether its store is made (ready)
    # or dropped after KEPT_DAYS (gone). And every partition step 2 made an index on its ids alone (a lookup by id
    # cannot lead with the primary key (model, id)), which the kernel makes itself for every partition since 3.12.1.
    """
    DO $$ DECLARE r record; BEGIN
        FOR r IN SELECT n.nspname AS s, c.relname AS t FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace WHERE i.inhparent = to_regclass('{s}.precedents') LOOP
            EXECUTE format('CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I.%I (id)', r.t || '_id', r.s, r.t);
        END LOOP;
    END $$;
    CREATE TABLE IF NOT EXISTS {s}.files (
        id uuid NOT NULL, n integer NOT NULL, data bytea NOT NULL, at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (id, n));
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS store text;
    UPDATE {s}.spec_versions SET store = replace(model_id::text, '-', '') WHERE store IS NULL;
    ALTER TABLE {s}.spec_versions ALTER COLUMN store SET NOT NULL;
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS learned jsonb;
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS backtest uuid;
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS retired_at timestamptz;
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS ready boolean NOT NULL DEFAULT true;
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS gone boolean NOT NULL DEFAULT false;
    """,
    # The precedents the model held when each version was made (unknown for those made before).
    "ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS precedents_at bigint;",
    # Ada versions (docs/specs/ada-cloud.md, 12): the Ada version each was made with (its name) and the exact kernel
    # it was made and learned with. Every version before was ada-1-0, kernel 3.12.2: the cloud's only one until then.
    """
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS ada text NOT NULL DEFAULT 'ada-1-0';
    ALTER TABLE {s}.spec_versions ADD COLUMN IF NOT EXISTS kernel text NOT NULL DEFAULT '3.12.2';
    ALTER TABLE {s}.spec_versions ALTER COLUMN ada DROP DEFAULT, ALTER COLUMN kernel DROP DEFAULT;
    """,
)

_UNFENCED = """
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s AND c.relkind IN ('r', 'p') AND NOT EXISTS (SELECT 1 FROM pg_policies p
        WHERE p.schemaname = n.nspname AND p.tablename = c.relname AND p.policyname = 'tenant')
"""


def lock(conn: psycopg.Connection, schema: str, org: str) -> None:
    """The kernel's own lock on the schema (glyphh_postgres takes the same, so every change to the schema's tables
    waits on it), and the org for this transaction. Then a read of pg_namespace: taking its lock makes this backend
    read the catalog changes committed while it waited (an advisory lock does not), so an IF NOT EXISTS after it sees
    what another worker just made. Called first in its transaction."""
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"glyphh:{schema}",))
    conn.execute("SELECT set_config('glyphh.org_id', %s, true), (SELECT count(*) FROM pg_namespace)", (org,))


def fence(conn: psycopg.Connection, schema: str, org: str) -> int:
    """Row-level security on every table of the schema without it yet (the kernel's new partitions too). Returns
    how many tables it fenced."""
    names = [r[0] for r in conn.execute(_UNFENCED, (schema,)).fetchall()]
    same = sql.SQL("current_setting('glyphh.org_id', true) = {}").format(sql.Literal(org))
    for name in names:
        table = sql.Identifier(schema, name)
        conn.execute(sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(table))
        conn.execute(sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(table))
        conn.execute(sql.SQL("CREATE POLICY tenant ON {} USING ({}) WITH CHECK ({})").format(table, same, same))
    return len(names)


def _migrate(conn: psycopg.Connection, schema: str, org: str) -> int:
    s = sql.Identifier(schema)
    conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {}.ada_schema (version integer NOT NULL)").format(s))
    fence(conn, schema, org)
    found = conn.execute(sql.SQL("SELECT max(version) FROM {}.ada_schema").format(s)).fetchone()
    done = (found[0] if found else None) or 0
    for version, text in enumerate(MIGRATIONS, start=1):
        if version > done:
            conn.execute(sql.SQL(text).format(s=s))  # type: ignore[arg-type]
            conn.execute(sql.SQL("INSERT INTO {}.ada_schema (version) VALUES (%s)").format(s), (version,))
    fence(conn, schema, org)
    return len(MIGRATIONS) - min(done, len(MIGRATIONS))


def ensure(conn: psycopg.Connection, org: str) -> str:
    """The org's schema, made and brought to the latest shape. Returns its name."""
    schema = schema_for(org)
    with conn.transaction():
        lock(conn, schema, org)
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        _migrate(conn, schema, org)
    return schema


def exists(conn: psycopg.Connection, org: str) -> bool:
    found = conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema_for(org),)).fetchone()
    return found is not None


def migrate_all(conn: psycopg.Connection) -> int:
    """Every org schema brought to the latest shape (a worker's start). Returns how many migrations ran."""
    found = conn.execute(r"SELECT nspname FROM pg_namespace WHERE nspname ~ '^ada_[0-9a-f]{32}$' ORDER BY 1")
    ran = 0
    for (schema,) in found.fetchall():
        with conn.transaction():
            lock(conn, schema, org_of(schema))
            ran += _migrate(conn, schema, org_of(schema))
    return ran
