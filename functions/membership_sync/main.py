import argparse
import base64
import json
import os

import functions_framework

from common.checkmein import CheckMeInClient
from common.discord_client import GuildConfig, sync_guild_roles
from common.google_groups import GoogleGroupsClient
from common.salesforce import SalesforceClient


def _normalize_email(email: str) -> str:
    """Gmail ignores dots and is case-insensitive, so normalize before comparing."""
    return email.lower().replace(".", "")


def run(dry_run: bool = False) -> None:
    if dry_run:
        print("Running in dry-run mode — no changes will be made")

    # --- Salesforce ---
    sf = SalesforceClient(
        url=os.environ["SFDC_URL"],
        client_id=os.environ["SFDC_CLIENT_ID"],
        client_secret=os.environ["SFDC_CLIENT_SECRET"],
    )
    contacts = sf.get_current_members()
    print(f"Salesforce: found {len(contacts)} current members")

    # --- CheckMeIn ---
    try:
        if not dry_run:
            checkmein = CheckMeInClient(
                url=os.environ["CHECKMEIN_URL"],
                token=os.environ["CHECKMEIN_TOKEN"],
            )
            checkmein.bulk_add(contacts)
            print(f"CheckMeIn: uploaded {len(contacts)} members")
    except Exception as e:
        print(f"ERROR CheckMeIn bulk_add failed: {e}")

    # --- Google Groups ---
    group_email = os.environ["GROUPS_MEMBERS_EMAIL"]
    try:
        groups_client = GoogleGroupsClient()
        current_members = groups_client.list_members(group_email)

        exceptions = [
            e.strip() for e in os.environ.get("GROUPS_EXCEPTIONS", "").split(",") if e.strip()
        ]

        sfdc_emails: dict[str, str] = {}
        for c in contacts:
            for field in ("group_email", "group_email_alt"):
                if c[field]:
                    sfdc_emails[_normalize_email(c[field])] = c[field]
        for exc in exceptions:
            sfdc_emails[_normalize_email(exc)] = exc

        group_emails = {_normalize_email(e): e for e in current_members}

        add, delete = [], []
        for key, email in sfdc_emails.items():
            if key not in group_emails:
                if dry_run:
                    print(f"Groups: would add {email}")
                else:
                    try:
                        groups_client.add_member(group_email, email)
                        print(f"Groups: added {email}")
                    except Exception as e:
                        print(f"ERROR Groups: failed to add {email}: {e}")
                        continue
                add.append(email)

        for key, email in group_emails.items():
            if key not in sfdc_emails:
                if dry_run:
                    print(f"Groups: would remove {email}")
                else:
                    try:
                        groups_client.remove_member(group_email, email)
                        print(f"Groups: removed {email}")
                    except Exception as e:
                        print(f"ERROR Groups: failed to remove {email}: {e}")
                        continue
                delete.append(email)

        print(f"Groups: +{len(add)} -{len(delete)}")

    except Exception as e:
        print(f"ERROR Google Groups sync failed: {e}")

    # --- Discord ---
    discord_token = os.environ["DISCORD_BOT_TOKEN"]
    guild_configs: dict[str, GuildConfig] = {
        "tfi": GuildConfig(
            guild_id=os.environ["DISCORD_GUILD_TFI_ID"],
            member_role_id=os.environ["DISCORD_GUILD_TFI_MEMBER_ROLE_ID"],
        ),
    }
    pyrotech_id = os.environ.get("DISCORD_GUILD_PYROTECH_ID")
    pyrotech_role = os.environ.get("DISCORD_GUILD_PYROTECH_MEMBER_ROLE_ID")
    if pyrotech_id and pyrotech_role:
        guild_configs["pyrotech"] = GuildConfig(guild_id=pyrotech_id, member_role_id=pyrotech_role)

    sfdc_discord_ids = {c["discord_id"] for c in contacts if c["discord_id"]}

    for guild_name, config in guild_configs.items():
        try:
            changes = sync_guild_roles(discord_token, config, sfdc_discord_ids, dry_run)
            print(
                f"Discord {guild_name}: +{len(changes['additions'])}"
                f" -{len(changes['deletions'])} errors={len(changes['errors'])}"
            )
        except Exception as e:
            print(f"ERROR Discord sync failed for {guild_name}: {e}")


@functions_framework.cloud_event
def membership_sync(cloud_event):
    run(dry_run=False)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
