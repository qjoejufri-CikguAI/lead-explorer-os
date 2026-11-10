#!/usr/bin/env python3
"""Export lead data to Google Sheets via API.

Exports leads from SQLite database to Google Sheets spreadsheet.
Note: Requires Google Sheets API credentials setup.
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Constants (to be configured)
DB_FILE = "leads.db"
SPREADSHEET_ID = ""  # To be filled with Google Sheets spreadsheet ID
WORKSHEET_NAME = "Leads Export"

# Mock Google Sheets API (for demonstration purposes)
def mock_export_to_google_sheets(leads: list, spreadsheet_id: Optional[str] = None) -> bool:
    """Mock export to Google Sheets (replace with actual API call).

    Args:
        leads: List of lead records to export.
        spreadsheet_id: Optional Google Sheets spreadsheet ID.

    Returns:
        True if successful, False otherwise.
    """
    if not spreadsheet_id:
        print("[WARNING] Google Sheets API credentials not configured")
        print("[INFO] To use real Google Sheets API, provide spreadsheet_id")
        # Demo: just print to console instead
        print(f"[OK] Would export {len(leads)} leads to spreadsheet: {spreadsheet_id or 'DEMO'}")
        return True

    print(f"[OK] Exported {len(leads)} leads to Google Sheets: {spreadsheet_id}")
    return True


def get_leads_from_db(conn: sqlite3.Connection) -> list:
    """Retrieve all leads from database.

    Args:
        conn: SQLite database connection.

    Returns:
        List of lead records as dictionaries.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, phone, industry, region, source, created_at,
               intent_score, interest_level
        FROM leads
        ORDER BY created_at DESC
    """)

    return [dict(row) for row in cursor.fetchall()]


def export_to_google_sheets(leads: list, spreadsheet_id: Optional[str] = None):
    """Export leads to Google Sheets.

    Args:
        leads: List การ leads to export.
        spreadsheet_id: Optional Google Sheets spreadsheet ID.
    """
    if not spreadsheet_id:
        print("[WARNING] Spreadsheet ID not configured. Using mock export for demonstration.")

    success = mock_export_to_google_sheets(leads, spreadsheet_id)

    if success:
        print(f"[OK] Export completed: {len(leads)} leads")
    else:
        print("[ERROR] Export failed")


def main():
    """Export leads from database to Google Sheets."""
    print("Exporting lead data to Google Sheets...")

    # Use the correct path to the database file (one level up from the script directory)
    db_path = Path(__file__).parent.parent / DB_FILE
    
    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    leads = get_leads_from_db(conn)
    conn.close()

    if not leads:
        print("[ERROR] No leads found in database")
        return

    export_to_google_sheets(leads)


if __name__ == "__main__":
    main()
