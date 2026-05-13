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
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup, NavigableString
except ImportError:
    sys.exit("bs4 not installed. Run: pip3 install --user beautifulsoup4")


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PUBLIC = ROOT / "public"

CONFIGS = {}


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


def phase1_segments():
    items = [
        cfg for key, cfg in CONFIGS.items()
        if key != "main" and not key.startswith("_") and not cfg.get("is_hub") and cfg.get("phase") == "phase1"
    ]
    return sorted(items, key=lambda c: c.get("hub_order", 999))


def set_currency_text(tag, text):
    tag.string = text
    tag["data-price-usd"] = text
    tag["data-price-gel"] = text.replace("$1,500", "₾4,050").replace("$3,000+", "₾8,100+").replace("$3,000", "₾8,100").replace("$500", "₾1,350").replace("$129", "₾350").replace("$35", "₾95")


def apply_common_currency_config(soup):
    for label in soup.select(".sx-calc2__addon-price"):
        raw = label.get_text(strip=True).replace("$", "").replace(",", "")
        try:
            usd = int(raw)
        except ValueError:
            continue
        gel = int(round(usd * CONFIGS.get("_currency_config", {}).get("gel_rate", 2.7) / 10) * 10)
        label["data-price-amount"] = str(usd)
        label["data-price-usd"] = f"${usd:,}"
        label["data-price-gel"] = f"₾{gel:,}"
        label.string = f"${usd:,}"


# ──────────────────────────────────────────────────────────────────────
# Hub renderer — minimal changes from template (keeps everything)
# ──────────────────────────────────────────────────────────────────────

def render_hub(cfg, template_html):
    soup = BeautifulSoup(template_html, "html.parser")
    apply_common_currency_config(soup)

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

    render_hub_segment_cards(soup)
    render_footer_segments(soup)
    collapse_about_block(soup)
    rewrite_hub_faq(soup)

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
        cap.string = cfg["demo_caption"]

    # ── Segment accordion: open the configured one (hub only) ─────────
    active_seg = cfg.get("active_segment", "hotel")
    for det in soup.select(".sx-segcard"):
        is_match = det.get("data-seg") == active_seg
        if is_match:
            det["open"] = ""
        elif det.has_attr("open"):
            del det["open"]

    # ── Calculator: active kind on hub (preserves interactive grid) ───
    active_kind = cfg.get("active_kind", "apartment")
    for btn in soup.select("[data-kind]"):
        is_match = btn.get("data-kind") == active_kind
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

    # ── Remove all segment-only elements (objection block, pricing anchor,
    #    segment-only footer "More" column) ─────────────────────────────
    for el in soup.select("[data-segment-only]"):
        el.decompose()
    for el in soup.select("[data-segment-only-footer]"):
        el.decompose()

    # ── Body data attrs for runtime JS ─────────────────────────────────
    body = soup.find("body")
    if body is not None:
        body["data-segment"] = ""
        body["data-active-tour"] = active_tour
        body["data-active-kind"] = active_kind
        body["data-outcomes-filter"] = outcomes_filter

    return str(soup)


def render_hub_segment_cards(soup):
    grid = soup.select_one("#seg-cards")
    if not grid:
        return
    grid.clear()
    for idx, cfg in enumerate(phase1_segments()):
        card = cfg["hub_card"]
        details = soup.new_tag("details", attrs={"class": "sx-segcard", "data-seg": cfg["slug"]})
        if idx == 0:
            details["open"] = ""
        summary = soup.new_tag("summary", attrs={"class": "sx-segcard__head"})
        label = soup.new_tag("span", attrs={"class": "sx-segcard__label"})
        label.string = card["label"]
        mini = soup.new_tag("span", attrs={"class": "sx-segcard__range-mini"})
        set_currency_text(mini, card["range"])
        chev = soup.new_tag("span", attrs={"class": "sx-segcard__chev", "aria-hidden": "true"})
        chev.string = "+"
        summary.extend([label, mini, chev])
        body = soup.new_tag("div", attrs={"class": "sx-segcard__body"})
        pitch = soup.new_tag("h3", attrs={"class": "sx-segcard__pitch"})
        set_currency_text(pitch, card["hook"])
        foot = soup.new_tag("div", attrs={"class": "sx-segcard__foot"})
        link = soup.new_tag("a", attrs={"href": f"/{cfg['slug']}", "class": "rd-btn rd-btn--outline"})
        link.string = card["button"]
        foot.append(link)
        body.extend([pitch, foot])
        details.extend([summary, body])
        grid.append(details)


