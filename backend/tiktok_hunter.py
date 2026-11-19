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
from TikTokLive.events import CommentEvent, JoinEvent

DATA_PATH = Path(__file__).parent / "tiktok_hunter_multi_data.json"
TARGETS_PATH = Path(__file__).parent / "targets.txt"

SUPABASE_URL = "https://ypcccthqbnkurkslsvdi.supabase.co"
SUPABASE_KEY = "sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj"

# Global state
seen_comments = set()
seen_joins = set()
data_queue = asyncio.Queue()
semaphore = asyncio.Semaphore(3)


def save_to_json(data_list):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data_list, f, indent=2, ensure_ascii=False)


def fetch_targets_from_supabase():
    """Ambil semua username dari table scout_targets di Supabase, tulis ke targets.txt."""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/scout_targets?select=username&order=created_at.asc",
            headers=headers,
            timeout=30,
        )
        if res.status_code != 200:
            print(f"[WARN] Gagal fetch scout_targets dari Supabase: {res.status_code} {res.text}")
            return []

        data = res.json()
        usernames = [row['username'] for row in data if row.get('username')]

        # Tulis ke targets.txt
        if usernames:
            TARGETS_PATH.write_text("\n".join(usernames) + "\n", encoding="utf-8")
            print(f"[INFO] Dapat {len(usernames)} target dari Supabase scout_targets.")
        else:
            TARGETS_PATH.write_text("", encoding="utf-8")
            print("[INFO] Tiada target dalam database scout_targets.")

        return usernames
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


async def monitor_live(username: str):
    """Pantau satu TikTok Live hingga tamat, kemudian lepaskan semaphore."""
    async with semaphore:
        print(f"[INFO] Memantau @{username}...")

        client = TikTokLiveClient(unique_id=username)

        # Buffer untuk mengumpulkan komen per user sebelum flush
        user_comments = {}  # username -> list of comment texts

        @client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            user = event.user.unique_id
            comment = event.comment
            comment_key = f"{username}_{user}_{comment}"
            if comment_key in seen_comments:
                return
            seen_comments.add(comment_key)

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

        try:
            await client.connect()
        except Exception as e:
            print(f"[ERROR] @{username} gagal connect: {e}")
        finally:
            # Flush semua komen yang dikumpulkan - gabungkan per user, ambil skor tertinggi
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
    usernames = fetch_targets_from_supabase()

    # Baca targets dari fail (yang baru ditulis dari Supabase)
    targets_path = Path(targets_file)
    if not targets_path.exists():
        print(f"[ERROR] Fail targets tidak jumpa: {targets_file}")
        print("[INFO] Cipta fail contoh targets.txt...")
        targets_path.write_text("@dealer_kereta\n@jualan_motor\n", encoding="utf-8")

    with open(targets_path, "r", encoding="utf-8") as f:
        targets = [line.strip().replace("@", "") for line in f if line.strip()]

    if not targets:
        print("[INFO] Tiada target dalam database. Hunter berhenti.")
        return

    print(f"[INFO] Dapat {len(targets)} target: {targets}")

    # Init database
    init_db()

    # Start queue worker
    worker_task = asyncio.create_task(queue_worker())

    # Cipta tasks untuk semua target (semaphore hadkan concurrency kepada 3)
    tasks = []
    for target in targets:
        task = asyncio.create_task(monitor_live(target))
        tasks.append(task)

    try:
        # Tunggu semua live monitor tamat
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n[INFO] Dihentikan oleh pengguna.")
        # Disconnect semua client
        for task in tasks:
            task.cancel()
    finally:
        # Berhenti worker
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Sync ke Supabase
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
        print("\n[INFO] Dihentikan.")
