#!/usr/bin/env python3
"""Diagnostic: Inspect Facebook HTML JSON tags to understand structure."""

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

HTML_PATH = Path(__file__).parent / "fb_page_content.html"


def find_keys_with_words(obj, words, path=""):
    """Recursive: cari keys yang mengandungi kata-kata tertentu."""
    matches = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            k_lower = str(k).lower()
            for w in words:
                if w in k_lower:
                    matches.append((path + "." + str(k), k, str(v)[:80]))
                    break
            matches.extend(find_keys_with_words(v, words, path + "." + str(k)))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            matches.extend(find_keys_with_words(item, words, path + "[" + str(i) + "]"))
    return matches


def main():
    if not HTML_PATH.exists():
        print(f"[ERROR] Fail HTML tidak jumpa: {HTML_PATH}")
        return

    print(f"[INFO] Membaca fail HTML: {HTML_PATH}")
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print(f"[INFO] Saiz HTML: {len(html_content)} aksara")

    soup = BeautifulSoup(html_content, 'html.parser')
    json_tags = soup.find_all('script', type='application/json')
    print(f"[INFO] Dapat {len(json_tags)} tag <script type=\"application/json\">\n")

    words_to_find = ['text', 'message', 'author', 'actor', 'comment']

    for i, tag in enumerate(json_tags[:5]):
        print(f"===== TAG #{i+1} =====")
        content = tag.string or tag.get_text()
        if not content or not content.strip():
            print("(kosong)\n")
            continue

        # Print 500 aksara pertama
        preview = content[:500]
        print(f"--- Preview (500 aksara pertama) ---")
        print(preview)
        print("...")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[WARN] JSON tidak valid: {e}\n")
            continue

        # Top-level keys
        if isinstance(data, dict):
            top_keys = list(data.keys())[:10]
            print(f"--- Top-level keys (pertama 10): {top_keys}")
        elif isinstance(data, list):
            print(f"--- Top-level adalah list dengan {len(data)} item")
        else:
            print(f"--- Top-level type: {type(data).__name__}")

        # Cari keys yang mengandungi kata-kata target
        matches = find_keys_with_words(data, words_to_find)
        if matches:
            print(f"--- Keys yang mengandungi ['text','message','author','actor','comment'] (pertama 10):")
            for path, key, val in matches[:10]:
                print(f"  {path} :: {key} = {val}")
        else:
            print("--- Tiada key yang match kata-kata target")

        print("\n")

        # Print full JSON (indent=2) untuk tag pertama sahaja
        if i == 0:
            print("--- FULL JSON (indent=2) TAG #1 ---")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
            print("...\n")


if __name__ == "__main__":
    main()
