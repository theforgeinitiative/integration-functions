from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from common.discord_client import GuildConfig, sync_guild_roles

GUILD_CONFIG = GuildConfig(guild_id="100", member_role_id="999")


async def _async_members(*members):
    for m in members:
        yield m


def _make_member(user_id: str, role_ids: list[int] = None, name: str = "TestUser"):
    member = MagicMock()
    member.id = int(user_id)
    member.nick = None
    member.global_name = name
    member.name = name
    member.roles = [MagicMock(id=rid) for rid in (role_ids or [])]
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    return member


@pytest.fixture
def mock_discord():
    with (
        patch("common.discord_client.discord.Client") as mock_client_cls,
        patch("common.discord_client.discord.Intents"),
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.login = AsyncMock()
        mock_client.close = AsyncMock()
        mock_guild = MagicMock()
        mock_client.fetch_guild = AsyncMock(return_value=mock_guild)
        yield mock_client, mock_guild


def test_adds_role_to_sfdc_member_without_role(mock_discord):
    _, mock_guild = mock_discord
    member = _make_member("42", role_ids=[])
    mock_guild.fetch_members.return_value = _async_members(member)

    result = sync_guild_roles("token", GUILD_CONFIG, {"42"}, dry_run=False)

    member.add_roles.assert_awaited_once()
    assert len(result["additions"]) == 1
    assert result["deletions"] == []
    assert result["errors"] == []


def test_removes_role_from_non_member_who_has_it(mock_discord):
    _, mock_guild = mock_discord
    member = _make_member("42", role_ids=[999])
    mock_guild.fetch_members.return_value = _async_members(member)

    result = sync_guild_roles("token", GUILD_CONFIG, set(), dry_run=False)

    member.remove_roles.assert_awaited_once()
    assert result["additions"] == []
    assert len(result["deletions"]) == 1
    assert result["errors"] == []


def test_no_change_when_already_in_sync(mock_discord):
    _, mock_guild = mock_discord
    current_member = _make_member("1", role_ids=[999])  # in sfdc + has role
    non_member = _make_member("2", role_ids=[])  # not in sfdc + no role
    mock_guild.fetch_members.return_value = _async_members(current_member, non_member)

    result = sync_guild_roles("token", GUILD_CONFIG, {"1"}, dry_run=False)

    current_member.add_roles.assert_not_awaited()
    current_member.remove_roles.assert_not_awaited()
    non_member.add_roles.assert_not_awaited()
    non_member.remove_roles.assert_not_awaited()
    assert result == {"additions": [], "deletions": [], "errors": []}


def test_dry_run_prints_changes_without_api_calls(mock_discord, capsys):
    _, mock_guild = mock_discord
    to_add = _make_member("1", role_ids=[], name="Alice")
    to_remove = _make_member("2", role_ids=[999], name="Bob")
    mock_guild.fetch_members.return_value = _async_members(to_add, to_remove)

    result = sync_guild_roles("token", GUILD_CONFIG, {"1"}, dry_run=True)

    to_add.add_roles.assert_not_awaited()
    to_remove.remove_roles.assert_not_awaited()
    assert len(result["additions"]) == 1
    assert len(result["deletions"]) == 1
    out = capsys.readouterr().out
    assert "would add" in out
    assert "would remove" in out


def test_role_error_recorded_not_raised(mock_discord):
    _, mock_guild = mock_discord
    import discord

    member = _make_member("42", role_ids=[999])
    member.remove_roles = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "forbidden"))
    mock_guild.fetch_members.return_value = _async_members(member)

    result = sync_guild_roles("token", GUILD_CONFIG, set(), dry_run=False)

    assert result["errors"] == [member.global_name]
    assert result["deletions"] == []
