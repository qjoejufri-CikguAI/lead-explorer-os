#!/usr/bin/env python3
"""
The Overseer - Pantau status Live semua VIP secara automatik (24/7).
Jalankan fail ini di latar belakang untuk update is_live pada vip_targets.
"""

import asyncio
import sys
import os
from datetime import datetime

from vip_manager import get_all_vips, update_vip_status
from TikTokLive import TikTokLiveClient


async def check_vips_loop():
    """Loop utama yang menyemak status Live semua VIP setiap 60 saat."""
    print("[INFO] The Overseer bermula... semak setiap 60 saat.")

    while True:
        try:
            vips = get_all_vips()
        except Exception as e:
            print(f"[ERROR] Gagal ambil senarai VIP: {e}")
            await asyncio.sleep(60)
            continue

        if not vips:
            print("[INFO] Tiada VIP dalam senarai.")
            await asyncio.sleep(60)
            continue

        for vip in vips:
            username = vip.get("username")
            if not username:
                continue

            print(f"[INFO] Semak status Live: @{username}")

            client = TikTokLiveClient(unique_id=username)

            try:
                task = asyncio.create_task(client.connect())
                await asyncio.sleep(5)

                is_connected = getattr(client, "connected", False) or getattr(client, "is_connected", False)

                if is_connected:
                    viewer_count = getattr(client, "viewer_count", None) or 100
                    update_vip_status(username, is_live=True, viewer_count=viewer_count)
                    print(f"[LIVE] @{username} sedang Live (Viewers: {viewer_count})")

                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                else:
                    update_vip_status(username, is_live=False, viewer_count=0)
                    print(f"[OFFLINE] @{username} tidak sedang Live.")

                    try:
                        await client.disconnect()
                    except Exception:
                        pass

                await asyncio.sleep(1)

            except Exception as e:
                if "UserOfflineError" in str(e) or "not live" in str(e).lower():
                    update_vip_status(username, is_live=False, viewer_count=0)
                    print(f"[OFFLINE] @{username} tidak sedang Live.")
                else:
                    print(f"[WARN] Ralat semak @{username}: {e}")

            await asyncio.sleep(2)  # jeda kecil antara setiap VIP

        print("[INFO] Seterusnya semak selepas 60 saat...")
        await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(check_vips_loop())
    except KeyboardInterrupt:
        print("\n[INFO] The Overseer dihentikan.")
