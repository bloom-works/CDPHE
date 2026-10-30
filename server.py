#!/usr/bin/env python3
"""
Local development server for data_explorer_cim.html.

Serves this folder and adds two endpoints that call Socrata with the credentials in .env.
The browser never sees the credentials, and because the page and the endpoints share an
origin, there's no CORS.

    GET /api/datasets       Trimmed metadata for the datasets in CIM_DATASET_IDS (used by the page)
    GET /api/raw/<id>       Socrata's full, untrimmed response for one dataset, for inspection
    GET /api/csv/<id>       The rows of one dataset in CIM_DATASET_IDS, as a CSV download

LOCAL DEMO ONLY. Python standard library only; nothing to install.

    python3 server.py          # http://localhost:8000/data_explorer_cim.html
    python3 server.py 8080     # another port
"""
import base64
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
TIMEOUT_SECONDS = 15
DATASET_ID = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$")
RAW_ROUTE = re.compile(r"^/api/raw/([^/]+)/?$")
CSV_ROUTE = re.compile(r"^/api/csv/([^/]+)/?$")
CSV_TIMEOUT_SECONDS = 120   # exports of large datasets take a while
CHUNK = 64 * 1024
UTF8_BOM = b"\xef\xbb\xbf"  # lets Excel read characters like en dashes correctly

# Socrata metadata passed to the page: these top-level fields, plus all public and private
# custom fields (see trim). Sharing and permission details stay on the server.
VIEW_FIELDS = ["id", "name", "description", "category", "attribution", "tags",
               "assetType", "attributionLink", "rowsUpdatedAt", "viewLastModified"]


def load_env(path):
    """Reads KEY=VALUE lines. Ignores blank lines and # comments; strips surrounding quotes."""
    if not path.exists():
        sys.exit(f"No .env file at {path}.\nCopy .env.example to .env and fill it in.")
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        env[key.strip()] = value
    return env


ENV = load_env(ENV_FILE)

missing = [k for k in ("SOCRATA_API_KEY_ID", "SOCRATA_API_KEY_SECRET") if not ENV.get(k)]
if missing:
    sys.exit(f".env is missing {' and '.join(missing)}.")

DOMAIN = ENV.get("SOCRATA_DOMAIN") or "data.colorado.gov"
DATASET_IDS = [i.strip() for i in ENV.get("CIM_DATASET_IDS", "").split(",") if i.strip()]
bad_ids = [i for i in DATASET_IDS if not DATASET_ID.match(i)]
if bad_ids:
    sys.exit(f"CIM_DATASET_IDS has IDs that don't look like Socrata IDs (xxxx-xxxx): {', '.join(bad_ids)}")

HEADERS = {
    "Accept": "application/json",
    "Authorization": "Basic " + base64.b64encode(
        f"{ENV['SOCRATA_API_KEY_ID']}:{ENV['SOCRATA_API_KEY_SECRET']}".encode("utf-8")).decode("ascii"),
}
if ENV.get("SOCRATA_APP_TOKEN"):
    HEADERS["X-App-Token"] = ENV["SOCRATA_APP_TOKEN"]


def trim(view):
    out = {k: view[k] for k in VIEW_FIELDS if k in view}
    metadata = view.get("metadata") or {}
    if metadata.get("custom_fields"):
        out["custom_fields"] = metadata["custom_fields"]
    # Where an external-link asset points.
    if metadata.get("accessPoints"):
        out["access_points"] = metadata["accessPoints"]
    # Private fields are only in the response because the API key can see them. The page can
    # use them locally, but a public deployment should pass only the ones meant to be public.
    private = view.get("privateMetadata") or {}
    if private.get("custom_fields"):
        out["private_custom_fields"] = private["custom_fields"]
    if private.get("contactEmail"):
        out["private_contact_email"] = private["contactEmail"]
    return out


def fetch_view(dataset_id):
    """Returns ("ok", trimmed view) or ("error", {id, status, message})."""
    url = f"https://{DOMAIN}/api/views/{dataset_id}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT_SECONDS) as res:
            return "ok", trim(json.load(res))
    except urllib.error.HTTPError as e:
        message = {
            401: "access was denied (HTTP 401). Check the API key ID and secret in .env",
            403: "access was denied (HTTP 403). Check that your account can see this dataset",
            404: "no dataset with this ID was found",
        }.get(e.code, f"{DOMAIN} returned HTTP {e.code}")
        return "error", {"id": dataset_id, "status": e.code, "message": message}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        reason = getattr(e, "reason", None) or e
        return "error", {"id": dataset_id, "status": None, "message": f"couldn't reach {DOMAIN} ({reason})"}


