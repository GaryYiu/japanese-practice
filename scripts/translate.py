#!/usr/bin/env python3
"""Look up a short English definition for a Japanese word via Jisho.org's free API.

Usage: translate.py <word>
Prints one line: "<word>\t<definition>" (empty definition if nothing found).
No API key needed. Not called from the browser — Jisho doesn't send CORS
headers, so this only works server-side (e.g. from the daily content task).
"""
import json
import sys
import urllib.parse
import urllib.request


def main():
    word = sys.argv[1]
    url = "https://jisho.org/api/v1/search/words?keyword=" + urllib.parse.quote(word)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except Exception:
        print(f"{word}\t")
        return

    entries = data.get("data", [])
    entry = next((e for e in entries if e.get("is_common")), entries[0] if entries else None)
    if not entry or not entry.get("senses"):
        print(f"{word}\t")
        return

    definitions = entry["senses"][0].get("english_definitions", [])
    gloss = ", ".join(definitions[:2])
    print(f"{word}\t{gloss}")


if __name__ == "__main__":
    main()
