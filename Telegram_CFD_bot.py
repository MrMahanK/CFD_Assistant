import json
import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# --- ۱. ساخت سرور Flask برای فعال نگه داشتن Web Service در Render ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running successfully!"

def run_flask():
    # دریافت پورت از متغیرهای محیطی Render یا پورت پیش‌فرض 8080
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)


# --- ۲. تنظیمات ربات ---
BOT_TOKEN = "8833988999:AAGYTymK0y64xHsUzsvVfusxaoxQ68LUmaE"  # توکن دریافت شده از BotFather
ADMIN_CHAT_ID = 78663377          # Chat ID عددی تلگرام شما

DATA_FILE = "data.json"

# وضعیت‌های ConversationHandler
WAITING_FOR_NAME = 1
WAITING_FOR_STUDENT_ID = 2


# --- ۳. توابع مدیریت داده‌ها ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- ۴. کیبورد شیشه‌ای اعداد ۱ تا ۴۷ ---
def get_numbers_keyboard():
    data = load_data()
    keyboard = []
    row = []
    
    for num in range(1, 48):
        str_num = str(num)
        if str_num in data:
            btn_text = f"❌ {num}"
        else:
            btn_text = f"✅ {num}"
            
        row.append(InlineKeyboardButton(btn_text, callback_data=f"select_{num}"))
        
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    return InlineKeyboardMarkup(keyboard)


# --- ۵. توابع هندلر تلگرام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! لطفاً یکی از شماره‌های خالی را انتخاب کنید:",
        reply_markup=get_numbers_keyboard()
    )
    return ConversationHandler.END

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_num = query.data.split("_")[1]
    data = load_data()
    
    if selected_num in data:
        await query.edit_message_text(
            f"متأسفانه شماره {selected_num} قبلاً توسط شخص دیگری ثبت شده است.\nلطفاً مجدداً /start را بزنید و شماره دیگری انتخاب کنید."
        )
        return ConversationHandler.END
    
    context.user_data["selected_number"] = selected_num
    await query.edit_message_text(f"شما شماره {selected_num} را انتخاب کردید.\nلطفاً **نام و نام خانوادگی** خود را ارسال کنید:")
    return WAITING_FOR_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text
    context.user_data["full_name"] = user_name
    
    await update.message.reply_text("لطفاً **شماره دانشجویی** خود را وارد کنید:")
    return WAITING_FOR_STUDENT_ID

async def get_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_id = update.message.text
    full_name = context.user_data.get("full_name", "نامشخص")
    selected_num = context.user_data.get("selected_number")
    user = update.effective_user
    
    data = load_data()
    
    if selected_num in data:
        await update.message.reply_text("متأسفانه این شماره در همین لحظه توسط شخص دیگری ثبت شد. لطفاً دوباره /start را بزنید.")
        return ConversationHandler.END
    
    # ثبت در دیتابیس
    data[selected_num] = {
        "full_name": full_name,
        "student_id": student_id,
        "username": f"@{user.username}" if user.username else "ندارد",
        "user_id": user.id
    }
    save_data(data)
    
    await update.message.reply_text(f"✅ شماره {selected_num} با موفقیت به نام شما ({full_name}) ثبت شد.")
    
    # ارسال اطلاعات به پی‌وی ادمین
    admin_message = (
        f"📌 **ثبت‌نام جدید انجام شد:**\n\n"
        f"🔢 **شماره انتخابی:** {selected_num}\n"
        f"👤 **نام و نام خانوادگی:** {full_name}\n"
        f"🎓 **شماره دانشجویی:** {student_id}\n"
        f"🆔 **آیدی تلگرام:** {data[selected_num]['username']} (ID: `{user.id}`)"
    )
    
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, parse_mode="Markdown")
    except Exception as e:
        print(f"خطا در ارسال پیام به ادمین: {e}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد. برای شروع مجدد /start را بزنید.")
    return ConversationHandler.END


# --- ۶. اجرای اصلی برنامه ---
def main():
    # اجرای Flask در یک گردهای (Thread) جداگانه
    threading.Thread(target=run_flask, daemon=True).start()

    # ساخت اپلیکیشن تلگرام
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_click, pattern="^select_")],
        states={
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            WAITING_FOR_STUDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_student_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    print("ربات و سرور وب فعال شدند...")
    app.run_polling()

if __name__ == "__main__":
    main()
