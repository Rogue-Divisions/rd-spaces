#!/usr/bin/env python3
"""Verify generated Spaces pages against the v4 30-check matrix."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Comment

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SRC = ROOT / "src"

PHASE1 = ["developers", "weddings", "hotels", "managers", "galleries"]
DEMOTED = ["clinics", "hosts", "restaurants"]

CHECKS = [
    "h1_matches",
    "subhead_matches",
    "hero_win_visible_markup",
    "segments_grid_removed",
    "filter_strip_removed",
    "built_for_spaces_removed",
    "multi_property_removed",
    "about_block_removed",
    "outcomes_correct",
    "objection_present",
    "pricing_anchor_present",
    "calc_h2_correct",
    "calc_step1_correct",
    "calc_step2_label_correct",
    "calc_step2_options_correct",
    "calc_step3_correct",
    "faq_5_items_correct",
    "demo_caption_correct",
    "final_cta_correct",
    "cta_labels_coherent",
    "sticky_cta_correct",
    "title_meta_correct",
    "no_cross_segment_below_hero",
    "weddings_pricing_transparency",
    "currency_no_gbp",
    "currency_toggle_propagates",
    "pricing_schema_consistent",
    "hub_grid_five_cards",
    "footer_five_segments",
    "demoted_pages_unlinked",
]


def load_configs():
    return json.loads((SRC / "segments.json").read_text(encoding="utf-8"))


def page_path(cfg):
    return PUBLIC / cfg["slug"] / "index.html"


def soup_for(path):
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def visible_text(soup):
    clone = BeautifulSoup(str(soup), "html.parser")
    for s in clone(["script", "style"]):
        s.decompose()
    for c in clone.find_all(string=lambda text: isinstance(text, Comment)):
        c.extract()
    return clone.get_text(" ", strip=True)


def h1_text(soup):
    h1 = soup.select_one(".sx-hero__h1")
    return h1.get_text(" ", strip=True) if h1 else ""


def expected_h1(cfg):
    return " ".join(p for p in [cfg["h1_line1"], cfg.get("h1_mark"), cfg.get("h1_line2")] if p).strip()


def body_text_below_hero(soup):
    clone = BeautifulSoup(str(soup), "html.parser")
    for s in clone(["script", "style"]):
        s.decompose()
    for c in clone.find_all(string=lambda text: isinstance(text, Comment)):
        c.extract()
    hero = clone.select_one(".sx-hero")
    if not hero:
        return clone.get_text(" ", strip=True)
    chunks = []
    el = hero.next_sibling
    while el is not None:
        if hasattr(el, "get_text"):
            chunks.append(el.get_text(" ", strip=True))
        el = el.next_sibling
    return " ".join(chunks)


def html_pages(configs):
    pages = {"hub": PUBLIC / "index.html"}
    for slug, cfg in configs.items():
        if slug != "main" and not slug.startswith("_") and not cfg.get("is_hub"):
            pages[slug] = page_path(cfg)
    return pages


def price_token(text):
    m = re.search(r"From\s+\$[\d,]+(?:\+)?(?: per door per month| per suite)?", text)
    return m.group(0) if m else ""


def run_playwright_currency_check():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False, "playwright import failed"
    target = (PUBLIC / "weddings" / "index.html").resolve().as_uri()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(target, wait_until="load")
            page.locator("[data-cur='USD']").click()
            usd_prices = page.locator("[data-price-usd], .sx-calc2__opt-price, [data-total]").all_inner_texts()
            page.locator("[data-cur='GEL']").click()
            gel_prices = page.locator("[data-price-usd], .sx-calc2__opt-price, [data-total]").all_inner_texts()
            browser.close()
        usd_blob = " ".join(usd_prices)
        gel_blob = " ".join(gel_prices)
        return ("$" in usd_blob and "₾" not in usd_blob and "₾" in gel_blob and "$" not in gel_blob), ""
    except Exception as exc:
        return False, str(exc)


def global_results(configs):
    results = {}
    pages = html_pages(configs)
    soups = {slug: soup_for(path) for slug, path in pages.items()}
    raw_html = {slug: path.read_text(encoding="utf-8") for slug, path in pages.items()}

    results["currency_no_gbp"] = all("£" not in html and "GBP" not in html for html in raw_html.values())

    ok, err = run_playwright_currency_check()
    results["currency_toggle_propagates"] = ok
    if err:
        results["_currency_toggle_error"] = err

    hub = soups["hub"]
    cards = hub.select("#seg-cards .sx-segcard")
    labels = [c.select_one(".sx-segcard__label").get_text(strip=True) for c in cards if c.select_one(".sx-segcard__label")]
    results["hub_grid_five_cards"] = len(cards) == 5 and labels == [configs[s]["hub_card"]["label"] for s in PHASE1]

    results["footer_five_segments"] = True
    for soup in soups.values():
        headings = [h for h in soup.select(".sx-footer__col") if h.select_one(".sx-footer__heading") and h.select_one(".sx-footer__heading").get_text(strip=True).lower() == "for"]
        if len(headings) != 1 or len(headings[0].select("li a")) != 5:
            results["footer_five_segments"] = False
            break

    forbidden = tuple(f"/{s}" for s in DEMOTED)
    surfacing = []
    surfacing.extend(hub.select(".sx-nav a"))
    surfacing.extend(hub.select("#seg-cards a"))
    for soup in soups.values():
        surfacing.extend(soup.select(".sx-footer a"))
    results["demoted_pages_unlinked"] = all(not (a.get("href") or "").startswith(forbidden) for a in surfacing)

    price_ok = True
    for slug in PHASE1:
        hub_card = hub.select_one(f"#seg-cards .sx-segcard a[href='/{slug}']")
        card = hub_card.find_parent(class_="sx-segcard") if hub_card else None
        card_text = card.get_text(" ", strip=True) if card else ""
        anchor = soups[slug].select_one(".sx-pricing-anchor")
        anchor_text = anchor.get_text(" ", strip=True) if anchor else ""
        if price_token(card_text) != price_token(anchor_text):
            price_ok = False
    results["pricing_schema_consistent"] = price_ok
    return results


def check_page(slug, cfg, soup, global_checks):
    body_below_hero = body_text_below_hero(soup).lower()
    page_text = visible_text(soup)
    lower = page_text.lower()
    results = {}

    results["h1_matches"] = h1_text(soup) == expected_h1(cfg)
    sub = soup.select_one(".sx-hero__sub")
    results["subhead_matches"] = sub is not None and sub.get_text(strip=True) == cfg["subhead"]
    results["hero_win_visible_markup"] = cfg.get("demoted") or soup.select_one(".sx-hero__h1 .rd-win") is not None
    results["segments_grid_removed"] = soup.select_one("#segments") is None and soup.select_one(".sx-segcards") is None
    results["filter_strip_removed"] = soup.select_one("#outcome-filter") is None and soup.select_one(".sx-filter") is None
    results["built_for_spaces_removed"] = "built for spaces" not in lower and "pick yours" not in lower
    results["multi_property_removed"] = "Multi-property & subscription." not in page_text
    results["about_block_removed"] = "Operators, not a marketplace." not in page_text

    outcomes = soup.select(".sx-outcome")
    results["outcomes_correct"] = (
        len(outcomes) == len(cfg["outcomes"])
        and {o.select_one(".sx-outcome__title").get_text(strip=True) for o in outcomes} == {o["title"] for o in cfg["outcomes"]}
    )
    quote = soup.select_one(".sx-objection__quote")
    reply = soup.select_one(".sx-objection__reply")
    results["objection_present"] = quote and reply and quote.get_text(strip=True) == cfg["objection"]["quote"] and reply.get_text(strip=True) == cfg["objection"]["reply"]
    anchor = soup.select_one(".sx-pricing-anchor")
    results["pricing_anchor_present"] = anchor and anchor.get_text(" ", strip=True) == cfg["pricing_anchor"]
    calc_h2 = soup.select_one("[data-calculator-h2]")
    results["calc_h2_correct"] = cfg.get("demoted") or (calc_h2 and calc_h2.get_text(strip=True) == cfg.get("calculator_h2"))
    locked = soup.select_one(".sx-calc2__locked-kind-name")
    results["calc_step1_correct"] = locked and locked.get_text(strip=True) == cfg["calculator"]["step1_kind_label"]
    step2 = soup.select_one("[data-step2-title]")
    results["calc_step2_label_correct"] = step2 and step2.get_text(strip=True) == cfg["calculator"]["step2_label"]
    opt_names = [o["name"] for o in cfg["calculator"]["step2_options"]]
    script_text = soup.select_one("[data-sx-cfg]").string or ""
    results["calc_step2_options_correct"] = all(name in script_text for name in opt_names)
    step3 = soup.select_one("[data-step3-title]")
    results["calc_step3_correct"] = (
        not cfg["calculator"].get("step3_active")
        or (step3 and step3.get_text(strip=True) == cfg["calculator"].get("step3_label"))
    )

    faq_items = soup.select("#faq-list .sx-faq__item")
    actual_qs = {it.select_one(".sx-faq__q").get_text(strip=True) for it in faq_items if it.select_one(".sx-faq__q")}
    results["faq_5_items_correct"] = len(faq_items) == 5 and actual_qs == {f["q"] for f in cfg["faq"]}
    cap = soup.select_one("[data-demo-caption]")
    results["demo_caption_correct"] = cap and cap.get_text(" ", strip=True) == cfg["demo_caption"]
    cta_h2 = soup.select_one("[data-final-cta-h2]")
    cta_body = soup.select_one("[data-final-cta-body]")
    results["final_cta_correct"] = cta_h2 and cta_body and cta_h2.get_text(strip=True) == cfg["final_cta"]["h2"] and cta_body.get_text(strip=True) == cfg["final_cta"]["body"]
    if cfg.get("phase") == "phase1":
        wanted = cfg.get("sticky_cta_label", cfg["hero_cta_primary"])
        surfaces = [
            soup.select_one("[data-hero-cta-primary]"),
            soup.select_one(".sx-nav__cta"),
            soup.select_one(".sx-final__cta .rd-btn--filled"),
        ]
        results["cta_labels_coherent"] = all(el and el.get_text(strip=True) in {wanted, cfg["hero_cta_primary"]} for el in surfaces)
        sticky = soup.select_one(".sx-sticky-cta")
        results["sticky_cta_correct"] = sticky and sticky.get_text(strip=True) == wanted
    else:
        results["cta_labels_coherent"] = True
        results["sticky_cta_correct"] = True

    title = soup.find("title").get_text(strip=True)
    desc = soup.find("meta", attrs={"name": "description"})
    og_title = soup.find("meta", attrs={"property": "og:title"})
    results["title_meta_correct"] = title == cfg["title"] and desc and desc["content"] == cfg["description"] and og_title and og_title["content"] == cfg["og_title"]

    fingerprints = {
        "managers": [" fleet standard"],
        "hosts": ["$129 one-off"],
        "hotels": ["ota commission"],
        "developers": ["off-plan deposits"],
        "weddings": ["bridal suite"],
        "clinics": ["bookimed"],
        "restaurants": ["private hire conversion"],
        "galleries": ["grant evidence"],
    }
    leaks = []
    for other_slug, terms in fingerprints.items():
        if other_slug == slug:
            continue
        leaks += [(other_slug, t) for t in terms if t in body_below_hero]
    results["no_cross_segment_below_hero"] = not leaks
    if leaks:
        results["_leaks"] = leaks[:5]

    trans = soup.select_one("[data-pricing-transparency]")
    results["weddings_pricing_transparency"] = (
        (slug == "weddings" and trans and trans.get_text(" ", strip=True) == cfg.get("pricing_transparency"))
        or (slug != "weddings" and trans is None)
    )

    for name in ["currency_no_gbp", "currency_toggle_propagates", "pricing_schema_consistent", "hub_grid_five_cards", "footer_five_segments", "demoted_pages_unlinked"]:
        results[name] = global_checks[name]
    return results


def main():
    configs = load_configs()
    global_checks = global_results(configs)
    segments = [(s, c) for s, c in configs.items() if s != "main" and not s.startswith("_") and not c.get("is_hub")]
    all_results = {slug: check_page(slug, cfg, soup_for(page_path(cfg)), global_checks) for slug, cfg in segments}

    print()
    print(f"{'Check':<35} " + " ".join(f"{s[:10]:>10}" for s, _ in segments))
    print("-" * (35 + 11 * len(segments)))
    fails = 0
    for check in CHECKS:
        cells = []
        for slug, _ in segments:
            ok = bool(all_results[slug].get(check))
            cells.append(" ✓ pass   " if ok else " ✗ FAIL   ")
            fails += 0 if ok else 1
        print(f"{check:<35} " + " ".join(cells))

    print()
    for slug, _ in segments:
        if all_results[slug].get("_leaks"):
            print(f"  ⚠ /{slug}: leaks {all_results[slug]['_leaks']}")
    if global_checks.get("_currency_toggle_error"):
        print(f"  ⚠ currency_toggle_propagates: {global_checks['_currency_toggle_error']}")

    print()
    if fails:
        print(f"❌ {fails} check(s) failed across {len(segments)} pages.")
        sys.exit(1)
    print(f"✅ All {len(CHECKS)} checks passed on all {len(segments)} pages.")


if __name__ == "__main__":
    main()
