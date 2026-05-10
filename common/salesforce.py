import requests
from simple_salesforce import Salesforce

_MEMBER_QUERY = """
SELECT
    Id,
    TFI_Barcode_for_Button__c,
    TFI_Display_Name_for_Button__c,
    FirstName,
    LastName,
    npo02__MembershipEndDate__c,
    Email,
    Google_group__c,
    Google_group_email_2ndary__c,
    Discord_ID__c,
    Account.npsp__Membership_Status__c
FROM Contact
WHERE Account.npsp__Membership_Status__c IN ('Current', 'Grace Period')
AND (NOT Name LIKE '%test%')
"""


class SalesforceClient:
    def __init__(self, url: str, client_id: str, client_secret: str):
        self._url = url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._sf = self._authenticate()

    def _authenticate(self) -> Salesforce:
        resp = requests.post(
            f"{self._url}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return Salesforce(instance_url=data["instance_url"], session_id=data["access_token"])

    def get_current_members(self) -> list[dict]:
        result = self._sf.query_all(_MEMBER_QUERY)
        contacts = []
        for record in result["records"]:
            account = record.get("Account") or {}
            contacts.append(
                {
                    "id": record.get("Id", "") or "",
                    "barcode": record.get("TFI_Barcode_for_Button__c", "") or "",
                    "display_name": record.get("TFI_Display_Name_for_Button__c", "") or "",
                    "first_name": record.get("FirstName", "") or "",
                    "last_name": record.get("LastName", "") or "",
                    "membership_end_date": record.get("npo02__MembershipEndDate__c", "") or "",
                    "email": record.get("Email", "") or "",
                    "group_email": record.get("Google_group__c", "") or "",
                    "group_email_alt": record.get("Google_group_email_2ndary__c", "") or "",
                    "discord_id": record.get("Discord_ID__c", "") or "",
                    "membership_status": account.get("npsp__Membership_Status__c", "") or "",
                }
            )
        return contacts
