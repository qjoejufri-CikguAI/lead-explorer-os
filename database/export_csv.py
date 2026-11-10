import sqlite3
import csv
from pathlib import Path

def main():
    db_path = Path(__file__).parent / "leads.db"
    output_file = Path(__file__).parent / "leads_export.csv"
    
    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        return 1
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get column names from schema
    cursor.execute("PRAGMA table_info(leads)")
    columns = [col[1] for col in cursor.fetchall()]
    
    # Export all records
    cursor.execute("SELECT * FROM leads")
    rows = cursor.fetchall()
    
    # Write clean CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    print(f"[OK] Exported {len(rows)} records to {output_file}")
    conn.close()
    return 0

if __name__ == "__main__":
    main()