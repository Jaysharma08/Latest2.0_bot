# ================= IMPORTS =================
import asyncio
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
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

active_orders = {}
token_counter = 0
prepaid_wait = {}  # user_id -> token

# ================= HELPERS =================
def generate_token():
    global token_counter
    token_counter += 1
    return token_counter


def final_amount(price, gst):
    return round((price * 0.5) + gst, 2)


# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # ---- MAIN ADMIN ----
    if uid == MAIN_ADMIN_ID:
        kb = [["Add New Admin ➕", "Remove Admin ➖"], ["📊 Admin Status"]]
        await update.message.reply_text(
            "👑 Main Admin Panel",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return

    # ---- CUSTOMER ----
    kb = [[InlineKeyboardButton("🍔 Food Ordering", callback_data="food")]]
    await update.message.reply_text(
        f"👋 Welcome to {BOT_NAME}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= BUTTON HANDLER =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "food":
        context.user_data.clear()
        context.user_data["step"] = "address"
        await q.message.reply_text("📍 Send delivery address:")
        return

    if q.data.startswith("pay_"):
        mode = q.data.split("_")[1]
        token = context.user_data["token"]
        order = active_orders[token]
        order["payment_mode"] = mode

        if mode == "cod":
            await send_to_admin(context, token)
            await q.message.reply_text("✅ Order placed (COD)")
        else:
            prepaid_wait[q.from_user.id] = token
            await q.message.reply_text("💳 Apni UPI ID bheje:")

# ================= MESSAGE HANDLER =================
async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    # ---------- ORDER FLOW ----------
    if "step" in context.user_data:
        step = context.user_data["step"]

        if step == "address":
            context.user_data["address"] = text
            context.user_data["step"] = "price"
            await update.message.reply_text("💵 Enter item price (min ₹149):")
            return

        if step == "price":
            try:
                price = float(text)
                if price < 149:
                    raise ValueError
            except:
                await update.message.reply_text("❌ Enter valid price (≥149)")
                return

            context.user_data["price"] = price
            context.user_data["step"] = "gst"
            await update.message.reply_text("🧾 Enter GST:")
            return

        if step == "gst":
            try:
                gst = float(text)
            except:
                await update.message.reply_text("❌ Enter valid GST")
                return

            token = generate_token()
            final = final_amount(context.user_data["price"], gst)

            active_orders[token] = {
                "customer": {
                    "id": uid,
                    "address": context.user_data["address"],
                    "final": final,
                    "upi": None
                },
                "payment_mode": None
            }

            context.user_data.clear()
            context.user_data["token"] = token

            kb = [
                [InlineKeyboardButton("💵 COD", callback_data="pay_cod")],
                [InlineKeyboardButton("💳 PREPAID", callback_data="pay_prepaid")]
            ]

            await update.message.reply_text(
                f"🎟 Token: {token}\n💰 Total: ₹{final}\n\nSelect payment mode:",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            return

    # ---------- PREPAID UPI ----------
    if uid in prepaid_wait:
        token = prepaid_wait.pop(uid)
        active_orders[token]["customer"]["upi"] = text
        await send_to_admin(context, token)
        await update.message.reply_text("✅ Order placed (PREPAID)")
        return

# ================= SEND TO ADMIN =================
async def send_to_admin(context, token):
    order = active_orders[token]
    cust = order["customer"]

    msg = (
        f"📦 NEW ORDER\n"
        f"🆔 User: {cust['id']}\n"
        f"📍 Address: {cust['address']}\n"
        f"🎟 Token: {token}\n"
        f"💰 Amount: ₹{cust['final']}\n"
        f"💳 Payment: {order['payment_mode'].upper()}\n"
    )

    if order["payment_mode"] == "prepaid":
        msg += f"👛 UPI: {cust['upi']}\n"

    await context.bot.send_message(MAIN_ADMIN_ID, msg)

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT, messages))

    print("🚀 Bot running...")
    app.run_polling()
