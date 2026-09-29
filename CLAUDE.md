# CLAUDE.md

Project context and working guidance for Claude Code. Read this at the start of every session.

## What this is

A set of **discovery-phase prototypes** for the Colorado Department of Public Health & Environment (CDPHE) Data Modernization Initiative (DMI). The prototypes are reached from a shared **index page** and share one look and feel (see Visual identity). Each demonstrates part of how public health staff would find the right data source(s) to answer a public health question.

There are two prototypes:

### Prototype 1 — find → understand → access (self-contained)

A searchable public health data catalog that demonstrates the full **find → understand → access** flow for finding the right data source(s) to answer a public health question. The first example is from the Chronic Disease cohort with the example search "cancer prevalence by county." All data is illustrative and hard-coded in the file (see Constraints); there is no backend.

### Prototype 2 — functional search + filter

A narrower prototype focused only on the **search and filter** experience, linked from the same index and built to the same look and feel as Prototype 1, branded 'CDPHE Data explorer'.

- **Real read-only backend hosted in the data folder of this repo.** Catalog records are pulled from the JSON files in the `data` folder.
- **Functional search.** Search queries the real records pulled from the JSON and returns actual matches; filters narrow the real result set.
- **Schema.** The data schema is in the `data/schema.json` file; it describes the metadata shown in the result cards and available filters for the search.

## What this is NOT

- Not a production system, and not a platform build. Platform selection, procurement, and enterprise data infrastructure are explicitly out of scope for this phase.
- Not production data infrastructure. Prototype 1 has no backend at all. Prototype 2 reads from a Google Sheet, but that is a lightweight, illustrative content store — not a server, database, or platform build.
- Not a place for sensitive CDPHE data — and this includes the Google Sheet. The sheet holds catalog **metadata** only (source names, descriptions, topic area, geography, update cadence, and public links) — never real record-level data, credentials, or internal-only material. We use publicly accessible links to dashboards and documentation.

## Deployment

These prototypes are deployed to a password-protected Netlify environment for easy sharing with partners. When possible they should link out to real CDPHE dashboards and sources available publicly on the internet.

Prototype 2 additionally fetches its catalog data at runtime from a published Google Sheet, so it depends on network access to that sheet's published endpoint. Keep the sheet's sharing scoped to read-only published data.

## Constraints

1. **Single HTML file, no build step.** Each prototype is one `.html` file that runs by opening it in a browser — no build step, no bundler, no framework, no server-side code. Keep it that way unless explicitly asked to change the architecture.
   - Prototype 1 is fully **self-contained**: all data is hard-coded in the file.
   - Prototype 2 is one HTML file but **not fully self-contained**: markup, styles, and logic all live in the one file, but catalog data is fetched at runtime from the published Google Sheet. That sheet is its only external dependency.
2. **Design tokens are inlined**, not borrowed from any host environment, so each renders identically wherever it is hosted.
3. **Demonstrative, not comprehensive.** Scope features small and testable. When in doubt, do the simplest thing that makes the flow legible to a stakeholder.

## Visual identity

Applies to the index and both prototypes — keep the look and feel consistent across all of them.

Use gray scale to reinforce that this is a prototype, with standard colors for callouts (success, error, warning).

Typography: **Trebuchet MS** for body/UI (official state secondary typeface, a standard system font). Museo Slab is the state headline font but is not a system font, so do not depend on it in a standalone file. Use sentence case everywhere — never Title Case or ALL CAPS (except the "COLORADO" wordmark).

Branding: the header shows a simplified upward-arrow "C" mark and the "COLORADO / Department of Public Health & Environment" wordmark. Keep the "· prototype" marker visible so no one mistakes this for a shipped product.

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
- Prototype 2: handle the network fetch gracefully. Show loading, empty, and error states so the page never sits blank if the sheet is slow or unreachable. Don't hard-code a fallback copy of the data that can drift from the sheet.
