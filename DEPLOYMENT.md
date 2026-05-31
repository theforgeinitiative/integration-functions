# GCP Deployment

One-time setup steps. The deploy workflow handles subsequent deployments automatically on push to `main`.

## 1. Secrets in Secret Manager

All runtime configuration — sensitive or not — lives in GCP Secret Manager so values can be updated without touching the deployment pipeline.

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

## 2. Google Groups — Domain-Wide Delegation

In the Google Workspace Admin Console, configure Domain-Wide Delegation for the function's runtime service account with scope `https://www.googleapis.com/auth/admin.directory.group.member`. The function uses ADC, so no key file or extra configuration is needed in the code.

## 3. Discord bot

1. Create a bot in the [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable the **Server Members Intent** (required for fetching all guild members)
3. Invite the bot to each guild with `Manage Roles` permission
4. Ensure the bot's role is positioned above the Current Member role in each guild's role hierarchy

## 4. Cloud Scheduler

Each function is triggered by a Cloud Scheduler HTTP job. The function URL is available in the GCP console after the first deploy.

```bash
# membership-sync — nightly at 06:00 UTC
gcloud scheduler jobs create http membership-sync-nightly \
  --location us-central1 \
  --schedule "0 6 * * *" \
  --time-zone "UTC" \
  --uri <membership-sync-function-url> \
  --http-method POST

# checkmein-group-sync — hourly
gcloud scheduler jobs create http checkmein-group-sync-hourly \
  --location us-central1 \
  --schedule "0 * * * *" \
  --time-zone "UTC" \
  --uri <checkmein-group-sync-function-url> \
  --http-method POST
```

## 5. GitHub Actions — Workload Identity Federation

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
