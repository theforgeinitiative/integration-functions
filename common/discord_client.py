"""
Discord role management via REST API only (no gateway/websocket connection).

discord.py is used for its HTTP client, rate-limit handling, and typed objects.
The bot requires the GUILD_MEMBERS privileged intent enabled in the Discord
Developer Portal for guild.fetch_members() to work.
"""

import asyncio
from dataclasses import dataclass

import discord


@dataclass
class GuildConfig:
    guild_id: str
    member_role_id: str


def sync_guild_roles(
    token: str,
    guild_config: GuildConfig,
    sfdc_discord_ids: set[str],
    dry_run: bool = False,
) -> dict:
    """Reconcile Current Member role for one guild. Returns additions/deletions/errors."""
    return asyncio.run(_sync_guild_roles(token, guild_config, sfdc_discord_ids, dry_run))


async def _sync_guild_roles(
    token: str,
    guild_config: GuildConfig,
    sfdc_discord_ids: set[str],
    dry_run: bool,
) -> dict:
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)

    additions, deletions, errors = [], [], []
    role_id = int(guild_config.member_role_id)

    try:
        await client.login(token)
        guild = await client.fetch_guild(int(guild_config.guild_id))
        members = [m async for m in guild.fetch_members(limit=None)]

        for member in members:
            user_id = str(member.id)
            has_role = any(r.id == role_id for r in member.roles)
            name = member.nick or member.global_name or member.name

            if user_id in sfdc_discord_ids and not has_role:
                if dry_run:
                    print(f"Discord: would add Current Member role to {name}")
                else:
                    try:
                        await member.add_roles(
                            discord.Object(id=role_id), reason="membership-sync"
                        )
                        print(f"Discord: added Current Member role to {name}")
                    except discord.HTTPException as e:
                        print(f"ERROR Discord: failed to add role to {name}: {e}")
                        errors.append(name)
                        continue
                additions.append(name)

            elif has_role and user_id not in sfdc_discord_ids:
                if dry_run:
                    print(f"Discord: would remove Current Member role from {name}")
                else:
                    try:
                        await member.remove_roles(
                            discord.Object(id=role_id), reason="membership-sync"
                        )
                        print(f"Discord: removed Current Member role from {name}")
                    except discord.HTTPException as e:
                        print(f"ERROR Discord: failed to remove role from {name}: {e}")
                        errors.append(name)
                        continue
                deletions.append(name)
    finally:
        await client.close()

    return {"additions": additions, "deletions": deletions, "errors": errors}
