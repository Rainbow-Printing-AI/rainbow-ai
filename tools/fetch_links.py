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
  WeTransfer         wetransfer.com/downloads/..., we.tl/t-...              TESTED 2026-10-23
                     (each file saved separately with its own name; expired/deleted
                     transfers and password-protected ones FAIL with the reason)
  Box                app.box.com/s/..., <company>.app.box.com/s/..., box.com/shared/static/...
                     file links: page parse + "downloads disabled" path tested 2026-10-23,
                     an actual download untested; folder links untested
  iCloud Drive       icloud.com/iclouddrive/<id>#name (single files)        untested
                     iCloud Photos links and shared albums are NOT handled (FAIL with a note):
                     shared albums are downscaled by Apple (~2048 px long side), not print-res.

How OneDrive works (no login needed for "anyone with the link" shares):
  1. POST api-badgerp.svc.ms/v1.0/token with OneDrive web's public appId -> anonymous "Badger" token
  2. GET my.microsoftpersonalcontent.com/_api/v2.0/shares/u!<base64url(link)>/driveitem
     with "Authorization: Badger <token>" and "Prefer: autoredeem" -> name, size, @content.downloadUrl
  3. GET the downloadUrl (pre-signed, short-lived) -> original bytes; size is checked against the API.
  The plain api.onedrive.com/shares call without the token now returns 401 for migrated accounts.

How WeTransfer works (no login for normal transfers):
  POST wetransfer.com/api/v4/transfers/<id>/prepare-download {security_hash, recipient_id?}
  -> state, password_protected, items[]; then POST .../<id>/download with intent single_file
  and file_ids=[item id] -> direct_link per file. we.tl short links redirect to the long form.

