#!/usr/bin/env python3
"""
Spaces — per-segment page generator (v2).

Reads `src/segments.json` and `src/template.html`, emits 9 HTML files into `public/`:
one hub at index.html and eight ICP-specific pages (managers, hosts, hotels, developers,
weddings, clinics, restaurants, galleries).

Per the v2 brief (Rebuild as real ICP pages, not hub variants), segment pages differ from
the hub in much more than is-active class swaps. They REMOVE the omnibus segment grid,
the outcomes filter, and the "Built for spaces" H2. They INJECT segment-specific
outcomes, an objection block, a pricing anchor line, segment-tuned FAQ, demo caption,
hero CTAs, and calculator configuration.

Source-of-truth copy lives in `/Users/sage/LOCAL/RD/RD-SPACES/Collateral/03 EXTERNAL Per-Segment Page Copy.md`.
Do not invent strings — every customer-facing text MUST come from segments.json.

Run from repo root:  python3 scripts/build.py
"""

from __future__ import annotations
import json
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup, NavigableString
except ImportError:
    sys.exit("bs4 not installed. Run: pip3 install --user beautifulsoup4")


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PUBLIC = ROOT / "public"


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def set_text(soup, selector_dict, text):
    """Find element by selector dict (e.g. {"property": "og:title"}) and set content/text."""
    el = soup.find(attrs=selector_dict)
    if el is None:
        return
    if "content" in el.attrs:
        el["content"] = text
    else:
        el.string = text


def set_attr(soup, selector_dict, attr, value):
    el = soup.find(attrs=selector_dict)
    if el is not None:
        el[attr] = value


def replace_string(el, new_text):
    """Wipe element's children and set its visible text."""
    if el is None:
        return
    el.clear()
    el.append(new_text)


def fill_currency_text(soup, el, text):
    """Render text, wrapping USD amounts so the runtime currency toggle can update them.

    v4: text is authored in USD ($X). Every $-amount becomes a
    <span data-money-usd="N" data-money-suffix="+?">$N</span> wrapper that the
    runtime JS rewrites when the user clicks the GEL toggle.
    """
    if el is None:
        return
    el.clear()
    cursor = 0
    for match in re.finditer(r"\$([0-9][0-9,]*)(\+?)", text):
        if match.start() > cursor:
            el.append(text[cursor:match.start()])
        amount = int(match.group(1).replace(",", ""))
        suffix = match.group(2)
        price = soup.new_tag(
            "span",
            attrs={"data-money-usd": str(amount), "data-money-suffix": suffix},
        )
        price.string = match.group(0)
        el.append(price)
        cursor = match.end()
    if cursor < len(text):
        el.append(text[cursor:])


def step1_sentence_label(label):
    """Lowercase a kind label for the Step 01 'For <label>.' heading, preserving acronyms.

    v4.1: closes a bug where "STR property managers" was being .lower()-ed into "str ...",
    breaking the acronym. Now: all-uppercase words of length >= 2 are kept as-is, others
    are lowercased. Also defensively strips a leading "For " if an author left it in
    segments.json (which produced the doubled "For for str ..." in v4 live).
    """
    label = re.sub(r"^[Ff]or\s+", "", label).strip()
    out = []
    for w in label.split():
        if w.isupper() and len(w) >= 2:
            out.append(w)  # acronym — STR, OTA, ICP, etc.
        else:
            out.append(w.lower())
    return " ".join(out)


def renumber_calculator_steps(soup, modules_active):
    """Keep visible calculator step numbers sequential after optional steps are hidden."""
    visible_steps = []
    for step in soup.select(".sx-calc2__step"):
        step_id = step.get("data-step-id")
        if step_id == "modules" and not modules_active:
            step["hidden"] = ""
            continue
        visible_steps.append(step)
    for i, step in enumerate(visible_steps, start=1):
        num = step.select_one(".sx-calc2__step-num")
        if num:
            num.string = f"{i:02d}"


# ──────────────────────────────────────────────────────────────────────
# v4 helpers
# ──────────────────────────────────────────────────────────────────────

def phase1_segments(configs):
    """Return [(slug, cfg)] for Phase 1 segments, sorted by phase1_order."""
    out = []
    for slug, cfg in configs.items():
        if slug == "main" or slug.startswith("_") or not isinstance(cfg, dict):
            continue
        if cfg.get("phase") == "phase1":
            out.append((slug, cfg))
    out.sort(key=lambda x: x[1].get("phase1_order", 99))
    return out


