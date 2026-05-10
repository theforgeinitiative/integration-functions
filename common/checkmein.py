import csv
import io
from datetime import datetime
from urllib.parse import urlencode

import requests

_SFDC_DATE_FORMAT = "%Y-%m-%d"
_CSV_FIELDS = [
    "TFI Barcode for Button",
    "TFI Display Name for Button",
    "First Name",
    "Last Name",
    "Membership End Date",
    "Email",
]


class CheckMeInClient:
    def __init__(self, url: str, username: str, password: str):
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._session = requests.Session()
        self._authenticated = False

    def _authenticate(self) -> None:
        params = urlencode({"username": self._username, "password": self._password})
        resp = self._session.get(f"{self._url}/profile/loginAttempt?{params}")
        resp.raise_for_status()
        self._authenticated = True

    def bulk_add(self, contacts: list[dict]) -> None:
        if not self._authenticated:
            self._authenticate()

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
        writer.writeheader()

        for c in contacts:
            if not c["membership_end_date"]:
                print(f"Skipping {c['display_name']!r}: no membership end date")
                continue
            try:
                end_date = datetime.strptime(c["membership_end_date"], _SFDC_DATE_FORMAT)
            except ValueError:
                print(
                    f"Skipping {c['display_name']!r}: invalid membership end date"
                    f" {c['membership_end_date']!r}"
                )
                continue
            writer.writerow(
                {
                    "TFI Barcode for Button": c["barcode"],
                    "TFI Display Name for Button": c["display_name"],
                    "First Name": c["first_name"],
                    "Last Name": c["last_name"],
                    # CheckMeIn expects M/D/YYYY with no leading zeros
                    "Membership End Date": f"{end_date.month}/{end_date.day}/{end_date.year}",
                    "Email": c["email"],
                }
            )

        csv_bytes = buf.getvalue().encode("utf-8")
        resp = self._session.post(
            f"{self._url}/admin/bulkAddMembers",
            files={"csvfile": ("report.csv", csv_bytes, "text/csv")},
        )
        resp.raise_for_status()
