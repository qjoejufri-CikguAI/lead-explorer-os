#!/usr/bin/env python3
"""
Test TikTok Live - Tangkap komen dan join secara real-time melalui WebSocket.
Fail berasingan, jangan usik scout_engine.py.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, JoinEvent

DATA_PATH = Path(__file__).parent / "tiktok_live_test_data.json"


def save_to_json(data_list):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data_list, f, indent=2, ensure_ascii=False)


async def main(username: str):
    # Hapus @ jika ada
    username = username.replace("@", "")

    client = TikTokLiveClient(unique_id=username)

    collected = []

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        user = event.user
        comment = event.comment
        msg = f"[KOMEN] {user.unique_id}: {comment}"
        print(msg)
        collected.append({
            "type": "comment",
            "user": user.unique_id,
            "comment": comment,
        })
        save_to_json(collected)

    @client.on(JoinEvent)
    async def on_join(event: JoinEvent):
        user = event.user
        msg = f"[MASUK] {user.unique_id}"
        print(msg)
        collected.append({
            "type": "join",
            "user": user.unique_id,
        })
        save_to_json(collected)

    print(f"[INFO] Menghubungkan ke TikTok Live @{username}...")
    print("[INFO] Tekan Ctrl+C untuk berhenti.")
    await client.connect()
    await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test TikTok Live Comment & Join capture")
    parser.add_argument("--username", required=True, help="Username TikTok (contoh: @dealer_kereta atau dealer_kereta)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.username))
    except KeyboardInterrupt:
        print("\n[INFO] Dihentikan oleh pengguna.")
        print(f"[INFO] Data disimpan di: {DATA_PATH}")
