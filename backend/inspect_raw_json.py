#!/usr/bin/env python3
"""Diagnostic: Inspect GraphQL raw dump to find where Facebook keeps post/comment text."""

import json
from pathlib import Path

DUMP_PATH = Path(__file__).parent / "graphql_raw_dump.json"


def print_keys(obj, layer=0, max_layer=3):
    """Print keys layer by layer up to max_layer."""
    indent = "  " * layer
    if layer > max_layer:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            v_type = type(v).__name__
            v_preview = ""
            if isinstance(v, str):
                v_preview = f" = '{v[:60]}'" if len(v) <= 60 else f" = '{v[:57]}...'"
            elif isinstance(v, (int, float, bool, type(None))):
                v_preview = f" = {v}"
            print(f"{indent}{k} [{v_type}]{v_preview}")
            if layer < max_layer and isinstance(v, (dict, list)):
                print_keys(v, layer + 1, max_layer)
    elif isinstance(obj, list) and layer < max_layer:
        print(f"{indent}[list with {len(obj)} items]")
        if len(obj) > 0:
            print_keys(obj[0], layer + 1, max_layer)


def find_long_strings(obj, path="", min_len=20):
    """Recursive: find all strings longer than min_len and print with path."""
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}" if path else k
            results.extend(find_long_strings(v, new_path, min_len))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = f"{path}[{i}]"
            results.extend(find_long_strings(item, new_path, min_len))
    elif isinstance(obj, str):
        if len(obj) > min_len:
            results.append((path, obj))
    return results


def main():
    if not DUMP_PATH.exists():
        print(f"[ERROR] Fail dump GraphQL tidak jumpa: {DUMP_PATH}")
        return

    print(f"[INFO] Membaca fail: {DUMP_PATH}")
    with open(DUMP_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[INFO] Jumlah response GraphQL: {len(data)}\n")

    # Print structure of first 5 responses
    for i in range(min(5, len(data))):
        entry = data[i]
        url = entry.get('url', 'N/A')
        status = entry.get('status', 'N/A')
        body = entry.get('body', {})

        print(f"===== RESPONSE #{i + 1} =====")
        print(f"URL: {url}")
        print(f"Status: {status}")

        if isinstance(body, dict):
            print(f"\nTop-level keys: {list(body.keys())[:10]}")

            # Layer 2
            for key in list(body.keys())[:5]:
                val = body[key]
                if isinstance(val, dict):
                    print(f"\n  '{key}' keys: {list(val.keys())[:10]}")
                    # Layer 3
                    for k2 in list(val.keys())[:5]:
                        v2 = val[k2]
                        if isinstance(v2, dict):
                            print(f"    '{k2}' keys: {list(v2.keys())[:10]}")
                        elif isinstance(v2, list) and len(v2) > 0:
                            print(f"    '{k2}' = list[{len(v2)}], first item type: {type(v2[0]).__name__}")
                elif isinstance(val, list) and len(val) > 0:
                    print(f"\n  '{key}' = list[{len(val)}], first item type: {type(val[0]).__name__}")
                    if isinstance(val[0], dict):
                        print(f"    First item keys: {list(val[0].keys())[:10]}")
        elif isinstance(body, list):
            print(f"\nBody is list[{len(body)}]")
            if len(body) > 0 and isinstance(body[0], dict):
                print(f"First item keys: {list(body[0].keys())[:10]}")

        print()

    # Find long strings in ALL responses
    print("=" * 60)
    print("CARI STRING > 20 AKSARA (semua response):")
    print("=" * 60)

    all_long_strings = []
    for i, entry in enumerate(data):
        body = entry.get('body', {})
        url = entry.get('url', '')
        strings = find_long_strings(body, f"response[{i}].body")
        for path, text in strings:
            all_long_strings.append((i, url, path, text))

    print(f"\n[INFO] Dapat {len(all_long_strings)} string > 20 aksara secara keseluruhan\n")

    # Print first 20 long strings with path
    print("--- Pertama 20 string panjang dengan path ---")
    for idx, (resp_idx, url, path, text) in enumerate(all_long_strings[:20]):
        # Truncate text for display
        display_text = text[:120] + "..." if len(text) > 120 else text
        # Replace newlines for cleaner display
        display_text = display_text.replace('\n', ' | ')
        print(f"#{idx + 1} [response#{resp_idx + 1}] {path}:")
        print(f"    '{display_text}'")
        print()


if __name__ == "__main__":
    main()
