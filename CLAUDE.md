# CLAUDE.md

Project context and working guidance for Claude Code. Read this at the start of every session.

## What this is

A **discovery-phase prototype** for the Colorado Department of Public Health & Environment (CDPHE) Data Modernization Initiative (DMI). It is a searchable public health data catalog that demonstrates a **find → understand → access** flow for finding the right data source(s) to answer a public health question.

The first example is from the Chronic Disease cohort with the example search "cancer prevalence by county." 


## What this is NOT

- Not a production system, and not a platform build. Platform selection, procurement, and enterprise data infrastructure are explicitly out of scope for this phase.
- Not a real backend. All data in the prototype is illustrative/sample content hard-coded in the file. There is no server, database, or live data connection.
- Not a place for real or sensitive CDPHE data. Keep everything in the repo synthetic. Do not add real record-level data, credentials, or internal-only material.

## Hard constraints (do not break without being asked)

1. **Single self-contained HTML file.** The deliverable is one `.html` file that runs anywhere by opening it in a browser — no build step, no bundler, no framework, no server. Keep it that way unless explicitly asked to change the architecture.
2. **Design tokens are inlined**, not borrowed from any host environment, so it renders identically wherever it is hosted.
3. **Demonstrative, not comprehensive.** Scope features small and testable. When in doubt, do the simplest thing that makes the flow legible to a stakeholder.

## Visual identity

Use gray scale to reinforce that this is a prototype, with standard colors for callouts (success, error, warning).

Typography: **Trebuchet MS** for body/UI (official state secondary typeface, a standard system font). Museo Slab is the state headline font but is not a system font, so do not depend on it in a standalone file. Use sentence case everywhere — never Title Case or ALL CAPS (except the "COLORADO" wordmark).

Branding: the header shows a simplified upward-arrow "C" mark and the "COLORADO / Department of Public Health & Environment" wordmark. Keep the "· prototype" marker visible so no one mistakes this for a shipped product.

## Accessibility

This is a government-facing artifact, so accessibility is a requirement, not a nice-to-have.

- Maintain WCAG AA contrast (4.5:1 for normal text). Many state brand colors fail as text on white and must be darkened — check before using a brand color as text.
- Keep the visually-hidden `<h2 class="sr-only">` summary and `aria-hidden` on decorative icons; give icon-only controls an `aria-label`.
- Preserve keyboard operability and visible focus. Don't remove focus outlines.
- Minimum font size 11px; body text larger.

## Working preferences

- Commit the current working prototype before large changes so there's a clean rollback point.
- Plan before large multi-part edits; make the smallest change that achieves the goal.
- Round any displayed numbers; don't leak floating-point artifacts.
- Ask before adding any dependency, framework, or build tooling — the single-file, low-maintenance constraint is deliberate.