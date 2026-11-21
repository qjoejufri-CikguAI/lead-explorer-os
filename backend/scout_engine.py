import os
import sys
import time
import json
import re
import sqlite3
import requests
import argparse
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Import fungsi AI & Intent Parser
try:
    from ai_brain import generate_smart_search_queries
except ImportError:
    def generate_smart_search_queries(goal):
        return [f"nak beli {goal}", f"cari {goal}", f"wanted {goal}"]

try:
    from intent_parser import parse_intent
except ImportError:
    def parse_intent(text):
        text = text.lower()
        if any(w in text for w in ["nak", "pm", "berapa", "minat", "loan"]): return 0.9
        return 0.1

load_dotenv()

# ================= KONFIGURASI =================
SUPABASE_URL = "https://ypcccthqbnkurkslsvdi.supabase.co"
SUPABASE_KEY = "sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj"
TARGET_FB_URL = "https://www.facebook.com/groups/168234697021322"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "leads.db")
COOKIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.json")

# ================= SQLITE =================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            niche TEXT,
            area TEXT,
            intent_score REAL,
            interest_level TEXT,
            phone TEXT,
            email TEXT,
            social_link TEXT,
            platform TEXT,
            source_type TEXT,
            context TEXT,
            plate_number TEXT,
            keyword TEXT,
            source_account TEXT,
            created_at TEXT,
            processed_at TEXT,
            brand TEXT,
            UNIQUE(name, source_account)
        )
    ''')
    conn.commit()
    conn.close()

def save_to_sqlite(leads):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    saved = 0
    skipped = 0
    for lead in leads:
        name = lead.get('name')
        source_account = lead.get('source_account', '')
        context = lead.get('context', '')
        intent_score = lead.get('intent_score', 0)
        interest_level = lead.get('interest_level', '')

        # Upsert: jika nama + source_account sudah wujud, gabungkan konteks dan ambil skor tertinggi
        try:
            cursor.execute('''
                INSERT INTO leads (name, niche, area, intent_score, interest_level, phone, email, social_link, platform, source_type, context, plate_number, keyword, source_account, created_at, brand)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, source_account) DO UPDATE SET
                    context = leads.context || ' | ' || excluded.context,
                    intent_score = MAX(leads.intent_score, excluded.intent_score),
                    interest_level = CASE
                        WHEN MAX(leads.intent_score, excluded.intent_score) >= 0.8 THEN 'Hot'
                        WHEN MAX(leads.intent_score, excluded.intent_score) >= 0.6 THEN 'Warm'
                        ELSE 'Cold'
                    END,
                    brand = excluded.brand
            ''', (
                name, lead.get('niche'), lead.get('area'), intent_score, interest_level,
                lead.get('phone', ''), lead.get('email', ''), lead.get('social_link', ''),
                lead.get('platform'), lead.get('source_type'), context, lead.get('plate_number', ''),
                lead.get('keyword'), source_account, datetime.now().isoformat(),
                lead.get('brand', '')
            ))
            saved += 1
            print(f"[SIMPAN] Berjaya simpan @{name} ke SQLite (skor={intent_score}).")
        except Exception as e:
            print(f"[ERROR] Gagal simpan @{name} ke SQLite: {e}")
            skipped += 1
    conn.commit()
    conn.close()
    print(f"[DONE] {saved} leads disimpan ke SQLite, {skipped} lead gagal.")

def sync_sqlite_to_supabase():
    print("[INFO] Memulakan sinkronisasi SQLite ke Supabase...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM leads").fetchall()
    conn.close()

    if not rows:
        print("[WARN] Tiada data di SQLite.")
        return

    payload = []
    for r in rows:
        # Betulkan isu tarikh kosong ("") kepada None (NULL)
        created_at = r['created_at'] if r['created_at'] else None
        processed_at = r['processed_at'] if r['processed_at'] else None

        payload.append({
            "name": r['name'],
            "niche": r['niche'],
            "area": r['area'],
            "intent_score": r['intent_score'],
            "interest_level": r['interest_level'],
            "phone": r['phone'] or "",
            "email": r['email'] or "",
            "social_link": r['social_link'] or "",
            "platform": r['platform'] or "Facebook",
            "source_type": r['source_type'] or "Comment",
            "context": r['context'] or "",
            "plate_number": r['plate_number'] or "",
            "keyword": r['keyword'] or "",
            "source_account": r['source_account'] or "",
            "brand": r['brand'] or "",
            "created_at": created_at,
            "processed_at": processed_at
        })

    print(f"[SYNC] Menghantar {len(payload)} data ke Supabase...")

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    res = requests.post(f"{SUPABASE_URL}/rest/v1/leads?on_conflict=name,source_account", headers=headers, json=payload)
    if res.status_code in [200, 201]:
        print(f"[SYNC] Berjaya! {len(payload)} data dihantar ke Supabase.")
    else:
        print(f"[SYNC] Gagal! {res.status_code} {res.text}")

# ================= SCRAPER =================
def scrape_facebook(niche, area):
    keywords = generate_smart_search_queries(f"{niche} di {area}")
    print(f"[INFO] Keyword AI: {keywords}")

    all_leads = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        if os.path.exists(COOKIES_PATH):
            with open(COOKIES_PATH, 'r') as f:
                context.add_cookies(json.load(f))
            print("[INFO] Cookie dimuatkan.")

        page = context.new_page()
        page.goto(TARGET_FB_URL)
        page.wait_for_timeout(5000)

        for keyword in keywords:
            print(f"=== Mencari: {keyword} ===")
            try:
                # Taip carian
                search_box = page.locator('input[placeholder*="Cari"], input[aria-label="Search"]').first
                if search_box.count() > 0:
                    search_box.fill(keyword)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(4000)
                    
                    # Scroll
                    for _ in range(4):
                        page.mouse.wheel(0, 2000)
                        page.wait_for_timeout(1000)

                    # Ekstrak KOMEN dari ul > li (HTML selector yang kebal)
                    posts = page.locator('div[role="article"]').all()
                    
                    for i, post in enumerate(posts):
                        try:
                            # AUTO-CLICK butang "Lihat lagi komen" / "See more comments" SEBELUM extract
                            see_more_texts = ["Lihat lagi komen", "See more comments", "View more comments", "Tampilkan lebih banyak komen"]
                            for sm_text in see_more_texts:
                                try:
                                    btns = page.get_by_text(sm_text).all()
                                    for btn in btns:
                                        try:
                                            btn.click()
                                            page.wait_for_timeout(1000)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                            # Cari ul di dalam post (Facebook letak komen dalam <ul>)
                            ul_elements = post.locator('ul').all()
                            
                            for ul_el in ul_elements:
                                try:
                                    li_elements = ul_el.locator('li').all()
                                except Exception:
                                    continue
                                
                                for li_el in li_elements:
                                    try:
                                        # Ambil nama dari <a> atau <strong> dalam li
                                        name_el = li_el.locator('a, strong').first
                                        name = name_el.inner_text(timeout=1000).strip() if name_el.count() > 0 else "Unknown"
                                        
                                        # Ambil teks komen dari div[dir="auto"] dalam li
                                        text_el = li_el.locator('div[dir="auto"]').first
                                        comment_text = text_el.inner_text(timeout=2000).strip() if text_el.count() > 0 else ""
                                        
                                        if not comment_text or len(comment_text) <= 5:
                                            continue
                                        if len(comment_text) > 100:
                                            continue
                                        
                                        comment_lower = comment_text.lower()
                                        
                                        # Buang iklan penjual / spec kereta
                                        skip_keywords = ["perodua", "myvi", "honda", "toyota", "mudah.my", "waranti", "lihat butiran"]
                                        if any(k in comment_lower for k in skip_keywords):
                                            continue
                                        
                                        # Skip jika ada tahun 2010-2025
                                        if re.search(r'\b(201[0-9]|202[0-5])\b', comment_text):
                                            continue
                                        
                                        # Hanya simpan jika ada perkataan niat beli
                                        buying_keywords = ["berapa", "pm", "minat", "loan", "masih ada", "nak", "detail", "info"]
                                        if not any(k in comment_lower for k in buying_keywords):
                                            continue
                                        
                                        score = parse_intent(comment_text)
                                        
                                        if score >= 0.5:
                                            all_leads.append({
                                                "name": name,
                                                "niche": niche,
                                                "area": area,
                                                "context": comment_text,
                                                "intent_score": score,
                                                "interest_level": "Hot" if score > 0.8 else "Warm",
                                                "platform": "Facebook",
                                                "source_type": "Comment",
                                                "keyword": keyword
                                            })
                                    except Exception:
                                        continue
                        except Exception:
                            continue
            except Exception as e:
                print(f"[WARN] Ralat carian keyword '{keyword}': {e}")
                continue

            print(f"[INFO] Kumulatif leads: {len(all_leads)}")
            if len(all_leads) >= 20: break
        
        # Simpan Cookie
        with open(COOKIES_PATH, 'w') as f:
            json.dump(context.cookies(), f)
            
        browser.close()
    
    return all_leads

# ================= MAIN =================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", default="Jualan Kereta")
    parser.add_argument("--area", default="Tangkak")
    args = parser.parse_args()

    init_db()
    
    print(f"[INFO] Memulakan Hunter untuk {args.niche} di {args.area}...")
    leads = scrape_facebook(args.niche, args.area)
    
    if leads:
        save_to_sqlite(leads)
        sync_sqlite_to_supabase()
    else:
        print("[WARN] Tiada leads baru dijumpai.")