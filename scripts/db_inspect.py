import sqlite3

conn = sqlite3.connect('cowork.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cols = [c[1] for c in cur.execute('PRAGMA table_info(workspaces)').fetchall()]
print('columns:', cols)
rows = cur.execute('SELECT id,name,currency,price_per_hour,image_path FROM workspaces').fetchall()
print('count:', len(rows))
for r in rows:
    print({k: r[k] for k in r.keys()})
conn.close()
