import re

with open('backend/scout_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_marker = '# KOREK KOMEN: cari elemen komen dalam post'
start_line = None
for i, line in enumerate(lines):
    if start_marker in line:
        start_line = i
        break

if start_line is None:
    print('START MARKER NOT FOUND')
    exit(1)

print(f'Start line: {start_line}: {lines[start_line].rstrip()}')

# Find end line: look for 'except Exception as e:' at 24 spaces indent (same level as outer container loop)
# after start_line
end_line = None
for i in range(start_line + 1, len(lines)):
    stripped = lines[i]
    # Check if line starts with 24 spaces then 'except Exception as e:'
    if stripped.startswith('                        except Exception as e:') and 'Gagal proses komen' in stripped:
        end_line = i
        break

if end_line is None:
    print('END LINE NOT FOUND - trying alternative end marker')
    # Alternative: find any 'except Exception as e:' at 24 spaces after start_line
    for i in range(start_line + 1, len(lines)):
        if lines[i].startswith('                        except Exception as e:'):
            end_line = i
            print(f'Found alternative end at line {i}: {lines[i].rstrip()}')
            break

if end_line is None:
    print('END LINE NOT FOUND')
    exit(1)

print(f'End line: {end_line}: {lines[end_line].rstrip()}')

# New block content
new_block = '''                        # KOREK KOMEN: cari div[role="article"] -> ul -> li -> (nama, teks komen)
                        # Buang teks sampah penjual/iklan
                        trash_keywords = [
                            "Ditaja", "Lihat seterusnya", "Dijual", "CARSOME",
                            "Harga tawaran", "Jom cari", "Hubungi", "Sila klik",
                            "Awam ·", "ahli", "Sertai",
                        ]

                        # Cari ul di dalam article (Facebook simpan komen dalam <ul><li>)
                        ul_elements = []
                        try:
                            ul_elements = article.locator('ul').all()
                        except Exception:
                            pass

                        print(f"[INFO] Dapat {len(ul_elements)} <ul> container dalam post #{i}.")

                        for ul_idx, ul_el in enumerate(ul_elements):
                            try:
                                li_elements = ul_el.locator('li').all()
                                print(f"[INFO]   <ul>#{ul_idx}: Dapat {len(li_elements)} <li>.")
                            except Exception:
                                continue

                            for li_idx, li_el in enumerate(li_elements):
                                try:
                                    # Ambil nama pengguna dari <a> atau <span> dalam li
                                    commenter_name = ''
                                    try:
                                        name_el = li_el.locator('a[role="link"], span[role="link"], a, span').first
                                        if name_el:
                                            commenter_name = name_el.inner_text(timeout=3000).strip()
                                    except Exception:
                                        pass

                                    # Ambil teks komen dari div[dir="auto"] dalam li yang sama
                                    comment_text = ''
                                    try:
                                        text_el = li_el.locator('div[dir="auto"]').first
                                        if text_el:
                                            comment_text = text_el.inner_text(timeout=3000).strip()
                                    except Exception:
                                        pass

                                    if not comment_text or len(comment_text) <= 5:
                                        continue

                                    # --- BUANG TEKS SAMPAAH (penjual/iklan) ---
                                    comment_lower = comment_text.lower()
                                    is_trash = False
                                    for trash in trash_keywords:
                                        if trash.lower() in comment_lower:
                                            is_trash = True
                                            break
                                    if is_trash:
                                        continue

                                    # Skip jika hanya kata-kata sistem
                                    words = comment_lower.split()
                                    if len(words) <= 2:
                                        continue
                                    non_system_words = [w for w in words if w not in FB_SYSTEM_WORDS and len(w) > 2]
                                    if len(non_system_words) == 0:
                                        continue

                                    # --- Ambil link profil ---
                                    profile_url = ''
                                    try:
                                        link_el = li_el.locator('a[role="link"], a').first
                                        if link_el:
                                            href = link_el.get_attribute('href')
                                            if href:
                                                profile_url = href
                                    except Exception:
                                        pass

                                    # --- Ambil No. Plat (jika ada dalam teks komen) ---
                                    plate_number = ''
                                    try:
                                        plate_match = re.search(r'\b([A-Z]{1,2}\s*\d{1,4}\s*[A-Z]{0,2})\b', comment_text)
                                        if plate_match:
                                            plate_number = plate_match.group(0).strip()
                                    except Exception:
                                        pass

                                    # --- Bersihkan teks komen ---
                                    clean_name, clean_phone, clean_price, clean_ctx = clean_post_text(comment_text)
                                    if not clean_ctx:
                                        clean_ctx = comment_text

                                    # Simpan komen sebagai lead (pembeli)
                                    all_leads.append({
                                        'username': commenter_name or clean_name,
                                        'platform': 'Facebook',
                                        'source_type': 'Comment',
                                        'context': clean_ctx,
                                        'price': clean_price,
                                        'phone': clean_phone,
                                        'plate_number': plate_number,
                                        'profile_url': profile_url,
                                        'created_at': '',
                                        'url': target_url,
                                        'keyword': keyword,
                                        'comment_index': li_idx,
                                    })
                                    kw_leads += 1

                                except Exception:
                                    continue

                            except Exception:
                                continue'''

# Replace lines[start_line:end_line+1] with new_block
new_lines = lines[:start_line] + [new_block + '\n'] + lines[end_line + 1:]
new_content = ''.join(new_lines)

with open('backend/scout_engine.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('REPLACEMENT DONE')
print(f'Replaced lines {start_line} to {end_line} (inclusive)')
