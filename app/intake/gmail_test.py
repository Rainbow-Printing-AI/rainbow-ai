"""Step 0.6 done-test: prove the saved Google login works, without a browser.

  py app/intake/gmail_test.py

Prints the account, the 5 newest inbox threads (date, sender, subject), and
a Drive check. Read-only: changes nothing in Gmail or Drive.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import google_auth as ga  # noqa: E402


def main():
    creds = ga.get_credentials()
    gm = ga.gmail(creds)

    email = gm.users().getProfile(userId="me").execute()["emailAddress"]
    print(f"Gmail account: {email}")

    threads = gm.users().threads().list(userId="me", labelIds=["INBOX"],
                                        maxResults=5).execute().get("threads", [])
    print(f"\n{len(threads)} newest inbox threads:")
    for i, t in enumerate(threads, 1):
        th = gm.users().threads().get(userId="me", id=t["id"], format="metadata",
                                      metadataHeaders=["Subject", "From", "Date"]).execute()
        first = th["messages"][0]["payload"]["headers"]
        h = {x["name"]: x["value"] for x in first}
        n = len(th["messages"])
        print(f"  {i}. {h.get('Subject', '(no subject)')}")
        print(f"     from {h.get('From', '?')} | {h.get('Date', '?')} | {n} message{'s' * (n != 1)}")

    about = ga.drive(creds).about().get(fields="user(emailAddress)").execute()
    print(f"\nDrive account: {about['user']['emailAddress']} (read-only access OK)")

    ok = len(threads) == 5 and email.lower() == ga.SHOP_ACCOUNT
    print("\nRESULT", "PASS" if ok else "CHECK ABOVE")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
