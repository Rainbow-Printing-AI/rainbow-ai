"""One-time Google login for Rainbow AI. Run it yourself; it opens a browser.

  py app/intake/authorize.py

Sign in as the shop account (print@rainbowofficesupply.com, the Workspace
mailbox that rainbowincline@gmail.com also delivers into), tick both boxes,
and click Allow. The app is Internal to rainbowofficesupply.com, so there is
no "unverified app" warning.

Writes secrets/token.json. Run it again only if Google ever refuses the login
(password change on the shop account, or access removed).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import google_auth as ga  # noqa: E402


def main():
    ga._need_libs()
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not ga.CREDENTIALS.exists():
        sys.exit(f"Missing {ga.CREDENTIALS}\n"
                 "Download the Desktop OAuth client JSON from Google Cloud Console "
                 "(APIs & Services -> Credentials), rename it credentials.json, "
                 "and put it in C:\\Rainbow\\secrets\\.")

    flow = InstalledAppFlow.from_client_secrets_file(str(ga.CREDENTIALS), ga.SCOPES)
    # prompt=consent + offline access makes Google hand over a refresh token
    # every time, even if this account approved the app before.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent",
                                  login_hint=ga.SHOP_ACCOUNT,
                                  authorization_prompt_message="Opening the browser for the Google login...",
                                  success_message="Rainbow AI is allowed. You can close this tab.")

    granted = set(creds.scopes or [])
    missing = [s for s in ga.SCOPES if s not in granted]
    if missing:
        sys.exit("Not all permissions were ticked. Missing:\n  " + "\n  ".join(missing) +
                 "\nRun authorize.py again and tick every box.")
    if not creds.refresh_token:
        sys.exit("Google gave no refresh token. Run authorize.py again.")

    ga.SECRETS.mkdir(exist_ok=True)
    ga.TOKEN.write_text(creds.to_json(), encoding="utf-8")

    email = ga.gmail(creds).users().getProfile(userId="me").execute()["emailAddress"]
    print(f"Saved {ga.TOKEN}")
    print(f"Logged in as: {email}")
    if email.lower() != ga.SHOP_ACCOUNT:
        print(f">>> WARNING: that is not the shop account ({ga.SHOP_ACCOUNT}). "
              "Delete secrets/token.json and run again, signing in as the shop.")
        sys.exit(1)


if __name__ == "__main__":
    main()
