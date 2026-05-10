from google.cloud import bigquery

_ROLES_QUERY = """
SELECT
  c.Id                              AS contact_id,
  r.barcode,
  c.Google_group__c                 AS google_group_email,
  c.Discord_ID__c                   AS discord_id,
  r.coach,
  r.certifier,
  r.keyholder,
  r.steward
FROM `tfi-data.checkmein.roles` r
LEFT JOIN `tfi-data.salesforce.Contact` c
  ON c.TFI_Barcode_for_Button__c = r.barcode
ORDER BY r.barcode
"""


class BigQueryClient:
    def __init__(self):
        self._client = bigquery.Client()

    def get_role_members(self) -> list[dict]:
        rows = self._client.query(_ROLES_QUERY).result()
        return [
            {
                "contact_id": row.contact_id or "",
                "barcode": row.barcode or "",
                "google_group_email": row.google_group_email or "",
                "discord_id": row.discord_id or "",
                "coach": bool(row.coach),
                "certifier": bool(row.certifier),
                "keyholder": bool(row.keyholder),
                "steward": bool(row.steward),
            }
            for row in rows
        ]
