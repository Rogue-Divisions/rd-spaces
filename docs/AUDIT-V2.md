# AUDIT-V2.md — Spaces segment pages, post-rebuild audit

Date: 2026-05-12
Auditor: Claude (this thread)
Subject: The eight per-segment landing pages shipped in commit `1baa9c0`
Build verifier: passed 14/14 against `docs/SEGMENT-COPY.md`
Live audit verdict: **15 outstanding defects** (12 from manual Chrome audit + 3 from Codex codebase review)

The build-time verifier confirms every content field on every segment page matches the source-of-truth doc. The verifier is a text-matching matrix; it does not run the page in a browser, does not check paint, does not check currency propagation, does not check visual treatment.

A manual end-to-end audit in Chrome at desktop resolution (1440×900, then 1729×954) on the live site at `https://spaces.roguedivisions.com/<segment>/` surfaced the defects below. They group into two patterns:

1. **Hub-section leakage.** The build correctly injects per-segment hero, outcomes, objection, FAQ, calculator config, and final CTA. It does NOT strip several hub-only sections (Multi-property, About RD, demo pill row) from segment-page output. Result: segment pages are 90% segment-targeted and 10% hub-bleed.
2. **Cross-page state propagation.** Currency, calculator step numbering, and final-CTA verb-language do not share state with their hero counterparts. Result: a page in GBP renders USD add-ons; a page that hides a calculator step shows step numbering 02 → 04.

---

## P0 — launch blockers

### V2-001 — Hero H1 emphasis span (`.rd-win`) is invisible on most segment pages

**Affected pages:** /hosts, /hotels, /weddings (confirmed). /developers, /clinics, /restaurants, /galleries (likely; uncomfirmed by audit). /managers renders correctly.

**Symptom:** The italic-red second clause of the H1 ("For ninety-nine pounds." on /hosts, "Booking takes." on /hotels, "before she flies in." on /weddings) is in the DOM and has correct computed style (italic, brand red, 76px, visible, opacity 1). The bounding rect is identical to /managers (`top=413, height=107, left=256`). Yet the text does not paint visibly on the rendered page.

**Diagnosis from audit:** The DOM and computed CSS are identical between /managers (works) and the failing pages. Difference must be in stacking context / overlay z-index of the hero video layer. The brand-red text is either being painted under an opaque overlay or is failing colour contrast against a video frame at that paint moment.

**Files to investigate:**
- `src/template.html` — hero section markup
- `public/spaces.css` — `.sx-hero__h1`, `.rd-win`, `.sx-hero__overlay` rules
- `scripts/build.py` — verify the segment-page DOM has identical structure around the H1 to the hub page

**Acceptance:**
- All 8 segment pages render their `.rd-win` clause visibly on first paint at 1440×900
- The clause is readable (contrast ratio ≥ 4.5:1 against the worst-case video frame, or covered by a dark overlay layer that sits BELOW the H1)
- Verifier `scripts/verify.py` extended with a Playwright paint check that screenshots the H1 region and asserts `.rd-win` text occupies expected pixels

### V2-002 — Calculator step numbering jumps 02 → 04 → 05

**Affected pages:** /managers (confirmed). Any segment page where `calculator_config.step3_active` is false.

**Symptom:** Calculator section renders "01 For property manager." → "02 How many units in your fleet?" → (no 03) → "04 Add-ons" → "05 Currency". Step 03 (modules) was correctly hidden but the remaining step numbers were not renumbered.

**Files to touch:**
- `scripts/build.py` — renumber step labels when `step3_active` is false
- `src/template.html` — confirm step number nodes have a stable selector or data-attribute

**Acceptance:**
- On /managers, calculator steps read 01, 02, 03, 04 in sequence (no gaps)
- On segments where modules step is active (hotels, developers, weddings, clinics, restaurants, galleries), steps read 01, 02, 03, 04, 05
- Verifier check: `step_numbers_sequential` — extracts visible step numbers and asserts sequential integers from 1

### V2-003 — Currency toggle does not propagate to add-on prices or other price strings

**Affected pages:** All segments (confirmed on /managers).

**Symptom:** Calculator main number renders in GBP (£3,000 / month). Add-on prices render in USD ($400, $200, $250) immediately adjacent. Currency toggle below ("£ GBP" / "$ USD") changes the main number but not the add-on row.

**Files to touch:**
- `src/template.html` — add-on price spans need data-attributes for currency-state binding
- `public/spaces.css` or inline `<script>` — currency state needs to be a single source read by all price renderers

**Acceptance:**
- Currency toggle propagates to: main calculator total, add-on prices, pricing-anchor line (if it contains a currency symbol), any other price text on the page
- Verifier check: `currency_consistency` — assert all visible currency symbols on a page match the active currency state

