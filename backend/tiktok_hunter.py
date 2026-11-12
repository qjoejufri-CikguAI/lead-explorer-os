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
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scout_engine import init_db, save_to_sqlite, sync_sqlite_to_supabase, parse_intent

from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, JoinEvent

DATA_PATH = Path(__file__).parent / "tiktok_hunter_multi_data.json"

# Global state
seen_comments = set()
seen_joins = set()
data_queue = asyncio.Queue()
semaphore = asyncio.Semaphore(3)


def save_to_json(data_list):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data_list, f, indent=2, ensure_ascii=False)


async def queue_worker():
    """Worker yang ambil data dari queue, dedup, score AI, simpan ke SQLite."""
    while True:
        item = await data_queue.get()
        try:
            event_type = item["type"]
            user = item["user"]

            if event_type == "comment":
                comment = item["comment"]
                user = item["user"]
                source_account = item.get("source_account", "")

                seen_comments.add(f"{source_account}_{user}_{comment}")

                score = parse_intent(comment)

                if score >= 0.5:
                    lead = {
                        "name": user,
                        "niche": "TikTok Live",
                        "area": "",
                        "intent_score": score,
                        "interest_level": "Hot",
                        "phone": "",
                        "email": "",
                        "social_link": f"https://tiktok.com/@{user}",
                        "platform": "TikTok",
                        "source_type": "Comment",
                        "context": comment,
                        "plate_number": "",
                        "keyword": "",
                        "source_account": source_account,
                        "created_at": datetime.now().isoformat(),
                    }
                    save_to_sqlite([lead])
                    print(f"[HOT] SQLite: {user} (score={score})")

            elif event_type == "join":
                seen_joins.add(f"{item.get('source_account', '')}_{user}")

                lead = {
                    "name": user,
                    "niche": "TikTok Live",
                    "area": "",
                    "intent_score": 0.3,
                    "interest_level": "Warm",
                    "phone": "",
                    "email": "",
                    "social_link": f"https://tiktok.com/@{user}",
                    "platform": "TikTok",
                    "source_type": "Join",
                    "context": f"Masuk live",
                    "plate_number": "",
                    "keyword": "",
                    "source_account": item.get("source_account", ""),
                    "created_at": datetime.now().isoformat(),
                }
                save_to_sqlite([lead])
                print(f"[WARM] SQLite: {user}")

        except Exception as e:
            print(f"[ERROR] Worker gagal memproses item: {e}")
        finally:
            data_queue.task_done()


async def monitor_live(username: str):
    """Pantau satu TikTok Live hingga tamat, kemudian lepaskan semaphore."""
    async with semaphore:
        print(f"[INFO] Memantau @{username}...")

        client = TikTokLiveClient(unique_id=username)

        @client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            comment_key = f"{username}_{event.user.unique_id}_{event.comment}"
            if comment_key in seen_comments:
                return
            seen_comments.add(comment_key)
            await data_queue.put({
                "type": "comment",
                "user": event.user.unique_id,
                "comment": event.comment,
                "source_account": username,
            })

        @client.on(JoinEvent)
        async def on_join(event: JoinEvent):
            join_key = f"{username}_{event.user.unique_id}"
            if join_key in seen_joins:
                return
            seen_joins.add(join_key)
            await data_queue.put({
                "type": "join",
                "user": event.user.unique_id,
                "source_account": username,
            })

        try:
            await client.connect()
        except Exception as e:
            print(f"[ERROR] @{username} gagal connect: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
            print(f"[INFO] @{username} Live tamat/disconnect. Lepasan semaphore.")


async def main(targets_file: str):
    # Baca targets dari fail
    targets_path = Path(targets_file)
    if not targets_path.exists():
        print(f"[ERROR] Fail targets tidak jumpa: {targets_file}")
        print("[INFO] Cipta fail contoh targets.txt...")
        targets_path.write_text("@dealer_kereta\n@jualan_motor\n", encoding="utf-8")

    with open(targets_path, "r", encoding="utf-8") as f:
        targets = [line.strip().replace("@", "") for line in f if line.strip()]

    if not targets:
        print("[ERROR] Tiada target dalam fail.")
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
