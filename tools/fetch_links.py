#!/usr/bin/env python3
"""fetch_links.py - download the original files behind cloud share links.

Pulls every share link out of pasted email text (or takes URLs directly) and saves
the ORIGINAL file (full-res, original name) into an output folder. Stdlib only.

    python3 fetch_links.py -o "Customer - Print Order 10.8.26" URL [URL ...]
    python3 fetch_links.py -o OUT --from-file email.txt      # extracts links from text
    pbpaste | python3 fetch_links.py -o OUT -                 # macOS clipboard

Supported:
  OneDrive personal  1drv.ms/..., onedrive.live.com, photos.onedrive.com   TESTED 2026-10-08
                     (files; folder links recurse into children - untested)
  Dropbox            dropbox.com/s/..., dropbox.com/scl/fi/...           best-effort, untested
  Google Drive file  drive.google.com/file/d/<id>/..., ?id=<id>           best-effort, untested
  SharePoint (work)  *.sharepoint.com anonymous links via download=1      best-effort, untested

How OneDrive works (no login needed for "anyone with the link" shares):
  1. POST api-badgerp.svc.ms/v1.0/token with OneDrive web's public appId -> anonymous "Badger" token
  2. GET my.microsoftpersonalcontent.com/_api/v2.0/shares/u!<base64url(link)>/driveitem
     with "Authorization: Badger <token>" and "Prefer: autoredeem" -> name, size, @content.downloadUrl
  3. GET the downloadUrl (pre-signed, short-lived) -> original bytes; size is checked against the API.
  The plain api.onedrive.com/shares call without the token now returns 401 for migrated accounts.

Never overwrites: an existing name gets " (2)", " (3)"... Exit code 1 if any link failed.
"""
import argparse, base64, json, os, re, sys, urllib.parse, urllib.request
from email.message import Message

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36"
URL_RE = re.compile(r"https?://[^\s<>\"'\]\)]+")
ONEDRIVE_HOSTS = ("1drv.ms", "onedrive.live.com", "photos.onedrive.com", "onedrive.com")
OD_APPID = "5cbed6ac-a083-4e14-b191-b4ba07653de2"   # OneDrive web client's public app id
OD_API = "https://my.microsoftpersonalcontent.com/_api/v2.0"
_badger = None


def req(url, data=None, headers=None, method=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=120)


def get_json(url, headers=None, data=None):
    with req(url, data=data, headers=headers) as r:
        return json.load(r)


def safe_name(name):
    name = re.sub(r"[\x00-\x1f/\\:]", "_", name).strip().strip(".")
    return name or "download"


def unique_path(outdir, name):
    base, ext = os.path.splitext(safe_name(name))
    p, n = os.path.join(outdir, base + ext), 2
    while os.path.exists(p):
        p, n = os.path.join(outdir, f"{base} ({n}){ext}"), n + 1
    return p


