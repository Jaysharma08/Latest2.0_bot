# ================= IMPORTS =================
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

# ================= HELPERS =================
def generate_token():
    global token_counter
    token_counter += 1
    return token_counter

def calculate_final(item, gst):
    return round((item * 0.5) + gst, 2)

def online_admins():
    return sorted(
        [
            aid for aid, info in ADMINS.items()
            if info["role"] == "admin" and info["status"] == "online"
        ],
        key=lambda x: ADMINS[x]["login_time"]
    )

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
            await q.message.reply_text("✅ Order placed (COD)")
        else:
            await q.message.reply_text("👛 Enter UPI ID (any text):")

# ================= MESSAGE HANDLER =================
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""

    # ===== TRACKING =====
    if uid in tracking_wait:
        token = tracking_wait.pop(uid)
        order = active_orders.get(token)
        if order:
            await context.bot.send_message(
                order["customer"]["id"],
                f"🚚 Tracking Link:\n{text}\n\n🙏 Thanks for ordering with {BOT_NAME}"
            )
            del active_orders[token]
        return

    # ===== FOOD ORDER FLOW =====
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
            except:
                await update.message.reply_text("❌ Enter valid amount")
            return

        if "gst" not in data:
            try:
                gst = float(text)
                data["final"] = calculate_final(data["item"], gst)
                kb = [[
                    InlineKeyboardButton("💵 COD", callback_data="cod"),
                    InlineKeyboardButton("💳 PREPAID", callback_data="prepaid"),
                ]]
                await update.message.reply_text(
                    f"💰 Total: ₹{data['final']}\nChoose payment:",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
            except:
                await update.message.reply_text("❌ Enter valid GST")
            return

        # ===== PREPAID (ANY TEXT) =====
        if context.user_data.get("payment_mode") == "prepaid" and "upi" not in data:
            data["upi"] = text
            await finalize_order(context, uid)
            await update.message.reply_text("✅ Order placed (PREPAID)")
            return

# ================= FINALIZE ORDER =================
async def finalize_order(context, uid):
    data = context.user_data["data"]
    token = generate_token()
    admins = online_admins()

    if not admins:
        await context.bot.send_message(uid, "❌ No admin online")
        return

    chat = await context.bot.get_chat(uid)

    active_orders[token] = {
        "status": "pending",
        "admins": admins,
        "index": 0,
        "assigned_admin": admins[0],
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

    await send_to_admin(context, token)
    await context.bot.send_message(uid, "✅ Order sent to admin")
    context.user_data.clear()

    # Auto forward every 60s
    asyncio.create_task(auto_forward(context, token))

# ================= AUTO FORWARD LOOP =================
async def auto_forward(context, token):
    while True:
        await asyncio.sleep(60)
        order = active_orders.get(token)
        if not order:
            return

        if order["status"] == "accepted":
            return

        order["index"] += 1
        if order["index"] < len(order["admins"]):
            order["assigned_admin"] = order["admins"][order["index"]]
            await send_to_admin(context, token)
        else:
            # EXPIRED
            await context.bot.send_message(
                order["customer"]["id"],
                "❌ Sorry, your order expired (no admin available). Please order again."
            )
            del active_orders[token]
            return

# ================= SEND TO ADMIN =================
async def send_to_admin(context, token):
    order = active_orders[token]
    cust = order["customer"]

    caption = (
        f"📦 NEW ORDER\n"
        f"👤 {cust['name']}\n"
        f"🆔 {cust['id']}\n"
        f"📍 {cust['address']}\n"
        f"🎟 Token: {token}\n"
        f"💰 ₹{cust['final']}\n"
        f"💳 {cust['payment']}"
    )

    if cust.get("upi"):
        caption += f"\n👛 UPI: {cust['upi']}"

    kb = [
        [InlineKeyboardButton("Accept ✅", callback_data=f"accept_{token}")],
        [InlineKeyboardButton("Reject ❌", callback_data=f"reject_{token}")]
    ]

    await context.bot.send_photo(
        order["assigned_admin"],
        cust["image"],
        caption=caption,
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= ADMIN CALLBACKS =================
async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action, token = q.data.split("_")
    token = int(token)
    order = active_orders.get(token)

    if not order:
        await q.message.reply_text("❌ Order expired")
        return

    if q.from_user.id != order["assigned_admin"]:
        await q.message.reply_text("❌ Order expired or reassigned")
        return

    if order["status"] == "accepted" and action != "complete":
        await q.message.reply_text("❌ Order already accepted")
        return

    if action == "accept":
        order["status"] = "accepted"
        await context.bot.send_message(
            order["customer"]["id"],
            "✅ Your order has been accepted"
        )
        kb = [[InlineKeyboardButton("Complete Order 📦", callback_data=f"complete_{token}")]]
        await q.message.reply_text("Order accepted:", reply_markup=InlineKeyboardMarkup(kb))

    elif action == "reject":
        order["index"] += 1
        if order["index"] < len(order["admins"]):
            order["assigned_admin"] = order["admins"][order["index"]]
            await send_to_admin(context, token)
        else:
            await context.bot.send_message(
                order["customer"]["id"],
                "❌ Sorry, your order was rejected by all admins."
            )
            del active_orders[token]

    elif action == "complete":
        tracking_wait[q.from_user.id] = token
        await q.message.reply_text("🚚 Send tracking link:")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons, pattern="^(order|price|cod|prepaid)$"))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^(accept|reject|complete)_"))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, messages))

    print("🚀 Bot running...")
    app.run_polling()
