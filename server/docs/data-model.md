# Data model

The rule: the data model is drawn here first, then built. Database `glyphh`. Every table's id is a GUID (`uuid`).

```mermaid
erDiagram
    plans ||--o{ orgs : "limits"
    orgs ||--o{ orgs : "parent of"
    orgs ||--o{ users : "has"
    orgs ||--o{ teams : "has"
    teams ||--o{ users : "has"
    orgs ||--o{ allowed_models : "limits to"
    teams ||--o{ allowed_models : "limits further to"
    catalog_models ||--o{ allowed_models : "allowed as"
    orgs ||--o{ allowed_connections : "limits to"
    teams ||--o{ allowed_connections : "limits further to"
    powers ||--o{ tool_permissions : "sets"
    super_powers ||--o{ tool_permissions : "overrides"
    users ||--o{ tokens : "signs in with"
    users ||--|| user_settings : "sets"
    users ||--o{ sign_in_identities : "signs in as"
    oauth_clients ||--o{ oauth_codes : "asks for"
    users ||--o{ oauth_codes : "approves"
    oauth_clients |o--o{ tokens : "issued to"
    users ||--o{ launch_tickets : "opens with"
    machines ||--o{ launch_tickets : "opened by"
    machines ||--o{ folders : "holds"
    machines ||--o{ fence_events : "reports"
    super_powers ||--o{ fence_events : "tried"
    runs ||--o{ fence_events : "during"
    users ||--o{ tool_permissions : "sets"
    orgs ||--o{ powers : "holds"
    users ||--o{ powers : "owns"
    users ||--o{ super_powers : "owns"
    orgs ||--o{ super_powers : "has"
    super_powers ||--o{ grants : "is granted"
    powers ||--o{ grants : "granted as"
    machines ||--o{ grants : "granted as"
    powers ||--o{ super_powers : "is the loop of"
    powers |o--o{ loops : "thinks with"
    powers ||--o{ slots : "declares"
    powers ||--o{ slots : "fills"
    super_powers ||--o{ schedules : "on a clock"
    powers ||--o{ schedules : "on a clock"
    machines ||--o{ schedules : "runs on"
    schedules ||--o{ runs : "fires"
    super_powers ||--o{ runs : "runs"
    machines ||--o{ runs : "ran on"
    runs ||--o{ usage_events : "spends"
    powers ||--o| models : "is a"
    providers ||--o{ catalog_models : "offers"
    providers ||--o{ models : "serves"
    catalog_models |o--o{ models : "picked from"
    powers ||--o| connections : "is a"
    powers ||--o| folders : "is a"
    powers ||--o| skills : "is a"
    powers ||--o| tasks : "is a"
    powers ||--o| plugins : "is a"
    powers ||--o| loops : "is a"
    powers ||--o| browsers : "is a"
    machines ||--o{ browsers : "holds"
    orgs ||--o{ api_keys : "issues"
    orgs ||--o| subscriptions : "pays through"
    plans ||--o{ subscriptions : "sold as"
    orgs ||--o{ credit_ledger : "earns and spends"
    orgs ||--o{ usage_events : "uses"
    users ||--o{ usage_events : "makes"
    powers ||--o{ usage_events : "called through"
    super_powers ||--o{ usage_events : "called from"
    machines ||--o{ usage_events : "called on"
    usage_events ||--o| credit_ledger : "spends"
    users ||--o{ machines : "registers"
    machine_sign_ins |o--o| machines : "registers"
    orgs ||--o{ invites : "invites"
    users ||--o{ invites : "sends"

    plans {
        uuid id PK
        text name UK
        int price_cents "per seat, per month"
        text stripe_price_id UK "null for Free and Enterprise"
        int max_seats "the most seats an org may have; null = no limit"
        int monthly_credits "included each billing period"
        int included_machines "null = no limit"
        int extra_machine_cents "per extra machine per month; null = no extras on this plan"
        text stripe_machine_price_id UK "the Stripe price extras are billed on"
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
        bool limit_models "true = only the org's allowed models"
        bool limit_connections "true = only the org's allowed connections"
        text image_key "the org's picture, in object storage"
        bool member_api_keys "members may make their own API keys"
        jsonb memory_policy "per lane (search, capture, sensitive): member, on or off"
        timestamptz created_at
    }

    teams {
        uuid id PK
        uuid org_id FK
        text name "unique in its org"
        bool limit_models "true = only the team's allowed models"
        bool limit_connections "true = only the team's allowed connections"
        timestamptz created_at
        timestamptz updated_at
    }

    allowed_models {
        uuid id PK
        uuid org_id FK
        uuid team_id FK "null = the org's list"
        uuid catalog_model_id FK "unique per list"
        timestamptz created_at
    }

    allowed_connections {
        uuid id PK
        uuid org_id FK
        uuid team_id FK "null = the org's list"
        text service "gmail, slack, ...; unique per list"
        timestamptz created_at
    }

    users {
        uuid id PK
        uuid org_id FK
        uuid team_id FK "null = in no team: only the org's limits apply"
        text role "super_admin | org_admin | user"
        text email UK
        text first_name
        text last_name
        text image_url
        text time_zone "every schedule reads its cron in it"
        timestamptz disabled_at "an org admin disabled the member"
        timestamptz created_at
        timestamptz updated_at
    }

    user_settings {
        uuid user_id PK, FK
        text theme "dark, light, system, ..."
        text notifications "on, off, ask"
        text permission_mode "ask, plan, accept_edits, auto: how new sessions start"
        text voice_mode "off, push_to_talk, continuous"
        bool voice_autoplay
        bool voice_brief "spoken replies kept short"
        bool memory_search "search and use past sessions"
        bool memory_capture "make memory from sessions"
        bool memory_sensitive "include sensitive topics"
        uuid embeddings_model_id FK "the model memory is indexed with; null = off"
        timestamptz memory_policy_accepted_at
        text memory_policy_version
        bool sandbox_strict "runs reach only the allowed hosts"
        text[] allowed_hosts "hosts every sandboxed run may reach"
        timestamptz updated_at
    }

    powers {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "whose it is: every power is one user's, for now"
        text kind "model, connection, folder, browser, ada, skill, task, plugin, loop"
        text name "unique for its owner"
        timestamptz disabled_at "set while a limit leaves it out: it stops working and can only be deleted; cleared when allowed again"
        text disabled_reason "which limit left it out"
        timestamptz created_at
        timestamptz updated_at
    }

    tool_permissions {
        uuid id PK
        uuid user_id FK "whose setting it is"
        uuid power_id FK "the power whose tool it is: a connection, a plugin, ...; null = one of rrotor's own built-in tools"
        text tool "the tool's name; unique per user, power (or built-in), tool and super power"
        uuid super_power_id FK "null = the user's own setting; set = that super power's override, for its autonomous runs"
        text permission "allow, ask, deny (an override is allow or deny)"
        timestamptz created_at
        timestamptz updated_at
    }

    models {
        uuid power_id PK, FK
        uuid provider_id FK
        uuid catalog_model_id FK "null = not in the catalog: a fine-tune, a private model"
        text model "the provider's own model id"
        text base_url "null = the provider's own"
        bytea api_key "encrypted; never returned"
        text api_key_last4
    }

    providers {
        uuid id PK
        text slug UK "anthropic, openai, google, fireworks, ..."
        text name "Anthropic"
        text logo_key "its logo, in object storage"
        text base_url "the provider's endpoint"
        bool active
        int sort
        timestamptz created_at
        timestamptz updated_at
    }

    catalog_models {
        uuid id PK
        uuid provider_id FK
        text model "the provider's own model id; unique per provider"
        text name "Claude Sonnet, GPT-5, ..."
        text description "one or two lines on what it is good for"
        text type "chat, embedding, image, audio, video"
        text logo_key "null = the provider's logo; set when the maker differs (Llama on Fireworks)"
        bool active
        timestamptz created_at
        timestamptz updated_at
    }

    connections {
        uuid power_id PK, FK
        text service "what it connects to: gmail, slack, ... (Pipedream calls it the app slug)"
        text account_id "the Pipedream account, once the user has connected it"
    }

    folders {
        uuid power_id PK, FK
        uuid machine_id FK "the machine the folder is on: the same path on two machines is two folders"
        text path "unique per machine for its owner"
    }

    browsers {
        uuid power_id PK, FK
        uuid machine_id FK "the rrotor its profile lives on"
        text profile "the profile's name in rrotor; its cookies and sessions never leave that machine"
    }

    skills {
        uuid power_id PK, FK
        text bundle_key "its files, in object storage"
    }

    tasks {
        uuid power_id PK, FK
        text bundle_key "its program, in object storage"
    }

    plugins {
        uuid power_id PK, FK
        text bundle_key "its files, in object storage"
    }

    loops {
        uuid power_id PK, FK
        text engine "claude_code (the member's Claude subscription), codex (their ChatGPT subscription) or glyphh (the Glyphh loop)"
        uuid model_id FK "for glyphh: the model it thinks with, one of the member's; null for a CLI, which signs in on the machine"
    }

    super_powers {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "whose it is: every super power is one user's"
        text name "unique for its owner"
        text description "when to use it: the main assistant reads it to hand work over"
        text instructions "its standing brief, at the head of every turn"
        int avatar_variant "1..16, the face it wears"
        text avatar_color "a CSS colour"
        text avatar_key "a picture instead of the face, in object storage"
        int personality "1..5: serious to playful; 3 = as it comes"
        int directness "1..5: gentle to blunt"
        int temperament "1..5: kind to spicy"
        text effort "low, medium, high, xhigh, max; null = the session's own"
        text role "orchestrator or worker"
        bool live "false = paused: its schedules hold, nothing deleted"
        jsonb map_layout "where its power map's cards sit, as the member left them"
        bool glyphh "true = the member's Glyphh, the super agent: one per member, granted everything"
        uuid loop_id FK "the loop that runs it: one of its owner's loops; every super power has one"
        uuid voice_model_id FK "its voice: the speech model it speaks with, one of the owner's; null = it does not speak"
        text voice_id "which of that model's voices it speaks in"
        text voice_name "that voice's name, as shown"
        uuid listen_model_id FK "the speech-to-text model it hears the member with; set on the member's Glyphh"
        jsonb definition "the rrotor definition, still to be drawn; its data lives in rrotor"
        text bundle_key "its files (workflows, pipelines, screens), in object storage"
        timestamptz created_at
        timestamptz updated_at
    }

    grants {
        uuid id PK
        uuid super_power_id FK "the super power granted it"
        uuid power_id FK "a power: folder, connection, model, skill, task, plugin (the loop is picked, not granted); or"
        uuid machine_id FK "a machine it may run on; or"
        uuid granted_super_power_id FK "a super power it may call (exactly one of the three)"
        text access "for a folder: read or write; null for anything else"
        bool denied "on the member's Glyphh only: taken away from what it otherwise has"
        timestamptz created_at
    }

    slots {
        uuid id PK
        uuid power_id FK "the task (or other power) that declares it"
        text name "what its program calls it: writer, reviewer, ..."
        uuid model_id FK "the model that fills it, one of the owner's; null = not filled yet"
        timestamptz created_at
        timestamptz updated_at
    }

    schedules {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "whose schedule it is"
        uuid super_power_id FK "what it runs: a super power; or"
        uuid power_id FK "a task (exactly one of the two)"
        uuid machine_id FK "where it runs"
        text name
        text cron "five fields"
        text time_zone "the zone the cron reads in: America/New_York, ..."
        jsonb input "what each run is handed"
        bool enabled
        timestamptz next_run_at
        timestamptz created_at
        timestamptz updated_at
    }

    runs {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "who it ran for"
        uuid super_power_id FK "what ran: a super power; or"
        uuid power_id FK "a task (exactly one of the two)"
        uuid schedule_id FK "null = started by hand, or by an agent"
        uuid machine_id FK "where it ran"
        text trigger "schedule, manual, agent"
        text mode "driven (the member is at it: ask asks) or autonomous (nobody is: ask is refused)"
        text status "queued, running, succeeded, failed, canceled, missed"
        text error "the reason, when it did not succeed"
        jsonb result "what it returned, kept small"
        text log_key "its full log, in object storage"
        timestamptz scheduled_for "the time the clock meant; null when not scheduled"
        timestamptz started_at
        timestamptz finished_at
        timestamptz created_at
    }

    subscriptions {
        uuid id PK
        uuid org_id FK, UK
        uuid plan_id FK
        text stripe_customer_id UK
        text stripe_subscription_id UK "null on Free"
        text status "trialing, active, past_due, canceled"
        int seats "the seats Stripe bills for"
        int extra_machines "bought on top of the plan's included machines"
        bool auto_top_up "buy a credit pack when the balance runs low"
        int auto_top_up_below "credits left that trigger it"
        int auto_top_up_pack "credits it buys"
        timestamptz current_period_start
        timestamptz current_period_end
        timestamptz created_at
        timestamptz updated_at
    }

    credit_ledger {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "who spent it; null for allowances and purchases"
        text entry "allowance, purchase, usage"
        int credits "plus for allowance and purchase, minus for usage"
        text source "a Stripe payment id for a purchase; null otherwise"
        uuid usage_event_id FK, UK "the call a usage entry pays for"
        timestamptz expires_at "the period's end for an allowance; null for a purchase"
        timestamptz created_at
    }

    usage_events {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "whose call it was"
        text kind "connection or ada"
        uuid power_id FK "the connection power, or the Ada model power"
        text service "a connection's service (gmail, slack, ...); for Ada, the model's id; kept as called"
        text tool "the tool or Ada operation: gmail-send-email, query, record, ..."
        uuid super_power_id FK "the super power that called it"
        uuid machine_id FK "the machine it ran on"
        uuid run_id FK "the run it was part of"
        text status "ok, error, refused"
        text error "the reason, for error and refused"
        int duration_ms "the time the call took, timed by the server"
        int input_tokens "Ada: the arguments as JSON, counted by the server"
        int output_tokens "Ada: the result, counted by the server"
        int credits "connection: max(1, ceil(seconds / 30)); Ada: its tokens at the Ada price; 0 when refused"
        int request_bytes
        int response_bytes
        timestamptz started_at
        timestamptz created_at
    }

    invites {
        uuid id PK
        uuid org_id FK
        text email "who is invited"
        text role "org_admin or user"
        uuid invited_by FK
        text token_hash UK "the invite link's token; only the hash is kept"
        timestamptz expires_at
        timestamptz accepted_at
        timestamptz revoked_at
        timestamptz created_at
    }

    machine_sign_ins {
        uuid id PK
        text code_hash UK "the code the machine holds; only the hash is kept"
        text user_code UK "the short code the member types or sees"
        text machine_name "what the machine calls itself"
        text source "approve (the machine shows a code, the member approves it) or one_click (minted approved, for a new host)"
        text host "for one_click: fly, aws, azure, gcp, digitalocean, hetzner, vps"
        text status "pending, approved, denied, used"
        uuid user_id FK "who approved or minted it"
        uuid machine_id FK "the machine it registered"
        int interval_seconds "how often the machine may ask"
        timestamptz last_polled_at
        timestamptz expires_at
        timestamptz created_at
    }

    machines {
        uuid id PK
        uuid org_id FK
        uuid user_id FK "whose machine it is"
        text name "unique for its owner"
        text host "where it runs: fly, aws, azure, gcp, digitalocean, hetzner, vps, docker on a laptop; shown, never a limit"
        text platform "macos, windows, linux"
        text version "the rrotor build it runs"
        text token_hash UK "what it connects with; only the hash is kept"
        text ssh_public_key UK "the machine's SSH key; its private key never leaves the machine"
        text ssh_fingerprint "shown when the machine is registered, to check by eye"
        bool shell_enabled "false until the member turns it on: a shell on this machine over SSH"
        int[] local_ports "ports on this machine its runs may reach"
        timestamptz last_seen_at "null = never connected"
        timestamptz revoked_at
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

    sign_in_identities {
        uuid id PK
        uuid user_id FK
        text provider "google or github"
        text subject "the provider's own id for the person; unique per provider"
        text email "the email the provider gave, at the last sign-in"
        timestamptz last_used_at
        timestamptz created_at
    }

    oauth_clients {
        uuid id PK
        text client_id UK "what the agent host sends"
        text name "Claude Code, Cursor, ChatGPT, ..."
        text[] redirect_uris
        timestamptz created_at
    }

    oauth_codes {
        uuid id PK
        uuid oauth_client_id FK
        uuid user_id FK "who approved it"
        text code_hash UK "only the hash is kept"
        text redirect_uri
        text code_challenge "PKCE"
        timestamptz expires_at "a minute or so"
        timestamptz used_at "a code works once"
        timestamptz created_at
    }

    launch_tickets {
        uuid id PK
        uuid user_id FK "the only member it opens for"
        uuid machine_id FK "the only machine it opens"
        text page "where in rrotor's UI it lands: home, a super power, a model's key, ..."
        text token_hash UK "only the hash is kept"
        timestamptz expires_at "a minute"
        timestamptz used_at "a ticket works once"
        timestamptz created_at
    }

    fence_events {
        uuid id PK
        uuid org_id FK
        uuid user_id FK
        uuid machine_id FK "where it happened"
        uuid super_power_id FK "what tried"
        uuid run_id FK "in which run"
        text kind "path, network, channel"
        text detail "what it reached for: a path, a host, a channel"
        timestamptz created_at
    }

    stripe_events {
        uuid id PK
        text stripe_event_id UK "Stripe's own id: an event is handled once"
        text type
        timestamptz received_at
        timestamptz processed_at
    }

    tokens {
        uuid id PK
        uuid user_id FK
        uuid oauth_client_id FK "the agent host it was issued to; null = the player or rrotor's UI"
        text access_hash UK
        text refresh_hash UK
        timestamptz access_expires_at
        timestamptz refresh_expires_at
        timestamptz revoked_at
        timestamptz created_at
    }
```

