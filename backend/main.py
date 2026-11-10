#!/usr/bin/env python3
"""CLI entry point: parse raw data, filter leads, write CSV output.

Usage:
    python main.py <input.csv|input.json> [-o OUTPUT_CSV]

Reads the raw input file, normalizes it via parser.load_records(),
filters hot leads via filter_leads(), and writes the result to stdout or a CSV file.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parser import load_records
from ai_filtering import filter_leads


def main():
    ap = argparse.ArgumentParser(description="Parse lead data and filter hot leads.")
    ap.add_argument("input", help="Path to input CSV or JSON file (raw)")
    ap.add_argument("--output-csv", default=None, help="Output CSV path (default: <input>_filtered.csv)")
    args = ap.parse_args()

    records = load_records(args.input)
    filtered = filter_leads(records, min_intent=0.3, require_mod_national=True, require_mod_local=True)

    if filtered:
        fieldnames = filtered[0].keys()
    else:
        fieldnames = [
            "id",
            "name",
            "email",
            "phone",
            "industry",
            "region",
            "source",
            "created_at",
            "intent_score",
            "interest_level",
        ]

    if args.output_csv:
        out_path = Path(args.output_csv)
    else:
        out_path = Path(f"{args.input}_filtered.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filtered)

    print(f"Parsed {len(records)} records, kept {len(filtered)} hot leads -> {out_path}")


if __name__ == "__main__":
    main()
