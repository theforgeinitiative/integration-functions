# integration-functions

GCP Cloud Functions for data integrations at [The Forge Initiative](https://theforgeinitiative.org). Written in Python, deployed via GitHub Actions.

## Functions

### `membership-sync`

Runs nightly. Queries Salesforce for current members and syncs that list to:

- **CheckMeIn** — full member roster upload via CSV
- **Google Groups** — adds/removes members from `members@theforgeinitiative.org`
- **Discord** — assigns/removes the Current Member role in configured guilds

Triggered nightly at 06:00 UTC by Cloud Scheduler.

### `checkmein-group-sync`

Runs hourly. Reads role assignments from `tfi-data.checkmein.roles` (via BigQuery) and reconciles each role to its corresponding Google Group, Discord role, and Salesforce campaign. Role-to-group mappings are stored in the `checkmein-role-configs` Secret Manager secret as a JSON array.

Currently synced roles: keyholder, shop steward, shop certifier. Mappings (Google Group, Discord role ID, Salesforce campaign ID) are configured in the `checkmein-role-configs` secret.

Triggered hourly by Cloud Scheduler.

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

## Triggering manually

Each function exposes an HTTP endpoint. Append `?dry_run=true` to log what would change without making any modifications.

```bash
curl -X POST <function-url>
curl -X POST "<function-url>?dry_run=true"
```

The function URL is available in the GCP console under Cloud Functions after deploy.

**Make.com:** use the **HTTP → Make a request** module with method `POST` and the function URL.

## GCP setup

See [DEPLOYMENT.md](DEPLOYMENT.md) for one-time GCP setup (secrets, scheduler jobs, Discord bot, GitHub Actions WIF).