![The data model](img/data-model.png)

## orgs

Glyphh is the parent org: the one org with no parent. Every customer org's parent is Glyphh. Every org is on a plan: Glyphh itself is on Enterprise, and a new org starts on Free.

**For now an org is for billing and for limiting models and connections:** its plan, subscription, seats, machines and credits, who is in it (members and invites), and which models and connections its users may add (below). It owns no powers or super powers; those are each user's. Rows still carry `org_id` so the database keeps every org's data apart and counts its limits.

## plans

What an org pays per seat each month, and how many seats it may have (`max_seats`).

Seats are billed as the old server billed them (his rule, 2026-09-18):

- **A seat is an active user.** The subscription's `seats` is what Stripe bills for.
- **Adding a seat mid-cycle** raises `seats` at once, and the part-month is billed on the next invoice, never charged on the spot.
- **Removing a seat never lowers `seats` mid-cycle.** It drops only when the next invoice is created, with nothing refunded for a month already billed.
- **The billing date never moves:** it is set when the subscription starts.
- **At `max_seats`, an org upgrades to add more people.**

`stripe_price_id` is the Stripe price an org subscribes to; Free and Enterprise have none (Free needs no checkout, Enterprise is arranged with us). A plan that is no longer sold is set `active = false`, never deleted, so orgs on it keep working.

