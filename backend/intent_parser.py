#!/usr/bin/env python3
"""Intent parser for lead scouting agent."""

import re
from typing import Tuple

def parse_intent(text: str) -> float:
    """
    Parse intent from text and return a score between 0.0 and 1.0.
    Higher scores indicate stronger buying signals.
    """
    # Define strong buying keywords (Malay and English)
    strong_keywords = [
        "beli", "order", "harga", "diskon", "promo", "urgent", "segera",
        "spesial", "tingkat", "penawaran", "buy", "price", "discount",
        "promotion", "limited", "special", "menarik", "tinggal", "terbatas"
    ]
    
    # Normalize text
    text_lower = text.lower()
    
    # Check for strong keywords
    for kw in strong_keywords:
        if kw in text_lower:
            return 1.0
    
    # If no strong keywords, return moderate score
    return 0.5