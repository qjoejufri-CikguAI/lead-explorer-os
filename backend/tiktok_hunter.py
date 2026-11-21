#!/usr/bin/env python3
"""
TikTok Hunter Multi - Pantau banyak TikTok Live serentak dengan asyncio Queue & Semaphore.
Simpan ke SQLite dan sinkronkan ke Supabase.
"""

import argparse
import asyncio
import json
import os
import sys
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scout_engine import init_db, save_to_sqlite, sync_sqlite_to_supabase, parse_intent

from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, JoinEvent, ConnectEvent, DisconnectEvent

DATA_PATH = Path(__file__).parent / "tiktok_hunter_multi_data.json"
TARGETS_PATH = Path(__file__).parent / "targets.txt"

SUPABASE_URL = "https://ypcccthqbnkurkslsvdi.supabase.co"
SUPABASE_KEY = "sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj"

# Global state
seen_comments = set()
seen_joins = set()
data_queue = asyncio.Queue()
semaphore = asyncio.Semaphore(3)
target_brands = {}      # username -> brand
active_monitors = set()  # username yang sedang dipantau


def save_to_json(data_list):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data_list, f, indent=2, ensure_ascii=False)


def fetch_targets_from_supabase():
    """Ambil semua username + brand dari table scout_targets di Supabase.
    HANYA ambil target yang berstatus 'hunting' sahaja."""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/scout_targets?select=username,brand,status&status=eq.hunting&order=created_at.asc",
            headers=headers,
            timeout=30,
        )
        if res.status_code != 200:
            print(f"[WARN] Gagal fetch scout_targets dari Supabase: {res.status_code} {res.text}")
            return []

        data = res.json()
        results = []
        for row in data:
            username = row.get('username')
            brand = row.get('brand') or ''
            status = row.get('status') or 'pending'
            if username and status == 'hunting':
                results.append({"username": username, "brand": brand, "status": status})
                target_brands[username] = brand

        # Tulis ke targets.txt (backward compat) — hanya hunting targets
        usernames = [r["username"] for r in results]
        if usernames:
            TARGETS_PATH.write_text("\n".join(usernames) + "\n", encoding="utf-8")
            print(f"[INFO] Dapat {len(results)} target (status=hunting) dari Supabase scout_targets.")
        else:
            TARGETS_PATH.write_text("", encoding="utf-8")
            print("[INFO] Tiada target status=hunting dalam database scout_targets.")

        return results
    except Exception as e:
        print(f"[WARN] Ralat fetch scout_targets: {e}")
        return []


async def queue_worker():
    """Worker yang ambil data dari queue, dedup, score AI, simpan ke SQLite."""
    while True:
        item = await data_queue.get()
        try:
            # Kumpulkan semua item dari queue sebelum proses (batch dedup)
            batch = [item]
            while True:
                try:
                    next_item = data_queue.get_nowait()
                    batch.append(next_item)
                except asyncio.QueueEmpty:
                    break

            # Pre-database dedup: gabungkan berdasarkan name + source_account
            merged_leads = {}
            for item in batch:
                event_type = item["type"]
                if event_type == "comment_lead":
                    lead = item["lead"]
                    key = f"{lead['name']}_{lead.get('source_account', '')}"
                    if key not in merged_leads:
                        merged_leads[key] = lead.copy()
                    else:
                        existing = merged_leads[key]
                        existing_context = existing.get("context", "")
                        new_context = lead.get("context", "")
                        if new_context and new_context not in existing_context:
                            existing["context"] = existing_context + " | " + new_context
                        existing["intent_score"] = max(existing.get("intent_score", 0), lead.get("intent_score", 0))
                elif event_type == "join_lead":
                    lead = item["lead"]
                    key = f"{lead['name']}_{lead.get('source_account', '')}"
                    if key not in merged_leads:
                        merged_leads[key] = lead.copy()

            save_to_sqlite(list(merged_leads.values()))
            for lead in merged_leads.values():
                print(f"[{lead['interest_level']}] SQLite: {lead['name']} (score={lead['intent_score']})")

        except Exception as e:
            print(f"[ERROR] Worker gagal memproses item: {e}")
        finally:
            for _ in batch:
                data_queue.task_done()


