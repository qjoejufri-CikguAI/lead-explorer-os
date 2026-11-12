import json
from pathlib import Path

JSON_PATH = Path(__file__).parent / "network_debug.json"

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Jumlah response JSON di fail: {len(data)}\n")

for i, entry in enumerate(data):
    print(f"=== Response #{i + 1} ===")
    print(f"URL: {entry.get('url', 'N/A')}")
    print(f"Status: {entry.get('status', 'N/A')}")
    body = entry.get('body', {})
    if isinstance(body, dict):
        top_keys = list(body.keys())[:5]
        print(f"5 keys teratas body: {top_keys}")
    # Cari text/string lebih 10 aksara
    def find_strings(obj, depth=0):
        if depth > 3:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and len(v.strip()) > 10:
                    print(f"  String [{k}]: {v.strip()[:100]}")
                find_strings(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                find_strings(item, depth + 1)
    find_strings(body)
    print()
