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
def client_and_session():
    with patch("common.checkmein.requests.Session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        c = CheckMeInClient(url="https://example.com", username="user", password="pass")
        yield c, mock_session


def _get_uploaded_csv(mock_session) -> list[dict]:
    csv_bytes = mock_session.post.call_args.kwargs["files"]["csvfile"][1]
    return list(csv.DictReader(io.StringIO(csv_bytes.decode())))


def test_bulk_add_authenticates_then_uploads(client_and_session):
    client, session = client_and_session
    client.bulk_add([_make_contact()])
    session.get.assert_called_once()
    session.post.assert_called_once()


def test_bulk_add_date_no_leading_zeros(client_and_session):
    client, session = client_and_session
    client.bulk_add([_make_contact(membership_end_date="2025-01-05")])
    rows = _get_uploaded_csv(session)
    assert rows[0]["Membership End Date"] == "1/5/2025"


def test_bulk_add_date_december(client_and_session):
    client, session = client_and_session
    client.bulk_add([_make_contact(membership_end_date="2025-12-31")])
    rows = _get_uploaded_csv(session)
    assert rows[0]["Membership End Date"] == "12/31/2025"


def test_bulk_add_csv_fields_match_contact(client_and_session):
    client, session = client_and_session
    contact = _make_contact()
    client.bulk_add([contact])
    rows = _get_uploaded_csv(session)
    assert rows[0]["TFI Barcode for Button"] == contact["barcode"]
    assert rows[0]["TFI Display Name for Button"] == contact["display_name"]
    assert rows[0]["First Name"] == contact["first_name"]
    assert rows[0]["Last Name"] == contact["last_name"]
    assert rows[0]["Email"] == contact["email"]


def test_bulk_add_skips_missing_end_date(client_and_session, capsys):
    client, session = client_and_session
    client.bulk_add([_make_contact(membership_end_date="")])
    rows = _get_uploaded_csv(session)
    assert rows == []
    assert "Skipping" in capsys.readouterr().out


def test_bulk_add_skips_invalid_end_date(client_and_session, capsys):
    client, session = client_and_session
    client.bulk_add([_make_contact(membership_end_date="not-a-date")])
    rows = _get_uploaded_csv(session)
    assert rows == []
    assert "invalid membership end date" in capsys.readouterr().out


def test_bulk_add_skips_bad_keeps_good(client_and_session):
    client, session = client_and_session
    contacts = [
        _make_contact(display_name="Bad", membership_end_date=""),
        _make_contact(display_name="Good", membership_end_date="2025-06-01"),
    ]
    client.bulk_add(contacts)
    rows = _get_uploaded_csv(session)
    assert len(rows) == 1
    assert rows[0]["TFI Display Name for Button"] == "Good"


def test_bulk_add_does_not_authenticate_twice(client_and_session):
    client, session = client_and_session
    client.bulk_add([_make_contact()])
    client.bulk_add([_make_contact()])
    assert session.get.call_count == 1
