#!/usr/bin/env python3
"""
Global Scout - Cari Live TikTok secara automatik berdasarkan carian,
simpan username yang mempunyai viewer > 50 ke targets.txt.
"""

import random
import re
import argparse
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from human_behavior import human_delay, human_typing, human_scroll

TARGETS_PATH = Path(__file__).parent / "targets.txt"
VIEWER_THRESHOLD = 50
TIKTOK_HOME = "https://www.tiktok.com"

SUPABASE_URL = "https://ypcccthqbnkurkslsvdi.supabase.co"
SUPABASE_KEY = "sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj"


def close_tiktok_popup(page):
    """Tutup popup 'Get the full app experience' kalau muncul."""
    try:
        close_btn = page.locator('button[aria-label="Close"], div[role="button"][aria-label="Close"], .css-1s815x0').first
        if close_btn.is_visible(timeout=3000):
            close_btn.click(force=True)
            print("[SCOUT] Popup di-close (butang X).")
            return
    except Exception:
        pass

    try:
        page.keyboard.press("Escape")
        print("[SCOUT] Popup di-cuba tutup via Escape key.")
    except Exception:
        pass

    print("[SCOUT] Tiada popup dikesan.")


def discover_lives(brand="proton"):
    found_usernames = []
    search_query = f"{brand} live"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768}
            )
            page = context.new_page()
            stealth = Stealth()
            stealth.apply_stealth_sync(page)

            # --- Human Simulation: Buka page carian TikTok (Desktop) ---
            search_url = f"https://www.tiktok.com/search?q={brand}+live"
            try:
                print(f"[SCOUT] Membuka carian TikTok (Desktop): {search_url}")
                page.goto(search_url, timeout=60000)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(5000)

                # --- Tutup popup login wall ---
                try:
                    close_btn = page.locator('div[role="dialog"] svg[aria-label="Close"], div[role="dialog"] button[aria-label="Close"], div[role="dialog"] path[d*="M"]').first
                    if close_btn.is_visible(timeout=3000):
                        close_btn.click(force=True)
                        print("[SCOUT] Popup login ditutup (X).")
                        human_delay(2, 4)
                except Exception as e:
                    print(f"[SCOUT] Gagal tutup popup login: {e}")

                close_tiktok_popup(page)
                page.screenshot(path="debug_desktop_search.png")
                print("[SCOUT] Screenshot disimpan ke debug_desktop_search.png.")
            except Exception as e:
                print(f"[SCOUT] Gagal muat carian TikTok: {e}")
                browser.close()
                return []

            # Scroll sikit ke bawah supaya result muncul (macam manusia)
            human_scroll(page)
            human_delay(2.0, 4.0)

            # --- Cuba klik tab "LIVE" pada page hasil carian ---
            try:
                live_tab = page.locator('div[role="tab"]:has-text("LIVE"), span:has-text("LIVE")').first
                if live_tab.is_visible(timeout=3000):
                    live_tab.click()
                    page.wait_for_load_state("networkidle")
                    human_delay(5.0, 9.0)
                    human_scroll(page)
                    close_tiktok_popup(page)
                    page.screenshot(path="debug_live_page.png")
                    page.screenshot(path="debug_live_page_after_wait.png")
                    print("[SCOUT] Tab LIVE ditekan. Screenshot disimpan ke debug_live_page_after_wait.png.")
            except Exception:
                print("[SCOUT] Tab LIVE tidak jumpa, lanjut dengan page carian semasa.")

            # --- Verifikasi masih di page search/live ---
            current_url = page.url
            if "/search" not in current_url and "/foryou" in current_url:
                print(f"[SCOUT] Gagal cari Live. TikTok block IP atau layout berubah. URL: {current_url}")
                browser.close()
                return []

            # Tunggu kad Live muncul sebelum extract
            try:
                page.wait_for_selector('div[data-e2e="search-live-card"], div[data-e2e="search-result-card"], a[href*="/@"]', timeout=10000)
            except Exception:
                print("[SCOUT] Tiada kad Live jumpa selepas timeout.")
                browser.close()
                return []

            # Scroll perlahan untuk muat lebih banyak kad Live
            for i in range(6):
                try:
                    human_scroll(page)
                except Exception as e:
                    print(f"[SCOUT] Ralat scroll: {e}")
                    break

            # Pastikan masih di search sebelum extract
            if "/search" not in page.url:
                print(f"[SCOUT] Page bukan search ({page.url}), hentikan ekstraksi.")
                browser.close()
                return found_usernames

            # Cari elemen kad Live (bijak: guna data-e2e dahulu)
            live_cards = page.locator('div[data-e2e="search-live-card"], div[data-e2e="search-result-card"]').all()

            if len(live_cards) == 0:
                # Fallback: cuba cari link profil biasa
                live_cards = page.locator('a[href*="/@"]').all()

            if len(live_cards) == 0:
                print("[SCOUT] Tiada Live untuk keyword ini. Mungkin S.A. guna hashtag lain atau tiada Live sekarang.")
                browser.close()
                return found_usernames

            print(f"[SCOUT] Dapati {len(live_cards)} kad profil/posibiliti.")

            for card in live_cards:
                try:
                    # Ambil href dari tag <a> di dalam kad
                    href = ""
                    try:
                        a_tag = card.locator('a').first
                        href = a_tag.get_attribute("href") or ""
                    except Exception:
                        href = card.get_attribute("href") or ""

                    if not href or "/@" not in href:
                        continue

                    username = href.split("/@")[-1].split("/")[0].strip()
                    if not username or username.startswith("search"):
                        continue

                    card_text = card.inner_text(timeout=2000)

                    # --- Extract viewer count ---
                    viewer_count = 0

                    # Cari text yang mengandungi "penonton", "viewers", atau angka dengan K/M
                    viewers_match = re.search(r'([\d,.]+)\s*([KMkM]?)', card_text)
                    if viewers_match:
                        raw = viewers_match.group(1).replace(",", "").replace(".", "")
                        suffix = viewers_match.group(2).upper()
                        try:
                            base = int(raw)
                            if suffix == "K":
                                viewer_count = base * 1000
                            elif suffix == "M":
                                viewer_count = base * 1000000
                            else:
                                viewer_count = base
                        except ValueError:
                            viewer_count = 0

                    # Pendekatan 2: cari teks yang mesti mengandungi kata "viewer" / "penonton"
                    if viewer_count == 0:
                        viewers_match2 = re.search(r'([\d,.]+)\s*(?:viewer|penonton|penguji)', card_text, re.IGNORECASE)
                        if viewers_match2:
                            raw = viewers_match2.group(1).replace(",", "").replace(".", "")
                            try:
                                viewer_count = int(raw)
                            except ValueError:
                                viewer_count = 0

                    # Deteksi indikator merah "LIVE" (fallback kalau viewer count tak jumpa)
                    is_live_badge = False
                    try:
                        live_badge = card.locator('text=LIVE, text=Live, text=live').first
                        if live_badge.is_visible(timeout=1000):
                            is_live_badge = True
                    except Exception:
                        pass

                    # Logik lulus:
                    # - Jika viewer_count > 50 => LULUS
                    # - Jika viewer_count == 0 TAPI ada badge LIVE => masih masuk (fallback), biarkan hunter verify
                    passed = False
                    if viewer_count > VIEWER_THRESHOLD:
                        passed = True
                    elif viewer_count == 0 and is_live_badge:
                        passed = True  # fallback: assume live, let hunter verify

                    status = "LULUS" if passed else "GAGAL"
                    print(f"[SCOUT] Menjumpai Live: @{username} (Viewers: {viewer_count}) - [{status}]")

                    if passed and username not in found_usernames:
                        found_usernames.append(username)

                except Exception as e:
                    print(f"[SCOUT] Ralat proses kad: {e}")
                    continue

            browser.close()

    except Exception as e:
        print(f"[SCOUT] Ralat kritikal: {e}")

    # Simpan ke Supabase scout_targets (bagi Hunter baca nanti)
    try:
        if found_usernames:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            }
            rows = [{"username": u, "status": "pending"} for u in found_usernames]
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/scout_targets",
                headers=headers,
                json=rows,
                timeout=30,
            )
            if res.status_code in [200, 201]:
                print(f"[SCOUT] Disimpan {len(found_usernames)} username ke Supabase scout_targets.")
            else:
                print(f"[SCOUT] Gagal simpan ke Supabase: {res.status_code} {res.text}")
        else:
            print("[SCOUT] Tiada live yang lulus penapis viewer > 50.")
    except Exception as e:
        print(f"[SCOUT] Ralat simpan ke Supabase scout_targets: {e}")

    return found_usernames


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Global Scout - Cari Live TikTok ikut Brand")
    parser.add_argument("--brand", type=str, default="proton", help="Brand kereta (contoh: proton, toyota, honda, perodua)")
    args = parser.parse_args()
    discover_lives(brand=args.brand)
