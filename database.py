# database.py
import sqlite3

conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

# Orders table
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    user_name TEXT,
    address TEXT,
    food_image TEXT,
    price REAL,
    final_price REAL,
    token INTEGER,
    status TEXT
)
""")

# Token counter table
cursor.execute("""
CREATE TABLE IF NOT EXISTS token_counter (
    id INTEGER PRIMARY KEY,
    last_token INTEGER
)
""")

# Initialize token
cursor.execute("INSERT OR IGNORE INTO token_counter (id, last_token) VALUES (1, 0)")
conn.commit()