### V2-004 — Demo pill row above iframe shows wrong segments and wrong active

**Affected pages:** /managers (confirmed). Likely all segment pages.

**Symptom:** On /managers, the pill row reads `Restaurants / Hotels / Hosts (active) / Developers / Venues`. "Managers" is missing entirely. "Hosts" is incorrectly pre-selected.

**Root cause:** The pill row is a hub-pattern (segment-swap-the-demo). The build script injects the segment context but does not update the pill row.

**Decision needed:** Either (a) strip the pill row entirely on segment pages, since the visitor is already on the segment they care about, OR (b) include the current segment in the pill list and pre-select it.

**Recommendation:** Strip the pill row on segment pages. The visitor came to /managers; offering them to swap the demo to a different segment fights against the monomania the page is built for.

**Files to touch:**
- `scripts/build.py` — add the demo pill row to the hub-only selector list

**Acceptance:**
- No demo pill row visible on any of the 8 segment pages
- Hub at `/` retains the pill row with all 8 segments selectable
- Verifier check: `demo_pill_row_absent_on_segment` — DOM absence assertion

---

## P1 — should ship in the same pass

### V2-005 — "Multi-property & subscription." three-card section is present on every segment page

**Affected pages:** All segments (confirmed on /managers).

**Symptom:** A three-card block titled "Multi-property & subscription." with cards `Volume discount -30% / Manager subscription $35 per unit / month / Bespoke contract $5,000 starting` renders below the calculator on segment pages. It is:

1. Redundant on /managers (the calculator already shows per-door subscription)
2. In USD on GBP-default pages
3. Contains cross-segment vocabulary ("hospital, museum") in its CTA strip ("Got a hospital, a multi-floor museum, or a mixed-use development? Talk to us about a bespoke engagement")

**Files to touch:**
- `scripts/build.py` — add the section to the hub-only selector list
- `src/template.html` — confirm the section has a stable data-attribute or class for selection (e.g. `data-hub-only="multi-property"`)

**Acceptance:**
- No "Multi-property & subscription." section on any segment page
- Hub at `/` retains the section
- Verifier check: `multi_property_section_absent_on_segment`

### V2-006 — One-off onboarding capture fee missing from /managers price card

**Affected pages:** /managers.

**Symptom:** The pricing-anchor line above the calculator reads "From £30 per door per month, **plus a one-off capture fee**." When a fleet size is selected, the right-hand price card shows only the monthly subscription (`£3,000 / month`). The one-off capture fee is not rendered anywhere.

**Files to touch:**
- `src/segments.json` — add `calculator_config.one_off_fee` per fleet-size option (or a per-door rate that the JS multiplies)
- `src/template.html` and inline calculator JS — render the one-off fee as a second line on the price card when present
- `scripts/build.py` — pass through the one_off_fee config

**Acceptance:**
- /managers price card shows monthly subscription AND one-off capture fee as separate lines
- Other segments unaffected (no one_off_fee field → no second line)
- Verifier check: `managers_price_card_shows_onboarding_fee`

### V2-007 — "How it works" 3-step is hub copy on every segment page

**Affected pages:** All segments. Most obviously wrong on /managers, /developers, /clinics.

**Symptom:** Every segment page shows the same 3-step block:
- "We arrive. At a time that suits you. We do not redress your space. About 20 minutes per room."
- "Ready by tomorrow. We process and quality-check the capture overnight."
- "We help you publish. Hosted link, embed snippet, and the help to get it live on your site."

For /managers this is wrong: a property manager with 80 doors does not have "your space"; they have a fleet. The 20-minutes-per-room flavour is for a single-unit Lite engagement, not a fleet onboarding.

**Files to touch:**
- `src/segments.json` — add `process_steps` array per segment (3 items, each `{title, body}`)
- `scripts/build.py` — when `process_steps` is present, override the shared 3-step section; when absent, use the hub default

**Acceptance:**
- /managers reads: scoping → cluster capture → handover-to-listings-team (or similar fleet-flavoured language; see SEGMENT-COPY.md for canonical text once authored)
- /developers reads: show-flat capture → multilingual processing → sales-agent ammunition (or similar)
- /clinics reads: privacy SOP agreed → off-hours capture → multilingual deployment (or similar)
- Other segments either get bespoke copy or fall back to the hub default if appropriate
- This task requires Sage to author the per-segment process_steps copy. Default behaviour while awaiting copy: fall back to hub copy with NO error.

### V2-008 — Objection block has no visual differentiation from neighbouring sections

**Affected pages:** All segments.

