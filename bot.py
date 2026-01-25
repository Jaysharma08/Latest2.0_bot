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
payment_wait = {}   # uid -> token (for prepaid)
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
        [aid for aid, a in ADMINS.items() if a["role"] == "admin" and a["status"] == "online"],
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
        kb = [["Online ✅", "Offline ❌"]]
        await update.message.reply_text(
            "👋 Admin Panel",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return

    kb = [[InlineKeyboardButton("🍔 Food Ordering", callback_data="order")]]
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

    if q.data.startswith("pay_"):
        mode = q.data.split("_")[1]
        token = context.user_data.get("token")
        order = active_orders.get(token)

        if not order:
            await q.message.reply_text("❌ Order expired")
            return

        order["payment_mode"] = mode

        if mode == "cod":
            await send_to_admin(context, token)
            await q.message.reply_text("✅ Order placed (Cash on Delivery)")
        else:
            payment_wait[q.from_user.id] = token
            await q.message.reply_text("💳 Apni UPI ID bheje (example: name@upi)")

# ================= MESSAGE HANDLER =================
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    text = update.message.text if update.message.text else ""

    # ===== FOOD ORDER FLOW =====
    if context.user_data.get("mode") == "order":
        data = context.user_data.setdefault("data", {})

        if "address" not in data:
            data["address"] = text
            await update.message.reply_text("📸 Send food/card image")
            return

        if "image" not in data and update.message.photo:
            data["image"] = update.message.photo[-1].file_id
            await update.message.reply_text("💵 Enter item price (minimum ₹149):")
            return

        if "price" not in data:
            try:
                data["price"] = float(text)
                if data["price"] < 149:
                    await update.message.reply_text("❌ Minimum item price is ₹149")
                    return
            except:
                await update.message.reply_text("❌ Enter valid price")
                return

            await update.message.reply_text("🧾 Enter GST:")
            return

        if "gst" not in data:
            try:
                gst = float(text)
            except:
                await update.message.reply_text("❌ Enter valid GST")
                return

            token = generate_token()
            final = calculate_final(data["price"], gst)
            admins = online_admins()

            if not admins:
                await update.message.reply_text("❌ No admin online")
                return

            active_orders[token] = {
                "status": "pending",
                "admins": admins,
                "index": 0,
                "assigned_admin": admins[0],
                "payment_mode": None,
                "customer": {
                    "id": uid,
                    "name": user.full_name,
                    "address": data["address"],
                    "image": data["image"],
                    "final": final,
                    "upi": None
                }
            }

            context.user_data.clear()
            context.user_data["token"] = token

            kb = [
                [InlineKeyboardButton("💵 Cash on Delivery", callback_data="pay_cod")],
                [InlineKeyboardButton("💳 Prepaid", callback_data="pay_prepaid")]
            ]

            await update.message.reply_text(
                f"🎟 Token {token}\n💰 Total: ₹{final}\n\nSelect payment mode:",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return

    # ===== USER ENTERS UPI ID (PREPAID) =====
    if uid in payment_wait and update.message.text and "@" in text:
        token = payment_wait[uid]
        active_orders[token]["customer"]["upi"] = text
        await update.message.reply_text("📸 Ab payment screenshot bheje")
        return

    # ===== PAYMENT SCREENSHOT =====
    if uid in payment_wait and update.message.photo:
        token = payment_wait.pop(uid)
        await send_to_admin(context, token)
        await update.message.reply_text("✅ Payment received, order sent to admin")
        return

# ================= ADMIN FLOW =================
async def send_to_admin(context, token):
    order = active_orders[token]
    admin = order["assigned_admin"]
    cust = order["customer"]

    kb = [
        [InlineKeyboardButton("Accept ✅", callback_data=f"accept_{token}")],
        [InlineKeyboardButton("Reject ❌", callback_data=f"reject_{token}")]
    ]

    caption = (
        f"📦 NEW ORDER\n"
        f"👤 {cust['name']}\n"
        f"🆔 {cust['id']}\n"
        f"📍 {cust['address']}\n"
        f"🎟 Token: {token}\n"
        f"💰 Amount: ₹{cust['final']}\n"
        f"💳 Payment: {order['payment_mode'].upper()}\n"
    )

    if order["payment_mode"] == "prepaid":
        caption += f"👛 User UPI: {cust.get('upi', 'N/A')}\n"

    await context.bot.send_photo(
        admin,
        cust["image"],
        caption=caption,
        reply_markup=InlineKeyboardMarkup(kb)
    )

    asyncio.create_task(admin_timeout(context, token))


async def admin_timeout(context, token):
    await asyncio.sleep(60)
    order = active_orders.get(token)
    if order and order["status"] == "pending":
        order["index"] += 1
        if order["index"] < len(order["admins"]):
            order["assigned_admin"] = order["admins"][order["index"]]
            await send_to_admin(context, token)
        else:
            del active_orders[token]

# ================= CALLBACKS =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if "_" not in q.data:
        return

    action, token = q.data.split("_", 1)
    token = int(token)
    order = active_orders.get(token)

    if not order:
        await q.message.reply_text("❌ Order expired")
        return

    if action == "accept":
        order["status"] = "accepted"
        await context.bot.send_message(order["customer"]["id"], "✅ Order accepted")

    elif action == "reject":
        order["index"] += 1
        if order["index"] < len(order["admins"]):
            order["assigned_admin"] = order["admins"][order["index"]]
            await send_to_admin(context, token)
        else:
            del active_orders[token]

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, messages))

    print("🚀 Bot running...")
    app.run_polling()
