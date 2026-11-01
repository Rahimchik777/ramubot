import os
import time
import threading
import requests
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- НАСТРОЙКИ ---
BOT_TOKEN = "9244886158:AAEof79CZ7_LKOTX-ExtqGDrgXc365HHifs"
ADMIN_GROUP_ID = -1001234567895  # Потом поменяешь на ID своей группы

# --- ВЕБ-СЕРВЕР ДЛЯ БЕССМЕРТИЯ НА RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "RAMU Store Bot 24/7 ishlamoqda!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def self_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        while True:
            try:
                time.sleep(240)
                requests.get(url)
            except Exception:
                pass

def keep_alive():
    t1 = threading.Thread(target=run_flask)
    t1.daemon = True
    t1.start()
    t2 = threading.Thread(target=self_ping)
    t2.daemon = True
    t2.start()

# --- ЛОГИКА БОТА НА УЗБЕКСКОМ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_html(
        f"Assalomu alaykum, <b>{user_name}</b>! 🚀\n"
        f"<b>RAMU Store</b> rasmiy botiga xush kelibsiz.\n\n"
        f"Murojaat matnini yoki buyurtmangizni shu yerga yozib qoldiring:"
    )

async def notify_admin_group(context: ContextTypes.DEFAULT_TYPE, order_details: str):
    try:
        await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=f"🔔 <b>YANGI XABAR!</b>\n\n{order_details}", parse_mode="HTML")
    except Exception as e:
        print(f"Xatolik: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    order_info = (
        f"👤 <b>Mijoz:</b> {user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"💬 <b>Xabar:</b> {text}"
    )
    await update.message.reply_text("✅ Xabaringiz qabul qilindi! Operatorimiz tez orada javob beradi.")
    await notify_admin_group(context, order_info)

def main():
    keep_alive() # Запускаем Flask до бота!
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 BOT ISHGA TUSHDI!")
    application.run_polling()

if __name__ == '__main__':
    main()