**Symptom:** The objection block ("'We already pay for professional photos.' / Keep them. Walkthroughs do not replace photos...") has correct content but no tinted background, no border, no surrounding card. The italic quote is rendered in italic sans (the body font) at large size, not the spec'd italic serif. Result: the block reads as "another paragraph" rather than a deliberate "we know what you're thinking" beat.

**Spec from the v2 prompt (re-stated):**
- Centred column, max-width ~720px on desktop
- Quote renders as italic SERIF heading in muted brand colour with curly quotes
- Reply renders below in body type, 2-4 sentences
- Subtle background tint to mark the block as a deliberate beat
- Mobile-responsive

**Files to touch:**
- `public/spaces.css` — add `.sx-objection`, `.sx-objection__quote`, `.sx-objection__reply` rules
- `src/template.html` — confirm objection markup wraps correctly for the CSS

**Acceptance:**
- The objection block sits in a visibly distinct container (background tint OR border OR breathing room ≥ 2x the sibling-section margin)
- Quote uses a serif font (or italic at a noticeably different weight from body)
- A user scrolling at speed would identify the block as a deliberate beat, not miss it
- Reviewed on desktop (1440×900) and mobile (390×844)

---

## P2 — polish, visible, do not block ship

### V2-009 — "Operators, not a marketplace." (About RD) is present on every segment page with broken layout

**Affected pages:** All segments.

**Symptom:** The two-paragraph About-RD block renders on every segment page in a two-column layout. The right column was meant to hold "Selected credits" logos which are hidden (no real logos yet). Result: visible empty space in the right column.

**Files to touch:**
- `scripts/build.py` — either strip the section on segment pages OR reflow to full-width when credits aside is hidden
- `src/template.html` — option B requires conditional layout based on data-attribute

**Recommendation:** Strip on segment pages. The segment page is monomania; About-RD content does not aid the conversion. Keep on hub.

**Acceptance:**
- No empty right column on any segment page
- About-RD either absent (strip) or full-width single-paragraph (tighten)
- Hub at `/` retains current treatment until decided otherwise

### V2-010 — Final CTA buttons revert to hub-generic on /managers (and likely all segments)

**Affected pages:** /managers (confirmed).

**Symptom:** Hero primary CTA reads "Book a fleet pilot". Hero secondary reads "See a manager-built tour →". Final CTA below the final-CTA H2 reverts to "Book your free pilot scan" and "See pricing" — hub-generic.

**Files to touch:**
- `src/segments.json` — add `final_cta.button_primary` and `final_cta.button_secondary` fields per segment
- `scripts/build.py` — render the buttons from the per-segment config
- `src/template.html` — confirm the buttons have stable selectors

**Acceptance:**
- Final CTA buttons match hero CTAs in segment-flavour and verb-language
- Verifier check: `final_cta_buttons_segment_flavoured` — asserts the button text on segment pages differs from the hub default

### V2-011 — Footer "MORE" column collapsed to single "All segments" link

**Affected pages:** All segments.

**Symptom:** CC over-corrected on the "no other segment word below the hero" rule by collapsing the footer segment list to a single "All segments →" link back to the hub. Result: a visitor on /managers who realises they want /hotels has no direct footer navigation; they must return to the hub first.

**Files to touch:**
- `scripts/build.py` — restore the 8-segment footer list on segment pages
- `public/spaces.css` — de-emphasise the list slightly (smaller font, muted colour) so it does not pull attention from the segment focus

**Acceptance:**
- Footer "For" or "Segments" column on every segment page lists all 8 segment links
- Visual emphasis is de-prioritised relative to the segment's own CTA
- Hub footer unchanged

### V2-012 — Sticky mobile CTA label is not segment-aware (unconfirmed)

**Affected pages:** All segments. **Audit limitation:** Could not be confirmed via Chrome MCP because viewport resize did not flow to mobile width in the audit environment. Sage to confirm on actual phone.

**Symptom (suspected):** The sticky mobile CTA from C4 reads "Book a pilot" regardless of which segment page is rendered. The hero primary CTA is correctly segment-flavoured ("Book a fleet pilot" on /managers).

**Files to touch:**
- `src/segments.json` — add `sticky_cta_label` field per segment
- `src/template.html` — sticky CTA element reads the per-segment label
- `scripts/build.py` — pass through

**Acceptance:**
- Sticky mobile CTA label matches the hero primary CTA verb-language on each segment page
- Visible on iOS Safari and Android Chrome at 390×844 viewport
- Sage to confirm before close

---

### V2-013 — Security headers do not apply to segment pages

**Affected pages:** All 8 segment pages.

