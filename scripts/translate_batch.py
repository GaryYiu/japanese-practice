#!/usr/bin/env python3
"""Fetch a short English gloss for every clickable word in index.html's segments
data — both ruby-anchored kanji terms AND standalone kana words/phrases (e.g.
ニュース, それ, あるそうです) — via Jisho.org (no API key needed), and rewrite
the TRANSLATIONS object in index.html to match.

The word list comes from scripts/extract_words.js, which reuses the actual
vendored TinySegmenter + PARTICLE_STOP_WORDS straight out of index.html, so it
can't drift from what the browser's click-to-pronounce feature considers
clickable.

Run this once, after the day's narration/reaction/vocab text is final. Does
the whole batch in one process — no per-word shell calls — to keep the
scheduled task's tool-call/context footprint small even with 200+ words a day.

Usage: translate_batch.py [path/to/index.html]  (defaults to ./index.html)
"""
import json
import os
import re
import subprocess
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

    script_dir = os.path.dirname(os.path.abspath(__file__))
    extractor = os.path.join(script_dir, "extract_words.js")
    result = subprocess.run(["node", extractor, path], capture_output=True, text=True, check=True)
    terms = json.loads(result.stdout)

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
