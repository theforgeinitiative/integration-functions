import csv
import io
from unittest.mock import MagicMock, patch

import pytest

from common.checkmein import CheckMeInClient


def _make_contact(**overrides):
    contact = {
        "barcode": "TFI-001",
        "display_name": "Alice Smith",
        "first_name": "Alice",
        "last_name": "Smith",
        "membership_end_date": "2025-12-31",
        "email": "alice@example.com",
    }
    contact.update(overrides)
    return contact


@pytest.fixture
def client_and_post():
    with patch("common.checkmein.requests.post") as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()
        yield CheckMeInClient(url="https://example.com", token="test-token"), mock_post


def _get_uploaded_csv(mock_post) -> list[dict]:
    csv_bytes = mock_post.call_args.kwargs["files"]["csvfile"][1]
    return list(csv.DictReader(io.StringIO(csv_bytes.decode())))


def test_bulk_add_posts_to_sync_members(client_and_post):
    client, mock_post = client_and_post
    client.bulk_add([_make_contact()])
    assert mock_post.call_args.args[0] == "https://example.com/sync/members"


def test_bulk_add_sends_bearer_token(client_and_post):
    client, mock_post = client_and_post
    client.bulk_add([_make_contact()])
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_bulk_add_date_no_leading_zeros(client_and_post):
    client, mock_post = client_and_post
    client.bulk_add([_make_contact(membership_end_date="2025-01-05")])
    rows = _get_uploaded_csv(mock_post)
    assert rows[0]["Membership End Date"] == "1/5/2025"


def test_bulk_add_date_december(client_and_post):
    client, mock_post = client_and_post
    client.bulk_add([_make_contact(membership_end_date="2025-12-31")])
    rows = _get_uploaded_csv(mock_post)
    assert rows[0]["Membership End Date"] == "12/31/2025"


def test_bulk_add_csv_fields_match_contact(client_and_post):
    client, mock_post = client_and_post
    contact = _make_contact()
    client.bulk_add([contact])
    rows = _get_uploaded_csv(mock_post)
    assert rows[0]["TFI Barcode for Button"] == contact["barcode"]
    assert rows[0]["TFI Display Name for Button"] == contact["display_name"]
    assert rows[0]["First Name"] == contact["first_name"]
    assert rows[0]["Last Name"] == contact["last_name"]
    assert rows[0]["Email"] == contact["email"]


def test_bulk_add_skips_missing_end_date(client_and_post, capsys):
    client, mock_post = client_and_post
    client.bulk_add([_make_contact(membership_end_date="")])
    rows = _get_uploaded_csv(mock_post)
    assert rows == []
    assert "Skipping" in capsys.readouterr().out


def test_bulk_add_skips_invalid_end_date(client_and_post, capsys):
    client, mock_post = client_and_post
    client.bulk_add([_make_contact(membership_end_date="not-a-date")])
    rows = _get_uploaded_csv(mock_post)
    assert rows == []
    assert "invalid membership end date" in capsys.readouterr().out


def test_bulk_add_skips_bad_keeps_good(client_and_post):
    client, mock_post = client_and_post
    contacts = [
        _make_contact(display_name="Bad", membership_end_date=""),
        _make_contact(display_name="Good", membership_end_date="2025-06-01"),
    ]
    client.bulk_add(contacts)
    rows = _get_uploaded_csv(mock_post)
    assert len(rows) == 1
    assert rows[0]["TFI Display Name for Button"] == "Good"