Never overwrites: an existing name gets " (2)", " (3)"... Exit code 1 if any link failed.
"""
import argparse, base64, http.cookiejar, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from email.message import Message

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129 Safari/537.36"
URL_RE = re.compile(r"https?://[^\s<>\"'\]\)]+")
ONEDRIVE_HOSTS = ("1drv.ms", "onedrive.live.com", "photos.onedrive.com", "onedrive.com")
OD_APPID = "5cbed6ac-a083-4e14-b191-b4ba07653de2"   # OneDrive web client's public app id
OD_API = "https://my.microsoftpersonalcontent.com/_api/v2.0"
_badger = None
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def req(url, data=None, headers=None, method=None):
    h = {"User-Agent": UA}
    h.update(headers or {})
    return _opener.open(urllib.request.Request(url, data=data, headers=h, method=method), timeout=120)


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


def save_url(url, outdir, name, size=None, sub=""):
    d = os.path.join(outdir, sub)
    os.makedirs(d, exist_ok=True)
    with req(url) as r:
        if r.headers.get("Content-Type", "").startswith("text/html"):
            raise IOError(f"got a web page instead of {name}")
        path = unique_path(d, name)
        n = stream_to(r, path)
    if size is not None and n != int(size):
        raise IOError(f"size mismatch for {name}: got {n}, server says {size}")
    return [(path, n)]


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


# ---------- WeTransfer ----------
WT_API = "https://wetransfer.com/api/v4/transfers"


def wt_post(path, body):
    try:
        return get_json(f"{WT_API}/{path}", data=json.dumps(body).encode(),
                        headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"})
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            raise IOError(f"WeTransfer refused the link (HTTP {e.code}) - link incomplete, wrong, or not for us")
        raise


def wetransfer(url, outdir):
    host = urllib.parse.urlsplit(url).hostname or ""
    if host == "we.tl" or host.endswith(".we.tl"):
        with req(url) as r:              # short link -> /downloads/<id>/<hash>
            url = r.geturl()
    m = re.search(r"/downloads/([0-9a-f]{20,})/(?:([0-9a-f]{20,})/)?([0-9a-f]{4,})(?=[/?#]|$)", url)
    if not m:
        raise ValueError("no transfer id in WeTransfer link")
    tid, rid, h = m.groups()
    body = {"security_hash": h}
    if rid:
        body["recipient_id"] = rid
    info = wt_post(f"{tid}/prepare-download", body)
    if info.get("password_protected"):
        raise IOError("password-protected transfer - open it in Chrome with the password")
    if info.get("state") != "downloadable":
        gone = f", deleted {info['deleted_at'][:10]}" if info.get("deleted_at") else ""
        raise IOError(f"transfer is {info.get('state')}{gone} - ask the customer to resend")
    items = info.get("items") or []
    if not items or any(i.get("item_type") != "file" for i in items):
        dl = wt_post(f"{tid}/download", dict(body, intent="entire_transfer"))   # folders: one zip
        return save_url(dl["direct_link"], outdir, info.get("recommended_filename") or "wetransfer.zip", info.get("size"))
    out = []
    for it in items:
        dl = wt_post(f"{tid}/download", dict(body, intent="single_file", file_ids=[it["id"]]))
        out += save_url(dl["direct_link"], outdir, it["name"], it.get("size"))
    return out


# ---------- Box ----------
def box_page(url):
    try:
        with req(url) as r:
            html, final = r.read().decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            raise IOError(f"Box link not found or not public (HTTP {e.code}) - removed, mistyped, or company-only")
        raise
    i = html.find("postStreamData")
    if i < 0:
        raise IOError("Box page has no shared item (needs sign-in, wrong link, or removed)")
    data, _ = json.JSONDecoder().raw_decode(html, html.index("{", i))
    return data, final


def box_files(host, sn, items, outdir, sub):
    out = []
    for it in items:
        if it.get("type") != "file":
            continue
        if it.get("canDownload") is False:
            raise IOError(f"{it.get('name')}: the owner turned downloads off (preview only) - "
                          "ask the customer to allow downloads or email the file")
        q = urllib.parse.urlencode({"rm": "box_download_shared_file", "shared_name": sn, "file_id": f"f_{it['id']}"})
        out += save_url(f"https://{host}/index.php?{q}", outdir, it["name"], it.get("itemSize"), sub)
    return out


def box(url, outdir, sub="", seen=None):
    if "/shared/static/" in url:         # direct-download link
        return generic(url, outdir)
    data, final = box_page(url)
    host = urllib.parse.urlsplit(final).hostname or "app.box.com"
    si = data.get("/app-api/enduserapp/shared-item")
    if not si:
        raise IOError("Box page has no shared item (needs sign-in, wrong link, or removed)")
    sn = si["sharedName"]
    if si.get("itemType") == "file":
        items = data.get(f"/app-api/enduserapp/item/f_{si['itemID']}", {}).get("items", [])
        return box_files(host, sn, items, outdir, sub)
    # folder share (untested): files on this page, then each subfolder and further pages
    seen = seen if seen is not None else set()
    out = []
    for key, val in data.items():
        if not key.startswith("/app-api/enduserapp/folder/") or not isinstance(val, dict):
            continue
        items = val.get("items", [])
        out += box_files(host, sn, items, outdir, sub)
        for it in items:
            if it.get("type") == "folder" and it["id"] not in seen:
                seen.add(it["id"])
                out += box(f"https://{host}/s/{sn}/folder/{it['id']}", outdir,
                           os.path.join(sub, safe_name(it.get("name", str(it["id"])))), seen)
        page, pages = val.get("pageNumber", 1), val.get("pageCount", 1)
        if page < pages:
            base = url.split("?")[0]
            out += box(f"{base}?page={page + 1}", outdir, sub, seen)
    if not out:
        raise IOError("Box folder: found no downloadable files")
    return out


# ---------- iCloud Drive ----------
CK_RESOLVE = "https://ckdatabasews.icloud.com/database/1/com.apple.cloudkit/production/public/records/resolve"


def icloud(url, outdir):
    u = urllib.parse.urlsplit(url)
    m = re.search(r"/iclouddrive/([0-9A-Za-z_-]{10,})", u.path)
    if not m:
        raise IOError("iCloud Photos links / shared albums aren't handled here - open in Chrome. "
                      "Shared albums are downscaled by Apple (~2048 px); ask for originals for print.")
    d = get_json(CK_RESOLVE, data=json.dumps({"shortGUIDs": [{"value": m.group(1)}]}).encode(),
                 headers={"Content-Type": "text/plain", "Origin": "https://www.icloud.com"})
    res = (d.get("results") or [{}])[0]
    rec = res.get("rootRecord")
    if not rec:
        raise IOError(f"iCloud says: {res.get('reason')} ({res.get('serverErrorCode')}) - "
                      "link dead, stopped sharing, or not set to 'Anyone with the link'")
    f = rec.get("fields", {})
    fc = (f.get("fileContent") or {}).get("value")
    if not fc or not fc.get("downloadURL"):
        raise IOError("iCloud Drive folder links aren't handled yet - open in Chrome")
    name = ""
    try:
        name = base64.b64decode(f["encryptedBasename"]["value"]).decode("utf-8")
    except Exception:
        pass
    if not name or not name.isprintable():
        name = urllib.parse.unquote(u.fragment).replace("_", " ") or "icloud-file"
    ext = (f.get("extension") or {}).get("value")
    if ext and not name.lower().endswith("." + ext.lower()):
        name += "." + ext
    dl = fc["downloadURL"].replace("${f}", urllib.parse.quote(name))
    return save_url(dl, outdir, name, fc.get("size"))


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
    if host in ("we.tl", "wetransfer.com") or host.endswith(".we.tl") or host.endswith(".wetransfer.com"):
        return wetransfer if ("/downloads/" in url or "we.tl" in host) else None
    if host == "box.com" or host.endswith(".box.com"):
        p = urllib.parse.urlsplit(url).path
        return box if (p.startswith("/s/") or p.startswith("/v/") or "/shared/static/" in p) else None
    if host in ("icloud.com", "www.icloud.com", "share.icloud.com"):
        return icloud
    return None


def link_key(u):
    """Same transfer/file linked twice with different tracking params counts once."""
    m = re.search(r"wetransfer\.com/downloads/([0-9a-f]{20,})", u)
    if m:
        return "wt:" + m.group(1)
    return u


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
        k = link_key(u)
        if k not in seen:
            seen.add(k)
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
