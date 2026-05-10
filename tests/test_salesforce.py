from unittest.mock import MagicMock, patch

import pytest

from common.salesforce import SalesforceClient


def _make_record(**overrides):
    record = {
        "Id": "003000000000001",
        "TFI_Barcode_for_Button__c": "TFI-001",
        "TFI_Display_Name_for_Button__c": "Alice Smith",
        "FirstName": "Alice",
        "LastName": "Smith",
        "npo02__MembershipEndDate__c": "2025-12-31",
        "Email": "alice@example.com",
        "Google_group__c": "alice@gmail.com",
        "Google_group_email_2ndary__c": None,
        "Discord_ID__c": "123456789",
        "Account": {"npsp__Membership_Status__c": "Current"},
    }
    record.update(overrides)
    return record


@pytest.fixture
def client_and_sf():
    with patch("common.salesforce.requests.post") as mock_post, patch(
        "common.salesforce.Salesforce"
    ) as mock_sf_cls:
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "access_token": "token123",
            "instance_url": "https://example.salesforce.com",
        }
        mock_sf = MagicMock()
        mock_sf_cls.return_value = mock_sf
        client = SalesforceClient(url="https://example.com", client_id="cid", client_secret="sec")
        yield client, mock_sf


def test_get_current_members_maps_all_fields(client_and_sf):
    client, mock_sf = client_and_sf
    mock_sf.query_all.return_value = {"records": [_make_record()]}

    members = client.get_current_members()

    assert len(members) == 1
    m = members[0]
    assert m["id"] == "003000000000001"
    assert m["barcode"] == "TFI-001"
    assert m["display_name"] == "Alice Smith"
    assert m["first_name"] == "Alice"
    assert m["last_name"] == "Smith"
    assert m["membership_end_date"] == "2025-12-31"
    assert m["email"] == "alice@example.com"
    assert m["group_email"] == "alice@gmail.com"
    assert m["group_email_alt"] == ""
    assert m["discord_id"] == "123456789"
    assert m["membership_status"] == "Current"


def test_get_current_members_none_fields_become_empty_strings(client_and_sf):
    client, mock_sf = client_and_sf
    mock_sf.query_all.return_value = {
        "records": [
            _make_record(
                TFI_Barcode_for_Button__c=None,
                Discord_ID__c=None,
                Google_group_email_2ndary__c=None,
            )
        ]
    }

    members = client.get_current_members()
    m = members[0]

    assert m["barcode"] == ""
    assert m["discord_id"] == ""
    assert m["group_email_alt"] == ""


def test_get_current_members_null_account(client_and_sf):
    client, mock_sf = client_and_sf
    mock_sf.query_all.return_value = {"records": [_make_record(Account=None)]}

    members = client.get_current_members()

    assert members[0]["membership_status"] == ""


def test_get_campaign_members(client_and_sf):
    client, mock_sf = client_and_sf
    mock_sf.query_all.return_value = {
        "records": [
            {"ContactId": "003AAA", "Id": "00vAAA"},
            {"ContactId": "003BBB", "Id": "00vBBB"},
        ]
    }

    members = client.get_campaign_members("701CAMPAIGN")

    assert members == {"003AAA": "00vAAA", "003BBB": "00vBBB"}


def test_add_campaign_member(client_and_sf):
    client, mock_sf = client_and_sf
    client.add_campaign_member("701CAMPAIGN", "003CONTACT")
    mock_sf.CampaignMember.create.assert_called_once_with(
        {"CampaignId": "701CAMPAIGN", "ContactId": "003CONTACT"}
    )


def test_remove_campaign_member(client_and_sf):
    client, mock_sf = client_and_sf
    client.remove_campaign_member("00vMEMBER")
    mock_sf.CampaignMember.delete.assert_called_once_with("00vMEMBER")


def test_get_current_members_returns_all_records(client_and_sf):
    client, mock_sf = client_and_sf
    mock_sf.query_all.return_value = {
        "records": [
            _make_record(Id="001", Email="a@example.com"),
            _make_record(Id="002", Email="b@example.com"),
            _make_record(Id="003", Email="c@example.com"),
        ]
    }

    members = client.get_current_members()

    assert len(members) == 3
    assert [m["id"] for m in members] == ["001", "002", "003"]
