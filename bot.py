import json
import os
import threading
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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

# --- ۱. ساخت سرور Flask برای فعال نگه داشتن Render ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is running securely with Google Sheets!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)


# --- ۲. تنظیمات ربات ---
BOT_TOKEN = "8833988999:AAGYTymK0y64xHsUzsvVfusxaoxQ68LUmaE"  # توکن دریافت شده از BotFather
ADMIN_CHAT_ID = 78663377          # Chat ID عددی تلگرام شما

# وضعیت‌های ConversationHandler
WAITING_FOR_NAME = 1
WAITING_FOR_STUDENT_ID = 2


# --- ۳. اتصال امن به گوگل شیت (Google Sheets) ---
def get_google_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    google_creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    if google_creds_json:
        creds_dict = json.loads(google_creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        
    client = gspread.authorize(creds)
    sheet = client.open("TelegramBotData").sheet1
    return sheet

# دریافت لیست شماره‌های ثبت‌شده
def get_registered_numbers():
    try:
        sheet = get_google_sheet()
        numbers = sheet.col_values(1)  # ستون ۱: شماره
        if numbers and numbers[0] == "شماره انتخابی":
            numbers = numbers[1:]
        return set(numbers)
    except Exception as e:
        print(f"خطا در خواندن گوگل شیت: {e}")
        return set()

# دریافت شماره‌ای که این کاربر ثبت کرده (در صورت وجود)
def get_user_registered_number(user_id):
    try:
        sheet = get_google_sheet()
        records = sheet.get_all_records()
        str_user_id = str(user_id)
        for record in records:
            if str(record.get("User ID", "")) == str_user_id:
                return str(record.get("شماره انتخابی", ""))
        return None
    except Exception as e:
        print(f"خطا در بررسی شماره کاربر: {e}")
        return None

# ثبت ردیف جدید در گوگل شیت
def save_to_sheet(selected_num, full_name, student_id, username, user_id):
    try:
        sheet = get_google_sheet()
        sheet.append_row([str(selected_num), str(full_name), str(student_id), str(username), str(user_id)])
        return True
    except Exception as e:
        print(f"خطا در ثبت در گوگل شیت: {e}")
        return False

# حذف سطر کاربر از گوگل شیت
def delete_user_registration(user_id):
    try:
        sheet = get_google_sheet()
        cell = sheet.find(str(user_id))
        if cell:
            sheet.delete_rows(cell.row)
            return True
        return False
    except Exception as e:
        print(f"خطا در حذف از گوگل شیت: {e}")
        return False


# --- ۴. کیبورد شیشه‌ای اعداد و منوی کاربر ---
def get_main_menu_keyboard(user_id):
    registered_numbers = get_registered_numbers()
    user_number = get_user_registered_number(user_id)
    
    keyboard = []
    row = []
    
    # ساخت دکمه‌های اعداد ۱ تا ۴۷
    for num in range(1, 48):
        str_num = str(num)
        if str_num in registered_numbers:
            btn_text = f"❌ {num}"
        else:
            btn_text = f"✅ {num}"
            
        row.append(InlineKeyboardButton(btn_text, callback_data=f"select_{num}"))
        
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    # اگر کاربر قبلاً شماره ثبت کرده باشد، دکمه حذف هم اضافه می‌شود
    if user_number:
        keyboard.append([
            InlineKeyboardButton(f"🗑 حذف شماره ثبت‌شده من ({user_number})", callback_data="delete_my_number")
        ])
        
    return InlineKeyboardMarkup(keyboard)


# --- ۵. توابع هندلر تلگرام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_number = get_user_registered_number(user_id)
    
    msg = "سلام! لطفاً یکی از شماره‌های خالی را انتخاب کنید:"
    if user_number:
        msg = f"سلام! شما قبلاً شماره **{user_number}** را ثبت کرده‌اید.\nاگر می‌خواهید آن را پاک کرده و شماره دیگری انتخاب کنید، روی دکمه پایین بزنید:"
        
    if update.message:
        await update.message.reply_text(msg, reply_markup=get_main_menu_keyboard(user_id), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=get_main_menu_keyboard(user_id), parse_mode="Markdown")
        
    return ConversationHandler.END

# کلیک روی دکمه‌ها
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    data_action = query.data

    # درخواست حذف شماره توسط کاربر
    if data_action == "delete_my_number":
        user_num = get_user_registered_number(user.id)
        if user_num:
            success = delete_user_registration(user.id)
            if success:
                await query.edit_message_text(
                    f"✅ شماره {user_num} با موفقیت پاک شد و مجدداً آزاد گردید.\nبرای انتخاب شماره جدید /start را بزنید."
                )
                
                # اطلاع به ادمین
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=f"🗑 **حذف شماره:** کاربر {user.full_name} (@{user.username}) شماره {user_num} را پاک کرد."
                    )
                except Exception as e:
                    print(f"خطا در ارسال پیام حذف به ادمین: {e}")
            else:
                await query.edit_message_text("خطایی در پاک کردن شماره رخ داد. لطفاً مجدداً تلاش کنید.")
        else:
            await query.edit_message_text("شماره‌ای به نام شما پیدا نشد.")
        return ConversationHandler.END

    # انتخاب عدد
    selected_num = data_action.split("_")[1]
    
    # بررسی اینکه کاربر از قبل شماره‌ای ثبت نکرده باشد
    user_existing_number = get_user_registered_number(user.id)
    if user_existing_number:
        await query.edit_message_text(
            f"⚠️ شما قبلاً شماره **{user_existing_number}** را ثبت کرده‌اید!\n"
            f"برای انتخاب شماره جدید ابتدا باید شماره قبلی خود را حذف کنید.\nمجدداً /start را بزنید."
        )
        return ConversationHandler.END

    registered_numbers = get_registered_numbers()
    if selected_num in registered_numbers:
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
    username = f"@{user.username}" if user.username else "ندارد"
    
    # بررسی مجدد قفل همزمانی
    registered_numbers = get_registered_numbers()
    if selected_num in registered_numbers:
        await update.message.reply_text("متأسفانه این شماره در همین لحظه توسط شخص دیگری ثبت شد. لطفاً دوباره /start را بزنید.")
        return ConversationHandler.END
    
    # ثبت در گوگل شیت (همراه با User ID برای شناسایی موقع حذف)
    success = save_to_sheet(selected_num, full_name, student_id, username, user.id)
    
    if not success:
        await update.message.reply_text("خطایی در ثبت اطلاعات رخ داد. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END

    await update.message.reply_text(f"✅ شماره {selected_num} با موفقیت به نام شما ({full_name}) ثبت شد.")
    
    # ارسال پیام به پی‌وی ادمین
    admin_message = (
        f"📌 **ثبت‌نام جدید انجام شد:**\n\n"
        f"🔢 **شماره انتخابی:** {selected_num}\n"
        f"👤 **نام و نام خانوادگی:** {full_name}\n"
        f"🎓 **شماره دانشجویی:** {student_id}\n"
        f"🆔 **آیدی تلگرام:** {username} (ID: `{user.id}`)"
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
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_click, pattern="^(select_|delete_my_number)")],
        states={
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            WAITING_FOR_STUDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_student_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    print("ربات فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()