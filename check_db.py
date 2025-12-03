import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check Property table columns
print("Property table columns:")
cursor.execute("PRAGMA table_info(core_property);")
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")

# Check if any properties exist
print("\nProperties in database:")
cursor.execute("SELECT id, property_id, owner_id, address FROM core_property;")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"  ID={row[0]}, property_id={row[1]}, owner_id={row[2]}, address={row[3]}")
else:
    print("  (none)")

conn.close()
