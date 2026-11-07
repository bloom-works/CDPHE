#!/usr/bin/env python3
"""
Local development server for the prototypes.

Serves this folder, so every page works (index.html, both prototypes, and the CIM and ArcGIS
versions), and adds endpoints that call Socrata and ArcGIS with the credentials in
.env. The browser never sees the credentials, and because the page and the endpoints share
an origin, there's no CORS.

    GET /api/datasets            Trimmed metadata for the datasets in CIM_DATASET_IDS (used by the page)
    GET /api/raw/<id>            Socrata's full, untrimmed response for one dataset, for inspection
    GET /api/csv/<id>            The rows of one dataset in CIM_DATASET_IDS, as a CSV download
    GET /api/arcgis/items        Trimmed metadata for the items in ARCGIS_ITEM_IDS (used by data_explorer_arcgis.html)
    GET /api/arcgis/raw/<id>     ArcGIS's full, untrimmed response for one item, for inspection
    GET /api/arcgis/csv/<id>     The CSV a feature service in ARCGIS_ITEM_IDS was published from, as a download

Credentials are optional. Without Socrata or ArcGIS credentials in .env, the static pages still
work, and the API routes (and the CIM and ArcGIS pages) explain what's missing.

LOCAL DEMO ONLY. Python standard library only; nothing to install.

    python3 server.py          # http://localhost:8000/
                               # http://localhost:8000/data_explorer_cim.html
                               # http://localhost:8000/data_explorer_arcgis.html
    python3 server.py 8080     # another port
"""
import base64
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlencode, urlsplit

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
TIMEOUT_SECONDS = 15
DATASET_ID = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$")
RAW_ROUTE = re.compile(r"^/api/raw/([^/]+)/?$")
CSV_ROUTE = re.compile(r"^/api/csv/([^/]+)/?$")
CSV_TIMEOUT_SECONDS = 120   # exports of large datasets take a while
CHUNK = 64 * 1024
UTF8_BOM = b"\xef\xbb\xbf"  # lets Excel read characters like en dashes correctly

ARCGIS_ITEM_ID = re.compile(r"^[0-9a-f]{32}$")
ARCGIS_RAW_ROUTE = re.compile(r"^/api/arcgis/raw/([^/]+)/?$")
ARCGIS_CSV_ROUTE = re.compile(r"^/api/arcgis/csv/([^/]+)/?$")
ARCGIS_TOKEN_MINUTES = 60
ARCGIS_REFRESH_MARGIN_SECONDS = 5 * 60   # get a new token when the current one has less than this left
ARCGIS_INVALID_TOKEN = (498, 499)        # ArcGIS codes for an expired/invalid or missing token

# ArcGIS item fields passed to the page. Owner, org and sharing details stay on the server.
ITEM_FIELDS = ["id", "title", "type", "snippet", "description", "tags", "url",
               "modified", "accessInformation", "documentation", "licenseInfo"]

# Update frequency codes in ArcGIS metadata (ISO 19115 maintenance frequency), as the words the
# page's CONFIG.fields.update_frequency understands. "Not planned" means a one-time release.
MAINT_FREQ = {"001": "continual", "002": "daily", "003": "weekly", "004": "fortnightly",
              "005": "monthly", "006": "quarterly", "007": "biannually", "008": "annually",
              "009": "as needed", "010": "irregular", "011": "never", "998": "unknown"}

# Socrata metadata passed to the page: these top-level fields, plus all public and private
# custom fields (see trim). Sharing and permission details stay on the server.
VIEW_FIELDS = ["id", "name", "description", "category", "attribution", "tags",
               "assetType", "attributionLink", "rowsUpdatedAt", "viewLastModified"]


def load_env(path):
    """Reads KEY=VALUE lines. Ignores blank lines and # comments; strips surrounding quotes.
    A missing file is fine: the server still runs, just without the Socrata and ArcGIS routes."""
    if not path.exists():
        return {}
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

