# CLAUDE.md

Project context and working guidance for Claude Code. Read this at the start of every session.

## What this is

A **discovery-phase prototype** for the Colorado Department of Public Health & Environment (CDPHE) Data Modernization Initiative (DMI). It is a searchable public health data catalog that demonstrates a **discover → compare → request** flow for finding the right data source to answer a public health question.

- **Cohort / use case (this version):** Chronic Disease
- **Primary user:** CDPHE internal program staff (e.g. a chronic disease epidemiologist doing a community health assessment refresh)
- **Core insight it exists to prove:** the dominant barrier is *navigation, not trust* — data is "hard to find" more than "hard to trust." The prototype is built to show that helping users discover and compare the sources that answer a similar question is the high-value service.

## What this is NOT

- Not a production system, and not a platform build. Platform selection, procurement, and enterprise data infrastructure are explicitly out of scope for this phase.
- Not a real backend. All data in the prototype is illustrative/sample content hard-coded in the file. There is no server, database, or live data connection.
- Not a place for real or sensitive CDPHE data. Keep everything in the repo synthetic. Do not add real record-level data, credentials, or internal-only material.

## Hard constraints (do not break without being asked)

1. **Single self-contained HTML file.** The deliverable is one `.html` file that runs anywhere by opening it in a browser — no build step, no bundler, no framework, no server. Keep it that way unless explicitly asked to change the architecture.
2. **Design tokens are inlined**, not borrowed from any host environment, so it renders identically wherever it is hosted.
3. **Keep it light and sustainable.** A guiding design parameter for the whole engagement is "light tooling, sustainable by CDPHE's existing technology unit by 2028." Prefer simple, vanilla, low-maintenance solutions over clever or heavy ones. Every added dependency is a maintenance cost — justify it.
4. **Demonstrative, not comprehensive.** Scope features small and testable. When in doubt, do the simplest thing that makes the flow legible to a stakeholder.

## Visual identity — State of Colorado / Colorado Design System

Use the official State of Colorado primary palette and typography. Do not substitute arbitrary colors.

Primary palette (from the State of Colorado color system):

| Token | Hex | Use |
| --- | --- | --- |
| Main blue | `#005980` | Primary brand, headers, primary actions |
| Light blue | `#00A1E6` | Accent, the "C" arrow mark |
| Green | `#00953a` | Success, request/submit actions |
| Orange | `#ef7521` | Attention, "how current" / caveat cues |
| Dark grey | `#4e5758` | Secondary UI, neutral icons |

Supporting tints already used in the prototype: blue tint `#E6F1FB` / text `#0C447C`, green tint `#EAF3DE`, amber tint `#FAEEDA` / text `#854F0B`, light blue `#B5D4F4`.

Typography: **Trebuchet MS** for body/UI (official state secondary typeface, a standard system font). Museo Slab is the state headline font but is not a system font, so do not depend on it in a standalone file. Use sentence case everywhere — never Title Case or ALL CAPS (except the "COLORADO" wordmark).

Branding: the header shows a simplified upward-arrow "C" mark and the "COLORADO / Department of Public Health & Environment" wordmark. Keep the "· prototype" marker visible so no one mistakes this for a shipped product.

## Accessibility

This is a government-facing artifact, so accessibility is a requirement, not a nice-to-have.

- Maintain WCAG AA contrast (4.5:1 for normal text). Many state brand colors fail as text on white and must be darkened — check before using a brand color as text.
- Keep the visually-hidden `<h2 class="sr-only">` summary and `aria-hidden` on decorative icons; give icon-only controls an `aria-label`.
- Preserve keyboard operability and visible focus. Don't remove focus outlines.
- Minimum font size 11px; body text larger.

## Data sources represented (Chronic Disease)

Pulled from project files. All content is illustrative. Running example question: **"diabetes prevalence in adults."**

- **BRFSS** (Behavioral Risk Factor Surveillance System) — annual survey, ~6-month lag, ~10,000 surveys/year; state/region/county via multi-year pooling; flagged as **best fit** for adult prevalence. Note the 2011 methodology break and the under-50-respondent suppression rule.
- **Hospital Discharge Data** — administrative, quarterly, care events not community prevalence.
- **Vital Records (death certificates)** — registry, annual, mortality only.
- **Healthy Kids Colorado Survey (HKCS)** — youth survey, biennial, adjacent not direct.
- **Community Level Estimates** — modeled small-area estimates, wide CIs, good for local targeting.

Referenced dashboards: the **VISION** dashboards (Diabetes, Cardiovascular Health, Cancer Screening) and the **Cancer Incidence Dashboard**.

## Roadmap / possible next iterations

- Behavioral Health cohort version (the other PHDF cohort).
- A data-steward / publishing view (the producer side of the catalog).
- Inline the Tabler icons as SVG so the file has **zero external dependencies** and works fully offline (currently icons load from the cdnjs Tabler CDN — the one remaining external dependency).
- Optional: a different running example (e.g. a cancer question that foregrounds the Cancer Incidence Dashboard).

## Working preferences

- Commit the current working prototype before large changes so there's a clean rollback point.
- Plan before large multi-part edits; make the smallest change that achieves the goal.
- After changes, verify the core flow still works end to end: search → add to compare → compare table → view details → request access → confirmation.
- Round any displayed numbers; don't leak floating-point artifacts.
- Ask before adding any dependency, framework, or build tooling — the single-file, low-maintenance constraint is deliberate.