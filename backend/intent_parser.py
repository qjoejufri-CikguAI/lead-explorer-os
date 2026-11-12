#!/usr/bin/env python3
"""Intent parser for lead scouting agent - comment-based intent scoring."""

import re
from typing import Tuple

# Strong buying signals (high score 0.9) - HANYA untuk soalan/niat beli sebenar
STRONG_KEYWORDS = [
    "berapa", "pm", "minat", "nak", "loan", "masih ada", "detail", "info",
]

# Negative signals - return 0.1 (seller ads / car specs / non-buying)
NEGATIVE_KEYWORDS = [
    "myvi", "perodua", "tahun", "full loan", "mudah.my", "waranti",
    "spesifikasi", "lihat butiran", "jual", "untuk dijual", "promosi",
    "sa", "dealer", "iklan",
]

def parse_intent(text: str) -> float:
    """
    Parse intent from comment text and return a score between 0.0 and 1.0.
    Higher scores indicate stronger buying signals.
    """
    if not text:
        return 0.0

    text_lower = text.lower().strip()

    # Check for tagging (mentions @someone) - treat as weak
    if re.search(r'@\w+', text_lower):
        return 0.1

    # Check for negative signals FIRST (seller ads / car specs) - return 0.1
    for kw in NEGATIVE_KEYWORDS:
        if kw in text_lower:
            return 0.1

    # Check for strong buying keywords - return 0.9
    for kw in STRONG_KEYWORDS:
        if kw in text_lower:
            return 0.9

    # Default moderate score for other comments
    return 0.5
