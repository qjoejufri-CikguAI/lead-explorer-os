#!/usr/bin/env python3
"""Parse GraphQL raw dump dan ekstrak lead daripada struktur JSON rekursif."""

import json
from pathlib import Path

DUMP_PATH = Path(__file__).parent / "graphql_raw_dump.json"
OUTPUT_PATH = Path(__file__).parent / "final_leads.json"


def extract_leads_recursive(obj, path=""):
    """Recursive: cari objek yang ada name/author/user + text/message/body/comment + url/profile_url."""
    results = []

    if isinstance(obj, dict):
        # Cari nama
        author_name = ''
        if isinstance(obj.get('author'), dict):
            author_name = obj.get('author', {}).get('name', '')
        user_name = ''
        if isinstance(obj.get('user'), dict):
            user_name = obj.get('user', {}).get('name', '')
        name = author_name or user_name or obj.get('name', '') or obj.get('username', '') or obj.get('actor', {}).get('name', '') if isinstance(obj.get('actor'), dict) else ''

        # Cari teks
        message_text = ''
        if isinstance(obj.get('message'), dict):
            message_text = obj.get('message', {}).get('text', '')
        body_text = ''
        if isinstance(obj.get('body'), dict):
            body_text = obj.get('body', {}).get('text', '')
        comment_text = ''
        if isinstance(obj.get('comment'), dict):
            comment_text = obj.get('comment', {}).get('text', '')
        text_content = message_text or body_text or comment_text or obj.get('text', '') or obj.get('comment_text', '')

        # Cari URL profil
        profile_url = obj.get('profile_url', '') or obj.get('url', '') or obj.get('permalink_url', '')

        # Jika ada nama dan teks > 10 aksara, anggap sebagai lead
        if name and text_content and len(str(text_content).strip()) > 10:
            results.append({
                'username': str(name).strip(),
                'platform': 'Facebook',
                'source_type': 'Comment' if text_content else 'Post',
                'context': str(text_content).strip(),
                'profile_url': str(profile_url).strip(),
                'created_at': obj.get('created_time', '') or obj.get('timestamp', ''),
                'url': obj.get('url', ''),
                'path': path,
            })
            return results

        # Traverse semua nilai dalam dict
        for k, v in obj.items():
            results.extend(extract_leads_recursive(v, path + "." + str(k)))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(extract_leads_recursive(item, path + "[" + str(i) + "]"))

    return results


def main():
    if not DUMP_PATH.exists():
        print(f"[ERROR] Fail dump GraphQL tidak jumpa: {DUMP_PATH}")
        print("[INFO] Sila jalankan backend/scout_engine.py terlebih dahulu untuk menjana graphql_raw_dump.json")
        return

    print(f"[INFO] Membaca fail: {DUMP_PATH}")
    with open(DUMP_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[INFO] Jumlah response GraphQL: {len(data)}")

    all_leads = []
    for i, entry in enumerate(data):
        body = entry.get('body', {})
        url = entry.get('url', '')
        leads = extract_leads_recursive(body, f"response[{i}].body")
        if leads:
            print(f"[INFO] Response #{i+1} ({url}): Dapat {len(leads)} lead")
            all_leads.extend(leads)

    # Simpan ke final_leads.json
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_leads, f, indent=2, ensure_ascii=False)

    print(f"\n[INFO] Jumlah lead yang berjaya diekstrak: {len(all_leads)}")
    print(f"[INFO] Disimpan ke: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
