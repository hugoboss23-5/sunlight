import sqlite3

conn = sqlite3.connect('data/sunlight.db')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS contracts (
    contract_id TEXT PRIMARY KEY,
    award_amount REAL,
    vendor_name TEXT,
    agency_name TEXT,
    description TEXT,
    start_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()
print("Database table created!")