# Socrata is optional: without an API key ID and secret, the static pages still work, and the
# Socrata routes explain what's missing.
SOCRATA_MISSING = [k for k in ("SOCRATA_API_KEY_ID", "SOCRATA_API_KEY_SECRET") if not ENV.get(k)]
SOCRATA_ENABLED = not SOCRATA_MISSING
SOCRATA_DOMAIN = "data.colorado.gov"
DATASET_IDS = [i.strip() for i in ENV.get("CIM_DATASET_IDS", "").split(",") if i.strip()]
bad_ids = [i for i in DATASET_IDS if not DATASET_ID.match(i)]
if bad_ids:
    sys.exit(f"CIM_DATASET_IDS has IDs that don't look like Socrata IDs (xxxx-xxxx): {', '.join(bad_ids)}")

HEADERS = {"Accept": "application/json"}
if SOCRATA_ENABLED:
    HEADERS["Authorization"] = "Basic " + base64.b64encode(
        f"{ENV['SOCRATA_API_KEY_ID']}:{ENV['SOCRATA_API_KEY_SECRET']}".encode("utf-8")).decode("ascii")
if ENV.get("SOCRATA_APP_TOKEN"):
    HEADERS["X-App-Token"] = ENV["SOCRATA_APP_TOKEN"]

# ArcGIS is optional: without a username and password the Socrata routes still work, and the
# ArcGIS routes explain what's missing.
ARCGIS_HOST = "www.arcgis.com"   # ArcGIS Online; works for the CDPHE org (cdphe.maps.arcgis.com)
ARCGIS_REST = f"https://{ARCGIS_HOST}/sharing/rest"
ARCGIS_ENABLED = bool(ENV.get("ARCGIS_USERNAME") and ENV.get("ARCGIS_PASSWORD"))
ARCGIS_ITEM_IDS = [i.strip() for i in ENV.get("ARCGIS_ITEM_IDS", "").split(",") if i.strip()]
bad_arcgis_ids = [i for i in ARCGIS_ITEM_IDS if not ARCGIS_ITEM_ID.match(i)]
if bad_arcgis_ids:
    sys.exit(f"ARCGIS_ITEM_IDS has IDs that don't look like ArcGIS item IDs (32 lowercase hex characters): "
             f"{', '.join(bad_arcgis_ids)}")


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
    url = f"https://{SOCRATA_DOMAIN}/api/views/{dataset_id}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT_SECONDS) as res:
            return "ok", trim(json.load(res))
    except urllib.error.HTTPError as e:
        message = {
            401: "access was denied (HTTP 401). Check the API key ID and secret in .env",
            403: "access was denied (HTTP 403). Check that your account can see this dataset",
            404: "no dataset with this ID was found",
        }.get(e.code, f"{SOCRATA_DOMAIN} returned HTTP {e.code}")
        return "error", {"id": dataset_id, "status": e.code, "message": message}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        reason = getattr(e, "reason", None) or e
        return "error", {"id": dataset_id, "status": None, "message": f"couldn't reach {SOCRATA_DOMAIN} ({reason})"}


def fetch_raw(dataset_id):
    """Returns (HTTP status, parsed JSON) exactly as Socrata sent them, untrimmed."""
    url = f"https://{SOCRATA_DOMAIN}/api/views/{dataset_id}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT_SECONDS) as res:
            status, body = res.status, res.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, (e.read() if e.fp else b"")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", None) or e
        return 502, {"error": f"couldn't reach {SOCRATA_DOMAIN} ({reason})"}
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
    urls = [f"https://{SOCRATA_DOMAIN}/api/v3/views/{dataset_id}/export.csv",
            f"https://{SOCRATA_DOMAIN}/api/views/{dataset_id}/rows.csv?accessType=DOWNLOAD"]
    for i, url in enumerate(urls):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=CSV_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as e:
            if i == len(urls) - 1 or e.code not in (400, 404, 405):
                raise


