# CDPHE data discovery prototypes

Discovery-phase prototypes that test how staff at the Colorado Department of Public Health & Environment (CDPHE) could find, understand, and access the data they need to answer a public health question.

Built by Bloom Works for CDPHE's Data Modernization Initiative.

These are prototypes, not production software. Most of the data is illustrative.

Each prototype is a single HTML file with no build step. `index.html` links to Prototypes 1 and 2.

## Prototype 1: Data catalog

A searchable data catalog that walks through finding, understanding, and accessing data, using the example search "cancer prevalence by county."

All of its data is hard-coded in the page, and there's no backend. Open it straight from disk:

```sh
open chronic_disease_data_catalog_prototype.html
```

Homepage: `chronic_disease_data_catalog_prototype.html`

## Prototype 2: Data explorer

A data explorer with working search and filters over a catalog of public CDPHE data sources.

The page fetches its catalog from `data/data_sources.json` (schema in `data/schema.json`), then searches it in the browser with the MiniSearch library. It loads MiniSearch from jsDelivr and the Open Sans font from Google Fonts, so it needs internet access. Browsers block the JSON fetch when a page is opened from disk, so run a local web server:

```sh
python3 -m http.server
```

Homepage: <http://localhost:8000/data_explorer.html> (or <http://localhost:8000/> for the index)

## Prototypes 2.5: CIM and ArcGIS

Two versions of the data explorer that read their catalog from a vendor platform's API instead of local JSON.

- `data_explorer_cim.html` reads dataset metadata from the [Colorado Information Marketplace](https://data.colorado.gov/) (Socrata).
- `data_explorer_arcgis.html` reads item metadata from the [CDPHE Open Data Portal](https://data-cdphe.opendata.arcgis.com/) (ArcGIS Online).

Each page reads the metadata (name, description, tags, custom fields) for a set of records listed in `.env`, and can download a hosted record's data as CSV. Search and filters work as in Prototype 2.

The pages call `server.py`, a small local server that calls the APIs with the credentials in `.env`, so the credentials never reach the browser and there are no CORS errors. It uses only the Python standard library, so there's nothing to install.

```sh
cp .env.example .env    # then fill in real values
python3 server.py       # or: python3 server.py 8080
```

Homepages:

- <http://localhost:8000/data_explorer_cim.html>
- <http://localhost:8000/data_explorer_arcgis.html>

### Environment variables

`server.py` runs without any of these. Each version needs its own variables, and explains what's missing if they aren't set.

Colorado Information Marketplace, for `data_explorer_cim.html`:

| Variable | Required | Purpose |
| --- | --- | --- |
| `SOCRATA_API_KEY_ID` | Yes | API key ID (Developer settings > API Keys) |
| `SOCRATA_API_KEY_SECRET` | Yes | API key secret. Needed to read private datasets |
| `SOCRATA_APP_TOKEN` | No | App token, used for rate limits |
| `CIM_DATASET_IDS` | Yes | Comma-separated dataset IDs (`xxxx-xxxx`) to show |

CDPHE Open Data Portal, for `data_explorer_arcgis.html`:

| Variable | Purpose |
| --- | --- |
| `ARCGIS_USERNAME` | A built-in ArcGIS Online account (not SSO), used to get a token |
| `ARCGIS_PASSWORD` | That account's password |
| `ARCGIS_ITEM_IDS` | Comma-separated item IDs (32 hex characters) to show |

## Security

**The CIM and ArcGIS versions are for local use only. Don't deploy them as they are.** `server.py` signs in with the account owner's credentials, so it can return private metadata, including staff names and email addresses. Keep credentials in `.env`, which is gitignored, and never commit them.

The data in `data/data_sources.json` (links, contact names, and emails) is already public.

## Deployment

Prototypes 1 and 2 are deployed to a password-protected Netlify site, <https://cdphe-dmi-info-services.netlify.app/>, which was used for testing with users. That deployment may not stay online. The CIM and ArcGIS versions aren't deployed.
