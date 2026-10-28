# CLAUDE.md

Project context and working guidance for Claude Code. Read this at the start of every session.

## What this is

A set of **discovery-phase prototypes** for the Colorado Department of Public Health & Environment (CDPHE) Data Modernization Initiative (DMI). The prototypes are reached from a shared **index page** and share one look and feel (see Visual identity). Each demonstrates part of how public health staff would find the right data source(s) to answer a public health question.

There are two prototypes, and Prototype 2 has a second version that reads from the Colorado Information Marketplace:

### Prototype 1 — find → understand → access (self-contained)

A searchable public health data catalog that demonstrates the full **find → understand → access** flow for finding the right data source(s) to answer a public health question. The first example is from the Chronic Disease cohort with the example search "cancer prevalence by county." All data is illustrative and hard-coded in the file (see Constraints); there is no backend.

### Prototype 2 — functional search + filter

A narrower prototype focused only on the **search and filter** experience, linked from the same index and built to the same look and feel as Prototype 1, branded 'CDPHE Data explorer'.

- **Real read-only backend hosted in the data folder of this repo.** Catalog records are pulled from the JSON files in the `data` folder.
- **Functional search.** Search queries the real records pulled from the JSON and returns actual matches; filters narrow the real result set.
- **Schema.** The data schema is in the `data/schema.json` file; it describes the metadata shown in the result cards.

### Prototype 2, CIM version — `data_explorer_cim.html`

A version of Prototype 2 that pulls catalog records from the **Colorado Information Marketplace (CIM)**, a Socrata (Data & Insights) site at `data.colorado.gov`, instead of local JSON. It is part of a technical spike testing whether Socrata could be the backend data store for a custom search frontend.

- **Reads a small set of private datasets** (listed in `.env` as `CIM_DATASET_IDS`) through the Socrata API. It reads dataset **metadata** (name, description, tags, custom metadata fields, last updated), not the rows.
- **Uses a local server, `server.py`.** Socrata won't accept authenticated requests straight from a browser (CORS), and the API key must never reach the browser anyway. `server.py` serves the project folder and exposes one endpoint, `GET /api/datasets`, which calls Socrata with the credentials from `.env` and returns trimmed metadata to the page.
- **Search and filters are inert for now.** The page lists results; the search bar, filter checkboxes, and "View details" are shown but disabled.
- **Fields without a Socrata equivalent** (geographic level, population, years covered, update frequency) are mapped to Socrata custom metadata fields in the page's `CONFIG.customFields`, and show "Unknown" until mapped.

## What this is NOT

- Not a production system, and not a platform build. Platform selection, procurement, and enterprise data infrastructure are explicitly out of scope for this phase.
- Not production data infrastructure. Prototype 1 has no backend at all. Prototype 2 reads from local JSON files, but that is a lightweight, illustrative content store — not a server, database, or platform build. The CIM version's `server.py` is a local development proxy for demos, not a production backend.
- Not a place for sensitive CDPHE data. The JSON files hold catalog **metadata** only (source names, descriptions, topic area, geography, update cadence, and public links) — never real record-level data, credentials, or internal-only material. We use publicly accessible links to dashboards and documentation.

## Deployment

These prototypes are deployed to a password-protected Netlify environment for easy sharing with partners. When possible they should link out to real CDPHE dashboards and sources available publicly on the internet.

Prototype 2 additionally fetches its catalog data at runtime from the JSON files in the `data` folder (`data/schema.json`, `data/data_sources.json`), so those files must be deployed alongside the HTML. Browsers block these fetches when the page is opened straight from disk; run `python3 -m http.server` in the project folder to test locally. It also loads the MiniSearch library from jsDelivr and Open Sans from Google Fonts, so it needs network access to both (the font falls back to Trebuchet MS if Google Fonts is unreachable).

The CIM version (`data_explorer_cim.html`) is **local only** for now and is not deployed to Netlify. Run `python3 server.py` in the project folder and open `http://localhost:8000/data_explorer_cim.html`; it needs a filled-in `.env` (copy `.env.example`). `python3 -m http.server` will serve the page but not the `/api/datasets` endpoint. Deploying it would mean moving `/api/datasets` into a Netlify function that reads the same values from Netlify environment variables.

## Constraints

1. **Single HTML file, no build step.** Each prototype is one `.html` file that runs by opening it in a browser — no build step, no bundler, no framework, no server-side code. Keep it that way unless explicitly asked to change the architecture. The one approved exception is the CIM version's `server.py` (see below).
   - Prototype 1 is fully **self-contained**: all data is hard-coded in the file.
   - Prototype 2 is one HTML file but **not fully self-contained**: markup, styles, and logic all live in the one file, but catalog data is fetched from the JSON files in the `data` folder, and two approved external resources load from CDNs: MiniSearch (search) and Open Sans (Google Fonts).
   - The CIM version is one HTML file plus `server.py`. Keep `server.py` small and on the **Python standard library only** — no pip packages, no framework. It binds to `127.0.0.1` only, and its job is limited to serving files and proxying the Socrata calls the page needs.