# --- ArcGIS -----------------------------------------------------------------------------------

class ArcGISError(Exception):
    """generateToken failed, or ArcGIS couldn't be reached to ask for a token."""


class ArcGISToken:
    """One ArcGIS token for the whole server, shared by every request thread.

    The token acts as ARCGIS_USERNAME, so it sees everything that account can see, including
    private and org-only items. It stays on the server and is never sent to the browser.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._token = None
        self.expires = 0.0  # seconds since 1970

    def get(self):
        """Returns a token with at least ARCGIS_REFRESH_MARGIN_SECONDS left, fetching one if needed."""
        with self._lock:
            if self._token is None or time.time() > self.expires - ARCGIS_REFRESH_MARGIN_SECONDS:
                self._fetch()
            return self._token

    def refresh(self):
        """Fetches a new token now (used at startup)."""
        with self._lock:
            self._fetch()

    def discard(self, token):
        """Drops a token ArcGIS rejected, unless another thread has already replaced it."""
        with self._lock:
            if self._token == token:
                self._token = None

    def _fetch(self):
        body = urlencode({
            "username": ENV["ARCGIS_USERNAME"],
            "password": ENV["ARCGIS_PASSWORD"],
            "referer": "http://localhost",
            "expiration": ARCGIS_TOKEN_MINUTES,
            "f": "json",
        }).encode("utf-8")
        try:
            with urllib.request.urlopen(f"{ARCGIS_REST}/generateToken", data=body, timeout=TIMEOUT_SECONDS) as res:
                data = json.load(res)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            reason = getattr(e, "reason", None) or e
            raise ArcGISError(f"couldn't get an ArcGIS token from {ARCGIS_HOST} ({reason})") from None
        if not isinstance(data, dict) or "token" not in data:
            err = (data.get("error") if isinstance(data, dict) else None) or {}
            details = "; ".join(err.get("details") or []) or err.get("message") or "no token in the response"
            raise ArcGISError(f"ArcGIS wouldn't issue a token ({details.rstrip('.')}). "
                              "Check ARCGIS_USERNAME and ARCGIS_PASSWORD in .env")
        self._token = data["token"]
        self.expires = data["expires"] / 1000  # ArcGIS sends milliseconds


ARCGIS_TOKEN = ArcGISToken()


def arcgis_error_code(data):
    """The code in an ArcGIS {"error": {...}} body, or None."""
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        return data["error"].get("code")
    return None


def arcgis_get(url, params=None):
    """GETs an ArcGIS REST URL with the server's token. Returns (HTTP status, parsed JSON).

    ArcGIS usually reports errors as HTTP 200 with an "error" object in the body, so this checks
    the body as well as the status. If the token is rejected (498/499), it gets a fresh token and
    retries once. Raises ArcGISError if no token can be had, and URLError if ArcGIS can't be reached.
    """
    for attempt in (1, 2):
        token = ARCGIS_TOKEN.get()
        query = urlencode({**(params or {}), "f": "json", "token": token})
        request = urllib.request.Request(f"{url}?{query}", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as res:
                status, body = res.status, res.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, (e.read() if e.fp else b"")
        try:
            data = json.loads(body)
        except ValueError:
            # ArcGIS sent something that isn't JSON; show it as text.
            return status, {"status": status, "body": body.decode("utf-8", "replace")}
        rejected = status in ARCGIS_INVALID_TOKEN or arcgis_error_code(data) in ARCGIS_INVALID_TOKEN
        if rejected and attempt == 1:
            ARCGIS_TOKEN.discard(token)
            continue
        return status, data


def arcgis_message(code):
    return {
        400: "no item with this ID was found, or your account can't see it",
        403: "access was denied. Check that your account can see this item",
        404: "no item with this ID was found",
    }.get(code, f"{ARCGIS_HOST} returned error {code}")


def fetch_metadata(item_id):
    """The item's metadata XML (what you fill in with the Metadata editor), or None if it has none."""
    try:
        url = f"{ARCGIS_REST}/content/items/{item_id}/info/metadata/metadata.xml?{urlencode({'token': ARCGIS_TOKEN.get()})}"
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as res:
            return res.read()
    except (ArcGISError, urllib.error.URLError, TimeoutError, OSError):
        return None


