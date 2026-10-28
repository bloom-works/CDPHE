#!/usr/bin/env python3
"""
Local development server for data_explorer_cim.html.

Serves this folder and adds one endpoint, GET /api/datasets, which reads dataset
metadata from Socrata with the credentials in .env. The browser never sees the
credentials, and because the page and the endpoint share an origin, there's no CORS.

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

# Socrata metadata fields passed to the page. Everything else (such as sharing
# grants, which can include people's email addresses) stays on the server.
VIEW_FIELDS = ["id", "name", "description", "category", "attribution", "tags",
               "assetType", "rowsUpdatedAt", "viewLastModified"]


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
    custom = (view.get("metadata") or {}).get("custom_fields")
    if custom:
        out["custom_fields"] = custom
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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def is_hidden(self):
        # Never serve dotfiles or dot-folders (.env, .git, ...).
        path = unquote(urlsplit(self.path).path)
        return any(part.startswith(".") for part in path.split("/") if part)

    def do_GET(self):
        if urlsplit(self.path).path == "/api/datasets":
            return self.send_datasets()
        if self.is_hidden():
            return self.send_error(404, "File not found")
        super().do_GET()

    def do_HEAD(self):
        if self.is_hidden():
            return self.send_error(404, "File not found")
        super().do_HEAD()

    def send_datasets(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch_view, DATASET_IDS))
        body = json.dumps({
            "domain": DOMAIN,
            "datasets": [r for status, r in results if status == "ok"],
            "errors": [r for status, r in results if status == "error"],
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Socrata domain: {DOMAIN}")
    print(f"Datasets: {', '.join(DATASET_IDS) if DATASET_IDS else 'none (set CIM_DATASET_IDS in .env)'}")
    if not ENV.get("SOCRATA_APP_TOKEN"):
        print("Warning: no SOCRATA_APP_TOKEN in .env, so requests share Socrata's lower anonymous rate limit.")
    # 127.0.0.1 only: this server uses your credentials, so don't expose it to the network.
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Open http://localhost:{port}/data_explorer_cim.html  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