The plans carried over from the old server:

| Plan | Price per seat | Seats | Machines included | Extra machines |
|---|---|---|---|---|
| Free | $0 | 1 | 2 | none |
| Solo | $20 | 1 | to set | to set |
| Basic | $40 | 25 | to set | to set |
| Pro | $150 | 100 | to set | to set |
| Enterprise | arranged | no limit | no limit | n/a |

An org that already has its included machines plus its extras cannot register another: signing in from one more machine is refused with the reason (on Free: "Free includes 2 machines. Upgrade, or remove one."), and nothing is half registered.

Left behind from the old server: the margin and the dollar pool, the rate limits, the SSO and governance flags, the price history, and the machine terms. Beyond which models and connections users may add, Glyphh governs nothing: spend and rate limits belong to an AI gateway the customer puts in front of their models.

## users

A user belongs to one org and has one role in it:

- `super_admin`: runs Glyphh. Only users of the parent org.
- `org_admin`: runs their org's billing and members, and sees its usage.
- `user`: works in their org.

The profile is the user's first name, last name, email and profile image. A Google or GitHub sign-in finds the user by the provider's own id for them (below, Signing in), never by email alone. A user is in at most one team (`team_id`).

**user_settings** holds the member's own settings from the old app's Settings pages: theme, notifications, how new sessions start, voice, memory and its consent, and the sandbox's allowed hosts. What only ever applied to the desktop app's windows (workspaces, tabs, layouts, the dock, window sizes) is gone; a machine's own settings (its granted folders, its local ports, its shell) live on the machine.

