import sqlite3

conn = sqlite3.connect('database/leads.db')
cursor = conn.cursor()

# Tukar tarikh kosong kepada NULL
cursor.execute("UPDATE leads SET created_at = NULL WHERE created_at = ''")
try:
    cursor.execute("UPDATE leads SET processed_at = NULL WHERE processed_at = ''")
except:
    pass

conn.commit()
conn.close()
print("Database SQLite berjaya dibersihkan!")