def read_metadata(xml_bytes):
    """Pulls the fields the page uses out of ArcGIS metadata XML. Fields that aren't filled in are left out."""
    try:
        root = ET.fromstring(xml_bytes or b"")
    except ET.ParseError:
        return {}  # no metadata: ArcGIS sends a JSON error instead of XML
    if root.tag != "metadata":
        return {}

    def text(el, path):
        found = el.find(path) if el is not None else None
        return found.text.strip() if found is not None and found.text and found.text.strip() else None

    info = root.find("dataIdInfo")
    out = {}
    # The resource's point of contact. (mdContact is the contact for the metadata itself, so it's skipped.)
    poc = info.find("idPoC") if info is not None else None
    for key, path in (("contact_name", "rpIndName"), ("contact_org", "rpOrgName"),
                      ("contact_email", "rpCntInfo/cntAddress/eMailAdd")):
        if text(poc, path):
            out[key] = text(poc, path)
    freq = info.find("resMaint/maintFreq/MaintFreqCd") if info is not None else None
    if freq is not None and freq.get("value"):
        out["update_frequency"] = MAINT_FREQ.get(freq.get("value"), f"code {freq.get('value')}")
    # Temporal keywords, like "2000–2025". The page turns them into years.
    temporal = [k.text.strip() for k in (info.findall("tempKeys/keyword") if info is not None else []) if k.text and k.text.strip()]
    if temporal:
        out["temporal_keywords"] = temporal
    return out


def fetch_item(item_id):
    """Returns ("ok", trimmed item with its metadata fields) or ("error", {id, status, message})."""
    try:
        status, data = arcgis_get(f"{ARCGIS_REST}/content/items/{item_id}")
    except ArcGISError as e:
        return "error", {"id": item_id, "status": None, "message": str(e)}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", None) or e
        return "error", {"id": item_id, "status": None, "message": f"couldn't reach {ARCGIS_HOST} ({reason})"}
    code = arcgis_error_code(data) or (status if status >= 400 else None)
    if code or not isinstance(data, dict):
        return "error", {"id": item_id, "status": code, "message": arcgis_message(code)}
    item = {k: data[k] for k in ITEM_FIELDS if k in data}
    item["metadata"] = read_metadata(fetch_metadata(item_id))
    return "ok", item