## Teams: limiting models and connections

The org's Models and Connections pages exist only to say which models and connections users may add. They hold no keys and no accounts: a user still adds their own model with their own key, and connects their own account.

- **Two settings, two lists, at the org and at every team, with the same behaviour:** `limit_models` with `allowed_models` (picked from the catalog), and `limit_connections` with `allowed_connections` (services: Gmail, Slack, ...).
- **Everything is allowed by default:** both settings start off, and a user may add any model in the catalog and connect any service.
- **Limiting at the org:** when the org turns a setting on, the org admin adds what is allowed, and only that is allowed, org wide.
- **Limiting at a team:** a team turns its own setting on and lists what its members may add. Under an org that limits, a team can only narrow it: its list is part of the org's list, never more.
- **A user adds only what applies to them:** their team's list if their team limits, otherwise the org's if the org limits, otherwise anything. A user is in at most one team; a user in none has only the org's limits.
- **The database enforces it:** a model or connection power outside the user's lists is refused with the reason, and taking an entry off the org's list takes it off every team's list too.

**A limit set later disables what it leaves out.** A model or connection a user already has stops working the moment a limit leaves it out: the database marks it disabled with the reason, rrotor is never handed it, and its calls are refused. A disabled power can only be deleted, never edited. When the limit no longer leaves it out (the item is allowed again, or the limit is turned off), it comes back on its own: the mark is cleared and everything hanging off it works as before (its grants, tool permissions, slots, schedules, key and account), with nothing for the user to redo.

