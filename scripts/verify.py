#!/usr/bin/env python3
"""
Verify generated Spaces pages against the v3 audit matrix.

Run from repo root after `python3 scripts/build.py`:
  python3 scripts/verify.py
"""

from __future__ import annotations

import fnmatch
import io
import json
import re
import sys
import threading
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
SRC = ROOT / "src"
HEADERS_PATH = PUBLIC / "_headers"
WRANGLER_PATH = ROOT / "wrangler.toml"

SEGMENT_SLUGS = [
    "managers",
    "hosts",
    "hotels",
    "developers",
    "weddings",
    "clinics",
    "restaurants",
    "galleries",
]

REQUIRED_SECURITY_HEADERS = {
    "Content-Security-Policy",
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "Permissions-Policy",
}

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
    "paint_hero_emphasis",
    "step_numbers_sequential",
    "currency_consistency",
    "demo_pill_row_absent_on_segment",
    "multi_property_section_absent_on_segment",
    "about_rd_treatment",
    "final_cta_buttons_segment_flavoured",
    "footer_segments_list_present",
    "security_headers_present_on_segment",
    "hub_pill_caption_updates",
]


class QuietHandler(SimpleHTTPRequestHandler):
    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            return

    def copyfile(self, source, outputfile) -> None:
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, *_args) -> None:
        return


@contextmanager
def preview_server():
    handler = partial(QuietHandler, directory=str(PUBLIC))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def page_path(slug: str) -> Path:
    return PUBLIC / "index.html" if slug == "hub" else PUBLIC / slug / "index.html"


def load_soup(slug: str) -> BeautifulSoup:
    return BeautifulSoup(page_path(slug).read_text(encoding="utf-8"), "html.parser")


def normalized_text(el) -> str:
    if el is None:
        return ""
    text = el.get_text(" ", strip=True)
    return re.sub(r"\s+([.,;:!?])", r"\1", text)


def h1_text(soup: BeautifulSoup) -> str:
    h1 = soup.select_one(".sx-hero__h1")
    if not h1:
        return ""
    parts = []
    for ch in h1.children:
        if isinstance(ch, str):
            parts.append(ch.strip())
        elif getattr(ch, "name", None) == "br":
            parts.append("\n")
        else:
            parts.append(ch.get_text().strip())
    return " ".join(p for p in parts if p).replace(" \n ", " ").replace("\n", " ").strip()


def expected_h1(cfg: dict) -> str:
    parts = [cfg["h1_line1"]]
    if cfg.get("h1_mark"):
        parts.append(cfg["h1_mark"])
    if cfg.get("h1_line2"):
        parts.append(cfg["h1_line2"])
    return " ".join(p for p in parts if p).strip()


def body_text_below_hero(soup: BeautifulSoup) -> str:
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


def parse_headers_file() -> list[tuple[str, dict[str, str]]]:
    rules: list[tuple[str, dict[str, str]]] = []
    current_pattern: str | None = None
    current_headers: dict[str, str] = {}
    for raw in HEADERS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not raw.startswith((" ", "\t")):
            if current_pattern:
                rules.append((current_pattern, current_headers))
            current_pattern = line
            current_headers = {}
            continue
        if ":" in line and current_pattern:
            name, value = line.strip().split(":", 1)
            current_headers[name] = value.strip()
    if current_pattern:
        rules.append((current_pattern, current_headers))
    return rules


def pattern_matches(pattern: str, path: str) -> bool:
    if pattern == path:
        return True
    if pattern.endswith("*"):
        return fnmatch.fnmatch(path, pattern)
    return fnmatch.fnmatch(path, pattern)