**Symptom:** `public/_headers` rules match `/` and `/*.html`. Segment pages are served as folder-style URLs (`/managers/`, `/hosts/`, etc.) which resolve to `public/<slug>/index.html`. Cloudflare Workers' default HTML handling redirects bare `/folder` to `/folder/`, and the `_headers` URL patterns do not match `/<slug>/`. Result: Content-Security-Policy, HSTS, X-Content-Type-Options, Permissions-Policy are missing on segment-page responses but present on the hub.

**Files to touch:**
- `public/_headers` — move security headers under a `/*` block so they apply to every path. Keep cache-control rules in their existing path-specific blocks.
- `wrangler.toml` — decide and pin the trailing-slash policy (`html_handling = "drop-trailing-slash"` or its inverse) so URLs are canonical.
- Confirm with the Cloudflare `_headers` and HTML handling docs.

**Acceptance:**
- `curl -I https://spaces.roguedivisions.com/managers/` returns the same security headers as `curl -I https://spaces.roguedivisions.com/`
- Trailing-slash behaviour is consistent across all 9 pages (either all `/path/` or all `/path`, not mixed)
- Verifier check: `security_headers_present_on_segment` — assert response headers on each segment URL include `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`, `Permissions-Policy`

### V2-014 — Demo block caption stale on hub when visitor switches tour pills

**Affected pages:** Hub at `/` only.

**Symptom:** The hub demo block has a pill row (Restaurants / Hotels / Hosts / Developers / Venues) that switches the iframe `src` on click. The template JS targets `[data-tour-title]` to update the caption text alongside the iframe. The build generator replaces the entire caption text and removes the `data-tour-title` span. Result: clicking the Hotels pill loads the hotel iframe but the caption underneath still reads the previous tour's title (or the default).

**Files to touch:**
- `scripts/build.py` (line ~1094 area, per Codex's review) — preserve the `[data-tour-title]` span when generating caption text instead of replacing the whole caption
- `src/template.html` (line ~1094 area) — confirm the span structure the JS expects

**Acceptance:**
- On hub, click each of the 5 pills → caption updates to match the active tour
- Verifier check: `hub_pill_caption_updates` — Playwright clicks each pill and asserts the visible caption matches the data-tour-title for that pill

### V2-015 — README misleads about editing target

**Affected file:** `README.md`.

**Symptom:** README documents the edit workflow as "edit files in `public/`", but `public/<slug>/index.html` is overwritten on every build by `scripts/build.py` reading `src/template.html` and `src/segments.json`. A new contributor following the README will edit `public/` and lose their changes on next CI build.

**Files to touch:**
- `README.md` — rewrite the contributor section. Canonical edit targets: `src/template.html`, `src/segments.json`, `public/spaces.css`, `public/_headers`. Generated files (`public/*/index.html`) are NEVER edited directly.

**Acceptance:**
- README explicitly lists the source-of-truth files and explicitly states that `public/*/index.html` is generated
- A contributor reading the README understands the build flow before they edit anything

---

## Verifier extensions required

Extend `scripts/verify.py` with the following checks. These are NOT currently in the 14-check matrix.

1. **paint_hero_emphasis** — headless Chrome navigates each segment URL, screenshots the hero region, asserts the `.rd-win` element occupies non-empty pixels of the brand-red colour.
2. **step_numbers_sequential** — extract visible step numbers from the calculator section, assert they are sequential integers starting at 1.
3. **currency_consistency** — for each currency state (GBP, USD), assert all visible currency symbols on the page match.
4. **demo_pill_row_absent_on_segment** — assert no segment-swap pill row exists in the demo block on segment pages.
5. **multi_property_section_absent_on_segment** — assert no "Multi-property & subscription." section on segment pages.
6. **about_rd_treatment** — assert either absent or full-width single-paragraph on segment pages.
7. **final_cta_buttons_segment_flavoured** — assert button text differs from hub defaults.
8. **footer_segments_list_present** — assert footer contains all 8 segment links on segment pages.
9. **security_headers_present_on_segment** — `curl -I` each segment URL and assert `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`, `Permissions-Policy` are present.
10. **hub_pill_caption_updates** — Playwright clicks each demo pill on the hub and asserts the visible caption matches the pill's tour title.

Add these alongside the existing 14 checks. Target: 24-check matrix passing on all 9 pages before declaring v3 done.

---

## Acceptance for the v3 fix pass

The pass is done when:

1. All 15 defects above are fixed.
2. The extended `verify.py` (24 checks) passes on all 9 pages.
3. Manual paint check confirms `.rd-win` visible on all 8 segment-page heroes.
4. Manual mobile check at 390×844 confirms objection block, calculator (subscription mode on /managers), and sticky CTA render correctly.
5. A single PR contains all changes. PR description references this audit doc and the verify.py output.
