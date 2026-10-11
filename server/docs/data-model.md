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
        timestamptz created_at
    }

    team_members {
        uuid id PK
        uuid team_id FK
        uuid user_id FK "unique with team_id"
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

## Scoping

Every API call and MCP tool runs as a principal: the user, their org, their role, and their teams. The role decides what an operation allows, the org decides which rows it sees, and in an org with teams the user's teams narrow that further. Row level security in Postgres enforces the org (and teams) under the code, so a bug in a query cannot reach another org's data.

## tokens

What the server hands out after a sign-in: a short-lived access token and a longer-lived refresh token. Only their hashes are stored, so a stolen database holds no usable token. A token is revoked by setting `revoked_at`.
