from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta

# Admin Telegram ID
ADMIN_ID = 1168307789

# In-memory storage
users = {}
blocked_users = set()
monthly_limit = 200000
monthly_used = 0
lifetime_profits = {}
withdraw_requests = {}

# Format user message
def format_message(user_id, status, profit, used_limit, other_limit=None):
    remaining_limit = monthly_limit - monthly_used
    return (
        "BINANCE P2P\n\n"
        f"Order Status: {status}\n"
        f"Date & Time: {datetime.now().strftime('%d-%b-%Y, %I:%M %p')}\n"
        f"Daily Profit: ₹{profit:,}\n"
        f"LIMIT REMAINING: ₹{remaining_limit:,} / ₹{monthly_limit:,}\n"
        f"Other Limit: {other_limit if other_limit else 'Nil'}\n"
        f"Lifetime Profit: ₹{lifetime_profits.get(user_id, 0):,}"
    )

def days_until_next_month():
    today = datetime.now()
    next_month = today.replace(day=28) + timedelta(days=4)
    first_of_next = next_month - timedelta(days=next_month.day - 1)
    return (first_of_next - today).days

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in blocked_users:
        return
    users[user.id] = {'username': user.username or user.full_name, 'daily_profit': 0, 'monthly_profit': 0}
    keyboard = [
        [InlineKeyboardButton("Check Daily Profit", callback_data="check_daily_profit")],
        [InlineKeyboardButton("Check Monthly Profit", callback_data="check_monthly_profit")],
        [InlineKeyboardButton("Withdraw", callback_data="withdraw")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome! Choose an option from the menu:", reply_markup=reply_markup)

# Button handler
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id in blocked_users:
        return
    if query.data == "check_daily_profit":
        daily_profit = users[user_id].get('daily_profit', 0)
        await query.edit_message_text(f"Your Daily Profit: ₹{daily_profit:,}")
    elif query.data == "check_monthly_profit":
        monthly_profit = users[user_id].get('monthly_profit', 0)
        await query.edit_message_text(f"Your Monthly Profit: ₹{monthly_profit:,}")
    elif query.data == "withdraw":
        if withdraw_requests.get(user_id, False):
            await query.edit_message_text("Your withdrawal request is already in process. Please wait.")
        else:
            withdraw_requests[user_id] = True
            days_left = days_until_next_month()
            await query.edit_message_text(f"Withdrawal request submitted. Please wait for admin confirmation;\n{days_left} day(s) remaining until the 1st of next month.")

# /withdraw
async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in blocked_users:
        return
    today = datetime.now()
    if today.day == 1:
        withdraw_requests[user_id] = True
        await update.message.reply_text("Withdrawal request submitted. Please wait for admin confirmation.")
    else:
        days_left = days_until_next_month()
        await update.message.reply_text(f"Withdrawals available on the 1st. Please wait {days_left} day(s).")

# /broadcast_all <profit> <used> [other]
async def broadcast_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /broadcast_all <profit> <limit_used> [other_limit]")
        return
    profit = int(context.args[0])
    used = int(context.args[1])
    other = context.args[2] if len(context.args) > 2 else None
    global monthly_used
    monthly_used += used
    for uid in users:
        if uid in blocked_users or uid == ADMIN_ID:
            continue
        lifetime_profits[uid] = lifetime_profits.get(uid, 0) + profit
        msg = format_message(uid, "Complete ✅", profit, used, other)
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except:
            continue
    await update.message.reply_text("Broadcast sent to all users.")

# /broadcast_user <uid> <profit> <used> [other]
async def broadcast_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or len(context.args) < 3:
        await update.message.reply_text("Usage: /broadcast_user <user_id> <profit> <limit_used> [other_limit]")
        return
    uid = int(context.args[0])
    if uid == ADMIN_ID:
        await update.message.reply_text("Cannot send message to admin.")
        return
    profit = int(context.args[1])
    used = int(context.args[2])
    other = context.args[3] if len(context.args) > 3 else None
    global monthly_used
    monthly_used += used
    lifetime_profits[uid] = lifetime_profits.get(uid, 0) + profit
    msg = format_message(uid, "Complete ✅", profit, used, other)
    try:
        await context.bot.send_message(chat_id=uid, text=msg)
        await update.message.reply_text(f"Message sent to user {uid}.")
    except:
        await update.message.reply_text("Failed to send message.")

# /withdraw_done <uid>
async def withdraw_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or len(context.args) != 1:
        return
    uid = int(context.args[0])
    if uid in users:
        withdraw_requests.pop(uid, None)
        await context.bot.send_message(chat_id=uid, text="Withdrawal completed successfully. Thank you!")
        await update.message.reply_text("Withdrawal marked as done.")
    global monthly_used
    monthly_used = 0

# /users
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    reply = "\n".join(f"{uid}: {info['username']}" for uid, info in users.items())
    await update.message.reply_text(f"Registered users:\n{reply}")

# /block <uid>
async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or len(context.args) != 1:
        return
    uid = int(context.args[0])
    blocked_users.add(uid)
    try:
        await context.bot.send_message(chat_id=uid, text="You have been blocked by the admin. You will no longer receive updates.")
    except:
        pass
    await update.message.reply_text(f"User {uid} has been blocked.")

# /status_fail
async def status_fail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    for uid in users:
        if uid in blocked_users:
            continue
        msg = format_message(uid, "Failed 🚫", 0, 0)
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except:
            continue
    await update.message.reply_text("Fail status sent to all users.")

# /send_message <uid> <msg>
async def send_custom_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or len(context.args) < 2:
        await update.message.reply_text("Usage: /send_message <user_id> <your message>")
        return
    uid = int(context.args[0])
    msg = " ".join(context.args[1:])
    try:
        await context.bot.send_message(chat_id=uid, text=msg)
        await update.message.reply_text("Message sent successfully.")
    except:
        await update.message.reply_text("Failed to send message.")

# /send_all_message <msg>
async def send_all_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args:
        await update.message.reply_text("Usage: /send_all_message <your message>")
        return
    msg = " ".join(context.args)
    sent = 0
    for uid in users:
        if uid in blocked_users:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
            sent += 1
        except:
            continue
    await update.message.reply_text(f"Custom message sent to {sent} users.")

# Start bot
app = ApplicationBuilder().token("6576492751:AAGWhArydCfGAjSFDE1g6ddRkAMcBe-BsPk").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("withdraw", withdraw))
app.add_handler(CommandHandler("broadcast_all", broadcast_all))
app.add_handler(CommandHandler("broadcast_user", broadcast_user))
app.add_handler(CommandHandler("withdraw_done", withdraw_done))
app.add_handler(CommandHandler("users", list_users))
app.add_handler(CommandHandler("block", block_user))
app.add_handler(CommandHandler("status_fail", status_fail))
app.add_handler(CommandHandler("send_message", send_custom_message))
app.add_handler(CommandHandler("send_all_message", send_all_message))
app.add_handler(CallbackQueryHandler(button))

print("Bot is running...")
app.run_polling()