## Invites

An org admin invites someone by email, with the role they will have. The invite link carries a token (only its hash is kept) and expires; signing in with Google or GitHub from it, as that email, makes the user in the org, and the invite is accepted. An open invite holds a seat, so an org at `max_seats` cannot invite more; an accepted one becomes a billed seat, and a revoked or expired one frees its seat. Only one open invite per email per org.

## Signing in

- **sign_in_identities:** a person signs in with Google or GitHub, and the server finds them by the provider's own id for them (`subject`), never by email alone: an email that changes, or a GitHub account with a hidden email, still finds the same person, and an email can never be used to reach someone else's account. The first sign-in links by email, once, through an invite or a new org.
- **The plugin signs in with OAuth:** an agent host (Claude Code, Cursor, ChatGPT) is an `oauth_clients` row; the member approves it in the browser, the host gets a one-time code (`oauth_codes`, with PKCE, a minute to live), and trades it for tokens issued to that client, so the member can see and revoke each host on its own.
- **launch_tickets:** how a machine's UI is opened, from Claude, the player or an agent's link (to enter a model's key, say): issued by the server for one member and one machine, landing on one page, for a minute, once. The rrotor checks it with the server and starts the session, so a member signs in once, on the server, never on a machine.

## tokens

What the server hands out after a sign-in: a short-lived access token and a longer-lived refresh token. Only their hashes are stored, so a stolen database holds no usable token. A token is revoked by setting `revoked_at`.

A token issued to an agent host carries its OAuth client (`oauth_client_id`), so each host is revoked on its own; the player's and rrotor's UI's carry none. Machines have their own token on `machines`, not here.

**api_keys** are the keys Glyphh issues, so a script or a runtime can call the Glyphh API; only a hash is stored, with a short prefix shown to tell keys apart.

## Powers

Everything a super power uses is a power: a model, a connection, a folder, a skill, a task, a plugin, or the loop that runs it. Who installed it is the control, with one more: the org and its teams may limit which models and connections can be added (above). Glyphh governs nothing else:

- **Models are a user's:** each person adds their own, with their own key. Nothing is shared or deduplicated: ten people adding the same model are ten rows, each with its own key, and one person may add the same model more than once (one per super power, say, to see each one's spend at the provider).
- **Connections are a user's:** always one person's own account (Pipedream accounts belong to a person; there are no shared or system accounts).
- **Folders, skills, tasks and plugins are a user's too:** for now every power is one person's own, built or installed for themselves. The org installs none.