def headers_for(path: str, rules: list[tuple[str, dict[str, str]]]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for pattern, headers in rules:
        if pattern_matches(pattern, path):
            merged.update(headers)
    return merged


def security_headers_ok(slug: str) -> bool:
    rules = parse_headers_file()
    url_path = "/" if slug == "hub" else f"/{slug}"
    headers = headers_for(url_path, rules)
    has_headers = REQUIRED_SECURITY_HEADERS.issubset(headers.keys())
    wrangler = WRANGLER_PATH.read_text(encoding="utf-8")
    has_policy = 'html_handling = "drop-trailing-slash"' in wrangler or 'html_handling = "force-trailing-slash"' in wrangler
    return has_headers and has_policy


def footer_links_ok(soup: BeautifulSoup) -> bool:
    expected = {f"/{slug}" for slug in SEGMENT_SLUGS}
    actual = {a.get("href") for a in soup.select(".sx-footer__col--segments a")}
    return expected.issubset(actual)


def check_static_page(slug: str, cfg: dict, soup: BeautifulSoup) -> dict[str, bool | list[tuple[str, str]]]:
    is_hub = slug == "hub"
    results: dict[str, bool | list[tuple[str, str]]] = {}
    page_text = soup.get_text(" ", strip=True).lower()
    body_below_hero = body_text_below_hero(soup).lower()

    results["h1_matches"] = h1_text(soup) == expected_h1(cfg)
    sub = soup.select_one(".sx-hero__sub")
    results["subhead_matches"] = sub is not None and normalized_text(sub) == cfg["subhead"]

    if is_hub:
        results["segments_grid_removed"] = soup.select_one("#segments") is not None
        results["filter_strip_removed"] = soup.select_one("#outcome-filter") is not None
        results["built_for_spaces_removed"] = "built for spaces" in page_text and "pick yours" in page_text
        results["outcomes_correct"] = len(soup.select(".sx-outcome")) >= 6
        results["objection_present"] = soup.select_one(".sx-objection") is None
        results["calc_step1_correct"] = soup.select_one("[data-step-id='kind']") is not None
        results["calc_step2_label_correct"] = soup.select_one("[data-step2-title]") is not None
        results["faq_5_items_correct"] = len(soup.select("#faq-list .sx-faq__item")) >= 5
        cap = soup.select_one("[data-demo-caption]")
        results["demo_caption_correct"] = cap is not None and normalized_text(cap) == cfg["demo_caption"]
        results["final_cta_correct"] = soup.select_one("[data-final-cta-h2]") is not None and soup.select_one("[data-final-cta-body]") is not None
        title = soup.find("title")
        desc = soup.find("meta", attrs={"name": "description"})
        results["title_meta_correct"] = bool(title and title.get_text(strip=True) == cfg["title"] and desc and desc.get("content") == cfg["description"])
        results["no_cross_segment_below_hero"] = True
    else:
        results["segments_grid_removed"] = soup.select_one("#segments") is None and soup.select_one(".sx-segcards") is None
        results["filter_strip_removed"] = soup.select_one("#outcome-filter") is None and soup.select_one(".sx-filter") is None
        results["built_for_spaces_removed"] = "built for spaces" not in page_text and "pick yours" not in page_text
        outcomes = soup.select(".sx-outcome")
        expected_titles = {o["title"] for o in cfg["outcomes"]}
        actual_titles = {normalized_text(o.select_one(".sx-outcome__title")) for o in outcomes if o.select_one(".sx-outcome__title")}
        results["outcomes_correct"] = len(outcomes) == len(cfg["outcomes"]) and actual_titles == expected_titles
        quote = soup.select_one(".sx-objection__quote")
        reply = soup.select_one(".sx-objection__reply")
        results["objection_present"] = bool(
            quote
            and reply
            and normalized_text(quote) == cfg["objection"]["quote"]
            and normalized_text(reply) == cfg["objection"]["reply"]
        )
        locked = soup.select_one(".sx-calc2__locked-kind-name")
        results["calc_step1_correct"] = locked is not None and normalized_text(locked) == cfg["calculator"]["step1_kind_label"]
        step2 = soup.select_one("[data-step2-title]")
        results["calc_step2_label_correct"] = step2 is not None and normalized_text(step2) == cfg["calculator"]["step2_label"]
        faq_items = soup.select("#faq-list .sx-faq__item")
        expected_qs = {f["q"] for f in cfg["faq"]}
        actual_qs = {normalized_text(it.select_one(".sx-faq__q")) for it in faq_items if it.select_one(".sx-faq__q")}
        results["faq_5_items_correct"] = len(faq_items) == 5 and actual_qs == expected_qs
        cap = soup.select_one("[data-demo-caption]")
        results["demo_caption_correct"] = cap is not None and normalized_text(cap) == cfg["demo_caption"]
        cta_h2 = soup.select_one("[data-final-cta-h2]")
        cta_body = soup.select_one("[data-final-cta-body]")
        results["final_cta_correct"] = bool(
            cta_h2
            and normalized_text(cta_h2) == cfg["final_cta"]["h2"]
            and cta_body
            and normalized_text(cta_body) == cfg["final_cta"]["body"]
        )
        title = soup.find("title")
        desc = soup.find("meta", attrs={"name": "description"})
        og_title = soup.find("meta", attrs={"property": "og:title"})
        results["title_meta_correct"] = bool(
            title
            and title.get_text(strip=True) == cfg["title"]
            and desc
            and desc.get("content") == cfg["description"]
            and og_title
            and og_title.get("content") == cfg["og_title"]
        )
        fingerprints = {
            "managers": ["per door", "per-door", " fleet "],
            "hosts": ["£99", "ninety-nine pounds"],
            "hotels": ["booking.com", "boutique hotel"],
            "developers": ["off-plan", "dubai"],
            "weddings": ["chapel", "wedding", "vineyard"],
            "clinics": [" clinic ", "bookimed", "theatre"],
            "restaurants": ["private hire", "dining room"],
            "galleries": ["curator", "exhibition", " gallery "],
        }
        leaks = []
        for other_slug, terms in fingerprints.items():
            if other_slug == slug:
                continue
            for term in terms:
                if term.lower() in body_below_hero:
                    leaks.append((other_slug, term))
        results["no_cross_segment_below_hero"] = len(leaks) == 0
        if leaks:
            results["_leaks"] = leaks[:5]

    results["demo_pill_row_absent_on_segment"] = soup.select_one(".sx-demo__pills") is not None if is_hub else soup.select_one(".sx-demo__pills") is None
    results["multi_property_section_absent_on_segment"] = soup.select_one(".sx-multi-wrap") is not None if is_hub else soup.select_one(".sx-multi-wrap") is None
    about_h2 = any("Operators, not a marketplace." == normalized_text(h) for h in soup.select(".sx-h2"))
    results["about_rd_treatment"] = about_h2 if is_hub else not about_h2
    if is_hub:
        results["final_cta_buttons_segment_flavoured"] = True
    else:
        buttons = [normalized_text(a) for a in soup.select(".sx-final__cta a")]
        results["final_cta_buttons_segment_flavoured"] = (
            cfg["final_cta"].get("button_primary") in buttons
            and cfg["final_cta"].get("button_secondary") in buttons
            and "Book your free pilot scan" not in buttons
            and "See pricing" not in buttons
        )
    results["footer_segments_list_present"] = footer_links_ok(soup)
    results["security_headers_present_on_segment"] = security_headers_ok(slug)
    results["paint_hero_emphasis"] = False
    results["step_numbers_sequential"] = False
    results["currency_consistency"] = False
    results["hub_pill_caption_updates"] = False
    return results


def brand_red_pixel_count(png_bytes: bytes) -> int:
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow is required for pixel checks. Run: python3 -m pip install pillow")
    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    count = 0
    pixels = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    for r, g, b, a in pixels:
        if a > 0 and r == 255 and g == 44 and b == 85:
            count += 1
    return count


def run_browser_checks(results: dict[str, dict[str, bool | list[tuple[str, str]]]], slugs: list[str]) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright is required for browser checks. Run: python3 scripts/setup_playwright.py")

    with preview_server() as base_url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            for slug in slugs:
                path = "/" if slug == "hub" else f"/{slug}/"
                page.goto(base_url + path, wait_until="domcontentloaded")
                page.wait_for_timeout(850)

                win = page.locator(".rd-win")
                bbox = win.bounding_box()
                color = win.evaluate("el => getComputedStyle(el).color") if win.count() else ""
                png = b""
                if bbox:
                    clip = {
                        "x": max(0, bbox["x"] + (bbox["width"] / 2) - 50),
                        "y": max(0, bbox["y"] + (bbox["height"] / 2) - 50),
                        "width": 100,
                        "height": 100,
                    }
                    png = page.screenshot(clip=clip)
                results[slug]["paint_hero_emphasis"] = bool(
                    bbox
                    and bbox["width"] > 20
                    and bbox["height"] > 20
                    and color == "rgb(255, 44, 85)"
                    and brand_red_pixel_count(png) > 0
                )

                nums = page.locator(".sx-calc2__step").evaluate_all(
                    """els => els
                      .filter(el => el.offsetParent !== null)
                      .map(el => el.querySelector('.sx-calc2__step-num')?.textContent.trim())
                      .filter(Boolean)"""
                )
                expected_nums = [f"{i:02d}" for i in range(1, len(nums) + 1)]
                results[slug]["step_numbers_sequential"] = nums == expected_nums

                results[slug]["currency_consistency"] = browser_currency_ok(page, slug)

            page.goto(base_url + "/", wait_until="domcontentloaded")
            page.wait_for_timeout(300)
            expected_titles = {
                "rest": "BlueTokai Coffee",
                "hotel": "Clarks Exotica",
                "str": "Living Room",
                "dev": "The Villa Tour",
                "venue": "Château La Sarraz",
            }
            caption_ok = True
            for tour, title in expected_titles.items():
                page.locator(f".sx-demo__pill[data-tour='{tour}']").click()
                actual = page.locator("[data-tour-title]").text_content()
                caption_ok = caption_ok and actual == title
            for slug in slugs:
                results[slug]["hub_pill_caption_updates"] = caption_ok if slug == "hub" else True
            browser.close()


def browser_currency_ok(page, slug: str) -> bool:
    # Select the first concrete size so total, option rows, add-ons, pricing anchor,
    # and the managers onboarding line all render in the current currency state.
    first_size = page.locator("[data-size]").first
    if first_size.count():
        first_size.click()

    if slug == "managers":
        row_visible = page.locator("[data-one-off-row]").is_visible()
        one_off_text = page.locator("[data-one-off-value]").text_content() or ""
        if not row_visible or "By quote" not in one_off_text:
            return False

    checks = [("GBP", "£", "$"), ("USD", "$", "£")]
    for cur, desired, forbidden in checks:
        page.locator(f"[data-cur='{cur}']").click()
        page.wait_for_timeout(50)
        texts = page.locator(
            "[data-money-gbp], [data-addon-price], .sx-calc2__opt-price, [data-total], [data-one-off-value]"
        ).evaluate_all(
            """els => els
              .filter(el => el.offsetParent !== null)
              .map(el => el.textContent.trim())
              .filter(text => text.includes('£') || text.includes('$'))"""
        )
        if not texts:
            return False
        for text in texts:
            if desired not in text or forbidden in text:
                return False
    return True


def main() -> None:
    configs = json.loads((SRC / "segments.json").read_text(encoding="utf-8"))
    slugs = ["hub"] + SEGMENT_SLUGS
    cfgs = {"hub": configs["main"], **{slug: configs[slug] for slug in SEGMENT_SLUGS}}
    soups = {slug: load_soup(slug) for slug in slugs}
    all_results = {slug: check_static_page(slug, cfgs[slug], soups[slug]) for slug in slugs}
    run_browser_checks(all_results, slugs)

    print()
    print(f"{'Check':<43} " + " ".join(f"{s[:10]:>10}" for s in slugs))
    print("-" * (43 + 11 * len(slugs)))

    fails = 0
    for check in CHECKS:
        cells = []
        for slug in slugs:
            ok = bool(all_results[slug].get(check, False))
            cells.append(" ✓ pass   " if ok else " ✗ FAIL   ")
            if not ok:
                fails += 1
        print(f"{check:<43} " + " ".join(cells))

    print()
    for slug in slugs:
        leaks = all_results[slug].get("_leaks")
        if leaks:
            print(f"  /{slug}: leaks {leaks}")

    print()
    if fails:
        print(f"❌ {fails} check(s) failed across {len(slugs)} pages.")
        sys.exit(1)
    print(f"✅ All {len(CHECKS)} checks passed on all {len(slugs)} pages.")


if __name__ == "__main__":
    main()