2. **Design tokens are inlined**, not borrowed from any host environment, so each renders identically wherever it is hosted. Web fonts are the one exception (see Visual identity).
3. **Demonstrative, not comprehensive.** Scope features small and testable. When in doubt, do the simplest thing that makes the flow legible to a stakeholder.
4. **Credentials stay in `.env`, never in the page.** Socrata API keys and app tokens live only in `.env`, which is gitignored and which `server.py` refuses to serve (it blocks every dotfile). Never put credentials in HTML or JavaScript, never commit `.env`, and keep `.env.example` up to date with placeholder values only. The API key carries all of its owner's account permissions, so treat it like a password.

## Visual identity

### Shared across the index and both prototypes

Use gray scale to reinforce that this is a prototype, with standard colors for callouts (success, error, warning).

Use sentence case everywhere — never Title Case or ALL CAPS (except the "COLORADO" wordmark).

Branding: the header shows a simplified upward-arrow "C" mark and the "COLORADO / Department of Public Health & Environment" wordmark on a charcoal masthead. Keep the "prototype" marker visible so no one mistakes this for a shipped product.

### Index and Prototype 1

Typography: **Trebuchet MS** for body/UI (official state secondary typeface, a standard system font). Museo Slab is the state headline font but is not a system font, so do not depend on it in a standalone file.

### Prototype 2 (data explorer)

The CIM version uses Prototype 2's visual identity unchanged. Prototype 2 has been reskinned to look like the data platform we are recommending (a "marketplace" style). It intentionally differs from the index and Prototype 1 in these ways; keep them consistent within Prototype 2:

- **Typography:** **Open Sans** (400, 600, 700, and 400 italic) from Google Fonts, falling back to Trebuchet MS and system fonts. This is the only web font in the project. Base size 15px, line height 1.5.
- **Accent color:** one darkened green, `--accent: #24603A` (7.5:1 on white), used for links, link-style buttons, topic tags, and the focus ring. Everything else stays gray scale. Callout colors: warning `#7A5F1C` on `#F7F1DE`, danger `#A03E3E` on `#F5E7E7`.
- **Shape:** 4px corner radius (`--radius`) on panels, cards, and buttons; 8px on the masthead and page shell; fully rounded (999px) search bar, badges, tags, and filter chips. Borders are 1px `--border` (`#DDE1E2`).
- **Layout:** max width 1080px; a 250px white filter panel beside the results; stacks to one column below 760px.
- **Result cards:** white panels split into sections by 1px rules: (1) data product icon, title, and product badge; (2) description, clamped to two lines; (3) "Topics" label and up to three green outlined tags; (4) footer with label-over-value facts (geographic level, years covered, update frequency) and "View details" / "Open …" buttons.
- **Detail view:** same panel style. Header row with a "Back to results" button, product icon, title, and badge; an optional gray "Newer data is available" bar with a charcoal left edge; a ruled grid of facts (contact spans two columns, with a mailto link and a "Copy" button); a "No longer updated" fact highlighted in warning colors with an alert icon; then description, topics, documentation, newer data, and related records sections; footer with the primary charcoal "Open …" button and a "Request more data" link.
- **Buttons:** `.btn` is charcoal outline on white, 600 weight; `.btn.primary` is filled charcoal; `.btn.small` for in-card and header buttons; `.link-btn` for underlined green text actions.

## Accessibility

This is a government-facing artifact, so accessibility is a requirement, not a nice-to-have.

- Maintain WCAG AA contrast (4.5:1 for normal text). Many state brand colors fail as text on white and must be darkened — check before using a brand color as text.
- Keep the visually-hidden `<h2 class="sr-only">` summary and `aria-hidden` on decorative icons; give icon-only controls an `aria-label`.
- Preserve keyboard operability and visible focus. Don't remove focus outlines.
- Minimum font size 11px; body text larger.
- Prototype 2: the search input, filter controls, and results must be keyboard operable and announced to assistive tech. Give results an appropriate live region so match counts update audibly.

## Working preferences

- Commit the current working prototype before large changes so there's a clean rollback point.
- Plan before large multi-part edits; make the smallest change that achieves the goal.
- Round any displayed numbers; don't leak floating-point artifacts.
- Ask before adding any dependency, framework, or build tooling — the single-file, low-maintenance constraint is deliberate.
- Prototype 2 and its CIM version: handle the network fetch gracefully. Show loading, empty, and error states so the page never sits blank if resources are slow or unreachable. In the CIM version, if some datasets fail, show the rest with a warning naming the ones that failed.
