#!/usr/bin/env python3
"""Parse Facebook HTML dan ekstrak lead daripada JSON tags dan DOM scraping."""

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

HTML_PATH = Path(__file__).parent / "fb_page_content.html"
OUTPUT_PATH = Path(__file__).parent / "parsed_leads.json"


def extract_leads_from_json(obj, path=""):
    """Recursive: cari objek yang ada author.name/user.name + message.text/body.text/comment.text + url/profile_url."""
    results = []

    if isinstance(obj, dict):
        # Cek jika objek ini mengandungi field lead
        author_name = ''
        if isinstance(obj.get('author'), dict):
            author_name = obj.get('author', {}).get('name', '')
        user_name = ''
        if isinstance(obj.get('user'), dict):
            user_name = obj.get('user', {}).get('name', '')
        name = author_name or user_name or obj.get('name', '') or obj.get('username', '')

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

        profile_url = obj.get('profile_url', '') or obj.get('url', '') or obj.get('permalink_url', '')

        # Jika ada nama dan teks yang panjang, anggap sebagai lead
        if name and text_content and len(str(text_content).strip()) > 10:
            results.append({
                'phase': 'json',
                'username': str(name).strip(),
                'platform': 'Facebook',
                'source_type': 'Comment' if text_content else 'Post',
                'context': str(text_content).strip(),
                'profile_url': str(profile_url).strip(),
                'created_at': obj.get('created_time', '') or obj.get('timestamp', ''),
                'url': obj.get('url', ''),
            })
            return results

        # Traverse semua nilai dalam dict
        for k, v in obj.items():
            results.extend(extract_leads_from_json(v, path + "." + str(k)))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(extract_leads_from_json(item, path + "[" + str(i) + "]"))

    return results


def main():
    if not HTML_PATH.exists():
        print(f"[ERROR] Fail HTML tidak jumpa: {HTML_PATH}")
        return

    print(f"[INFO] Membaca fail HTML: {HTML_PATH}")
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print(f"[INFO] Saiz HTML: {len(html_content)} aksara")

    soup = BeautifulSoup(html_content, 'html.parser')

    # ============================================================
    # FASA 1: Semua tag <script type="application/json">
    # ============================================================
    json_tags = soup.find_all('script', type='application/json')
    print(f"[INFO] Dapat {len(json_tags)} tag <script type=\"application/json\">")

    all_leads = []
    json_hits = 0
    for i, tag in enumerate(json_tags):
        try:
            content = tag.string or tag.get_text()
            if not content or not content.strip():
                continue
            data = json.loads(content)
            leads = extract_leads_from_json(data)
            if leads:
                json_hits += len(leads)
                print(f"[INFO] JSON Tag #{i+1}: Dapat {len(leads)} lead")
                all_leads.extend(leads)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"[WARN] JSON Tag #{i+1} ralat: {e}")

    print(f"[INFO] Jumlah lead dari JSON: {json_hits}")

    # ============================================================
    # FASA 2: DOM Scraping - cari teks dalam <div> / <span>
    # ============================================================
    print(f"[INFO] Memulakan DOM scraping untuk teks dalam <div> / <span>...")

    dom_texts = []
    seen_texts = set()

    # Kata-kata UI Facebook yang perlu difilter (bukan konten post/komen)
    ui_stopwords = {
        'pemberitahuan', 'notifikasi', 'semua', 'belum dibaca', 'baharu',
        'lihat semua', 'lihat lagi', 'view more', 'see more', 'tampilkan lebih',
        'bukan', 'sukakan', 'komen', 'kongsi', 'like', 'comment', 'share',
        'follow', 'ikut', 'muncul', 'baru', 'terkini', 'maklumat', 'info',
        'akaun', 'profil', 'masuk', 'daftar', 'log masuk', 'log keluar',
        'cari', 'search', 'beranda', 'home', 'watch', 'tonton', 'marketplace',
        'grup', 'game', 'video', 'reels', 'story', 'cerita', 'pesan', 'message',
        'rangkaian', 'friends', 'teman', 'orang', 'people', 'dikomeni',
        'direaksi', 'disebutkan', 'disebabkan', 'disimpan', 'disarankan',
        'meta', 'datang', 'dikemas', 'kini', 'kepada', 'tidak', 'lama',
    }

    # Frasa sistem Facebook yang pasti bukan konten pengguna
    system_phrases = [
        'akaun meta akan datang',
        'bilangan pemberitahuan yang belum dibaca',
        'anda akan dikemas kini',
        'pemberitahuan semua',
    ]

    # Cari semua elemen yang mungkin mengandungi teks post/komen
    candidates = soup.find_all(['div', 'span', 'p', 'article'])

    for elem in candidates:
        text = elem.get_text(strip=True)
        if not text or len(text) <= 20:
            continue

        text_lower = text.lower()

        # Filter frasa sistem Facebook
        is_system = False
        for phrase in system_phrases:
            if phrase in text_lower:
                is_system = True
                break
        if is_system:
            continue

        # Filter teks yang merupakan UI Facebook (hanya kata-kata UI, tanpa konten sebenar)
        words = text_lower.split()
        if len(words) <= 3:
            continue

        # Jika semua kata dalam text adalah UI stopwords, lewati
        non_ui_words = [w for w in words if w not in ui_stopwords and len(w) > 2]
        if len(non_ui_words) == 0:
            continue

        # Elak duplicate
        if text not in seen_texts:
            seen_texts.add(text)

            # Coba cari username dari elemen terdekat
            username = ''
            parent = elem.find_parent(['div', 'article'])
            if parent:
                name_el = parent.find(['span', 'a', 'strong'], string=re.compile(r'.{2,50}'))
                if name_el:
                    username = name_el.get_text(strip=True)

            dom_texts.append({
                'phase': 'dom',
                'username': username,
                'platform': 'Facebook',
                'source_type': 'DOM_Text',
                'context': text,
                'profile_url': '',
                'created_at': '',
                'url': '',
            })

    print(f"[INFO] Jumlah teks unik dari DOM: {len(dom_texts)}")
    all_leads.extend(dom_texts)

    # Simpan ke parsed_leads.json
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_leads, f, indent=2, ensure_ascii=False)

    print(f"\n[INFO] Jumlah lead yang berjaya diekstrak (JSON + DOM): {len(all_leads)}")
    print(f"[INFO] Disimpan ke: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
