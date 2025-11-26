import sqlite3
import os
from pprint import pprint

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'cowork.db')
DB_PATH = os.path.normpath(DB_PATH)

print('DB path:', DB_PATH)
if not os.path.exists(DB_PATH):
    print('Database file not found.')
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print('\nTables:')
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
    print('-', row[0])

print('\nSample rows:')
for table in ['users', 'workspaces', 'bookings', 'reviews']:
    try:
        rows = cur.execute(f"SELECT * FROM {table} LIMIT 5").fetchall()
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        print('\nTable:', table)
        print('Columns:', cols)
        if rows:
            for r in rows:
                # convert sqlite Row or tuple to dict-like print
                print(dict(zip(cols, r)))
        else:
            print('  (no rows)')
    except Exception as e:
        print('\nTable:', table, ' - error:', e)

conn.close()
