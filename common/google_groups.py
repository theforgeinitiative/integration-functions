import google.auth
from googleapiclient.discovery import build

_SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.member"]


class GoogleGroupsClient:
    def __init__(self):
        creds, _ = google.auth.default(scopes=_SCOPES)
        self._svc = build("admin", "directory_v1", credentials=creds)

    def list_members(self, group_email: str) -> list[str]:
        members = []
        page_token = None
        while True:
            resp = (
                self._svc.members()
                .list(groupKey=group_email, maxResults=200, pageToken=page_token)
                .execute()
            )
            for m in resp.get("members", []):
                members.append(m["email"])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return members

    def add_member(self, group_email: str, email: str) -> None:
        self._svc.members().insert(groupKey=group_email, body={"email": email}).execute()

    def remove_member(self, group_email: str, email: str) -> None:
        self._svc.members().delete(groupKey=group_email, memberKey=email).execute()
