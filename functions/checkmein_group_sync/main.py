import argparse
import json
import os
from dataclasses import dataclass

import functions_framework

from common.bigquery_client import BigQueryClient
from common.discord_client import GuildConfig, sync_guild_roles
from common.google_groups import GoogleGroupsClient
from common.salesforce import SalesforceClient


def _normalize_email(email: str) -> str:
    return email.lower().replace(".", "")


@dataclass
class RoleConfig:
    field: str
    group_email: str
    discord_role_id: str
    campaign_id: str


def run(dry_run: bool = False) -> None:
    if dry_run:
        print("Running in dry-run mode — no changes will be made")

    role_configs = [RoleConfig(**r) for r in json.loads(os.environ["CHECKMEIN_ROLE_CONFIGS"])]

    # --- BigQuery ---
    bq = BigQueryClient()
    all_members = bq.get_role_members()
    print(f"BigQuery: found {len(all_members)} role records")

    # --- Clients ---
    sf = SalesforceClient(
        url=os.environ["SFDC_URL"],
        client_id=os.environ["SFDC_CLIENT_ID"],
        client_secret=os.environ["SFDC_CLIENT_SECRET"],
    )
    groups_client = GoogleGroupsClient()
    discord_token = os.environ["DISCORD_BOT_TOKEN"]
    guild_id = os.environ["DISCORD_GUILD_TFI_ID"]

    for config in role_configs:
        role_members = [m for m in all_members if m[config.field]]
        print(f"{config.field}: {len(role_members)} members in CheckMeIn")

        # --- Google Groups ---
        try:
            current_members = groups_client.list_members(config.group_email)
            current_emails = {_normalize_email(e): e for e in current_members}

            target_emails: dict[str, str] = {}
            for m in role_members:
                if m["google_group_email"]:
                    target_emails[_normalize_email(m["google_group_email"])] = m[
                        "google_group_email"
                    ]

            add, delete = [], []
            for key, email in target_emails.items():
                if key not in current_emails:
                    if dry_run:
                        print(f"Groups {config.field}: would add {email}")
                    else:
                        try:
                            groups_client.add_member(config.group_email, email)
                            print(f"Groups {config.field}: added {email}")
                        except Exception as e:
                            print(f"ERROR Groups {config.field}: failed to add {email}: {e}")
                            continue
                    add.append(email)

            for key, email in current_emails.items():
                if key not in target_emails:
                    if dry_run:
                        print(f"Groups {config.field}: would remove {email}")
                    else:
                        try:
                            groups_client.remove_member(config.group_email, email)
                            print(f"Groups {config.field}: removed {email}")
                        except Exception as e:
                            print(f"ERROR Groups {config.field}: failed to remove {email}: {e}")
                            continue
                    delete.append(email)

            print(f"Groups {config.field}: +{len(add)} -{len(delete)}")

        except Exception as e:
            print(f"ERROR Google Groups sync failed for {config.field}: {e}")

        # --- Discord ---
        try:
            guild_config = GuildConfig(guild_id=guild_id, member_role_id=config.discord_role_id)
            discord_ids = {m["discord_id"] for m in role_members if m["discord_id"]}
            changes = sync_guild_roles(discord_token, guild_config, discord_ids, dry_run)
            print(
                f"Discord {config.field}: +{len(changes['additions'])}"
                f" -{len(changes['deletions'])} errors={len(changes['errors'])}"
            )
        except Exception as e:
            print(f"ERROR Discord sync failed for {config.field}: {e}")

        # --- Salesforce Campaign ---
        try:
            current_campaign = sf.get_campaign_members(config.campaign_id)
            role_contact_ids = {m["contact_id"] for m in role_members if m["contact_id"]}

            add_ids = role_contact_ids - set(current_campaign)
            remove_ids = set(current_campaign) - role_contact_ids

            for contact_id in add_ids:
                if dry_run:
                    print(f"Salesforce {config.field}: would add contact {contact_id} to campaign")
                else:
                    try:
                        sf.add_campaign_member(config.campaign_id, contact_id)
                        print(f"Salesforce {config.field}: added contact {contact_id} to campaign")
                    except Exception as e:
                        print(f"ERROR Salesforce {config.field}: failed to add {contact_id}: {e}")

            for contact_id in remove_ids:
                campaign_member_id = current_campaign[contact_id]
                if dry_run:
                    print(
                        f"Salesforce {config.field}: would remove contact {contact_id} from campaign"
                    )
                else:
                    try:
                        sf.remove_campaign_member(campaign_member_id)
                        print(
                            f"Salesforce {config.field}: removed contact {contact_id} from campaign"
                        )
                    except Exception as e:
                        print(
                            f"ERROR Salesforce {config.field}: failed to remove {contact_id}: {e}"
                        )

            print(f"Salesforce {config.field}: +{len(add_ids)} -{len(remove_ids)}")

        except Exception as e:
            print(f"ERROR Salesforce campaign sync failed for {config.field}: {e}")


@functions_framework.cloud_event
def checkmein_group_sync(cloud_event):
    run(dry_run=False)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
