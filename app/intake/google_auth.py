"""Shared Google login for Rainbow AI (Gmail + Drive).

How it works, in plain words:
- secrets/credentials.json is the program's ID card from Google Cloud Console
  (the "Desktop OAuth client"). It says which program is asking, not who you are.
- secrets/token.json is the permission slip the shop account gave that program
  when someone clicked Allow (authorize.py). It holds a refresh token: a
  long-lived key the program trades for a fresh one-hour access key whenever
  it needs one, so nobody has to log in again.
- Both files are secrets: secrets/ is git-ignored and must never be copied
  into a job folder, an email, or the repo.

Scopes (what the permission slip allows):
- gmail.modify   read mail and add/remove labels. No sending, no permanent delete.
- drive.readonly read/download files the shop account can see. No changes.
"""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
SECRETS = REPO / "secrets"
CREDENTIALS = SECRETS / "credentials.json"
TOKEN = SECRETS / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.readonly",
]

SHOP_ACCOUNT = "print@rainbowofficesupply.com"


def _need_libs():
    try:
        import google.oauth2.credentials  # noqa: F401
        import google_auth_oauthlib  # noqa: F401
        import googleapiclient  # noqa: F401
    except ImportError:
        sys.exit("Google libraries missing. Run:\n"
                 "  py -m pip install --user -r app/requirements.txt")


def get_credentials():
    """Return working credentials, refreshing the access key if it expired.

    Never opens a browser: if there is no usable token, it stops and says to
    run authorize.py. (The background program must never hang on a login.)
    """
    _need_libs()
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError

    if not TOKEN.exists():
        sys.exit(f"No Google login yet ({TOKEN} missing). Run:\n"
                 "  py app/intake/authorize.py")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                sys.exit("Google refused the saved login (access removed, or the shop "
                         "account's password changed).\n"
                         f"  Detail: {e}\n"
                         "Fix the cause, then run: py app/intake/authorize.py")
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
        else:
            sys.exit("Saved Google login is unusable. Run: py app/intake/authorize.py")
    return creds


def gmail(creds=None):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds or get_credentials(), cache_discovery=False)


def drive(creds=None):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=creds or get_credentials(), cache_discovery=False)
