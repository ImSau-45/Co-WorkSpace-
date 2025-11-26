import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.normpath(os.path.join(BASE_DIR, '..'))
UPLOAD_DIR = os.path.join(ROOT, 'static', 'uploads')
DB = os.path.join(ROOT, 'cowork.db')

# List candidate images (ignore our svg placeholders only if needed)
candidates = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
# Prefer jpg/png/jpeg first ordered by name
candidates = sorted(candidates, key=lambda s: s)
print('Found uploads:', candidates)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Find workspaces with no image
cur.execute("SELECT id, name FROM workspaces WHERE image_path IS NULL OR image_path = '' ORDER BY id")
rows = cur.fetchall()
print('Workspaces without images:', [(r['id'], r['name']) for r in rows])

updates = 0
for i, row in enumerate(rows):
    if i >= len(candidates):
        break
    filename = candidates[i]
    image_path = f"uploads/{filename}"
    print(f"Assigning {image_path} to workspace id={row['id']} name={row['name']}")
    cur.execute("UPDATE workspaces SET image_path = ? WHERE id = ?", (image_path, row['id']))
    updates += 1

conn.commit()
conn.close()
print(f"Updated {updates} rows.")