def fill_footer_segments(soup, p1):
    """Populate the Phase 1 footer 'For' column on EVERY page.

    Per v4 CT-002: footer 'FOR' column shows the 5 Phase 1 segments only.
    Demoted segments (clinics, hosts, restaurants) are never linked here.
    """
    ul = soup.select_one("[data-footer-segments]")
    if ul is None:
        return
    ul.clear()
    for slug, cfg in p1:
        li = soup.new_tag("li")
        a = soup.new_tag("a", attrs={"href": f"/{cfg['slug']}"})
        # Footer uses short labels; pull from hub_card.label, trimmed.
        label = cfg.get("hub_card", {}).get("label", cfg["slug"].title())
        # The footer is tight; shorten "Galleries and cultural venues" to "Cultural venues" etc.
        # We use the segment's natural footer label if present, else label as-is.
        a.string = cfg.get("footer_label", label)
        li.append(a)
        ul.append(li)


def render_hub_grid(soup, p1):
    """Generate the Phase 1 segment grid for the hub.

    Replaces the placeholder <div data-segments-grid-placeholder> with one
    <details class="sx-segcard"> per Phase 1 segment, using the segment's
    hub_card { label, hook, price_anchor } payload from segments.json.
    """
    placeholder = soup.select_one("[data-segments-grid-placeholder]")
    if placeholder is None:
        return
    for i, (slug, cfg) in enumerate(p1):
        card = cfg.get("hub_card", {})
        det = soup.new_tag(
            "details",
            attrs={"class": "sx-segcard", "data-seg": slug, **({"open": ""} if i == 0 else {})},
        )
        summary = soup.new_tag("summary", attrs={"class": "sx-segcard__head"})
        label_span = soup.new_tag("span", attrs={"class": "sx-segcard__label"})
        label_span.string = card.get("label", slug.title())
        price_span = soup.new_tag("span", attrs={"class": "sx-segcard__range-mini"})
        # Price is plain text on the hub card (no money wrappers — the segment-page
        # anchor below the hero is the runtime-toggleable rendering).
        price_span.string = card.get("price_anchor", "")
        chev = soup.new_tag("span", attrs={"class": "sx-segcard__chev", "aria-hidden": "true"})
        chev.string = "+"
        summary.append(label_span)
        summary.append(price_span)
        summary.append(chev)
        body = soup.new_tag("div", attrs={"class": "sx-segcard__body"})
        pitch = soup.new_tag("h3", attrs={"class": "sx-segcard__pitch"})
        pitch.string = card.get("hook", "")
        body.append(pitch)
        # Each card has a "More for X →" outline link to its segment page.
        foot = soup.new_tag("div", attrs={"class": "sx-segcard__foot"})
        more = soup.new_tag(
            "a",
            attrs={"href": f"/{cfg['slug']}", "class": "rd-btn rd-btn--outline"},
        )
        more.string = f"More for {card.get('label','').lower()} →"
        foot.append(more)
        body.append(foot)
        det.append(summary)
        det.append(body)
        placeholder.append(det)
    # Clear the placeholder marker (cards are now its children).
    del placeholder["data-segments-grid-placeholder"]


def inject_currency_config(soup, currency_config):
    """Inject window.__SX_CURRENCY__ before the calc IIFE for runtime FX state."""
    if not currency_config:
        return
    # Find a <script data-sx-cfg> or fall back to creating a new script tag in <head>.
    cfg_script = soup.select_one("[data-sx-cfg]")
    payload = (
        f"window.__SX_CURRENCY__ = {json.dumps(currency_config, ensure_ascii=False)};\n"
    )
    if cfg_script and cfg_script.string:
        # Append to the existing payload so __SX_CURRENCY__ is set BEFORE __SX_CFG__.
        cfg_script.string = payload + cfg_script.string
    elif cfg_script:
        cfg_script.string = payload


# ──────────────────────────────────────────────────────────────────────
# Hub renderer — minimal changes from template (keeps everything)
# ──────────────────────────────────────────────────────────────────────