async def poll_new_targets():
    """Background task: semak Supabase setiap 90 saat untuk target baru.
    Cipta monitor_live untuk username baru tanpa duplicate."""
    loop = asyncio.get_running_loop()
    while True:
        await asyncio.sleep(90)  # 1.5 minit
        try:
            targets = await loop.run_in_executor(None, fetch_targets_from_supabase)
            for t in targets:
                username = t["username"]
                brand = t.get("brand", "")
                if username not in active_monitors:
                    active_monitors.add(username)
                    task = asyncio.create_task(monitor_live(username, brand))
                    # Sahkan aktif kembali set bila task tamat
                    task.add_done_callback(lambda tsk, u=username: active_monitors.discard(u))
                    print(f"[INFO] Target baru dipantau: @{username} (brand: {brand or '-'})")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[WARN] Ralat poll target baru: {e}")


async def monitor_live(username: str, brand: str = ""):
    """Pantau satu TikTok Live hingga tamat, kemudian lepaskan semaphore."""
    async with semaphore:
        print(f"[INFO] Memantau @{username}...")

        client = TikTokLiveClient(unique_id=username)

        # Buffer untuk mengumpulkan komen per user sebelum flush (untuk scoring)
        user_comments = {}  # username -> list of comment texts
        last_comment_time = None  # untuk deteksi silent block

        @client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            print(f"[CONNECT] @{username} bersambung ke TikTok Live.")

        @client.on(DisconnectEvent)
        async def on_disconnect(event: DisconnectEvent):
            print(f"[DISCONNECT] @{username} putus sambungan dari TikTok Live.")

        async def silent_block_watcher():
            """Peringatan jika ada sambungan tapi tiada data komen selama 30 saat."""
            nonlocal last_comment_time
            while True:
                await asyncio.sleep(30)
                if last_comment_time is not None:
                    idle = asyncio.get_event_loop().time() - last_comment_time
                    if idle > 30:
                        print(f"[WARN] Silent block? @{username} sambung tapi tiada komen selama {int(idle)} saat.")

        @client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            user = event.user.unique_id
            comment = event.comment
            # Print SETIAP komen yang masuk, walaupun tak lulus skor/syarat
            print(f"[KOMEN] @{user}: {comment}")
            last_comment_time = asyncio.get_event_loop().time()
            comment_key = f"{username}_{user}_{comment}"
            if comment_key in seen_comments:
                return
            seen_comments.add(comment_key)

            # Simpan ke queue segera (bukan buffer sahaja) supaya save_to_sqlite dipanggil
            lead = {
                "name": user,
                "niche": "TikTok Live",
                "area": "",
                "intent_score": parse_intent(comment),
                "interest_level": "Hot" if parse_intent(comment) >= 0.8 else "Warm" if parse_intent(comment) >= 0.6 else "Cold",
                "phone": "",
                "email": "",
                "social_link": f"https://tiktok.com/@{user}",
                "platform": "TikTok",
                "source_type": "Comment",
                "context": comment,
                "plate_number": "",
                "keyword": "",
                "source_account": username,
                "brand": brand,
                "created_at": datetime.now().isoformat(),
            }
            await data_queue.put({
                "type": "comment_lead",
                "lead": lead,
            })

            # Juga simpan dalam buffer untuk agregasi scoring akhir
            if user not in user_comments:
                user_comments[user] = []
            user_comments[user].append(comment)

        @client.on(JoinEvent)
        async def on_join(event: JoinEvent):
            join_key = f"{username}_{event.user.unique_id}"
            if join_key in seen_joins:
                return
            seen_joins.add(join_key)
            # JoinEvent (penonton masuk) selalu skor rendah & konteks "Masuk live".
            # Jangan masukkan ke queue supaya tidak sesak database.
            return

        # Start silent block watcher
        watcher_task = asyncio.create_task(silent_block_watcher())

        try:
            await client.connect()
        except Exception as e:
            print(f"[ERROR] @{username} gagal connect: {e}")
            watcher_task.cancel()
        finally:
            watcher_task.cancel()
            # Flush semua komen yang masih ada dalam buffer (untuk agregasi scoring akhir)
            for user, comments in user_comments.items():
                combined_text = " | ".join(comments)
                scores = [parse_intent(c) for c in comments]
                best_score = max(scores) if scores else 0.6

                lead = {
                    "name": user,
                    "niche": "TikTok Live",
                    "area": "",
                    "intent_score": best_score,
                    "interest_level": "Hot" if best_score >= 0.8 else "Warm" if best_score >= 0.6 else "Cold",
                    "phone": "",
                    "email": "",
                    "social_link": f"https://tiktok.com/@{user}",
                    "platform": "TikTok",
                    "source_type": "Comment",
                    "context": combined_text,
                    "plate_number": "",
                    "keyword": "",
                    "source_account": username,
                    "brand": brand,
                    "created_at": datetime.now().isoformat(),
                }
                await data_queue.put({
                    "type": "comment_lead",
                    "lead": lead,
                })

            try:
                await client.disconnect()
            except Exception:
                pass
            print(f"[INFO] @{username} Live tamat/disconnect. Lepasan semaphore.")


