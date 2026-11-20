#!/usr/bin/env python3
"""
VIP Manager - Urus senarai VIP target di Supabase.
"""

import os
import sys
import requests
from datetime import datetime

SUPABASE_URL = "https://ypcccthqbnkurkslsvdi.supabase.co"
SUPABASE_KEY = "sb_publishable_psEsjDPRCqYEencypzNW9g_NgRW7ZPj"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

def add_vip(username: str):
    """Masukkan username ke table vip_targets (elak duplicate)."""
    url = f"{SUPABASE_URL}/rest/v1/vip_targets?on_conflict=username"
    payload = {
        "username": username,
        "is_live": False,
        "current_viewers": 0,
    }
    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code not in [200, 201, 204]:
        print(f"[ERROR] Supabase gagal update: {res.status_code} - {res.text}")
    return res

def update_vip_status(username: str, is_live: bool, viewer_count: int):
    """Kemaskini status live, viewer count, dan last_live_at."""
    url = f"{SUPABASE_URL}/rest/v1/vip_targets?username=eq.{username}"
    payload = {
        "is_live": is_live,
        "current_viewers": viewer_count,
    }
    if is_live:
        payload["last_live_at"] = datetime.now().isoformat()
    else:
        payload["last_live_at"] = None
    res = requests.patch(url, headers=HEADERS, json=payload)
    if res.status_code not in [200, 201, 204]:
        print(f"[ERROR] Supabase gagal update: {res.status_code} - {res.text}")
    return res

def get_all_vips():
    """Ambil semua VIP dari Supabase."""
    url = f"{SUPABASE_URL}/rest/v1/vip_targets?select=*"
    res = requests.get(url, headers=HEADERS)
    if res.status_code not in [200, 201]:
        print(f"[ERROR] Supabase gagal ambil: {res.status_code} - {res.text}")
        return []
    return res.json()