def render_hub(cfg, template_html, currency_config=None, all_configs=None):
    soup = BeautifulSoup(template_html, "html.parser")

    # ── Head ───────────────────────────────────────────────────────────
    soup.find("title").string = cfg["title"]
    set_attr(soup, {"name": "description"}, "content", cfg["description"])
    set_attr(soup, {"rel": "canonical"}, "href", cfg["url"])
    set_attr(soup, {"property": "og:url"}, "content", cfg["url"])
    set_attr(soup, {"property": "og:title"}, "content", cfg.get("og_title", cfg["title"]))
    set_attr(soup, {"property": "og:description"}, "content", cfg.get("og_description", cfg["description"]))
    set_attr(soup, {"name": "twitter:title"}, "content", cfg.get("og_title", cfg["title"]))
    set_attr(soup, {"name": "twitter:description"}, "content", cfg.get("og_description", cfg["description"]))

    # ── Hero ───────────────────────────────────────────────────────────
    h1 = soup.select_one(".sx-hero__h1")
    if h1:
        h1.clear()
        h1.append(cfg["h1_line1"])
        if cfg.get("h1_mark"):
            h1.append(soup.new_tag("br"))
            mark = soup.new_tag("span", attrs={"class": "rd-win"})
            mark.string = cfg["h1_mark"]
            h1.append(mark)
            if cfg.get("h1_line2"):
                h1.append(" ")
                h1.append(cfg["h1_line2"])

    sub = soup.select_one(".sx-hero__sub")
    if sub:
        sub.string = cfg["subhead"]

    # ── Hero CTAs ──────────────────────────────────────────────────────
    primary = soup.select_one("[data-hero-cta-primary]")
    if primary and cfg.get("hero_cta_primary"):
        primary.string = cfg["hero_cta_primary"]
    secondary = soup.select_one("[data-hero-cta-secondary]")
    if secondary and cfg.get("hero_cta_secondary"):
        # Secondary CTA contains a child span (arrow). Preserve structure but swap text.
        secondary.clear()
        # Strip trailing arrow from copy if present
        label = cfg["hero_cta_secondary"].rstrip(" →").rstrip()
        secondary.append(label + " ")
        arrow = soup.new_tag("span", attrs={"class": "arrow"})
        arrow.string = "➜"
        secondary.append(arrow)

    # ── Demo: active iframe + pill ─────────────────────────────────────
    active_tour = cfg.get("active_tour", "rest")
    for btn in soup.select(".sx-demo__pill"):
        is_match = btn.get("data-tour") == active_tour
        classes = [c for c in btn.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
        btn["class"] = classes
        btn["aria-selected"] = "true" if is_match else "false"

    for iframe in soup.select(".sx-demo__frame"):
        is_match = iframe.get("data-tour") == active_tour
        url = iframe.get("src") or iframe.get("data-deferred-src")
        classes = [c for c in iframe.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
            iframe["src"] = url
            for k in ("data-deferred-src", "aria-hidden"):
                if iframe.has_attr(k):
                    del iframe[k]
        else:
            iframe["data-deferred-src"] = url
            if iframe.has_attr("src"):
                del iframe["src"]
            iframe["aria-hidden"] = "true"
        iframe["class"] = classes

    # ── Demo caption ───────────────────────────────────────────────────
    cap = soup.select_one("[data-demo-caption]")
    if cap and cfg.get("demo_caption"):
        if " · " in cfg["demo_caption"]:
            title, rest = cfg["demo_caption"].split(" · ", 1)
            cap.clear()
            title_span = soup.new_tag("span", attrs={"data-tour-title": ""})
            title_span.string = title
            cap.append(title_span)
            cap.append(" · " + rest)
        else:
            fill_currency_text(soup, cap, cfg["demo_caption"])

    # ── Hub segment grid: populate from Phase 1 segments (CT-001, CT-017) ────
    if all_configs:
        p1 = phase1_segments(all_configs)
        render_hub_grid(soup, p1)
        # Footer 'For' column: same 5 segments (CT-002).
        fill_footer_segments(soup, p1)
        # Active segment accordion: open the configured one if it's a phase1 slug.
        active_seg = cfg.get("active_segment")
        for det in soup.select("#seg-cards .sx-segcard"):
            is_match = det.get("data-seg") == active_seg
            if is_match:
                det["open"] = ""
            elif det.has_attr("open") and active_seg:
                # Only override the default-open card if active_seg names a phase1 segment.
                del det["open"]

    # ── Calculator: active kind on hub (preserves interactive grid) ───
    # v4.1: hub default is no pre-selection (active_kind=null in segments.json).
    # Setting active_kind=null means no [data-kind] button gets is-active on first load,
    # and the JS sees window.__SX_CFG__.kind===null and shows "Pick a kind of space to continue."
    active_kind = cfg.get("active_kind")  # may be None (hub) or a kind id (legacy)
    for btn in soup.select("[data-kind]"):
        is_match = active_kind is not None and btn.get("data-kind") == active_kind
        classes = [c for c in btn.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
        btn["class"] = classes

    # ── Outcomes filter (hub keeps full set) ──────────────────────────
    outcomes_filter = cfg.get("outcomes_filter", "all")
    for btn in soup.select(".sx-filter__btn"):
        is_match = btn.get("data-filter") == outcomes_filter
        classes = [c for c in btn.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
        btn["class"] = classes

    # ── Hub Matterport FAQ rewrite (CT-009) ───────────────────────────
    matterport = soup.select_one("[data-matterport-answer]")
    if matterport and cfg.get("matterport_faq_answer"):
        matterport.string = cfg["matterport_faq_answer"]

    # ── Hub About-RD one-liner (CT-010) ───────────────────────────────
    about_oneliner = soup.select_one("[data-about-rd-body] .sx-about__oneliner")
    if about_oneliner and cfg.get("about_rd_oneliner"):
        about_oneliner.clear()
        about_oneliner.append(cfg["about_rd_oneliner"] + " ")
        a = soup.new_tag("a", attrs={"href": "https://roguedivisions.com", "class": "rd-link-arrow"})
        a.append("About Rogue Divisions ")
        arrow = soup.new_tag("span", attrs={"class": "arrow"})
        arrow.string = "→"
        a.append(arrow)
        about_oneliner.append(a)

    # ── Remove all segment-only elements (objection, pricing anchor,
    #    wedding pricing transparency, segment-only footer column) ────
    for el in soup.select("[data-segment-only]"):
        el.decompose()
    for el in soup.select("[data-pricing-transparency-only]"):
        el.decompose()
    for el in soup.select("[data-segment-only-footer]"):
        el.decompose()

    # ── Currency injection (CT-004) ───────────────────────────────────
    inject_currency_config(soup, currency_config)

    # ── Hub calc CFG: v4.1 UX-1. Inject window.__SX_CFG__ = {kind: null} so the calc IIFE
    #    knows the hub has no pre-selected kind and renders the "Pick a kind of space to
    #    continue." placeholder instead of pre-populating Step 02 size options.
    cfg_script = soup.select_one("[data-sx-cfg]")
    if cfg_script:
        hub_cfg_payload = f"window.__SX_CFG__ = {json.dumps({'kind': active_kind}, ensure_ascii=False)};"
        existing = cfg_script.string or ""
        cfg_script.string = existing + ("\n" if existing else "") + hub_cfg_payload

    # ── Body data attrs for runtime JS ─────────────────────────────────
    body = soup.find("body")
    if body is not None:
        body["data-segment"] = ""
        body["data-active-tour"] = active_tour
        body["data-active-kind"] = active_kind if active_kind else ""
        body["data-outcomes-filter"] = outcomes_filter

    return str(soup)


# ──────────────────────────────────────────────────────────────────────
# Segment renderer — heavy DOM transforms
# ──────────────────────────────────────────────────────────────────────

def render_segment(cfg, template_html, currency_config=None, all_configs=None):
    soup = BeautifulSoup(template_html, "html.parser")
    slug = cfg["slug"]

    # ── Head ───────────────────────────────────────────────────────────
    soup.find("title").string = cfg["title"]
    set_attr(soup, {"name": "description"}, "content", cfg["description"])
    set_attr(soup, {"rel": "canonical"}, "href", cfg["url"])
    set_attr(soup, {"property": "og:url"}, "content", cfg["url"])
    set_attr(soup, {"property": "og:title"}, "content", cfg["og_title"])
    set_attr(soup, {"property": "og:description"}, "content", cfg["og_description"])
    set_attr(soup, {"name": "twitter:title"}, "content", cfg["og_title"])
    set_attr(soup, {"name": "twitter:description"}, "content", cfg["og_description"])

    # ── Hero ───────────────────────────────────────────────────────────
    h1 = soup.select_one(".sx-hero__h1")
    if h1:
        h1.clear()
        h1.append(cfg["h1_line1"])
        if cfg.get("h1_mark"):
            h1.append(soup.new_tag("br"))
            mark = soup.new_tag("span", attrs={"class": "rd-win"})
            mark.string = cfg["h1_mark"]
            h1.append(mark)
            if cfg.get("h1_line2"):
                h1.append(" ")
                h1.append(cfg["h1_line2"])

    sub = soup.select_one(".sx-hero__sub")
    if sub:
        sub.string = cfg["subhead"]

    # ── Hero CTAs ──────────────────────────────────────────────────────
    primary = soup.select_one("[data-hero-cta-primary]")
    if primary:
        primary.string = cfg["hero_cta_primary"]
    secondary = soup.select_one("[data-hero-cta-secondary]")
    if secondary:
        secondary.clear()
        label = cfg["hero_cta_secondary"].rstrip(" →").rstrip()
        secondary.append(label + " ")
        arrow = soup.new_tag("span", attrs={"class": "arrow"})
        arrow.string = "➜"
        secondary.append(arrow)

    # ── Demo: active iframe + pill ─────────────────────────────────────
    active_tour = cfg.get("active_tour", "rest")
    for btn in soup.select(".sx-demo__pill"):
        is_match = btn.get("data-tour") == active_tour
        classes = [c for c in btn.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
        btn["class"] = classes
        btn["aria-selected"] = "true" if is_match else "false"

    for iframe in soup.select(".sx-demo__frame"):
        is_match = iframe.get("data-tour") == active_tour
        url = iframe.get("src") or iframe.get("data-deferred-src")
        classes = [c for c in iframe.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
            iframe["src"] = url
            for k in ("data-deferred-src", "aria-hidden"):
                if iframe.has_attr(k):
                    del iframe[k]
        else:
            iframe["data-deferred-src"] = url
            if iframe.has_attr("src"):
                del iframe["src"]
            iframe["aria-hidden"] = "true"
        iframe["class"] = classes

    # ── Demo caption (per-segment) ─────────────────────────────────────
    cap = soup.select_one("[data-demo-caption]")
    if cap:
        cap.clear()
        cap.append(cfg["demo_caption"])  # no need for inner span on segment pages

    # ── Outcomes: replace ALL cards with per-segment 3-4 cards ─────────
    outcomes_list = soup.select_one("#outcomes-list")
    if outcomes_list:
        outcomes_list.clear()
        for outcome in cfg["outcomes"]:
            article = soup.new_tag("article", attrs={"class": "sx-outcome"})
            h3 = soup.new_tag("h3", attrs={"class": "sx-outcome__title"})
            h3.string = outcome["title"]
            p = soup.new_tag("p", attrs={"class": "sx-outcome__body"})
            p.string = outcome["body"]
            article.append(h3)
            article.append(p)
            outcomes_list.append(article)

    # ── REMOVE filter chip strip (outcomes are pre-curated) ────────────
    # ── REMOVE omnibus segments grid section ──────────────────────────
    # Also remove the explanatory HTML comment that immediately precedes each
    # data-hub-only block — otherwise the comment text ("Built for spaces.") leaks
    # into the static markup of segment pages and trips literal-string verification.
    for el in soup.select("[data-hub-only]"):
        # Walk back through preceding siblings, eating any comments / whitespace nodes.
        prev = el.previous_sibling
        while prev is not None and (
            (isinstance(prev, NavigableString) and not prev.strip())
            or (prev.__class__.__name__ == "Comment")
        ):
            to_remove = prev
            prev = prev.previous_sibling
            to_remove.extract()
        el.decompose()

    # ── Inject objection block content ─────────────────────────────────
    obj_quote = soup.select_one("[data-objection-quote]")
    obj_reply = soup.select_one("[data-objection-reply]")
    if obj_quote and obj_reply:
        obj_quote.string = cfg["objection"]["quote"]
        fill_currency_text(soup, obj_reply, cfg["objection"]["reply"])
    # Strip the data-segment-only marker from the objection section so it stays in the DOM
    obj_section = soup.select_one(".sx-objection[data-segment-only]")
    if obj_section:
        del obj_section["data-segment-only"]

    # ── Process steps: use per-segment steps when authored, otherwise keep hub default.
    if cfg.get("process_steps"):
        for step_el, step_cfg in zip(soup.select(".sx-how .sx-step"), cfg["process_steps"]):
            title = step_el.select_one(".sx-step__title")
            body = step_el.select_one(".sx-step__body")
            if title:
                title.string = step_cfg["title"]
            if body:
                fill_currency_text(soup, body, step_cfg["body"])

    # ── Pricing anchor line ────────────────────────────────────────────
    anchor = soup.select_one(".sx-pricing-anchor[data-segment-only]")
    if anchor:
        fill_currency_text(soup, anchor, cfg["pricing_anchor"])
        del anchor["data-segment-only"]

    # ── Pricing transparency block (CT-012; only segments that author one) ─
    pt_block = soup.select_one("[data-pricing-transparency-only]")
    pt_body = soup.select_one("[data-pricing-transparency-body]")
    pt_text = cfg.get("pricing_transparency")
    if pt_block:
        if pt_text and pt_body:
            fill_currency_text(soup, pt_body, pt_text)
            del pt_block["data-pricing-transparency-only"]
        else:
            pt_block.decompose()

    # ── Calculator H2 per segment (CT-015) ─────────────────────────────
    calc_h2 = soup.select_one("[data-calc-h2]")
    if calc_h2 and cfg.get("calculator", {}).get("h2"):
        calc_h2.string = cfg["calculator"]["h2"]

    # ── Calculator Step 01: replace 8-button grid with locked indicator
    calc = cfg["calculator"]
    step1_block = soup.select_one("[data-step-id='kind']")
    if step1_block:
        # Title rewrite: "What kind of space is it?" → "For [segment label]."
        # Use acronym-preserving lowercaser so "STR property managers" doesn't become "str ...".
        step1_title = step1_block.select_one("[data-step1-title]")
        if step1_title:
            step1_title.string = f"For {step1_sentence_label(calc['step1_kind_label'])}."
        # Replace the grid with a locked indicator
        grid = step1_block.select_one(".sx-calc2__grid--kinds")
        if grid:
            locked = soup.new_tag("div", attrs={"class": "sx-calc2__locked-kind"})
            name = soup.new_tag("span", attrs={"class": "sx-calc2__locked-kind-name"})
            name.string = calc["step1_kind_label"]
            sub_el = soup.new_tag("span", attrs={"class": "sx-calc2__locked-kind-sub"})
            sub_el.string = calc["step1_kind_sub"]
            locked.append(name)
            locked.append(sub_el)
            grid.replace_with(locked)

    # ── Calculator Step 02: label override ─────────────────────────────
    step2_title = soup.select_one("[data-step2-title]")
    if step2_title and calc.get("step2_label"):
        step2_title.string = calc["step2_label"]

    # ── FAQ: replace omnibus with per-segment 5 items ──────────────────
    faq_list = soup.select_one("#faq-list")
    if faq_list:
        faq_list.clear()
        for i, item in enumerate(cfg["faq"]):
            wrap = soup.new_tag("div", attrs={"class": "sx-faq__item" + (" is-open" if i < 2 else "")})
            q_btn = soup.new_tag("button", attrs={"class": "sx-faq__q"})
            q_btn.string = item["q"]
            a_div = soup.new_tag("div", attrs={"class": "sx-faq__a"})
            fill_currency_text(soup, a_div, item["a"])
            wrap.append(q_btn)
            wrap.append(a_div)
            faq_list.append(wrap)

    # ── Final CTA ──────────────────────────────────────────────────────
    cta_h2 = soup.select_one("[data-final-cta-h2]")
    if cta_h2:
        cta_h2.string = cfg["final_cta"]["h2"]
    cta_body = soup.select_one("[data-final-cta-body]")
    if cta_body:
        fill_currency_text(soup, cta_body, cfg["final_cta"]["body"])

    # ── Inject window.__SX_CFG__ for the calculator JS ─────────────────
    # Build the kindOverride object that the calc IIFE merges into KIND_MAP.
    kind_override = {
        "label": calc["step1_kind_label"],
        "sizes": calc["step2_options"],
    }
    if calc.get("step3_active") and calc.get("step3_label"):
        kind_override["modLabel"] = calc["step3_label"]
        kind_override["modHint"] = calc.get("step3_hint", "")
    sx_cfg = {
        "kind": cfg["active_kind"],
        "kindOverride": kind_override,
        "modulesActive": bool(calc.get("step3_active", False)),
        "pricingMode": calc.get("pricing_mode", "one-off"),
    }
    if calc.get("pricing_mode") == "subscription":
        sx_cfg["subscriptionRate"] = calc.get("subscription_rate_per_door")
        sx_cfg["subscriptionUnitLabel"] = calc.get("subscription_unit_label", "per door / month")
        sx_cfg["oneOffLabel"] = calc.get("onboarding_label", "One-off capture fee")

    renumber_calculator_steps(soup, bool(calc.get("step3_active", False)))

    cfg_script = soup.select_one("[data-sx-cfg]")
    if cfg_script:
        cfg_script.string = f"window.__SX_CFG__ = {json.dumps(sx_cfg, ensure_ascii=False)};"

    # ── Body data attrs for runtime JS ─────────────────────────────────
    body = soup.find("body")
    if body is not None:
        body["data-segment"] = slug
        body["data-active-tour"] = active_tour
        body["data-active-kind"] = cfg["active_kind"]
        body["data-pricing-mode"] = calc.get("pricing_mode", "one-off")

    # ── Nav: rewrite anchor links so they fall back to hub for sections we removed
    #    "Who it's for" pointed at #segments which now doesn't exist on segment pages.
    for a in soup.select(".sx-nav__list a[href='#segments']"):
        a["href"] = "/"
        a.string = "All segments"

    # ── Final CTA buttons and sticky mobile CTA ────────────────────────
    final_cta = cfg.get("final_cta", {})
    final_primary = soup.select_one("[data-final-cta-primary]")
    if final_primary:
        final_primary.string = final_cta.get("button_primary", cfg["hero_cta_primary"])
    final_secondary = soup.select_one("[data-final-cta-secondary]")
    if final_secondary:
        final_secondary.string = final_cta.get("button_secondary", cfg["hero_cta_secondary"])
        final_secondary["href"] = "#demo"
    sticky = soup.select_one(".sx-sticky-cta")
    if sticky:
        sticky_label = cfg.get("sticky_cta_label", cfg["hero_cta_primary"])
        sticky.string = sticky_label
        sticky["aria-label"] = sticky_label

    # ── Footer 'For' column: same 5 Phase 1 segments on every page (CT-002) ──
    if all_configs:
        p1 = phase1_segments(all_configs)
        fill_footer_segments(soup, p1)

    # ── Currency injection (CT-004) ───────────────────────────────────
    inject_currency_config(soup, currency_config)

    return str(soup)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    template_path = SRC / "template.html"
    config_path = SRC / "segments.json"

    if not template_path.exists():
        sys.exit(f"Missing template: {template_path}")
    if not config_path.exists():
        sys.exit(f"Missing config: {config_path}")

    template_html = template_path.read_text(encoding="utf-8")
    configs = json.loads(config_path.read_text(encoding="utf-8"))

    if "main" not in configs:
        sys.exit("segments.json must include a 'main' entry")

    # v4: top-level currency_config drives the runtime FX state on every page.
    currency_config = configs.get("currency_config")
    if currency_config is None:
        sys.exit("segments.json must include a top-level 'currency_config' entry (v4).")

    # Hub
    hub_html = render_hub(configs["main"], template_html,
                         currency_config=currency_config, all_configs=configs)
    (PUBLIC / "index.html").write_text(hub_html, encoding="utf-8")
    print(f"  ✓ public/index.html  ({len(hub_html):,} bytes)  [hub]")

    # Segments
    for slug, cfg in configs.items():
        if slug == "main" or slug.startswith("_") or slug == "currency_config":
            continue
        if not isinstance(cfg, dict) or cfg.get("is_hub"):
            continue
        out_dir = PUBLIC / cfg["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        page_html = render_segment(cfg, template_html,
                                   currency_config=currency_config, all_configs=configs)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")
        phase = cfg.get("phase", "?")
        print(f"  ✓ public/{cfg['slug']}/index.html  ({len(page_html):,} bytes)  [{phase}]")


if __name__ == "__main__":
    print("Building Spaces pages...")
    main()
    print("Done.")
