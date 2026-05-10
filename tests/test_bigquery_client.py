from unittest.mock import MagicMock, patch

import pytest

from common.bigquery_client import BigQueryClient


def _make_row(**overrides):
    row = MagicMock()
    row.contact_id = "003000000000001"
    row.barcode = "TFI-001"
    row.google_group_email = "alice@gmail.com"
    row.discord_id = "123456789"
    row.coach = False
    row.certifier = False
    row.keyholder = True
    row.steward = False
    for k, v in overrides.items():
        setattr(row, k, v)
    return row


@pytest.fixture
def bq_client():
    with patch("common.bigquery_client.bigquery.Client") as mock_cls:
        mock_bq = MagicMock()
        mock_cls.return_value = mock_bq
        yield BigQueryClient(), mock_bq


def test_get_role_members_maps_fields(bq_client):
    client, mock_bq = bq_client
    mock_bq.query.return_value.result.return_value = [_make_row()]

    members = client.get_role_members()

    assert len(members) == 1
    m = members[0]
    assert m["contact_id"] == "003000000000001"
    assert m["barcode"] == "TFI-001"
    assert m["google_group_email"] == "alice@gmail.com"
    assert m["discord_id"] == "123456789"
    assert m["keyholder"] is True
    assert m["steward"] is False
    assert m["certifier"] is False
    assert m["coach"] is False


def test_get_role_members_none_fields_become_empty(bq_client):
    client, mock_bq = bq_client
    mock_bq.query.return_value.result.return_value = [
        _make_row(contact_id=None, google_group_email=None, discord_id=None)
    ]

    members = client.get_role_members()
    m = members[0]

    assert m["contact_id"] == ""
    assert m["google_group_email"] == ""
    assert m["discord_id"] == ""


def test_get_role_members_filters_by_role_field():
    # Verify that filtering by role field in main.py would work correctly
    # (integration check: the keyholder/steward/certifier fields are booleans)
    with patch("common.bigquery_client.bigquery.Client") as mock_cls:
        mock_bq = MagicMock()
        mock_cls.return_value = mock_bq
        mock_bq.query.return_value.result.return_value = [
            _make_row(keyholder=True, steward=False),
            _make_row(keyholder=False, steward=True),
            _make_row(keyholder=False, steward=False),
        ]
        client = BigQueryClient()
        all_members = client.get_role_members()

    keyholders = [m for m in all_members if m["keyholder"]]
    stewards = [m for m in all_members if m["steward"]]

    assert len(keyholders) == 1
    assert len(stewards) == 1
