# AUDIT-V4.md — Spaces v4 scope

Date: 2026-05-13
Author: Strategy + audit thread
Subject: Comprehensive v4 scope for spaces.roguedivisions.com
Build verifier baseline: v3 24-check matrix passing on all 9 pages

V4 is the **commercial calibration pass**. V3 fixed engineering and structural defects. V4 aligns the site with validated buyer pain points, narrows focus to five priority segments, removes commercial friction (currency inconsistency, generic CTAs, overclaim language), and replaces the de-prioritised segments with a tighter five-segment funnel.

V4 changes are concrete and individually small. The scope is one PR. The verifier extension adds 6 new checks bringing the matrix to 30.

---

## Strategic context

Three independent deep research reports (Gemini, Perplexity, ChatGPT Pro) validated and corrected the operator pain matrix for each of the eight buyer segments. Findings consolidated in `docs/PAIN-MATRIX.md` (also committed in this pass). Headlines:

1. **Off-plan developers, wedding venues, boutique hotels, STR managers, cultural venues** — strong, medium-strong, or medium fit per research. These five become **Phase 1**.
2. **Medical tourism clinics, solo Airbnb hosts** — forced fit per research. Demoted to inbound-only. Pages stay live; no acquisition spend.
3. **Design-led restaurants** — real but narrow fit. Phase 2 hold. Page stays live; revisit after Phase 1 traction.
4. **Currency strategy** — GBP was a UK-company-bias error. International Tbilisi business operates in USD with GEL as local-comfort currency. Drop GBP entirely.
5. **Pricing consistency** — hub cards previously mismatched segment-page anchors (USD ranges on hub, GBP on segments). Single pricing schema, rendered consistently across hub cards, segment pages, and calculator.

---

## V4 defects (CT-001 through CT-018)

### P0 — launch blockers

#### CT-001 — Hub segment grid reduces from 8 cards to 5

**Affected:** Hub at `/`.

**Symptom:** Hub currently shows 8 segment cards including clinics, hosts, restaurants which are now demoted.

**Action:**
- Hub segment grid shows 5 cards only: Developers, Weddings, Hotels, Managers, Galleries
- Card order = priority order from PAIN-MATRIX
- Card copy = short hook line per segment (see `docs/SEGMENT-COPY.md`)

**Files:** `src/template.html`, `src/segments.json`, `scripts/build.py` (filter active vs demoted segments).

**Acceptance:** Hub renders exactly 5 segment cards. The demoted three (clinics, hosts, restaurants) do not appear in the grid.

#### CT-002 — Footer "FOR" column reduces from 8 links to 5

**Affected:** All pages (hub + segments + demoted).

**Symptom:** Footer currently lists all 8 segment links.

**Action:** Footer "FOR" column lists only Phase 1 segments: Developers, Weddings, Hotels, Managers, Galleries.

**Files:** `src/template.html`, `scripts/build.py`.

**Acceptance:** All 9 pages show 5-link footer column. No links to /clinics, /hosts, /restaurants from footer on any page.

#### CT-003 — Hub navigation removes demoted segments

**Affected:** Hub at `/`.

**Symptom:** Hub nav currently has "Who it's for" or "All segments" — verify it does not surface demoted segments.

**Action:** Confirm hub navigation does not link to /clinics, /hosts, /restaurants. The hub segment grid (above) is the only surfacing for the 5 Phase 1 segments.

**Files:** `src/template.html`.

**Acceptance:** Demoted pages reachable only by direct URL.

#### CT-004 — Currency stack: USD primary, GEL secondary, GBP removed

**Affected:** All pages.

**Symptom:** Current site uses GBP default + USD toggle. GEL not represented.

