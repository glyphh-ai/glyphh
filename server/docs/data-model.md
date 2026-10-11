# Data model

The rule: the data model is drawn here first, then built. Database `glyphh`. Every table's id is a GUID (`uuid`).

```mermaid
erDiagram
    plans ||--o{ orgs : "limits"
    orgs ||--o{ orgs : "parent of"
    orgs ||--o{ users : "has"
    users ||--o{ tokens : "signs in with"
    orgs ||--o{ models : "adds"
    orgs ||--o{ api_keys : "issues"

    plans {
        uuid id PK
        text name UK
        int price_cents "per month"
        text stripe_price_id UK "null for Free and Enterprise"
        int max_seats "null = no limit"
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

    models {
        uuid id PK
        uuid org_id FK
        text name "what super powers call it, unique in the org"
        text provider "anthropic, openai, google, fireworks, ..."
        text model "the provider's own model id"
        bytea api_key "encrypted; never returned"
        text api_key_last4
        text base_url "null = the provider's own"
        uuid created_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    api_keys {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "who made it"
        text name
        text key_hash UK
        text prefix "shown, to tell keys apart"
        timestamptz expires_at
        timestamptz last_used_at
        timestamptz revoked_at
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

What an org pays, and how many users it may have (`max_seats`).

`stripe_price_id` is the Stripe price an org subscribes to; Free and Enterprise have none (Free needs no checkout, Enterprise is arranged with us). A plan that is no longer sold is set `active = false`, never deleted, so orgs on it keep working.

The plans carried over from the old server:

| Plan | Price | Seats |
|---|---|---|
| Free | $0 | 1 |
| Solo | $20 | 1 |
| Basic | $40 | 25 |
| Pro | $150 | 100 |
| Enterprise | arranged | no limit |

Left behind from the old server: the margin and the dollar pool, the rate limits, the SSO and governance flags, the price history, and the machine terms. Glyphh governs nothing: limits and access belong to an AI gateway the customer puts in front of their models.

## orgs

Glyphh is the parent org: the one org with no parent. Every customer org's parent is Glyphh. Every org is on a plan: Glyphh itself is on Enterprise, and a new org starts on Free.

## users

A user belongs to one org and has one role in it:

- `super_admin`: runs Glyphh. Only users of the parent org.
- `org_admin`: runs their org.
- `user`: works in their org.

The profile is the user's first name, last name, email and profile image. The email is how a Google or GitHub sign-in finds the user.

## Models

Glyphh is a model runtime, not a gateway: it stores how a model is reached and never sits in the call, and it governs nothing. A customer who wants limits or access rules puts their own AI gateway in front of their models; a model's base URL can point at it. A super power names one of its org's models; when it runs, rrotor calls the provider directly with that model's key. Glyphh does not route, meter, limit or pay for model calls.

- **models** are what an org admin adds: a provider, the provider's model id, and the API key for it, plus a base URL for providers that need one. The key is encrypted at rest, never returned after it is saved (only the last four characters are shown), and handed only to a member's own runtime when a super power runs.
- The public list of models (about 3,900 across 130 providers, with each one's provider, kind, context size and prices) ships with the server to help pick one; it is reference data, not a table.
- **api_keys** are the keys Glyphh issues, so a script or a runtime can call the Glyphh API; only a hash is stored, with a short prefix shown to tell keys apart. A sign-in token works too.

Left behind from the old gateway: the router itself, LiteLLM's 80-odd tables, model access lists, the request log, budgets, margins and the dollar pool, spend roll-ups, auto-routers, and the per-model flags nothing enforced.

## Scoping

Every API call and MCP tool runs as a principal: the user, their org and their role. The role decides what an operation allows and the org decides which rows it sees. Row level security in Postgres enforces the org under the code, so a bug in a query cannot reach another org's data.

## tokens

What the server hands out after a sign-in: a short-lived access token and a longer-lived refresh token. Only their hashes are stored, so a stolen database holds no usable token. A token is revoked by setting `revoked_at`.
