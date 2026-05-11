#!/usr/bin/env python3
"""
Spaces — per-segment page generator.

Reads `src/segments.json` and `src/template.html`, emits 9 HTML files into
`public/` (main + 8 segment pages). Each segment page differs from main in:

  - <title>, <meta name=description>, canonical URL, og:* URL
  - Hero H1 (line 1, signal-red "mark" word, line 2)
  - Hero subhead
  - Default-active demo pill (which sample tour loads first)
  - Default-open segment accordion (which segment's pitch is expanded)
  - Default-active calculator "kind" tile (which space type is pre-picked)
  - Default-active outcomes filter chip

Run from the repo root:  python3 scripts/build.py

Idempotent. Overwrites public/*/index.html. Does not touch CSS, JS, assets.
"""

from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("bs4 not installed. Run: pip3 install --user beautifulsoup4")


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PUBLIC = ROOT / "public"


def render(config: dict, template_html: str) -> str:
    """Build a single page from the canonical template + a segment config."""
    soup = BeautifulSoup(template_html, "html.parser")
    slug = config["slug"]

    # ─── Head ────────────────────────────────────────────────────────────
    if t := soup.find("title"):
        t.string = config["title"]

    if md := soup.find("meta", attrs={"name": "description"}):
        md["content"] = config["description"]

    if canon := soup.find("link", rel="canonical"):
        canon["href"] = config["url"]

    if og_url := soup.find("meta", attrs={"property": "og:url"}):
        og_url["content"] = config["url"]

    # OG/Twitter share copy is more punchy than SEO copy — derive from H1+subhead
    # so the social preview reads like the hero, not the meta description.
    parts = [config["h1_line1"]]
    if config.get("h1_mark"):
        parts.append(config["h1_mark"])
    parts.append(config["h1_line2"])
    og_title_text = " ".join(p.strip() for p in parts if p and p.strip() != ".")
    if not og_title_text.endswith("."):
        og_title_text += "."

    if og_title := soup.find("meta", attrs={"property": "og:title"}):
        og_title["content"] = og_title_text

    if og_desc := soup.find("meta", attrs={"property": "og:description"}):
        og_desc["content"] = config["subhead"]

    if tw_title := soup.find("meta", attrs={"name": "twitter:title"}):
        tw_title["content"] = og_title_text

    if tw_desc := soup.find("meta", attrs={"name": "twitter:description"}):
        tw_desc["content"] = config["subhead"]

    # ─── Hero H1 + subhead ───────────────────────────────────────────────
    if h1 := soup.select_one(".sx-hero__h1"):
        h1.clear()
        h1.append(config["h1_line1"])
        h1.append(soup.new_tag("br"))
        if config.get("h1_mark"):
            mark = soup.new_tag("span", attrs={"class": "rd-win"})
            mark.string = config["h1_mark"]
            h1.append(" ")
            h1.append(mark)
            h1.append(" ")
        h1.append(config["h1_line2"])

    if sub := soup.select_one(".sx-hero__sub"):
        sub.string = config["subhead"]

    # ─── Demo pill: move is-active to the configured tour ────────────────
    active_tour = config.get("active_tour", "rest")
    for btn in soup.select(".sx-demo__pill"):
        is_match = btn.get("data-tour") == active_tour
        classes = [c for c in btn.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
        btn["class"] = classes
        btn["aria-selected"] = "true" if is_match else "false"

    # ─── Demo iframe: move src to active tour, others get data-deferred-src ──
    for iframe in soup.select(".sx-demo__frame"):
        is_match = iframe.get("data-tour") == active_tour
        # Determine current URL (either src= or data-deferred-src=)
        url = iframe.get("src") or iframe.get("data-deferred-src")
        classes = [c for c in iframe.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
            iframe["src"] = url
            if iframe.has_attr("data-deferred-src"):
                del iframe["data-deferred-src"]
            if iframe.has_attr("aria-hidden"):
                del iframe["aria-hidden"]
        else:
            iframe["data-deferred-src"] = url
            if iframe.has_attr("src"):
                del iframe["src"]
            iframe["aria-hidden"] = "true"
        iframe["class"] = classes

    # ─── Segment accordion: open the configured one ──────────────────────
    active_seg = config.get("active_segment", "hotel")
    for det in soup.select(".sx-segcard"):
        is_match = det.get("data-seg") == active_seg
        if is_match:
            det["open"] = ""
        elif det.has_attr("open"):
            del det["open"]

    # ─── Calculator "kind" tile: move is-active ──────────────────────────
    active_kind = config.get("active_kind", "apartment")
    for btn in soup.select("[data-kind]"):
        is_match = btn.get("data-kind") == active_kind
        classes = [c for c in btn.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
        btn["class"] = classes

    # ─── Outcomes filter chip ────────────────────────────────────────────
    outcomes_filter = config.get("outcomes_filter", "all")
    for btn in soup.select(".sx-filter__btn"):
        is_match = btn.get("data-filter") == outcomes_filter
        classes = [c for c in btn.get("class", []) if c != "is-active"]
        if is_match:
            classes.append("is-active")
        btn["class"] = classes

    # ─── Tell the runtime JS which segment page it's on ──────────────────
    # This lets the inline scripts react: e.g. outcomes filter applies on load,
    # calc steps to the right kind, etc.
    body = soup.find("body")
    if body is not None:
        if slug:
            body["data-segment"] = slug
        body["data-active-tour"] = active_tour
        body["data-active-kind"] = active_kind
        body["data-outcomes-filter"] = outcomes_filter

    return str(soup)


def main() -> None:
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

    # Main page
    main_html = render(configs["main"], template_html)
    (PUBLIC / "index.html").write_text(main_html, encoding="utf-8")
    print(f"  ✓ public/index.html  ({len(main_html):,} bytes)")

    # Segment pages — emit at public/<slug>/index.html so Cloudflare serves
    # /managers → /managers/index.html (clean URL, no .html extension)
    for slug, cfg in configs.items():
        if slug == "main":
            continue
        out_dir = PUBLIC / cfg["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        page_html = render(cfg, template_html)
        (out_dir / "index.html").write_text(page_html, encoding="utf-8")
        print(f"  ✓ public/{cfg['slug']}/index.html  ({len(page_html):,} bytes)")


if __name__ == "__main__":
    print("Building Spaces per-segment pages...")
    main()
    print("Done.")
