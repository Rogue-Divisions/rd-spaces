#!/usr/bin/env python3
"""
Verify each generated segment page passes the build-verification checklist
in `/Users/sage/LOCAL/RD/RD-SPACES/Collateral/03 EXTERNAL Per-Segment Page Copy.md`.

Reads segments.json, opens each public/<slug>/index.html, runs a battery of
assertions, and prints a pass/fail table.

Run:  python3 scripts/verify.py
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SRC = ROOT / "src"

CHECKS = [
    "h1_matches",
    "subhead_matches",
    "segments_grid_removed",
    "filter_strip_removed",
    "built_for_spaces_removed",
    "outcomes_correct",
    "objection_present",
    "calc_step1_correct",
    "calc_step2_label_correct",
    "faq_5_items_correct",
    "demo_caption_correct",
    "final_cta_correct",
    "title_meta_correct",
    "no_cross_segment_below_hero",
]


def h1_text(soup):
    h1 = soup.select_one(".sx-hero__h1")
    if not h1:
        return ""
    parts = []
    for ch in h1.children:
        if isinstance(ch, str):
            parts.append(ch.strip())
        elif ch.name == "br":
            parts.append("\n")
        else:
            parts.append(ch.get_text().strip())
    return " ".join(p for p in parts if p).replace(" \n ", " ").replace("\n", " ").strip()


def expected_h1(cfg):
    parts = [cfg["h1_line1"]]
    if cfg.get("h1_mark"):
        parts.append(cfg["h1_mark"])
    if cfg.get("h1_line2"):
        parts.append(cfg["h1_line2"])
    return " ".join(p for p in parts if p).strip()


def body_text_below_hero(soup):
    """Get the VISIBLE text content BELOW the hero — used for cross-segment leak check.
    Strips <script> and <style> bodies (their string literals are not user-visible)."""
    # Clone the soup so we don't mutate the original
    from copy import copy
    clone = BeautifulSoup(str(soup), "html.parser")
    for s in clone(["script", "style"]):
        s.decompose()
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


def check_page(slug, cfg, path):
    html = path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    body_below_hero = body_text_below_hero(soup).lower()

    results = {}

    # 1. H1 matches doc
    results["h1_matches"] = h1_text(soup) == expected_h1(cfg)

    # 2. Subhead matches
    sub = soup.select_one(".sx-hero__sub")
    results["subhead_matches"] = (sub is not None and sub.get_text(strip=True) == cfg["subhead"])

    # 3. Segments grid removed
    results["segments_grid_removed"] = soup.select_one("#segments") is None and soup.select_one(".sx-segcards") is None

    # 4. Filter strip removed
    results["filter_strip_removed"] = soup.select_one("#outcome-filter") is None and soup.select_one(".sx-filter") is None

    # 5. "Built for spaces. Pick yours." removed (excluding comments — but our build strips those too)
    page_text = soup.get_text(" ", strip=True).lower()
    results["built_for_spaces_removed"] = "built for spaces" not in page_text and "pick yours" not in page_text

    # 6. Outcomes correct count and titles match
    outcomes = soup.select(".sx-outcome")
    expected_count = len(cfg["outcomes"])
    expected_titles = {o["title"] for o in cfg["outcomes"]}
    actual_titles = {o.select_one(".sx-outcome__title").get_text(strip=True) for o in outcomes if o.select_one(".sx-outcome__title")}
    results["outcomes_correct"] = (len(outcomes) == expected_count and actual_titles == expected_titles)

    # 7. Objection block present with correct quote + reply
    quote = soup.select_one(".sx-objection__quote")
    reply = soup.select_one(".sx-objection__reply")
    results["objection_present"] = (
        quote is not None
        and reply is not None
        and quote.get_text(strip=True) == cfg["objection"]["quote"]
        and reply.get_text(strip=True) == cfg["objection"]["reply"]
    )

    # 8. Calc Step 01: locked indicator with the kind label
    locked = soup.select_one(".sx-calc2__locked-kind-name")
    results["calc_step1_correct"] = (locked is not None and locked.get_text(strip=True) == cfg["calculator"]["step1_kind_label"])

    # 9. Calc Step 02 label
    step2 = soup.select_one("[data-step2-title]")
    results["calc_step2_label_correct"] = (step2 is not None and step2.get_text(strip=True) == cfg["calculator"]["step2_label"])

    # 10. FAQ 5 items, content matches
    faq_items = soup.select("#faq-list .sx-faq__item")
    expected_qs = {f["q"] for f in cfg["faq"]}
    actual_qs = {it.select_one(".sx-faq__q").get_text(strip=True) for it in faq_items if it.select_one(".sx-faq__q")}
    results["faq_5_items_correct"] = (len(faq_items) == 5 and actual_qs == expected_qs)

    # 11. Demo caption
    cap = soup.select_one("[data-demo-caption]")
    results["demo_caption_correct"] = (cap is not None and cap.get_text(" ", strip=True) == cfg["demo_caption"])

    # 12. Final CTA H2 + body
    cta_h2 = soup.select_one("[data-final-cta-h2]")
    cta_body = soup.select_one("[data-final-cta-body]")
    results["final_cta_correct"] = (
        cta_h2 is not None and cta_h2.get_text(strip=True) == cfg["final_cta"]["h2"]
        and cta_body is not None and cta_body.get_text(strip=True) == cfg["final_cta"]["body"]
    )

    # 13. Title + meta description + og match
    title = soup.find("title").get_text(strip=True)
    desc = soup.find("meta", attrs={"name": "description"})
    desc_v = desc["content"] if desc else ""
    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_title_v = og_title["content"] if og_title else ""
    results["title_meta_correct"] = (
        title == cfg["title"]
        and desc_v == cfg["description"]
        and og_title_v == cfg["og_title"]
    )

    # 14. No cross-segment vocabulary below the hero
    # Define per-segment vocab fingerprints that must NOT appear in OTHER segments
    # Fingerprints calibrated per the v2 spec: a visitor on /managers should not see
    # "wedding" or "gallery" anywhere; a visitor on /hosts should not see "per door"
    # or "fleet". The lists below capture each segment's distinctive vocabulary, with
    # care taken NOT to include words that legitimately appear cross-segment
    # (e.g. "bride" appears on /restaurants in the private-hire outcome).
    fingerprints = {
        "managers":    ["per door", "per-door", " fleet "],
        "hosts":       ["£99", "ninety-nine pounds"],
        "hotels":      ["booking.com", "boutique hotel"],
        "developers":  ["off-plan", "dubai"],
        "weddings":    ["chapel", "wedding", "vineyard"],
        "clinics":     [" clinic ", "bookimed", "theatre"],
        "restaurants": ["private hire", "dining room"],
        "galleries":   ["curator", "exhibition", " gallery "],
    }
    others = []
    for other_slug, terms in fingerprints.items():
        if other_slug == slug:
            continue
        for term in terms:
            if term.lower() in body_below_hero:
                others.append((other_slug, term))
    results["no_cross_segment_below_hero"] = len(others) == 0
    if not results["no_cross_segment_below_hero"]:
        results["_leaks"] = others[:5]  # first 5 leaks for diagnostics

    return results


def main():
    configs = json.loads((SRC / "segments.json").read_text(encoding="utf-8"))

    segments = [(s, c) for s, c in configs.items() if s != "main" and not s.startswith("_") and not c.get("is_hub")]

    # Header
    print()
    print(f"{'Check':<35} " + " ".join(f"{s[:10]:>10}" for s, _ in segments))
    print("-" * (35 + 11 * len(segments)))

    all_results = {}
    for slug, cfg in segments:
        path = PUBLIC / cfg["slug"] / "index.html"
        all_results[slug] = check_page(slug, cfg, path)

    # One row per check
    fails = 0
    for check in CHECKS:
        cells = []
        for slug, _ in segments:
            ok = all_results[slug].get(check, False)
            cells.append(" ✓ pass   " if ok else " ✗ FAIL   ")
            if not ok:
                fails += 1
        print(f"{check:<35} " + " ".join(cells))

    print()
    # Surface any cross-segment leaks
    for slug, _ in segments:
        leaks = all_results[slug].get("_leaks")
        if leaks:
            print(f"  ⚠ /{slug}: leaks {leaks}")

    print()
    if fails:
        print(f"❌ {fails} check(s) failed across {len(segments)} pages.")
        sys.exit(1)
    else:
        print(f"✅ All {len(CHECKS)} checks passed on all {len(segments)} pages.")


if __name__ == "__main__":
    main()
