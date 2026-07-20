#!/usr/bin/env python3
"""Fetch a short English gloss for every unique <ruby> term in index.html's
segments data (via Jisho.org, no API key needed) and rewrite the TRANSLATIONS
object in index.html to match.

Run this once, after the day's narration/reaction/vocab text is final. Does
everything in one process — no per-word shell calls — to keep the scheduled
task's tool-call/context footprint small even with 150+ words a day.

Usage: translate_batch.py [path/to/index.html]  (defaults to ./index.html)
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request


def fetch_gloss(word):
    url = "https://jisho.org/api/v1/search/words?keyword=" + urllib.parse.quote(word)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except Exception:
        return ""
    entries = data.get("data", [])
    entry = next((e for e in entries if e.get("is_common")), entries[0] if entries else None)
    if not entry or not entry.get("senses"):
        return ""
    definitions = entry["senses"][0].get("english_definitions", [])
    return ", ".join(definitions[:2])


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    with open(path, encoding="utf-8") as f:
        html = f.read()

    start = html.index("const segments = [")
    end = html.index("let current", start)
    segment_data = html[start:end]
    terms = sorted(set(re.findall(r"<ruby>([^<]+)<rt>", segment_data)))

    results = {}
    for term in terms:
        gloss = fetch_gloss(term)
        if gloss:
            results[term] = gloss
        time.sleep(0.15)  # be polite to Jisho's free API

    obj_literal = json.dumps(results, ensure_ascii=False, indent=2)
    new_line = "const TRANSLATIONS = " + obj_literal + ";"
    html_new, n = re.subn(r"const TRANSLATIONS = \{.*?\};", lambda _: new_line, html, count=1, flags=re.S)
    if n == 0:
        print("WARNING: could not find 'const TRANSLATIONS = {...};' to replace", file=sys.stderr)
        sys.exit(1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html_new)

    print(f"{len(results)}/{len(terms)} terms translated and written to {path}")


if __name__ == "__main__":
    main()