**Action:**
- Strip all GBP / £ symbols across hub, segment pages, calculator, FAQ, pricing anchors, OG meta tags
- Default currency: USD
- Toggle: GEL (Georgian Lari) — symbol ₾, ISO 4217 code GEL
- FX strategy: fixed display rate updated quarterly. Codex picks a reasonable rate (approx 1 USD = 2.70 GEL as of May 2026) and stores it as a config value in `src/segments.json` under `currency_config.gel_rate`. Update mechanism: change the config value, run build, deploy.
- All price renderers (hub cards, segment-page anchors, calculator main number, calculator add-ons, "What's included" prices, pricing anchor lines, FAQ price mentions) MUST read from a single currency state and update on toggle.

**Files:** `src/template.html`, `src/segments.json`, `scripts/build.py`, `public/spaces.css`, inline calculator JS.

**Acceptance:**
- No `£` or `GBP` substring anywhere in the rendered HTML of any page
- Currency toggle on calculator switches between `$` and `₾` for ALL prices on the page
- All segment pages default to USD on first load
- Manual mental check: click GEL, every price on the page updates; click USD, every price reverts

#### CT-005 — Pricing schema consistency across hub and segment pages

**Affected:** All pages.

**Symptom:** Hub cards historically showed USD ranges ($1,000-$3,000 hotels, From $99 hosts, $35 per unit managers); segment pages showed GBP anchors (£500, £99, £30 per door). Same product, different currency, different anchor.

**Action:** Lock to single pricing schema from `docs/SEGMENT-COPY-V2.md`:

| Tier | USD | GEL |
| --- | --- | --- |
| Lite | $129 | ₾350 |
| Compact | $500 | ₾1,350 |
| Standard | $1,500 | ₾4,050 |
| Major | $3,000+ | ₾8,100+ |
| Managers subscription | $35 per door / month | ₾95 per door / month |

Hub cards and segment pages reference the same schema. Hub card lead line = "From $X" matching the segment's lowest anchor.

**Files:** `src/segments.json` (pricing schema as canonical source), `src/template.html` (hub cards), `scripts/build.py` (propagation).

**Acceptance:**
- Hub card price for Hotels: "From $500 per suite" (matches `/hotels` anchor)
- Hub card price for Developers: "From $1,500" (matches `/developers` anchor)
- Hub card price for Weddings: "From $1,500" (matches `/weddings` anchor)
- Hub card price for Managers: "From $35 per door per month"
- Hub card price for Galleries: "From $1,500"
- All match the segment-page pricing-anchor line below the hero

#### CT-006 — Phase 1 segment page reframes per PAIN-MATRIX

**Affected:** /developers, /managers, /hotels, /weddings, /galleries.

**Symptom:** Current pages hit secondary or product-led pains instead of validated top-of-mind buyer pains.

**Action:** Apply hero, subhead, outcomes, objection, FAQ, final CTA changes per `docs/SEGMENT-COPY-V2.md`. Specifically:

- **/developers** — full hero reframe to "Buyers wire faster when they have walked the space." New outcomes around sales velocity, remote close, render-to-real bridge, sales agent ammunition.
- **/managers** — full hero reframe to "Show owners you are investing in their door." New outcomes around owner-facing proof, door-level performance, predictable rollout, fleet standard. Fix calculator label "For property manager" → "For STR property managers."
- **/hotels** — hero sharpened: "Recover the commission OTAs take" (was "Booking takes" — broadened beyond one platform). Outcome cards sharpened to direct-booking economics with the "one avoided OTA booking pays back the scan" causal frame.
- **/weddings** — hero unchanged. New pricing-transparency block above calculator addressing the ghosting pain. Outcomes sharpened to remove "calendar fills without a single viewing" overclaim. Final CTA tightened: "Send it to the planner choosing between six venues" replaces "Watch what happens."
- **/galleries** — institutional/museum focus. Subhead corrected: "Curators, donors, jurors, and grant assessors walk the show after it closes" (was awkward "Frieze, Venice, Berlin"). Outcomes reordered to lead with donor/grant evidence, then venue hire revenue, then archive. Newsletter embed claim corrected (link not embed).

**Files:** `src/segments.json` (per-segment field updates), `scripts/build.py` (no architectural change needed — just data).