async def main(targets_file: str):
    # Ambil target dari Supabase scout_targets (Human-in-the-loop dari Dashboard)
    targets = fetch_targets_from_supabase()  # list of {"username":..., "brand":...}

    # Sahkan active_monitors dan target_brands untuk initial targets
    for t in targets:
        active_monitors.add(t["username"])
        target_brands[t["username"]] = t.get("brand", "")

    # Baca targets dari fail (backward compat)
    targets_path = Path(targets_file)
    if not targets_path.exists():
        print(f"[INFO] Cipta fail contoh targets.txt...")
        targets_path.write_text("@dealer_kereta\n@jualan_motor\n", encoding="utf-8")

    with open(targets_path, "r", encoding="utf-8") as f:
        file_targets = [line.strip().replace("@", "") for line in f if line.strip()]

    # Gabungkan file_targets yang belum ada dalam active_monitors
    for u in file_targets:
        if u not in active_monitors:
            active_monitors.add(u)
            target_brands[u] = target_brands.get(u, "")

    if not active_monitors:
        print("[INFO] Tiada target dalam database. Hunter berhenti.")
        return

    print(f"[INFO] Dapat {len(active_monitors)} target: {sorted(active_monitors)}")

    # Init database
    init_db()

    # Start queue worker
    worker_task = asyncio.create_task(queue_worker())

    # Start background poll task (cek target baru setiap 90 saat)
    poll_task = asyncio.create_task(poll_new_targets())

    # Cipta monitor tasks untuk semua target awal (semaphore hadkan concurrency kepada 3)
    monitor_tasks = []
    for u in sorted(active_monitors):
        task = asyncio.create_task(monitor_live(u, target_brands.get(u, "")))
        monitor_tasks.append(task)

    try:
        # Tunggu poll task (berjalan selamanya). Monitor tasks berjalan secara independent.
        await poll_task
    except KeyboardInterrupt:
        print("\n[INFO] Dihentikan oleh pengguna.")
        poll_task.cancel()
    finally:
        # Berhenti poll task
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass

        # Batalkan semua monitor tasks dan tunggu mereka selesai (untuk flush queue)
        print("[INFO] Menghentikan semua monitor tasks...")
        for task in monitor_tasks:
            task.cancel()
        if monitor_tasks:
            await asyncio.gather(*monitor_tasks, return_exceptions=True)

        # Batalkan worker task (jangan tunggu data_queue.join() yang boleh hang)
        print("[INFO] Menghentikan worker...")
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Sync ke Supabase - PENTING: ini mesti berjalan sebelum Python mati
        print("[INFO] Memulakan sinkronisasi ke Supabase...")
        sync_sqlite_to_supabase()
        print("[INFO] Selesai.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TikTok Hunter Multi - Multi-account Live monitor")
    parser.add_argument("--targets_file", default="targets.txt", help="Fail mengandungi senarai username TikTok (satu per baris)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.targets_file))
    except KeyboardInterrupt:
        print("\n[INFO] Dihentikan oleh pengguna.")