def render_footer_segments(soup):
    col = soup.select_one("[data-hub-only='footer-segments']")
    if not col:
        return
    ul = col.find("ul")
    if not ul:
        return
    ul.clear()
    for cfg in phase1_segments():
        li = soup.new_tag("li")
        a = soup.new_tag("a", attrs={"href": f"/{cfg['slug']}"})
        a.string = cfg["hub_card"]["label"]
        li.append(a)
        ul.append(li)


def collapse_about_block(soup):
    about = soup.select_one(".sx-about__body")
    if not about:
        return
    about.clear()
    p = soup.new_tag("p")
    p.string = "Spaces is a Rogue Divisions studio. We capture, host, and publish — your relationship is with operators, not a platform."
    about.append(p)


def rewrite_hub_faq(soup):
    for item in soup.select("#faq-list .sx-faq__item"):
        q = item.select_one(".sx-faq__q")
        a = item.select_one(".sx-faq__a")
        if q and a and q.get_text(strip=True) == "Is this as good as Matterport?":
            q.string = "How is this different from Matterport?"
            a.string = "For buyer-decision visualisation, this is sharper and faster. For property workflows that need precise floor plans and measurements, Matterport is stronger. Spaces is built for buyer confidence — faster capture, hosted walkthrough, embedded in your sales channels."


# ──────────────────────────────────────────────────────────────────────
# Segment renderer — heavy DOM transforms
# ──────────────────────────────────────────────────────────────────────