**Acceptance:** Each Phase 1 page exactly matches the corresponding section in `docs/SEGMENT-COPY-V2.md`.

#### CT-007 — Hub hero subhead broadens beyond "fly in"

**Affected:** Hub at `/`.

**Symptom:** Hub subhead "Tours they can walk before they fly in" works for developers, weddings, hotels, clinics, galleries but is weak for STR managers and design-led restaurants (whose buyers are not "flying in" — they are operating locally).

**Action:** Replace with `When the buyer is somewhere else, they need to walk the space before they commit.`

**Files:** `src/template.html`, `src/segments.json` (hub config).

**Acceptance:** Hub subhead reads the new line on first load. No reference to "fly in" in hub copy.

#### CT-008 — Generic CTAs and absolute-claim overclaims scrubbed

**Affected:** All Phase 1 pages.

**Symptom:** Existing copy contains several overclaim phrases identified by the external copy audit:

- "Your booking calendar fills without a single in-person viewing" (/weddings) — replace per SEGMENT-COPY-V2
- "Visitors who watch the walkthrough end-to-end become qualified leads" (/developers if still present) — remove
- "A walkthrough proves the room is competent" (/clinics — demoted but if anywhere still in copy, remove)
- "Stage gating" outcome card on /developers — rename to "The qualified-lead filter" or per SEGMENT-COPY-V2
- "Private hire enquiries close before the call ends" (/restaurants — demoted but check if still appearing on hub) — soften to "close on the first call" or similar
- "Pasted into a Mailchimp campaign" (/developers, /galleries) — clarify: hosted link in email, embed code on website
- Hub "Pocket money for what it returns" host card — remove with host card

**Files:** `src/segments.json`, `src/template.html` if any of these are template-hardcoded.

**Acceptance:** Each defect string is either removed or replaced with the corresponding string from SEGMENT-COPY-V2.

### P1 — should ship in same pass

#### CT-009 — Hub Matterport FAQ rewrite

**Affected:** Hub FAQ.

**Symptom:** Existing answer "Photo-realism, yes, and arguably better. Floor plans and measurements, no, Matterport is still ahead on those." reads as defensive and invites argument.

**Action:** Replace with the SEGMENT-COPY-V2 version: "For buyer-decision visualisation, this is sharper and faster. For property workflows that need precise floor plans and measurements, Matterport is stronger. Spaces is built for buyer confidence — faster capture, hosted walkthrough, embedded in your sales channels."

**Files:** `src/template.html`, `src/segments.json` (hub FAQ config if data-driven).

**Acceptance:** Hub FAQ renders the new answer.

#### CT-010 — "Operators, not a marketplace." collapses to one sentence at full width on hub

**Affected:** Hub.

**Symptom:** Current block is two paragraphs in a two-column layout with empty right column (Selected credits hidden).

**Action:** Replace block with single-sentence full-width: `Spaces is a Rogue Divisions studio. We capture, host, and publish — your relationship is with operators, not a platform.`

**Files:** `src/template.html` or `src/segments.json`.

**Acceptance:** Hub renders the one-sentence version with no empty right column.

#### CT-011 — Sticky mobile CTA segment-aware (carryover from V2-012)

**Affected:** All Phase 1 segment pages on mobile viewport.

**Symptom:** V3 audit could not verify; sticky CTA may read generic "Book a pilot" rather than segment-flavoured.

**Action:** Confirm sticky mobile CTA reads the per-segment `sticky_cta_label` from segments.json. Per SEGMENT-COPY-V2:
- /developers → "Book a show-flat pilot"
- /weddings → "Book a venue pilot"
- /hotels → "Book a suite pilot"
- /managers → "Book a fleet pilot"
- /galleries → "Book a venue pilot"

**Files:** `src/template.html`, `src/segments.json`, inline JS.

**Acceptance:** Render each Phase 1 page at 390px width. Sticky CTA at bottom shows the segment-specific label, not "Book a pilot".

#### CT-012 — Pricing-transparency block added to /weddings

**Affected:** /weddings.

