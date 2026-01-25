import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_ADMIN_ID = int(os.getenv("MAIN_ADMIN_ID"))

MIN_ORDER = 149
DISCOUNT = 0.5
BOT_NAME = "Swiggy Food Bot"




# # ================= BOT CONFIGURATION =================

# # 🔐 Telegram Bot Token
# BOT_TOKEN = "8348696504:AAHgcviCCk7TT3wn4PHYiMB9cXDGIt_Qzkc"


# # ================= ADMIN CONFIG =================
# # Admin format:
# # admin_id: {
# #     "name": "Admin Name",
# #     "status": "offline"   # online / offline (changed at /start)
# # }

# ADMINS = {
#     8343821588: {
#         "name": "Admin1",
#         "status": "offline"
#     },
#     8403558393: {
#         "name": "Admin2",
#         "status": "offline"
#     },
# }

# # 👑 Main Admin (can add new admins in future)
# MAIN_ADMIN_ID = 5808294584


# # ================= ORDER RULES =================

# # 🧾 Minimum food order value
# MIN_ORDER = 149

# # 💸 Discount rate (50%)
# DISCOUNT = 0.50

# # ⏱ Admin accept / reject countdown (seconds)
# COUNTDOWN = 60   # 1 minute


# # ================= PAYMENT =================

# # 💳 UPI ID shown to customers (change anytime)
# UPI_ID = "1234@okcici"


# # ================= BOT INFO =================

# BOT_NAME = "Swiggy Food Bot 🤖🍔"
# SUPPORT_MESSAGE = "For help, please wait — our admins are on the way 🚀"









# BOT_TOKEN = "8348696504:AAHBCFvIv_kKwKq5TV0phzz7g8Qq3XFy4vQ"

# MAIN_ADMIN_ID = 5808294584  # your telegram numeric ID

# MIN_ORDER = 149
# DISCOUNT = 0.5
# UPI_ID = "yourupi@bank"
# BOT_NAME = "Food Order Bot"

# import os

# BOT_TOKEN = os.environ.get("BOT_TOKEN")
# if not BOT_TOKEN:
#     raise RuntimeError("BOT_TOKEN is not set in environment variables")

# MAIN_ADMIN_ID = int(os.environ.get("MAIN_ADMIN_ID", "0"))
# MIN_ORDER = float(os.environ.get("MIN_ORDER", "149"))
# DISCOUNT = float(os.environ.get("DISCOUNT", "0.5"))
# BOT_NAME = os.environ.get("BOT_NAME", "FoodBot")



