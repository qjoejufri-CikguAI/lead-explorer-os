"""AI filtering logic: intent scoring & lead relevance selection."""

import re
from typing import List, Dict

# General intent-keyword phrases that signal lead buying intent.
INTENT_KEYWORDS = [
    r"\blead\b",
    r"\binvestment\b",
    r"\bopportunity\b",
    r"\brevenue\b",
    r"\bsales\b",
    r"\bclient\b",
    r"\bcontract\b",
    r"\bdeal\b",
]

# Mod Nasional signals: "jualan kenderaan seluruh Malaysia" -> motor vehicles / sale / Malaysia
MOD_NASIONAL_PATTERNS = [
    r"kereta|motor|kenderaan|jenis|penjualan|pembelian|buy|malaysia",
]

# Mod Lokal signals: "servis bengkel sekitar Johor/Melaka" -> service shop / bengkel / Johor / Melaka
MOD_LOCAL_PATTERNS = [
    r"johor|melaka|seris|bengkel|shop|kota-johor|kota-melaka",
]


def _matches_mod_national(text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in MOD_NASIONAL_PATTERNS)


def _matches_mod_local(text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in MOD_LOCAL_PATTERNS)


def compute_intent_score(record: Dict) -> float:
    """Return an intent score 0.0–1.0 for one lead record.

    Scores base keyword matches (0.4 each), adds +0.2 for Mod Nasional signals and +0.2 for Mod Lokal signals,
    capped at 1.0.
    """
    text = f"{record.get('name', '')} {record.get('company', '')}".lower()
    score = 0.0
    for kw in INTENT_KEYWORDS:
        if re.search(kw, text):
            score += 0.4
    if _matches_mod_national(text):
        score += 0.2
    if _matches_mod_local(text):
        score += 0.2
    return round(min(score, 1.0), 3)


def classify_level(score: float) -> str:
    """Label the interest level from the intent score.

    Hot >= 0.85, Warm >= 0.65, Cold below 0.65.
    """
    if score >= 0.85:
        return "Hot"
    if score >= 0.65:
        return "Warm"
    return "Cold"


def filter_leads(
    records: List[Dict],
    min_intent: float = 0.3,
    require_mod_national: bool = True,
    require_mod_local: bool = True,
) -> List[Dict]:
    """Filter records by intent score and mod-country mentions.

    Args:
        records: list of lead dicts from parser.load_records().
        min_intent: minimum raw intent score to retain.
        require_mod_national: drop records lacking Mod Nasional signals.
        require_mod_local: drop records lacking Mod Lokal signals.

    Returns:
        list of enriched dicts including 'intent_score' and 'interest_level'.
    """
    out = []
    for rec in records:
        score = compute_intent_score(rec)
        level = classify_level(score)
        rec_out = {
            "id": rec.get("id", ""),
            "name": rec.get("name", ""),
            "company": rec.get("company", ""),
            "email": rec.get("email", ""),
            "phone": rec.get("phone", ""),
            "industry": rec.get("industry", ""),
            "region": rec.get("region", ""),
            "source": rec.get("source", ""),
            "created_at": rec.get("created_at", ""),
            "intent_score": score,
            "interest_level": level,
        }
        if score >= min_intent:
            name_company = f"{rec.get('name', '')} {rec.get('company', '')}"
            if require_mod_national and not _matches_mod_national(name_company):
                continue
            if require_mod_local and not _matches_mod_local(name_company):
                continue
            out.append(rec_out)
    return out
