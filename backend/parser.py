"""Data parsing module: normalize raw inputs (CSV/JSON) into structured lead records."""

import csv
import json
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def load_records(path):
    """Load records from a CSV or JSON file and return them as uniform dicts.

    Args:
        path: str or Path to input file (CSV or JSON).

    Returns:
        list of dictionaries with uniform keys:
            id, name, email, phone, industry, region, source, created_at
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")
    suffix = p.suffix.lower()
    if suffix == ".json":
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return [{key: value for key, value in row.items()} for row in data]
        if isinstance(data, dict) and "records" in data:
            return data["records"]
        raise ValueError("JSON file must contain an array or an object with a 'records' key")
    if suffix == ".csv":
        records = []
        with open(p, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                records.append({
                    "id": (row.get("id") or "").strip(),
                    "name": (row.get("name") or "").strip(),
                    "email": (row.get("email") or "").strip(),
                    "phone": (row.get("phone") or "").strip(),
                    "industry": (row.get("industry") or "").strip(),
                    "region": (row.get("region") or "").strip(),
                    "source": (row.get("source") or "").strip(),
                    "created_at": (row.get("created_at") or "").strip(),
                })
        return records
    raise ValueError(f"Unsupported file extension: {suffix}")
