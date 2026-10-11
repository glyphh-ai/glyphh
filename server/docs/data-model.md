# Data model

The rule: the data model is drawn here first, then built. Database `glyphh`. Every table's id is a GUID (`uuid`).

```mermaid
erDiagram
    orgs ||--o{ orgs : "parent of"
    orgs ||--o{ users : "has"
    users ||--o{ tokens : "signs in with"

    orgs {
        uuid id PK
        uuid parent_id FK "null only for Glyphh, the parent org"
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

## orgs

Glyphh is the parent org: the one org with no parent. Every customer org's parent is Glyphh.

## users

A user belongs to one org and has one role in it:

- `super_admin`: runs Glyphh. Only users of the parent org.
- `org_admin`: runs their org.
- `user`: works in their org.

The profile is the user's first name, last name, email and profile image. The email is how a Google or GitHub sign-in finds the user.

## tokens

What the server hands out after a sign-in: a short-lived access token and a longer-lived refresh token. Only their hashes are stored, so a stolen database holds no usable token. A token is revoked by setting `revoked_at`.