def render_segment(cfg, template_html):
    soup = BeautifulSoup(template_html, "html.parser")
    slug = cfg["slug"]
    apply_common_currency_config(soup)
    render_footer_segments(soup)

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
    nav_cta = soup.select_one(".sx-nav__cta")
    if nav_cta:
        nav_cta.string = cfg.get("sticky_cta_label", cfg["hero_cta_primary"])
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
        if el.get("data-hub-only") == "footer-segments":
            continue
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
    for el in soup.select(".sx-multi-wrap"):
        el.decompose()
    about_body = soup.select_one(".sx-about")
    if about_body:
        section = about_body.find_parent("section")
        if section:
            section.decompose()

    # ── Inject objection block content ─────────────────────────────────
    obj_quote = soup.select_one("[data-objection-quote]")
    obj_reply = soup.select_one("[data-objection-reply]")
    if obj_quote and obj_reply:
        obj_quote.string = cfg["objection"]["quote"]
        obj_reply.string = cfg["objection"]["reply"]
    # Strip the data-segment-only marker from the objection section so it stays in the DOM
    obj_section = soup.select_one(".sx-objection[data-segment-only]")
    if obj_section:
        del obj_section["data-segment-only"]

    # ── Pricing anchor line ────────────────────────────────────────────
    anchor = soup.select_one(".sx-pricing-anchor[data-segment-only]")
    if anchor:
        set_currency_text(anchor, cfg["pricing_anchor"])
        del anchor["data-segment-only"]

    transparency = soup.select_one("[data-pricing-transparency]")
    if transparency:
        if cfg.get("pricing_transparency"):
            set_currency_text(transparency, cfg["pricing_transparency"])
            del transparency["data-segment-only"]
        else:
            section = transparency.find_parent(class_="sx-pricing-transparency")
            if section:
                section.decompose()

    # ── Calculator Step 01: replace 8-button grid with locked indicator
    calc = cfg["calculator"]
    step1_block = soup.select_one("[data-step-id='kind']")
    if step1_block:
        # Title rewrite: "What kind of space is it?" → "For [segment label]"
        step1_title = step1_block.select_one("[data-step1-title]")
        if step1_title:
            step1_title.string = f"For {calc['step1_kind_label'].lower()}."
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
    step3_title = soup.select_one("[data-step3-title]")
    if step3_title and calc.get("step3_active") and calc.get("step3_label"):
        step3_title.string = calc["step3_label"]
    step3_hint = soup.select_one("[data-step3-hint]")
    if step3_hint and calc.get("step3_active") and calc.get("step3_hint"):
        step3_hint.string = calc["step3_hint"]
    calc_h2 = soup.select_one("[data-calculator-h2]")
    if calc_h2 and cfg.get("calculator_h2"):
        calc_h2.string = cfg["calculator_h2"]

    # ── FAQ: replace omnibus with per-segment 5 items ──────────────────
    faq_list = soup.select_one("#faq-list")
    if faq_list:
        faq_list.clear()
        for i, item in enumerate(cfg["faq"]):
            wrap = soup.new_tag("div", attrs={"class": "sx-faq__item" + (" is-open" if i < 2 else "")})
            q_btn = soup.new_tag("button", attrs={"class": "sx-faq__q"})
            q_btn.string = item["q"]
            a_div = soup.new_tag("div", attrs={"class": "sx-faq__a"})
            a_div.string = item["a"]
            wrap.append(q_btn)
            wrap.append(a_div)
            faq_list.append(wrap)

    # ── Final CTA ──────────────────────────────────────────────────────
    cta_h2 = soup.select_one("[data-final-cta-h2]")
    if cta_h2:
        cta_h2.string = cfg["final_cta"]["h2"]
    cta_body = soup.select_one("[data-final-cta-body]")
    if cta_body:
        cta_body.string = cfg["final_cta"]["body"]
    for selector, key in ((".sx-final__cta .rd-btn--filled", "button_primary"), (".sx-final__cta .rd-btn--outline", "button_secondary")):
        btn = soup.select_one(selector)
        if btn and cfg["final_cta"].get(key):
            btn.string = cfg["final_cta"][key].rstrip(" →").rstrip()
    sticky = soup.select_one(".sx-sticky-cta")
    if sticky:
        sticky.string = cfg.get("sticky_cta_label", cfg["hero_cta_primary"])
        sticky["aria-label"] = cfg.get("sticky_cta_label", cfg["hero_cta_primary"])

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
        "currency": CONFIGS.get("_currency_config", {}),
    }
    if calc.get("pricing_mode") == "subscription":
        sx_cfg["subscriptionRate"] = calc.get("subscription_rate_per_door")
        sx_cfg["subscriptionUnitLabel"] = calc.get("subscription_unit_label", "per door / month")

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
        a.string = "Segments"

    for el in soup.select("[data-segment-only-footer]"):
        el.decompose()

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
    global CONFIGS
    CONFIGS = configs

    if "main" not in configs:
        sys.exit("segments.json must include a 'main' entry")

    # Hub
    hub_html = render_hub(configs["main"], template_html)
    (PUBLIC / "index.html").write_text(hub_html, encoding="utf-8")
    print(f"  ✓ public/index.html  ({len(hub_html):,} bytes)  [hub]")

    # Segments
    for slug, cfg in configs.items():
        if slug == "main" or slug.startswith("_"):
            continue
        if cfg.get("is_hub"):
            continue
        out_dir = PUBLIC / cfg["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        page_html = render_segment(cfg, template_html)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")
        print(f"  ✓ public/{cfg['slug']}/index.html  ({len(page_html):,} bytes)  [segment]")


if __name__ == "__main__":
    print("Building Spaces pages...")
    main()
    print("Done.")
