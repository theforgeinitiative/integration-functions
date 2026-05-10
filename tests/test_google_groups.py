from unittest.mock import MagicMock, patch

import pytest

from common.google_groups import GoogleGroupsClient


@pytest.fixture
def client_and_svc():
    with patch("common.google_groups.google.auth.default") as mock_auth, patch(
        "common.google_groups.build"
    ) as mock_build:
        mock_auth.return_value = (MagicMock(), None)
        mock_svc = MagicMock()
        mock_build.return_value = mock_svc
        yield GoogleGroupsClient(), mock_svc


def test_list_members_single_page(client_and_svc):
    client, svc = client_and_svc
    svc.members().list().execute.return_value = {
        "members": [{"email": "a@example.com"}, {"email": "b@example.com"}]
    }

    members = client.list_members("group@example.com")

    assert set(members) == {"a@example.com", "b@example.com"}


def test_list_members_pagination(client_and_svc):
    client, svc = client_and_svc
    svc.members().list().execute.side_effect = [
        {"members": [{"email": "a@example.com"}], "nextPageToken": "tok1"},
        {"members": [{"email": "b@example.com"}]},
    ]

    members = client.list_members("group@example.com")

    assert set(members) == {"a@example.com", "b@example.com"}


def test_list_members_empty_group(client_and_svc):
    client, svc = client_and_svc
    svc.members().list().execute.return_value = {}

    members = client.list_members("group@example.com")

    assert members == []


def test_add_member(client_and_svc):
    client, svc = client_and_svc
    client.add_member("group@example.com", "new@example.com")
    svc.members().insert.assert_called_once_with(
        groupKey="group@example.com", body={"email": "new@example.com"}
    )


def test_remove_member(client_and_svc):
    client, svc = client_and_svc
    client.remove_member("group@example.com", "old@example.com")
    svc.members().delete.assert_called_once_with(
        groupKey="group@example.com", memberKey="old@example.com"
    )
