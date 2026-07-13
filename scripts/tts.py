#!/usr/bin/env python3
"""Synthesize one line of Japanese speech via Google Cloud TTS.

Usage: tts.py <output.mp3> <voice-name> <text...>
Requires GOOGLE_TTS_API_KEY in the environment.
"""
import base64
import json
import os
import sys
import urllib.request


def main():
    out_path, voice, text = sys.argv[1], sys.argv[2], " ".join(sys.argv[3:])
    api_key = os.environ["GOOGLE_TTS_API_KEY"]
    body = json.dumps({
        "input": {"text": text},
        "voice": {"languageCode": "ja-JP", "name": voice},
        "audioConfig": {"audioEncoding": "MP3"},
    }).encode()
    req = urllib.request.Request(
        f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(data["audioContent"]))


if __name__ == "__main__":
    main()