def source_csv_id(item_id):
    """The ID of the CSV item a hosted feature service was published from, or None.

    ArcGIS records that link as a Service2Data relationship when you publish from a CSV.
    """
    status, data = arcgis_get(f"{ARCGIS_REST}/content/items/{item_id}/relatedItems",
                              {"relationshipType": "Service2Data", "direction": "forward"})
    for item in (data.get("relatedItems") or []) if isinstance(data, dict) else []:
        if item.get("type") == "CSV":
            return item["id"]
    return None


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
        if path == "/api/arcgis/items":
            return self.send_arcgis_items()
        arcgis_csv = ARCGIS_CSV_ROUTE.match(path)
        if arcgis_csv:
            return self.send_arcgis_csv(unquote(arcgis_csv.group(1)))
        arcgis_raw = ARCGIS_RAW_ROUTE.match(path)
        if arcgis_raw:
            return self.send_arcgis_raw(unquote(arcgis_raw.group(1)))
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

    def socrata_off(self):
        where = "to .env" if ENV_FILE.exists() else "to a .env file (copy .env.example)"
        return self.send_json(503, {"error": f"The Colorado Information Marketplace connection is off. "
                                             f"Add {' and '.join(SOCRATA_MISSING)} {where} and restart server.py."},
                              indent=2)

    def send_datasets(self):
        if not SOCRATA_ENABLED:
            return self.socrata_off()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch_view, DATASET_IDS))
        self.send_json(200, {
            "domain": SOCRATA_DOMAIN,
            "datasets": [r for status, r in results if status == "ok"],
            "errors": [r for status, r in results if status == "error"],
        })

    def send_raw(self, dataset_id):
        # Any dataset your API key can see, not just CIM_DATASET_IDS. Untrimmed, so it can
        # include people's names and emails (owners, sharing grants): fine locally, but
        # never deploy this route.
        if not SOCRATA_ENABLED:
            return self.socrata_off()
        if not DATASET_ID.match(dataset_id):
            return self.send_json(400, {"error": f"'{dataset_id}' isn't a Socrata dataset ID (xxxx-xxxx)."}, indent=2)
        status, data = fetch_raw(dataset_id)
        self.send_json(status, data, indent=2)

    def send_csv(self, dataset_id):
        # Only the datasets this explorer lists, not everything the API key can see.
        if not SOCRATA_ENABLED:
            return self.socrata_off()
        if dataset_id not in DATASET_IDS:
            return self.send_json(404, {"error": f"'{dataset_id}' isn't one of the datasets in CIM_DATASET_IDS."}, indent=2)
        try:
            res = open_export(dataset_id)
        except urllib.error.HTTPError as e:
            return self.send_json(e.code if e.code in (401, 403, 404) else 502,
                                  {"error": f"{SOCRATA_DOMAIN} returned HTTP {e.code} for the export of {dataset_id}."}, indent=2)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", None) or e
            return self.send_json(502, {"error": f"couldn't reach {SOCRATA_DOMAIN} ({reason})"}, indent=2)

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

    def arcgis_off(self):
        where = "to .env" if ENV_FILE.exists() else "to a .env file (copy .env.example)"
        return self.send_json(503, {"error": f"The ArcGIS connection is off. Add ARCGIS_USERNAME and "
                                             f"ARCGIS_PASSWORD {where} and restart server.py."}, indent=2)

    def send_arcgis_items(self):
        if not ARCGIS_ENABLED:
            return self.arcgis_off()
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch_item, ARCGIS_ITEM_IDS))
        self.send_json(200, {
            "host": ARCGIS_HOST,
            "items": [r for status, r in results if status == "ok"],
            "errors": [r for status, r in results if status == "error"],
        })

    def send_arcgis_csv(self, item_id):
        # Only the items this explorer lists, not everything the account can see.
        if not ARCGIS_ENABLED:
            return self.arcgis_off()
        if item_id not in ARCGIS_ITEM_IDS:
            return self.send_json(404, {"error": f"'{item_id}' isn't one of the items in ARCGIS_ITEM_IDS."}, indent=2)
        try:
            csv_id = source_csv_id(item_id)
            if not csv_id:
                return self.send_json(404, {"error": f"Item {item_id} has no CSV it was published from."}, indent=2)
            url = f"{ARCGIS_REST}/content/items/{csv_id}/data?{urlencode({'token': ARCGIS_TOKEN.get()})}"
            res = urllib.request.urlopen(url, timeout=CSV_TIMEOUT_SECONDS)
        except ArcGISError as e:
            return self.send_json(502, {"error": str(e)}, indent=2)
        except urllib.error.HTTPError as e:
            return self.send_json(e.code if e.code in (403, 404) else 502,
                                  {"error": f"{ARCGIS_HOST} returned HTTP {e.code} for the CSV of {item_id}."}, indent=2)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", None) or e
            return self.send_json(502, {"error": f"couldn't reach {ARCGIS_HOST} ({reason})"}, indent=2)

        with res:
            # ArcGIS sends errors as JSON with HTTP 200, so a JSON reply here means no file.
            if "json" in (res.headers.get("Content-Type") or ""):
                try:
                    code = arcgis_error_code(json.loads(res.read()))
                except ValueError:
                    code = None
                return self.send_json(502, {"error": f"{ARCGIS_HOST} sent an error instead of the CSV "
                                                     f"({arcgis_message(code) if code else 'unknown error'})."}, indent=2)
            # Stream the file through rather than holding it all in memory.
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

    def send_arcgis_raw(self, item_id):
        # Any item the ArcGIS account can see, private ones included. Untrimmed, so it includes
        # owner and org details: fine locally, but never deploy this route.
        if not ARCGIS_ENABLED:
            return self.arcgis_off()
        if not ARCGIS_ITEM_ID.match(item_id):
            return self.send_json(400, {"error": f"'{item_id}' isn't an ArcGIS item ID (32 lowercase hex characters)."},
                                  indent=2)
        try:
            status, data = arcgis_get(f"{ARCGIS_REST}/content/items/{item_id}")
        except ArcGISError as e:
            return self.send_json(502, {"error": str(e)}, indent=2)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = getattr(e, "reason", None) or e
            return self.send_json(502, {"error": f"couldn't reach {ARCGIS_HOST} ({reason})"}, indent=2)
        # ArcGIS errors arrive as HTTP 200, so give the browser a status that matches the body.
        code = arcgis_error_code(data)
        if code:
            status = code if code in (400, 403, 404) else 502
        self.send_json(status, data, indent=2)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    if not ENV_FILE.exists():
        print(f"No .env file at {ENV_FILE}, so the CIM and ArcGIS connections are off. "
              "Copy .env.example to .env to turn them on.")
    if SOCRATA_ENABLED:
        print(f"Socrata domain: {SOCRATA_DOMAIN}")
        print(f"Datasets: {', '.join(DATASET_IDS) if DATASET_IDS else 'none (set CIM_DATASET_IDS in .env)'}")
        if not ENV.get("SOCRATA_APP_TOKEN"):
            print("Warning: no SOCRATA_APP_TOKEN in .env, so requests share Socrata's lower anonymous rate limit.")
    else:
        print(f"Socrata: off (add {' and '.join(SOCRATA_MISSING)} to .env to turn it on)")
    if ARCGIS_ENABLED:
        # A fresh token on every start, so bad credentials show up now rather than on the first request.
        print(f"ArcGIS: {ENV['ARCGIS_USERNAME']} on {ARCGIS_HOST}")
        print(f"ArcGIS items: {', '.join(ARCGIS_ITEM_IDS) if ARCGIS_ITEM_IDS else 'none (set ARCGIS_ITEM_IDS in .env)'}")
        try:
            ARCGIS_TOKEN.refresh()
            print(f"ArcGIS token ready, valid until {time.strftime('%H:%M', time.localtime(ARCGIS_TOKEN.expires))}"
                  " (renewed automatically)")
        except ArcGISError as e:
            print(f"Warning: {e}. The ArcGIS routes will try again on their next request.")
    else:
        print("ArcGIS: off (add ARCGIS_USERNAME and ARCGIS_PASSWORD to .env to turn it on)")
    # 127.0.0.1 only: this server uses your credentials, so don't expose it to the network.
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Open http://localhost:{port}/  (Ctrl+C to stop)")
    print(f"CIM version: http://localhost:{port}/data_explorer_cim.html")
    print(f"ArcGIS version: http://localhost:{port}/data_explorer_arcgis.html")
    if SOCRATA_ENABLED:
        print(f"Raw Socrata metadata: http://localhost:{port}/api/raw/<dataset-id>")
    if ARCGIS_ENABLED:
        print(f"Raw ArcGIS item: http://localhost:{port}/api/arcgis/raw/<item-id>")
        for item_id in ARCGIS_ITEM_IDS:
            print(f"  http://localhost:{port}/api/arcgis/raw/{item_id}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
