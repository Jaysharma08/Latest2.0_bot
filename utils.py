# utils.py
import sqlite3
from config import ADMINS, DISCOUNT

conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

def calculate_price(price):
    """Apply discount and return final price"""
    final_price = price * DISCOUNT
    return round(final_price, 2)

def generate_token():
    """Generate incremental token"""
    cursor.execute("SELECT last_token FROM token_counter WHERE id=1")
    last_token = cursor.fetchone()[0] + 1
    cursor.execute("UPDATE token_counter SET last_token=? WHERE id=1", (last_token,))
    conn.commit()
    return last_token

def get_online_admins():
    """Return list of admin_ids who are online"""
    return [admin_id for admin_id, info in ADMINS.items() if info["status"] == "online"]

def assign_order_to_admin(order_id):
    """Assign order to first online admin"""
    online_admins = get_online_admins()
    if not online_admins:
        return None
    return online_admins[0]

def get_pending_orders_for_admin(admin_id):
    """Return all pending orders"""
    cursor.execute("SELECT id, token, user_id FROM orders WHERE status='pending'")
    return cursor.fetchall()