def fetch_raw(dataset_id):
    """Returns (HTTP status, parsed JSON) exactly as Socrata sent them, untrimmed."""
    url = f"https://{DOMAIN}/api/views/{dataset_id}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT_SECONDS) as res:
            status, body = res.status, res.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, (e.read() if e.fp else b"")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", None) or e
        return 502, {"error": f"couldn't reach {DOMAIN} ({reason})"}
    try:
        return status, json.loads(body)
    except ValueError:
        # Socrata sent something that isn't JSON; show it as text.
        return status, {"status": status, "body": body.decode("utf-8", "replace")}


def open_export(dataset_id):
    """Opens Socrata's CSV export for a dataset. Returns the open response, or raises HTTPError/URLError.

    Tries the SODA3 export endpoint first, then the older rows.csv endpoint if SODA3 rejects the request.
    """
    headers = {**HEADERS, "Accept": "text/csv"}
    urls = [f"https://{DOMAIN}/api/v3/views/{dataset_id}/export.csv",
            f"https://{DOMAIN}/api/views/{dataset_id}/rows.csv?accessType=DOWNLOAD"]
    for i, url in enumerate(urls):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=CSV_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as e:
            if i == len(urls) - 1 or e.code not in (400, 404, 405):
                raise


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def is_hidden(self):
        # Never serve dotfiles or dot-folders (.env, .git, ...).
        path = unquote(urlsplit(self.path).path)
        return any(part.startswith(".") for part in path.split("/") if part)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/datasets":
            return self.send_datasets()
        raw = RAW_ROUTE.match(path)
        if raw:
            return self.send_raw(unquote(raw.group(1)))
        csv = CSV_ROUTE.match(path)
        if csv:
            return self.send_csv(unquote(csv.group(1)))
        if self.is_hidden():
            return self.send_error(404, "File not found")
        super().do_GET()

    def do_HEAD(self):
        if self.is_hidden():
            return self.send_error(404, "File not found")
        super().do_HEAD()

    def send_json(self, status, data, indent=None):
        body = json.dumps(data, indent=indent, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_datasets(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch_view, DATASET_IDS))
        self.send_json(200, {
            "domain": DOMAIN,
            "datasets": [r for status, r in results if status == "ok"],
            "errors": [r for status, r in results if status == "error"],
        })

    def send_raw(self, dataset_id):
        # Any dataset your API key can see, not just CIM_DATASET_IDS. Untrimmed, so it can
        # include people's names and emails (owners, sharing grants): fine locally, but
        # never deploy this route.
        if not DATASET_ID.match(dataset_id):
            return self.send_json(400, {"error": f"'{dataset_id}' isn't a Socrata dataset ID (xxxx-xxxx)."}, indent=2)
        status, data = fetch_raw(dataset_id)
        self.send_json(status, data, indent=2)

    def send_csv(self, dataset_id):
        # Only the datasets this explorer lists, not everything the API key can see.
        if dataset_id not in DATASET_IDS:
            return self.send_json(404, {"error": f"'{dataset_id}' isn't one of the datasets in CIM_DATASET_IDS."}, indent=2)
        try:
            res = open_export(dataset_id)
        except urllib.error.HTTPError as e:
            return self.send_json(e.code if e.code in (401, 403, 404) else 502,
                                  {"error": f"{DOMAIN} returned HTTP {e.code} for the export of {dataset_id}."}, indent=2)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", None) or e
            return self.send_json(502, {"error": f"couldn't reach {DOMAIN} ({reason})"}, indent=2)

        # Stream the file through rather than holding it all in memory.
        with res:
            chunk = res.read(CHUNK)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            # No filename here, so the page's download="…" attribute names the file.
            self.send_header("Content-Disposition", "attachment")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not chunk.startswith(UTF8_BOM):
                self.wfile.write(UTF8_BOM)
            while chunk:
                self.wfile.write(chunk)
                chunk = res.read(CHUNK)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Socrata domain: {DOMAIN}")
    print(f"Datasets: {', '.join(DATASET_IDS) if DATASET_IDS else 'none (set CIM_DATASET_IDS in .env)'}")
    if not ENV.get("SOCRATA_APP_TOKEN"):
        print("Warning: no SOCRATA_APP_TOKEN in .env, so requests share Socrata's lower anonymous rate limit.")
    # 127.0.0.1 only: this server uses your credentials, so don't expose it to the network.
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Open http://localhost:{port}/data_explorer_cim.html  (Ctrl+C to stop)")
    print(f"Raw Socrata metadata: http://localhost:{port}/api/raw/<dataset-id>")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
