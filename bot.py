import asyncio
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, MAIN_ADMIN_ID, BOT_NAME

# ================= GLOBALS =================
ADMINS = {
    MAIN_ADMIN_ID: {"role": "main", "status": "online", "login_time": 0}
}

token_counter = 0
active_orders = {}
tracking_wait = {}
current_admin_turn = 0  # Global tracker for Round Robin
CHAT_SESSIONS = {} # Maps Admin ID <-> Customer ID

# ================= HELPERS =================
def generate_token():
    global token_counter
    token_counter += 1
    return token_counter

def calculate_final(item, gst):
    return round((item * 0.5) + gst, 2)

def get_online_admins():
    """Returns list of IDs of admins who are marked 'online'"""
    return [
        aid for aid, info in ADMINS.items()
        if info.get("role") == "admin" and info.get("status") == "online"
    ]

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid == MAIN_ADMIN_ID:
        kb = [["Add New Admin ➕", "Remove Admin ➖"], ["📊 Admin Status"]]
        await update.message.reply_text(
            "👑 Main Admin Panel",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return

    if uid in ADMINS:
        ADMINS[uid]["login_time"] = asyncio.get_event_loop().time()
        kb = [["Online ✅", "Offline ❌"]]
        await update.message.reply_text(
            "👋 Admin Panel",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return

    kb = [
        [InlineKeyboardButton("💰 Price Checking", callback_data="price")],
        [InlineKeyboardButton("🍔 Food Ordering", callback_data="order")]
    ]
    await update.message.reply_text(
        f"👋 Welcome to {BOT_NAME}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "order":
        context.user_data.clear()
        context.user_data["mode"] = "order"
        context.user_data["data"] = {}
        await q.message.reply_text("📍 Send delivery address link:")

    elif q.data == "price":
        context.user_data.clear()
        context.user_data["mode"] = "price"
        context.user_data["data"] = {}
        await q.message.reply_text("💵 Enter item total (minimum ₹149):")

    elif q.data in ["cod", "prepaid"]:
        context.user_data["payment_mode"] = q.data
        if q.data == "cod":
            await finalize_order(context, q.from_user.id)
        else:
            await q.message.reply_text("👛 Enter UPI ID:")

# ================= MESSAGE HANDLER =================
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""

    # ===== CHAT TUNNEL (Admin <-> Customer) =====
    if uid in CHAT_SESSIONS:
        recipient_id = CHAT_SESSIONS[uid]
        prefix = "💬 **Admin:**" if uid in ADMINS or uid == MAIN_ADMIN_ID else "💬 **Customer:**"
        
        if update.message.text:
            await context.bot.send_message(recipient_id, f"{prefix}\n{text}", parse_mode="Markdown")
        elif update.message.photo:
            await context.bot.send_photo(recipient_id, update.message.photo[-1].file_id, caption=f"{prefix} (Sent an image)")
        return

    # ===== TRACKING =====
    if uid in tracking_wait:
        token = tracking_wait.pop(uid)
        order = active_orders.get(token)
        if order:
            # Close chat session upon completion
            cust_id = order["customer"]["id"]
            CHAT_SESSIONS.pop(uid, None)
            CHAT_SESSIONS.pop(cust_id, None)

            await context.bot.send_message(
                cust_id,
                f"🚚 Your tracking link:\n{text}\n\n🙏 Thank you for ordering with {BOT_NAME}!"
            )
            await context.bot.send_message(uid, f"✅ Token {token} completed and Chat closed.")
            del active_orders[token]
        return

    # ===== PRICE CHECKING =====
    if context.user_data.get("mode") == "price":
        data = context.user_data["data"]
        if "item" not in data:
            try:
                item = float(text)
                if item < 149:
                    await update.message.reply_text("❌ Minimum item total is ₹149")
                    return
                data["item"] = item
                await update.message.reply_text("🧾 Enter GST:")
            except:
                await update.message.reply_text("❌ Enter valid amount")
            return
        if "gst" not in data:
            try:
                gst = float(text)
                data["gst"] = gst
                final = calculate_final(data["item"], gst)
                await update.message.reply_text(f"💰 Final Price:\nItem: ₹{data['item']}\nGST: ₹{gst}\n➡️ Total: ₹{final}")
                context.user_data.clear()
            except:
                await update.message.reply_text("❌ Enter valid GST")
            return

    # ===== MAIN ADMIN CONTROLS =====
    if uid == MAIN_ADMIN_ID:
        if text == "Add New Admin ➕":
            context.user_data["add_admin"] = True
            await update.message.reply_text("📩 Send Telegram User ID:")
            return
        if text == "Remove Admin ➖":
            context.user_data["remove_admin"] = True
            await update.message.reply_text("📩 Send Admin Telegram ID:")
            return
        if text == "📊 Admin Status":
            online = [str(aid) for aid, info in ADMINS.items() if info.get("role") == "admin" and info["status"] == "online"]
            offline = [str(aid) for aid, info in ADMINS.items() if info.get("role") == "admin" and info["status"] == "offline"]
            msg = f"📊 *Admin Status*\n\n🟢 Online ({len(online)})\n" + ("\n".join(online) or "None")
            msg += f"\n\n🔴 Offline ({len(offline)})\n" + ("\n".join(offline) or "None")
            await update.message.reply_text(msg, parse_mode="Markdown")
            return
        if context.user_data.get("add_admin"):
            try:
                aid = int(text)
                ADMINS[aid] = {"role": "admin", "status": "offline", "login_time": 0}
                await update.message.reply_text(f"✅ Admin added: {aid}")
            except: await update.message.reply_text("❌ Invalid ID")
            context.user_data.clear()
            return
        if context.user_data.get("remove_admin"):
            try:
                aid = int(text)
                if aid != MAIN_ADMIN_ID and aid in ADMINS:
                    del ADMINS[aid]
                    await update.message.reply_text(f"✅ Admin removed: {aid}")
                else: await update.message.reply_text("❌ Cannot remove")
            except: await update.message.reply_text("❌ Invalid ID")
            context.user_data.clear()
            return

    # ===== ADMIN STATUS =====
    if uid in ADMINS and ADMINS[uid]["role"] == "admin":
        if text in ["Online ✅", "Offline ❌"]:
            ADMINS[uid]["status"] = "online" if "Online" in text else "offline"
            ADMINS[uid]["login_time"] = asyncio.get_event_loop().time()
            await update.message.reply_text("✅ Status updated", reply_markup=ReplyKeyboardRemove())
            return

    # ===== FOOD ORDER =====
    if context.user_data.get("mode") == "order":
        data = context.user_data["data"]
        if "address" not in data:
            data["address"] = text
            await update.message.reply_text("📸 Send food/card image")
            return
        if "image" not in data and update.message.photo:
            data["image"] = update.message.photo[-1].file_id
            await update.message.reply_text("💵 Enter item total (minimum ₹149):")
            return
        if "item" not in data:
            try:
                item = float(text)
                if item < 149:
                    await update.message.reply_text("❌ Minimum item total is ₹149")
                    return
                data["item"] = item
                await update.message.reply_text("🧾 Enter GST:")
            except: await update.message.reply_text("❌ Enter valid amount")
            return
        if "gst" not in data:
            try:
                gst = float(text)
                data["gst"] = gst
                data["final"] = calculate_final(data["item"], gst)
                kb = [[InlineKeyboardButton("💵 COD", callback_data="cod"), InlineKeyboardButton("💳 PREPAID", callback_data="prepaid")]]
                await update.message.reply_text(f"💰 Total: ₹{data['final']}\nChoose payment:", reply_markup=InlineKeyboardMarkup(kb))
            except: await update.message.reply_text("❌ Enter valid GST")
            return
        if context.user_data.get("payment_mode") == "prepaid" and "upi" not in data:
            data["upi"] = text
            await finalize_order(context, uid)
            return

# ================= FINALIZE ORDER =================
async def finalize_order(context, uid):
    global current_admin_turn
    data = context.user_data.get("data")
    token = generate_token()
    admins = get_online_admins()

    if not admins:
        await context.bot.send_message(uid, "❌ No admin online")
        context.user_data.clear()
        return

    assigned_idx = current_admin_turn % len(admins)
    assigned_admin = admins[assigned_idx]
    current_admin_turn += 1 

    chat = await context.bot.get_chat(uid)
    active_orders[token] = {
        "status": "pending",
        "admins": admins, 
        "index": assigned_idx, 
        "assigned_admin": assigned_admin,
        "customer": {
            "id": uid,
            "name": chat.full_name,
            "address": data["address"],
            "image": data["image"],
            "final": data["final"],
            "payment": context.user_data.get("payment_mode"),
            "upi": data.get("upi"),
        }
    }

    pm = context.user_data.get("payment_mode", "N/A").upper()
    await context.bot.send_message(uid, f"✅ Order placed ({pm}). Waiting for admin acceptance...")
    await send_to_admin(context, token)
    context.user_data.clear()

    asyncio.create_task(auto_forward_after_1min(context, token))

# ================= AUTO FORWARD AFTER 1 MIN =================
async def auto_forward_after_1min(context, token):
    await asyncio.sleep(60)
    order = active_orders.get(token)
    if not order or order["status"] != "pending":
        return

    order["index"] = (order["index"] + 1) % len(order["admins"])
    order["assigned_admin"] = order["admins"][order["index"]]
    await send_to_admin(context, token)

# ================= SEND TO ADMIN =================
async def send_to_admin(context, token):
    order = active_orders.get(token)
    if not order: return
    cust = order["customer"]

    caption = (
        f"📦 NEW ORDER\n👤 {cust['name']}\n🆔 {cust['id']}\n📍 {cust['address']}\n"
        f"🎟 Token: {token}\n💰 ₹{cust['final']}\n💳 {cust['payment']}"
    )
    if cust.get("upi"): caption += f"\n👛 UPI: {cust['upi']}"

    kb = [
        [InlineKeyboardButton("Accept ✅", callback_data=f"accept_{token}")],
        [InlineKeyboardButton("Reject ❌", callback_data=f"reject_{token}")]
    ]
    try:
        await context.bot.send_photo(order["assigned_admin"], cust["image"], caption=caption, reply_markup=InlineKeyboardMarkup(kb))
    except: pass

# ================= ADMIN CALLBACKS =================
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    parts = q.data.split("_")
    action, token = parts[0], int(parts[1])
    order = active_orders.get(token)

    if not order:
        await q.message.edit_caption("❌ Order expired or already completed")
        return

    if q.from_user.id != order["assigned_admin"]:
        await q.message.reply_text("❌ Order expired / already forwarded")
        return

    if action == "accept":
        order["status"] = "accepted"
        admin_id = q.from_user.id
        cust_id = order["customer"]["id"]
        
        # Open Chat Tunnel
        CHAT_SESSIONS[admin_id] = cust_id
        CHAT_SESSIONS[cust_id] = admin_id

        await context.bot.send_message(cust_id, "✅ Your order has been accepted. You can now chat directly with the admin by typing here.")
        
        kb = [
            [InlineKeyboardButton("Complete Order 📦", callback_data=f"complete_{token}")],
            [InlineKeyboardButton("Close Chat 💬", callback_data=f"closechat_{token}")]
        ]
        await q.message.reply_text(f"✅ Token {token} Accepted. Chat tunnel is ACTIVE.", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "closechat":
        admin_id = q.from_user.id
        cust_id = order["customer"]["id"]
        CHAT_SESSIONS.pop(admin_id, None)
        CHAT_SESSIONS.pop(cust_id, None)
        await q.message.reply_text("📴 Chat session closed.")
        await context.bot.send_message(cust_id, "📴 Admin has closed the chat session.")

    elif action == "reject":
        order["index"] = (order["index"] + 1) % len(order["admins"])
        order["assigned_admin"] = order["admins"][order["index"]]
        await send_to_admin(context, token)
        await q.message.delete()

    elif action == "complete":
        tracking_wait[q.from_user.id] = token
        await q.message.reply_text("🚚 Send tracking link to complete order and close chat:")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons, pattern="^(order|price|cod|prepaid)$"))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^(accept|reject|complete|closechat)_"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, messages))
    print("🚀 Bot running with Chat feature...")
    app.run_polling()
