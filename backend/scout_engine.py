#!/usr/bin/env python3
"""Autonomous Lead Scouting Agent - Ghost Interceptor (Network Interception via Playwright, fully autonomous)."""

import argparse
import json
import sqlite3
import requests
from pathlib import Path
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

try:
    from intent_parser import parse_intent
except ImportError:
    def parse_intent(text):
        return 0.5

DB_PATH = Path(__file__).parent.parent / "database" / "leads.db"
CAPTURED_PATH = Path(__file__).parent / "captured_leads.json"
NETWORK_DEBUG_PATH = Path(__file__).parent / "network_debug.json"

# Supabase config (sync scrapped leads ke awalan)
SUPABASE_URL = 'https://ypcccthqbnkurkslsvdi.supabase.co'
SUPABASE_KEY = 'sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj'
SUPABASE_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': 'Bearer ' + SUPABASE_KEY,
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates',
}

captured_data = []
network_responses = []


def on_response(response):
    """Tangkap response JSON dari API TikTok/FB di belakang tabir."""
    try:
        url = response.url
        content_type = response.headers.get('content-type', '') or ''
        if 'application/json' not in content_type:
            return

        try:
            body = response.json()
        except Exception:
            return

        # Simpan semua response JSON untuk debug
        network_responses.append({
            'url': url,
            'status': response.status,
            'body': body,
            'timestamp': datetime.now().isoformat(),
        })

        # TikTok: comment list atau live detail
        if 'tiktok.com' in url:
            if '/api/comment/list/' in url or '/api/live/detail/' in url:
                extract_tiktok_json(body, url)
        # Facebook: feed atau graphql comment
        elif 'facebook.com' in url or 'fb.com' in url:
            if '/api/feed/' in url or 'graphql' in url or '/comments/' in url:
                extract_facebook_json(body, url)
    except Exception:
        pass


def extract_tiktok_json(body, url):
    global captured_data
    comments = []
    if isinstance(body, dict):
        comments = body.get('comments', []) or body.get('data', {}).get('comments', []) or []
    elif isinstance(body, list):
        comments = body

    for item in comments:
        if not isinstance(item, dict):
            continue
        user = item.get('user', {}) or item.get('author', {}) or {}
        username = user.get('unique_id') or user.get('nickname') or item.get('username') or ''
        profile_url = user.get('profile_url') or user.get('avatar_larger') or ''
        comment_text = item.get('text') or item.get('comment') or item.get('content') or ''
        timestamp = item.get('create_time') or item.get('createTime') or item.get('create_at') or datetime.now().isoformat()
        if username:
            captured_data.append({
                'username': username,
                'platform': 'TikTok',
                'source_type': 'Comment' if comment_text else 'Live',
                'context': comment_text,
                'profile_url': profile_url,
                'timestamp': timestamp,
                'url': url,
            })


def extract_facebook_json(body, url):
    global captured_data
    entries = []
    if isinstance(body, dict):
        data = body.get('data', {})
        if isinstance(data, dict):
            entries = data.get('comments', []) or data.get('edges', []) or data.get('posts', []) or []
        elif isinstance(data, list):
            entries = data

    for item in entries:
        if not isinstance(item, dict):
            continue
        node = item.get('node', item)
        if not isinstance(node, dict):
            continue
        from_field = node.get('from')
        username = node.get('username') or node.get('name') or (from_field.get('name', '') if isinstance(from_field, dict) else '')
        profile_url = node.get('url') or node.get('profile_url') or ''
        comment_text = node.get('text') or node.get('message') or node.get('comment_text') or ''
        timestamp = node.get('created_time') or node.get('timestamp') or datetime.now().isoformat()
        if username:
            captured_data.append({
                'username': username,
                'platform': 'Facebook',
                'source_type': 'Comment' if comment_text else 'Post',
                'context': comment_text,
                'profile_url': profile_url,
                'timestamp': timestamp,
                'url': url,
            })


def auto_scroll_and_expand(page, duration_seconds=10):
    """Scroll automatik dan klik 'See more comments' untuk trigger data API."""
    import time
    end_time = time.time() + duration_seconds
    last_height = 0

    while time.time() < end_time:
        # Scroll ke bawah
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

        # Coba klik butang 'See more comments' / 'Lihat semua komen'
        try:
            see_more_selectors = [
                'text="See more comments"',
                'text="Lihat semua komen"',
                'text="View more comments"',
                'text="Tampilkan lebih banyak komen"',
                'div[role="button"]:has-text("See more comments")',
                'div[role="button"]:has-text("Lihat semua komen")',
            ]
            for selector in see_more_selectors:
                els = page.query_selector_all(selector)
                for el in els[:3]:
                    try:
                        el.click()
                        page.wait_for_timeout(2000)
                    except Exception:
                        pass
        except Exception:
            pass

        # Cek jika page height bertambah
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