**Symptom:** Wedding venue ghosting (#1 pain per 2/3 research reports) is partly driven by pricing opacity. Page does not currently show pricing structure above the calculator.

**Action:** Add a pricing-transparency block above the calculator on /weddings, between the objection block and the calculator. Content per SEGMENT-COPY-V2:

`Standard engagement from $1,500. What is included: ceremony hall, dining space, gardens, bridal suite. Modules for additional bridal suites, dressing rooms, vineyard exterior, mountain or estate exterior. Multi-building estates at Major tier from $3,000.`

Visual: tinted background or border, similar treatment to objection block but visually distinct (not italic).

**Files:** `src/template.html` (new section pattern), `src/segments.json` (wedding-specific `pricing_transparency` field), `scripts/build.py` (conditional render for /weddings only).

**Acceptance:** /weddings renders the new block; other segments do not.

#### CT-013 — Manager calculator label fix

**Affected:** /managers.

**Symptom:** Calculator Step 01 currently reads "For property manager." Grammatically broken and visibly agent-generated.

**Action:** Change to "For STR property managers."

**Files:** `src/segments.json`.

**Acceptance:** /managers calculator Step 01 reads "For STR property managers."

#### CT-014 — Demoted pages currency update only

**Affected:** /clinics, /hosts, /restaurants.

**Symptom:** Pages are demoted but should still serve correctly. They currently render GBP prices.

**Action:** Apply currency changes (USD/GEL) on these pages. No other copy changes. No reframing. Page stays live and accessible by direct URL.

**Files:** `src/segments.json` (currency config propagates to all segments).

**Acceptance:** /clinics, /hosts, /restaurants render USD prices with GEL toggle. No other changes.

### P2 — polish, do not block ship

#### CT-015 — Calculator H2 on segment pages

**Affected:** All Phase 1 segment pages.

**Symptom:** Calculator H2 reads "See what your space costs, in a minute." — hub-generic.

**Action:** Optional per-segment H2 override via `segments.json` `calculator_h2` field:
- /developers → "Price your show flat engagement"
- /managers → "Price your fleet rollout"
- /weddings → "Price your venue capture"
- /hotels → "Price your suite engagement"
- /galleries → "Price your exhibition capture"

Hub continues to use the generic line.

**Files:** `src/segments.json`, `src/template.html` (conditional H2).

**Acceptance:** Each segment page renders its specific calculator H2.

#### CT-016 — Hero CTA buttons match across hero, sticky, final, nav

**Affected:** All Phase 1 segment pages.

**Symptom:** Hero primary CTA, sticky mobile CTA, final CTA primary, and nav CTA should all use the same verb-noun pattern for coherence.

**Action:** Per SEGMENT-COPY-V2, each segment has a canonical primary-CTA label that is used in all four places:
- /developers → "Book a show-flat pilot"
- /weddings → "Book a venue pilot"
- /hotels → "Book a free suite pilot" (hero), "Book a suite pilot" (sticky/nav)
- /managers → "Book a fleet pilot"
- /galleries → "Book a venue pilot"

**Files:** `src/segments.json` (cta_primary_label propagated to hero, sticky, final, nav).

**Acceptance:** Each page's four CTA surfaces use the matching segment label.

#### CT-017 — Segment hooks on hub grid cards

**Affected:** Hub segment grid.

**Symptom:** Hub grid card copy may currently be generic.

**Action:** Each card uses the hook line from SEGMENT-COPY-V2:
- Developers — "Show flat walkthroughs that close off-plan deposits faster. From $1,500."
- Weddings — "Let the couple walk the venue before they fly in. From $1,500."
- Hotels — "Recover the commission OTAs take. From $500 per suite."
- Managers — "A walkthrough for every door. From $35 per door per month."
- Galleries — "Permanent record. New revenue line. From $1,500."

**Files:** `src/segments.json`, `src/template.html`.

**Acceptance:** Hub grid renders these exact lines per card.

#### CT-018 — Demote URL deprecation strategy

**Affected:** /clinics, /hosts, /restaurants.

**Symptom:** Demoted pages should not be indexed as primary commercial pages but should still serve organic search traffic.

**Action:** Default behaviour: page serves, no noindex. Pages may receive long-tail organic search traffic. We do not pursue these segments but we accept inbound conversion if it arrives.

A future Phase 2 may decide to noindex or 410 these pages. Not in v4 scope.

**Files:** No changes in v4. Documented for future reference.

---

## Verifier extensions for v4

Extend `scripts/verify.py` from the v3 24-check matrix to a 30-check matrix. New checks:

1. **currency_no_gbp** — assert no `£` or `GBP` substring anywhere in rendered HTML on any page
2. **currency_toggle_propagates** — Playwright clicks the GEL toggle on a Phase 1 page; asserts all visible currency symbols change from `$` to `₾`
3. **pricing_schema_consistent** — extract hub card "From $X" values and segment page anchor line "From $X" values; assert they match per segment
4. **hub_grid_five_cards** — assert hub segment grid contains exactly 5 cards (Developers, Weddings, Hotels, Managers, Galleries)
5. **footer_five_segments** — assert footer "FOR" column on every page contains exactly 5 segment links
6. **demoted_pages_unlinked** — assert no links to /clinics, /hosts, /restaurants from hub navigation, hub grid, or footer on any page

Combined target: **30/30 verifier passing on all 9 pages.**

---

## Out of scope for v4

- Replacing the form CTA backend (mailto: stays — needs a Slack/Resend/Formspark destination decision)
- Real client logos for the Selected credits strip
- Real Tbilisi captures replacing the Spatial Studio sample iframe
- Reframing demoted pages (/clinics, /hosts, /restaurants) with new positioning
- Voice-of-customer interviews (Phase 1 cold-outreach feedback will be the next signal source)
- Cloudflare Web Analytics enable (dashboard toggle, no code)
- Live FX integration (fixed quarterly GEL rate is fine for Phase 1)
- Commercial gallery sub-segment (/galleries focuses on institutional only; commercial-gallery framing is a Phase 2 question)

---

## Acceptance for v4

The v4 PR is accepted when:

1. All 18 defects above (CT-001 through CT-018) are fixed
2. `scripts/verify.py` extended to 30 checks, all passing on all 9 pages
3. Manual paint check confirms `.rd-win` still visible on all 8 segment heroes (v3 regression check)
4. Manual mobile check at 390×844 confirms sticky CTA segment labels, objection block, calculator
5. Hub renders 5 segment cards (not 8). Footer renders 5 segment links (not 8). Demoted pages serve 200 by direct URL.
6. Currency toggle (USD ↔ GEL) propagates to every price on every page
7. No `£` or `GBP` substring anywhere in rendered HTML
8. PR description references this audit doc, lists each CT defect ID with file(s) touched, includes screenshots of the 5 Phase 1 hero/H1, includes the 30-check verifier output

---

## Sequence Codex should work in

1. Read AGENTS.md, `docs/SEGMENT-COPY-V2.md`, `docs/PAIN-MATRIX.md`, this `docs/AUDIT-V4.md`
2. Confirm baseline: `python3 scripts/build.py && python3 scripts/verify.py` passes 24/24
3. Update `src/segments.json` with v4 data (currency config, pricing schema, per-segment field updates, demoted segments flag)
4. Update `src/template.html` for any new structural patterns (pricing-transparency block on /weddings, conditional rendering of demoted segments in hub grid and footer, currency toggle for USD/GEL)
5. Update `scripts/build.py` for demoted-segment filtering (hub grid, footer)
6. Update `public/spaces.css` for any new visual patterns (pricing-transparency block tint, etc.)
7. Apply CT-001 through CT-018 sequentially. Run verify after each cluster.
8. Extend `scripts/verify.py` with the 6 new checks.
9. Run 30/30 verifier.
10. Open PR titled `v4: 5-segment focus, USD/GEL currency, pain-matrix reframes`.