def stream_to(resp, path):
    tmp = path + ".part"
    total = 0
    with open(tmp, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
            total += len(chunk)
    os.replace(tmp, path)
    return total


def cd_filename(resp, fallback):
    cd = resp.headers.get("Content-Disposition", "")
    if cd:
        m = Message()
        m["content-disposition"] = cd
        fn = m.get_filename()
        if fn:
            return fn
    return fallback


# ---------- OneDrive personal ----------
def badger_token():
    global _badger
    if _badger is None:
        body = json.dumps({"appId": OD_APPID}).encode()
        _badger = get_json("https://api-badgerp.svc.ms/v1.0/token", data=body,
                           headers={"Content-Type": "application/json"})["token"]
    return _badger


def share_id(url):
    return "u!" + base64.b64encode(url.encode()).decode().rstrip("=").replace("/", "_").replace("+", "-")


def od_headers():
    return {"Authorization": "Badger " + badger_token(), "Prefer": "autoredeem"}


def onedrive(url, outdir, sub=""):
    sel = "$select=id,name,size,file,folder,parentReference,@content.downloadUrl"
    item = get_json(f"{OD_API}/shares/{share_id(url)}/driveitem?{sel}", headers=od_headers())
    return od_item(item, outdir, sub)


def od_item(item, outdir, sub):
    if "folder" in item:                        # folder share: recurse (untested path)
        drive = item["parentReference"]["driveId"]
        nxt = f"{OD_API}/drives/{drive}/items/{item['id']}/children?$top=200"
        dest = os.path.join(sub, safe_name(item["name"]))
        out = []
        while nxt:
            page = get_json(nxt, headers=od_headers())
            for child in page.get("value", []):
                out += od_item(child, outdir, dest)
            nxt = page.get("@odata.nextLink")
        return out
    d = os.path.join(outdir, sub)
    os.makedirs(d, exist_ok=True)
    path = unique_path(d, item["name"])
    with req(item["@content.downloadUrl"]) as r:
        n = stream_to(r, path)
    if item.get("size") is not None and n != item["size"]:
        raise IOError(f"size mismatch for {item['name']}: got {n}, API says {item['size']}")
    return [(path, n)]


# ---------- others (best-effort) ----------
def dropbox(url, outdir):
    u = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(u.query))
    q["dl"] = "1"
    url = urllib.parse.urlunsplit(u._replace(query=urllib.parse.urlencode(q)))
    return generic(url, outdir)


def gdrive(url, outdir):
    m = re.search(r"/d/([\w-]{20,})", url) or re.search(r"[?&]id=([\w-]{20,})", url)
    if not m:
        raise ValueError("no Google Drive file id in link (folders not supported)")
    return generic(f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t", outdir)


def sharepoint(url, outdir):
    return generic(url + ("&" if "?" in url else "?") + "download=1", outdir)


def generic(url, outdir):
    with req(url) as r:
        ctype = r.headers.get("Content-Type", "")
        if ctype.startswith("text/html"):
            raise IOError("got a web page, not a file (link may need sign-in or is not shared publicly)")
        fallback = os.path.basename(urllib.parse.urlsplit(r.geturl()).path) or "download"
        path = unique_path(outdir, urllib.parse.unquote(cd_filename(r, fallback)))
        n = stream_to(r, path)
    return [(path, n)]


def route(url):
    host = urllib.parse.urlsplit(url).hostname or ""
    if any(host == h or host.endswith("." + h) for h in ONEDRIVE_HOSTS):
        return onedrive
    if host.endswith("dropbox.com"):
        return dropbox
    if host.endswith("drive.google.com") or host.endswith("docs.google.com"):
        return gdrive
    if host.endswith("sharepoint.com"):
        return sharepoint
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="share URLs, or '-' to read text from stdin")
    ap.add_argument("-o", "--out", required=True, help="output folder (created if missing)")
    ap.add_argument("--from-file", help="text/HTML file to pull links out of (e.g. a saved email)")
    ap.add_argument("--all", action="store_true", help="also try unrecognised http(s) links as direct downloads")
    a = ap.parse_args()

    text = " ".join(u for u in a.urls if u != "-")
    if "-" in a.urls:
        text += " " + sys.stdin.read()
    if a.from_file:
        text += " " + open(a.from_file, encoding="utf-8", errors="replace").read()
    seen, links = set(), []
    for u in URL_RE.findall(text.replace("&amp;", "&")):
        u = u.rstrip(".,;")
        if u not in seen:
            seen.add(u)
            links.append(u)

    os.makedirs(a.out, exist_ok=True)
    ok = bad = 0
    for u in links:
        fn = route(u) or (generic if a.all else None)
        if fn is None:
            continue
        try:
            for path, n in fn(u, a.out):
                ok += 1
                print(f"OK    {n/1e6:7.2f} MB  {os.path.relpath(path, a.out)}")
        except Exception as e:  # keep going; report at the end
            bad += 1
            print(f"FAIL  {u}\n      {type(e).__name__}: {e}", file=sys.stderr)
    print(f"\n{ok} file(s) saved to {a.out}" + (f", {bad} link(s) FAILED" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