def scrape_social_media(niche: str, area: str):
    """Main entry: Ghost Interceptor - autonomous, no manual input."""
    if sync_playwright is None:
        print('[ERROR] Gagal import Playwright. Sila pastikan playwright sudah di-install.')
        return []

    global captured_data, network_responses
    captured_data = []
    network_responses = []

    cookie_path = Path(__file__).parent / 'cookies.json'

    all_leads = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
        )

        # Load cookies jika wujud
        if cookie_path.exists():
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                context.add_cookies(cookies)
                print('[INFO] Cookie dimuatkan dari cookies.json')
            except Exception as e:
                print(f"[ERROR] Ralat memuatkan cookie: {e}")

        page = context.new_page()
        page.on("response", on_response)

        # Facebook search posts URL
        fb_query = (niche + ' ' + area).replace(' ', '%20')
        fb_url = f'https://www.facebook.com/search/posts/?q={fb_query}'
        # TikTok search URL
        tt_query = (niche + ' ' + area).replace(' ', '+')
        tt_url = f'https://www.tiktok.com/search?q={tt_query}'

        print(f'[INFO] Pergi ke Facebook: {fb_url}')
        try:
            page.goto(fb_url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(5000)
            print('[INFO] Auto-scroll dan expand komen untuk Facebook selama 10 saat...')
            auto_scroll_and_expand(page, 10)
        except Exception as e:
            print(f"[WARN] Facebook navigate/scroll gagal: {e}")

        print(f'[INFO] Pergi ke TikTok: {tt_url}')
        try:
            page.goto(tt_url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(5000)
            print('[INFO] Auto-scroll untuk TikTok selama 10 saat...')
            auto_scroll_and_expand(page, 10)
        except Exception as e:
            print(f"[WARN] TikTok navigate/scroll gagal: {e}")

        # Simpan network debug
        try:
            with open(NETWORK_DEBUG_PATH, 'w', encoding='utf-8') as f:
                json.dump(network_responses, f, indent=2, ensure_ascii=False)
            print(f'[INFO] Disimpan {len(network_responses)} response ke network_debug.json')
        except Exception as e:
            print(f"[WARN] Gagal simpan network_debug.json: {e}")

        # Simpan cookies
        try:
            cookies = context.cookies()
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)
            print('[INFO] Cookie disimpan ke cookies.json')
        except Exception as e:
            print(f"[ERROR] Ralat simpan cookie: {e}")

        page.screenshot(path="autonomous_debug.png")
        browser.close()

    all_leads = captured_data
    print(f"[INFO] Dapat {len(all_leads)} lead dari network interception (autonomous).")

    # Simpan captured data ke fail JSON
    try:
        with open(CAPTURED_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_leads, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Gagal simpan captured_leads.json: {e}")

    return all_leads


def main():
    parser = argparse.ArgumentParser(description="Ghost Interceptor Lead Scouting (Autonomous, Facebook & TikTok)")
    parser.add_argument("--niche", required=True, help="Niche category (e.g. Jualan Kereta)")
    parser.add_argument("--area", required=True, help="Malaysia area/region (e.g. Tangkak)")
    args = parser.parse_args()

    leads = scrape_social_media(args.niche, args.area)
    if not leads:
        print('[WARN] Tiada lead yang berhasil ditangkap dari network.')
        return

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            name TEXT,
            platform TEXT,
            source_type TEXT,
            context TEXT,
            niche TEXT,
            area TEXT,
            intent_score REAL,
            interest_level TEXT,
            phone TEXT,
            email TEXT,
            social_link TEXT,
            source TEXT,
            created_at TEXT,
            processed_at TEXT
        )
    ''')

    for lead in leads:
        comment_text = lead.get('context', '') or ''
        intent_score = parse_intent(comment_text) if comment_text else 0.5
        if intent_score >= 0.85:
            interest_level = "Hot"
        elif intent_score >= 0.65:
            interest_level = "Warm"
        else:
            interest_level = "Cold"

        username = lead.get('username', '')
        platform = lead.get('platform', '')
        area_val = args.area
        lead_id = platform.lower() + "_" + username.replace(" ", "_") + "_" + area_val.replace(" ", "_")

        cursor.execute("""
            INSERT OR IGNORE INTO leads
            (id, name, platform, source_type, context, niche, area, intent_score, interest_level, phone, email, social_link, source, created_at, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            lead_id,
            username,
            platform,
            lead.get('source_type', ''),
            comment_text,
            args.niche,
            area_val,
            intent_score,
            interest_level,
            '',
            '',
            lead.get('profile_url', ''),
            lead.get('source', 'network_interception'),
            lead.get('timestamp', datetime.now().isoformat()),
        ))

    conn.commit()
    conn.close()

    # Sync ke Supabase
    supabase_payload = []
    for lead in leads:
        comment_text = lead.get('context', '') or ''
        intent_score = parse_intent(comment_text) if comment_text else 0.5
        if intent_score >= 0.85:
            interest_level = "Hot"
        elif intent_score >= 0.65:
            interest_level = "Warm"
        else:
            interest_level = "Cold"

        username = lead.get('username', '')
        platform = lead.get('platform', '')
        area_val = args.area
        supabase_payload.append({
            'id': platform.lower() + "_" + username.replace(" ", "_") + "_" + area_val.replace(" ", "_"),
            'name': username,
            'niche': args.niche,
            'area': area_val,
            'intent_score': intent_score,
            'interest_level': interest_level,
            'phone': '',
            'email': '',
            'social_link': lead.get('profile_url', ''),
            'platform': platform,
            'created_at': lead.get('timestamp', datetime.now().isoformat()),
        })

    try:
        resp = requests.post(SUPABASE_URL + '/rest/v1/leads', headers=SUPABASE_HEADERS, json=supabase_payload)
        if resp.status_code in (200, 201):
            print("[OK] Sinkeer " + str(len(supabase_payload)) + " lead ke Supabase.")
        else:
            print("[WARN] Gagal sinkeer ke Supabase: " + str(resp.status_code) + " " + resp.text)
    except Exception as e:
        print("[WARN] Ralat sinkeer Supabase: " + str(e))

    print(f"[OK] Processed {len(leads)} leads for {args.niche} in {args.area}")
    print("[DONE] Leads stored in leads.db")


if __name__ == "__main__":
    main()
