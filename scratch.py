import sqlite3
import os

db_path = "mundo_stats.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS active_games;")
    conn.commit()
    conn.close()
    print("Table active_games dropped. It will be recreated by engine.")
else:
    print("DB not found.")