The database enforces it: every power has a `user_id`.

Every power is a row in `powers` (who owns it, its kind and name), and one row in the table for its kind, holding that kind's own columns: `models`, `connections`, `folders`, `browsers`, `skills`, `tasks`, `plugins` or `loops` (which engine runs a super power or the main assistant: Claude Code or Codex on the member's subscription, or the Glyphh loop on one of their models). A super power points at `powers`, whatever the kind. What skills, tasks and plugins hold beyond their files is drawn when they are built.

- **A model** is a provider, the provider's model id and the API key (an optional base URL for providers that need one). rrotor calls the provider directly with that key: Glyphh never sits in the call, never sees its rates or prices, and never counts its tokens. What a model costs is between the person and their provider. A customer who wants limits or access rules puts their own AI gateway in front, through the base URL.
- **A connection** is a user's own account at Pipedream: the service it connects to (Gmail, Slack, ...) and the account id. Pipedream calls a service an app; Glyphh says service, because an app is something else here. Glyphh stores no sign-in for it: Pipedream holds the account and its tokens, under the Glyphh user's id as Pipedream's external user id. Linking one: the server asks Pipedream for a connect token for that user, and Pipedream's own page does the sign-in. Using one: the loop reaches Pipedream's MCP server (`remote.mcp.pipedream.net/v3`) with the Pipedream project, environment, service (`x-pd-app-slug`) and the user's id as headers, and a short-lived Pipedream access token the server mints for the run (Glyphh's Pipedream client credentials never leave the server). Only Glyphh's connections are used: a super power's loop gets exactly its connections, nothing of the loop's own.
- **A folder** is a path on one machine (`machine_id`): the same path on two machines is two folders, and a folder grant says read or write.
- **An Ada model** is a member's own, like every power: the model's id on Glyphh's Ada service (`am_...`). Its kernel and records stay on Glyphh's servers; a super power is granted it, and a task calls it through the server, billed per token. Shared through Discover like any power.
- **A browser** is a browser profile on one rrotor: its cookies and signed-in sessions live there and never leave that machine or reach the server. It is granted like a folder, so one super power's signed-in sites are never another's.
- **Skills, tasks and plugins** are bundles of files in object storage (`bundle_key`); whether each save keeps a version is still open.
- **A secret** (a key, a sign-in) is encrypted at rest, never returned after it is saved, and handed only to the member's own runtime when a super power runs.
- **The catalog** is what rrotor's UI shows when someone picks a model, and where every model's logo comes from: `providers` (each with its name and logo) and `catalog_models` (each provider's models, with a name, a description and a type). Every entry shows the provider's logo, the provider, the model's name, its description and its type. It is Glyphh's reference data, the same for every org: anyone signed in reads it, only super admins change it. It starts from the old server's list (about 3,900 models across about 125 providers) and its 143 provider logos, kept in object storage. It holds no prices, rates or limits.
- **A model power** points at its provider (always) and at the catalog entry it was picked from (when there is one), so it shows that logo and name wherever it appears. A model the catalog does not have (a fine-tune, a private model) is still added, by its provider and model id, and wears the provider's logo.

Left behind from the old gateway: the router itself, LiteLLM's 80-odd tables, model access lists, the request log, budgets, margins and the dollar pool, spend roll-ups, auto-routers, and per-model flags nothing enforced.

## Tool permissions

Every tool a power brings (each tool of a connection, of a plugin's MCP server, ...) has a permission, set where rrotor's UI shows that power:

- **The user's own setting:** `allow` (runs without asking), `ask` (asks each time) or `deny` (never runs). A tool with no row is `ask`.
- **A super power's override:** for its autonomous runs, a super power can set a tool to `allow` or `deny`, whatever the user's own setting says. With no override, the user's own setting applies.
- **Autonomous means nobody to ask:** in a run nobody is watching, `ask` is refused, so an autonomous super power uses only tools that are allowed, by the user or by its override.
- **rrotor's own tools** (its ~250 built-in tools) have permissions too: a row with no power is a built-in tool's.
- **Where it is enforced:** a connection call at the server's relay, which every connection call passes through, so it holds even against a modified rrotor; every other tool in rrotor, which hands the loop only what is allowed.

## Super powers

Each member has one Glyphh, the super agent (`glyphh` true): it has every power, every super power and every machine they have, and needs no grants. Every other super power sits under it and has only its **grants**: each grant gives it one power (a folder, a connection, a model, a skill, a task or a plugin), one machine it may run on, or one other super power it may call. Nothing ungranted is ever handed to it, whether or not anyone is watching. A super power is one user's own, like every power: the org installs none.

**A loop runs it; models are granted.** Every super power has one loop (`loop_id`): Claude Code or Codex on the member's subscription, or the Glyphh loop on one of their models. The member's Glyphh has one too: its loop is the main assistant's. A CLI's sign-in never reaches this database; it stays in the CLI on the machine. Its models are grants like any other power, as many as it needs: the super power uses them directly, and the powers it has use them too (a task's slots).

**A super power's configuration** is everything its edit screen sets (ported field for field from the old app's editor): its name, description, instructions, avatar, voice, personality, directness and temperament sliders, effort, role, whether it is live, and its power map's layout. The member's Glyphh has the same fields, and has everything except what the member takes away from it: those are grants marked `denied`, so a new connection or model reaches Glyphh by itself. Left behind: per-model dollar caps (Glyphh never meters model calls) and the old per-agent guardrails, which nothing enforced.

**Every super power carries a voice,** part of its configuration on its edit screen, beside its avatar and name (ported from the old app's super power editor): a speech model of the member's own (`voice_model_id`) and one of that model's voices (`voice_id`), with a sample to hear before saving. The member's Glyphh also has the model it hears them with (`listen_model_id`). All are the member's own models, called directly on their keys; audio never reaches this database.

A super power's own files (its workflows, pipelines and screens) are a bundle in object storage (`bundle_key`); `definition` holds the rrotor definition, still to be drawn. What it stores (its data, vectors and graph) lives in rrotor, never here. Where the content of its conversations lives is still open.

## Slots

A task declares **slots**: the steps its program calls by name (`research`, `write`), and each slot is filled with a model. A task on a clock can run Gemini for step one and Claude for step two. A run is refused, with the slot named, while a slot it calls is empty. The UI for filling slots is still to be designed.

## Schedules and runs

Anything that runs on its own can be put on a clock: a super power or a task.

- **schedules:** what runs, on which of the member's machines, a five-field cron read in its own time zone, and the input each run is handed. Switched off with `enabled`, never deleted to pause.
- **The clock is the server's.** When a schedule is due, the server sends the run to its machine over the machine's connection. A machine that is offline at that moment gets the run marked `missed`, with the reason: nothing piles up and fires later in a burst.
- **A run is driven or autonomous** (`mode`): driven when the member is at it, so a tool set to `ask` asks them; autonomous when nobody is (a schedule, an agent), so `ask` is refused.
- **runs** is the history: every run, whether the clock, the member or an agent started it, with its status, its error, a small result and its full log (in object storage). A schedule's history is its runs. A run's connection calls are its usage events, so a run shows what it cost.
- **Who sees what:** as for usage. A user sees their own runs, an org admin the org's.

## Machines

Signing in always happens from a machine, and signing in is how a machine is registered: rrotor asks the server for a code, the member approves it in the browser, and the server registers the machine and issues its tokens (`machine_sign_ins` holds the code while it waits, only as a hash). Ported from the old server's device sign-in.

**One-click hosting** registers a new machine the same way, without the approve step: the member asks rrotor's UI or the plugin for a new host, the server mints a sign-in already approved (`source` one_click, the host named), and the host's button carries its code. On first boot the machine trades it for its own token and SSH key; the code works once and for minutes, then it is `used`. No code is minted when the plan has no machine left, so nothing is half set up.

A machine is a registered rrotor, the same full image wherever it runs: a server on any host, or a laptop through Docker. It connects out to the server with its own token (only the hash is kept) and reports what it is: where it runs, its platform, and the rrotor version it runs (builds update themselves, so the server sees which version each machine is on). `last_seen_at` says when it was last online. A folder is always on one machine (`folders.machine_id`): the same path on two machines is two folders, and a folder grant says whether the super power may only read it or also write it (`grants.access`). At sign-in a machine also makes its own SSH key pair: the private key stays on the machine, the public key is registered here with its fingerprint (see the architecture, Machine to machine). A plan includes a number of machines (`included_machines`). An org can add more for a monthly price per extra machine, set per plan (`extra_machine_cents`, billed on the plan's Stripe price for extras); the subscription carries how many it bought (`extra_machines`). An org can register up to its included plus its extra machines; revoking one stops it connecting and frees its place.

**Which server process holds a machine's connection is not in this database:** it is live state that is only true right now, so it lives in Redis (see the architecture, Data). `last_seen_at` here is updated when a machine connects and disconnects, not on every heartbeat.

**fence_events** are what rrotor reports when something inside a run reaches past its fence: a path that is not mounted, a host not on its network list, a channel it was not granted. The relay never reads the stream to find them; rrotor tells the server, and rrotor's UI shows them ("this super power tried to leave its folders").

A machine's shell over SSH is off until the member turns it on (`shell_enabled`).

## Billing and usage

An org pays a monthly fee for its plan, and the plan includes credits each billing period. Usage spends credits, and a Glyphh credit is a Pipedream credit: 30 seconds of a connection call. The server relays every connection call and times it, so a call costs `max(1, ceil(seconds / 30))` credits, exactly what Pipedream bills Glyphh for it. Model calls cost nothing here: they go straight to the provider on the member's own key.

What Pipedream charges Glyphh (Connect, Startup plan): $99 a month billed annually ($150 monthly) for 100 external users and 10,000 credits a month, then $2 per external user and $0.012 per credit. A connected user is a seat cost, so it belongs in the plan's price per seat; a call is a credit.

- **The cap is the tier.** When an org's credits run out, its connection calls stop until the next period, with a clear message; there is never a surprise bill. An org can upgrade, or buy a credit pack (a one-time purchase that does not expire with the period).
- **subscriptions** tie an org to its Stripe customer and subscription, its plan, its status and its current period. Stripe keeps the invoices and payment methods.
- **credit_ledger** is the whole story of an org's credits, append only: each period's allowance, each pack bought, and each use. The balance is the sum of what has not expired, so it is never stored twice. A usage entry points at the call it paid for (`usage_event_id`), one entry per call.

## Usage

Every usage event is logged in one place: the server, which every billed call passes through. Two kinds are billed: a connection call (rrotor → connector → server → Pipedream), a cost Glyphh pays, and an Ada call (rrotor → server → Ada, our own kernel), which costs Glyphh only its compute. Every one goes through the server, so the server sees each call whole: who, through which connection, from which super power, on which machine, how long, and what it cost. Nothing is reported by the runtime about itself, so a modified rrotor cannot under-report.

One call, as the relay handles it:

1. **Check:** lock the org's row and read the balance. At 0, the call is refused with the reason and logged as `refused` (0 credits). Nothing reaches Pipedream.
2. **Call:** relay it to Pipedream and time it.
3. **Record:** in one transaction, a `usage_events` row and its `credit_ledger` usage entry. A call that fails at Pipedream is still logged (`error`) and still costs what Pipedream bills for it.

The check runs before the cost is known, so calls already in flight when the balance reaches 0 finish and are counted: the balance can dip below 0 by at most those calls, and the next call is refused. It never turns into a bill.

- **usage_events** is append only: never updated, never deleted by a request. It holds what was called and how it went, **never what went through it**: no arguments, no results, no message bodies. Those are the member's own data, and they stay between the runtime and Pipedream.
- **Model calls are not usage.** They go straight to the provider on the member's key, and Glyphh never sees them. Jev is one of them: a TypeSafe model the member adds with their own key, never on Glyphh's key, never through the server, never charged.
- **An Ada call is priced on its tokens:** input is its arguments as JSON, output its result, both counted by the server with one tokenizer; the cost is the larger of the tokens at the Ada price and a floor per call. The old server's prices are the start: Ada $2 per million tokens in and $10 out with a $0.0005 floor; a published Ada model a cent per million each way. How that price is stated in credits is still open.
- **Operational logs are separate:** request logs and traces go to OpenTelemetry, tagged by org; they are not billing and do not decide a charge.
- **Size:** the table is partitioned by month on `created_at`, indexed by org and time, and by org, user and time, so every page reads one org's range.

### Who sees what

The same rows serve every view, scoped by the principal:

- **A user** sees their own calls and their org's balance.
- **An org admin** sees every call in the org, by user, by connector, by super power, by machine and by day, and the ledger.
- **A super admin** sees every org, and what Glyphh owes Pipedream for it: the same credits, at Pipedream's price.

## Stripe

**stripe_events** records every Stripe webhook by Stripe's own event id, so an event delivered twice is handled once: a credit pack is never added twice and a seat change never applied twice.

## Limits are enforced by the database

Every limit (seats, machines, credits, and the org's and teams' allowed models and connections) holds even when requests race or code has a bug:

- **The database enforces it.** A trigger refuses a write that would take an org over its limit: a machine past its included plus extra machines, a user or invite past its seats, a model or connection outside the user's allowed lists. Credits are checked by the connection relay under the same org lock. A bug in a route cannot get around it.
- **No races.** The check locks the org's row before counting, so requests at the same moment are taken one after another; exactly one gets the last place, and the rest are refused with the reason.
- **Freed at once:** a revoked machine, a removed user, a revoked or expired invite stops counting immediately.
- **Downgrades never cut anyone off:** an org over its new plan's limit keeps what it has and cannot add more until it is back under.
- **Tested for each limit:** the limit, the refusal and its message, freeing a place, the downgrade rule, and concurrent requests racing for the last place.

## Scoping

Every API call and MCP tool runs as a principal: the user, their org and their role. The role decides what an operation allows and the org decides which rows it sees. Row level security in Postgres enforces the org under the code, so a bug in a query cannot reach another org's data. Inside an org, powers, super powers, machines, runs and usage are each one user's: a user reaches only their own, an org admin reads the org's usage and runs (never its keys), a super admin every org's.
