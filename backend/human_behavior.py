#!/usr/bin/env python3
"""
Modul tingkah laku manusia untuk Global Scout.
Supaya robot nampak macam pengguna sebenar, bukan bot.
"""

import time
import random


def human_delay(min_sec=2.0, max_sec=6.0):
    """Tunggu sejumlah masa rawak di antara min_sec dan max_sec."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


def human_typing(page, text):
    """
    Taip teks seperti manusia:
    - Setiap huruf dengan delay rawak 0.1-0.3 saat.
    - 10% peluang buat typo, tunggu, backspace, taip betul.
    """
    for char in text:
        # 10% peluang typo
        if random.random() < 0.10:
            wrong_char = random.choice("qwertyuiopasdfghjklzxcvbnm")
            page.keyboard.type(wrong_char, delay=random.uniform(0.1, 0.3))
            human_delay(0.2, 0.5)
            page.keyboard.press("Backspace")
            human_delay(0.1, 0.3)
        page.keyboard.type(char, delay=random.uniform(0.1, 0.3))


def human_scroll(page):
    """
    Scroll seperti manusia:
    - Scroll ke bawah dengan jumlah rawak (300-800 piksel).
    - 30% peluang scroll balik ke atas sikit.
    - Letak human_delay di antara scroll.
    """
    human_delay(1.0, 2.5)
    page.mouse.wheel(0, random.randint(300, 800))
    human_delay(1.5, 3.0)

    if random.random() < 0.30:
        page.mouse.wheel(0, -random.randint(100, 300))
        human_delay(1.0, 2.0)
