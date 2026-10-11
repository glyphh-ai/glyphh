# Data model

The rule: the data model is drawn here first, then built. Database `glyphh`. Every table's id is a GUID (`uuid`).

```mermaid
erDiagram
    plans ||--o{ orgs : "limits"
    orgs ||--o{ orgs : "parent of"
    orgs ||--o{ users : "has"
    orgs ||--o{ teams : "has"
    teams ||--o{ team_members : "has"
    users ||--o{ team_members : "is in"
    users ||--o{ tokens : "signs in with"
    orgs ||--o{ provider_keys : "brings"
    teams ||--o{ provider_keys : "may scope"
    orgs ||--o{ api_keys : "issues"
    api_keys ||--o{ requests : "made"
    provider_keys ||--o{ requests : "paid"

    plans {
        uuid id PK
        text name UK
        int price_cents "per month"
        text stripe_price_id UK "null for Free and Enterprise"
        int max_seats "null = no limit"
        int rpm_limit "requests per minute, null = no limit"
        int tpm_limit "tokens per minute, null = no limit"
        bool active
        int sort
        timestamptz created_at
        timestamptz updated_at
    }

    orgs {
        uuid id PK
        uuid parent_id FK "null only for Glyphh, the parent org"
        uuid plan_id FK
        text name
        int rpm_cap "null = the plan's limit"
        int tpm_cap "null = the plan's limit"
        text_array models "null = every catalog model"
        timestamptz created_at
    }

    users {
        uuid id PK
        uuid org_id FK
        text role "super_admin | org_admin | user"
        text email UK
        text first_name
        text last_name
        text image_url
        timestamptz created_at
        timestamptz updated_at
    }

    teams {
        uuid id PK
        uuid org_id FK
        text name "unique within the org"
        int rpm_cap "null = the org's limit"
        int tpm_cap "null = the org's limit"
        text_array models "null = the org's models"
        timestamptz created_at
    }

    team_members {
        uuid id PK
        uuid org_id FK "the team's and the user's org, enforced by both keys"
        uuid team_id FK
        uuid user_id FK "unique with team_id"
        timestamptz created_at
    }

    provider_keys {
        uuid id PK
        uuid org_id FK
        uuid team_id FK "null = the whole org"
        text provider "anthropic, openai, google, ..."
        bytea secret "encrypted; never returned"
        text last4
        uuid created_by FK
        timestamptz created_at
        timestamptz revoked_at
    }

    api_keys {
        uuid id PK
        uuid org_id FK
        uuid team_id FK "null = the whole org"
        uuid user_id FK "who made it"
        text name
        text key_hash UK
        text prefix "shown, to tell keys apart"
        timestamptz expires_at
        timestamptz last_used_at
        timestamptz revoked_at
        timestamptz created_at
    }

    requests {
        uuid id PK
        uuid org_id FK
        uuid team_id FK
        uuid user_id FK
        uuid api_key_id FK "null when a sign-in token made it"
        uuid provider_key_id FK
        text provider
        text model
        int status
        int input_tokens
        int output_tokens
        int duration_ms
        timestamptz created_at
    }

    tokens {
        uuid id PK
        uuid user_id FK
        text access_hash UK
        text refresh_hash UK
        timestamptz access_expires_at
        timestamptz refresh_expires_at
        timestamptz revoked_at
        timestamptz created_at
    }
```

## plans

What an org pays and what it may do. The limits on a plan are the limits on every org on it:

- `max_seats`: how many users the org may have.
- `rpm_limit` and `tpm_limit`: the org's requests and tokens per minute through the router.

`stripe_price_id` is the Stripe price an org subscribes to; Free and Enterprise have none (Free needs no checkout, Enterprise is arranged with us). A plan that is no longer sold is set `active = false`, never deleted, so orgs on it keep working.

The plans carried over from the old server:

| Plan | Price | Seats | Requests/min | Tokens/min |
|---|---|---|---|---|
| Free | $0 | 1 | 60 | 50,000 |
| Solo | $20 | 1 | 200 | 200,000 |
| Basic | $40 | 25 | 600 | 500,000 |
| Pro | $150 | 100 | 2,000 | 2,000,000 |
| Enterprise | arranged | no limit | no limit | no limit |

Left behind from the old server: the margin and the dollar pool (with keys brought by the user, Glyphh resells no inference), the SSO and governance flags, the price history, and the machine terms.

## orgs

Glyphh is the parent org: the one org with no parent. Every customer org's parent is Glyphh. Every org is on a plan: Glyphh itself is on Enterprise, and a new org starts on Free.

## users

A user belongs to one org and has one role in it:

- `super_admin`: runs Glyphh. Only users of the parent org.
- `org_admin`: runs their org.
- `user`: works in their org.

The profile is the user's first name, last name, email and profile image. The email is how a Google or GitHub sign-in finds the user.

## teams

Teams are optional. An org with no teams is flat: everything in it is shared across the org. Once an org has teams, everything in it is team scoped: a user sees and works in the teams they are a member of.

- A user can be a member of several teams.
- Org admins create teams and manage their members, and see every team in their org; super admins see every team everywhere.
- A team belongs to one org, and its members are users of that org.

## Caps

The plan sets an org's limits. An org admin can cap the org lower, and cap each team lower still, never above what sits over it:

- **Plan:** the ceiling (`rpm_limit`, `tpm_limit`).
- **Org:** `rpm_cap`, `tpm_cap`, at or under the plan's. Null means the plan's limit.
- **Team:** `rpm_cap`, `tpm_cap`, at or under the org's. Null means the org's limit.

The limit a request runs under is the smallest that applies to it.

## The gateway

The router passes a model call to its provider on the member's own key: Glyphh never pays for inference.

- **The model catalog is not a table.** It is the public list of models (about 3,900 across 130 providers, with each one's provider, kind, context size and prices), shipped with the server and updated with it.
- **Model access:** `models` on an org narrows the catalog for the whole org (null = every model); `models` on a team narrows it again (null = the org's). A call is checked against both.
- **provider_keys** are the keys members bring: per provider, for the whole org or one team, encrypted at rest and never returned after they are saved (only the last four characters are shown). A team's own key wins over the org's.
- **api_keys** are the keys Glyphh issues, so a script or a runtime can call the router; only a hash is stored. A sign-in token works too.
- **requests** is the log of every call: who, which model and provider, the outcome, the tokens and the time. It is what the rate limits count and what usage shows.

Left behind from the old gateway: LiteLLM's 80-odd tables, its per-row model deployments and credentials table, budgets, margins and the dollar pool (BYOK has no money to meter), spend aggregates, auto-routers, the stored copy of each member's key, and the per-model flags nothing enforced. The Pipedream lane (connections) is drawn separately when it is built.

## Scoping

Every API call and MCP tool runs as a principal: the user, their org, their role, and their teams. The role decides what an operation allows, the org decides which rows it sees, and in an org with teams the user's teams narrow that further. Row level security in Postgres enforces the org (and teams) under the code, so a bug in a query cannot reach another org's data.

## tokens

What the server hands out after a sign-in: a short-lived access token and a longer-lived refresh token. Only their hashes are stored, so a stolen database holds no usable token. A token is revoked by setting `revoked_at`.
