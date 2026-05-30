# integration-functions

GCP Cloud Functions for data integrations at [The Forge Initiative](https://theforgeinitiative.org). Written in Python, deployed via GitHub Actions.

## Functions

### `membership-sync`

Runs nightly. Queries Salesforce for current members and syncs that list to:

- **CheckMeIn** — full member roster upload via CSV
- **Google Groups** — adds/removes members from `members@theforgeinitiative.org`
- **Discord** — assigns/removes the Current Member role in configured guilds

Triggered by Cloud Scheduler (nightly at 06:00 UTC) via the `membership-sync` Pub/Sub topic.

### `checkmein-group-sync`

Runs hourly. Reads role assignments from `tfi-data.checkmein.roles` (via BigQuery) and reconciles each role to its corresponding Google Group, Discord role, and Salesforce campaign.

#### Synced roles

| CheckMeIn field | Google Group | Discord role | Salesforce campaign |
|---|---|---|---|
| `keyholder` | ✓ | ✓ | ✓ |
| `steward` | ✓ | ✓ | ✓ |
| `certifier` | ✓ | ✓ | ✓ |

The `coach` field exists in BigQuery but is not currently synced.

Actual group emails, Discord role IDs, and campaign IDs are stored in the `checkmein-role-configs` Secret Manager secret as a JSON array — not in this repo. To add or update a role mapping, edit that secret directly. Schema:

```json
[
  {
    "field": "keyholder",
    "group_email": "keyholders@theforgeinitiative.org",
    "discord_role_id": "123456789012345678",
    "campaign_id": "701Hs00000XXXXXXIAQ"
  }
]
```

Triggered by Cloud Scheduler (hourly) via the `checkmein-group-sync` Pub/Sub topic.

## Repository structure

```
common/                  # Shared API clients (copied into each function at deploy time)
  salesforce.py          # Salesforce REST client (OAuth2 client credentials)
  checkmein.py           # CheckMeIn CSV uploader
  google_groups.py       # Google Admin Directory API
  discord_client.py      # Discord role management via discord.py
  bigquery_client.py     # BigQuery client for CheckMeIn role data
functions/
  membership_sync/
    main.py              # Cloud Function entry point
    requirements.txt
  checkmein_group_sync/
    main.py              # Cloud Function entry point
    requirements.txt
tests/
.github/workflows/
  ci.yml                 # Run tests + lint on pull requests
  deploy.yml             # Deploy to GCP on push to main
```

The `common/` package is copied into the function's source directory at deploy time so Cloud Functions sees a single flat directory. `functions/*/common/` is gitignored.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt \
  -r functions/membership_sync/requirements.txt \
  -r functions/checkmein_group_sync/requirements.txt

# Run tests
pytest

# Check formatting
black --check .

# One-time setup
ln -sfn ../../common functions/membership_sync/common
ln -sfn ../../common functions/checkmein_group_sync/common

cp .env.example .env  # fill in any missing values

# Authenticate ADC with the Workspace scope (requires your account to be a Workspace admin)
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/admin.directory.group.member

# Run
python functions/membership_sync/main.py --dry-run
python functions/checkmein_group_sync/main.py --dry-run
```

## GCP setup

These are one-time steps. The deploy workflow handles subsequent deployments automatically.

### 1. Secrets in Secret Manager

Create the following secrets in GCP Secret Manager:

All runtime configuration — sensitive or not — lives here so values can be updated without touching the deployment pipeline.

| Secret name | Description |
|---|---|
| `sfdc-url` | Salesforce instance URL (e.g. `https://tfi.my.salesforce.com`) |
| `sfdc-client-id` | Salesforce connected app client ID |
| `sfdc-client-secret` | Salesforce connected app client secret |
| `checkmein-url` | CheckMeIn site URL |
| `checkmein-username` | CheckMeIn admin username |
| `checkmein-password` | CheckMeIn admin password |
| `discord-bot-token` | Discord bot token |
| `discord-guild-tfi-id` | TFI Discord guild (server) ID |
| `discord-guild-tfi-member-role-id` | ID of the Current Member role in the TFI guild |
| `groups-members-email` | Members Google Group address (e.g. `members@theforgeinitiative.org`) |
| `groups-exceptions` | Comma-separated emails always kept in the group regardless of membership |
| `checkmein-role-configs` | JSON array of role→group/discord/campaign mappings for `checkmein-group-sync` |

### 2. Google Groups — Domain-Wide Delegation

In the Google Workspace Admin Console, configure Domain-Wide Delegation for the function's runtime service account with scope `https://www.googleapis.com/auth/admin.directory.group.member`. The function uses ADC, so no key file or extra configuration is needed in the code.

### 3. Discord bot

1. Create a bot in the [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable the **Server Members Intent** (required for fetching all guild members)
3. Invite the bot to each guild with `Manage Roles` permission
4. Ensure the bot's role is positioned above the Current Member role in each guild's role hierarchy

### 4. Pub/Sub topics and Cloud Scheduler

Each function is triggered by publishing a message to its Pub/Sub topic. The message body is `{}` for a normal run.

```bash
gcloud pubsub topics create membership-sync --project PROJECT
gcloud pubsub topics create checkmein-group-sync --project PROJECT
```

**Cloud Scheduler:**
```bash
# membership-sync — nightly at 06:00 UTC
gcloud scheduler jobs create pubsub membership-sync-nightly \
  --location us-central1 \
  --schedule "0 6 * * *" \
  --time-zone "UTC" \
  --topic projects/PROJECT/topics/membership-sync \
  --message-body '{}'

# checkmein-group-sync — hourly
gcloud scheduler jobs create pubsub checkmein-group-sync \
  --location us-central1 \
  --schedule "0 * * * *" \
  --time-zone "UTC" \
  --topic projects/PROJECT/topics/checkmein-group-sync \
  --message-body '{}'
```

To trigger manually:
```bash
gcloud pubsub topics publish membership-sync --message '{}'
gcloud pubsub topics publish checkmein-group-sync --message '{}'
```

**Make.com:**

Use the **Google Cloud Pub/Sub → Publish a Message** module. Connect it with a GCP service account that has `roles/pubsub.publisher` on the relevant topic.

### 5. GitHub Actions — Workload Identity Federation

Avoids storing long-lived GCP credentials in GitHub. One-time setup:

```bash
# Create a WIF pool and provider bound to this repo
gcloud iam workload-identity-pools create github \
  --location global \
  --display-name "GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github-actions \
  --location global \
  --workload-identity-pool github \
  --issuer-uri "https://token.actions.githubusercontent.com" \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition "assertion.repository=='theforgeinitiative/integration-functions'"

# Grant the deployer service account access via WIF
gcloud iam service-accounts add-iam-policy-binding deployer@PROJECT.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/theforgeinitiative/integration-functions"
```

Add these GitHub repository secrets:

| Secret | Value |
|---|---|
| `GCP_PROJECT_ID` | GCP project ID |
| `WIF_PROVIDER` | Full WIF provider resource name |
| `GCP_SERVICE_ACCOUNT` | Deployer service account email |
