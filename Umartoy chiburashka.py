import os
import time
import threading
import requests
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# --- ВАЖНЫЕ НАСТРОЙКИ ---
BOT_TOKEN = "9244886158:AAE9IMYFokxS2DIPHMyAPScudoNZi6494FA" # Вставь сюда свой НОВЫЙ токен, если ты его сбрасывал!

# ВНИМАНИЕ: Сюда нужно вставить НАСТОЯЩИЙ ID вашей группы! Без него пересылка работать НЕ БУДЕТ.
ADMIN_GROUP_ID = -1004328946925

# --- ВЕБ-СЕРВЕР ДЛЯ БЕССМЕРТИЯ НА RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "RAMU Store Bot 24/7 ishlamoqda!"s

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

# Красивое приветствие и физические кнопки
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    
    # Физическая клавиатура внизу экрана
    keyboard = [
        [KeyboardButton("💬 Admin bilan bog'lanish")],
        [KeyboardButton("🌐 RAMU Store saytiga o'tish")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    # Приветственный текст со стикерами
    welcome_text = (
        f"Assalomu alaykum, <b>{user_name}</b>! 🚀\n\n"
        f"Bu <b>RAMU Store</b> do'konining rasmiy qo'llab-quvvatlash xizmati.\n\n"
        f"Istalgan savolingizni yoki buyurtma ma'lumotlarini shu yerda yozib qoldiring. "
        f"Biz 24/7 rejimida ishlaymiz va sizga yordam berishdan xursandmiz! 🕒✨"
    )
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)


# Обработка любых текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user

    # Если клиент нажал на кнопку поддержки
    if text == "💬 Admin bilan bog'lanish":
        await update.message.reply_text("Iltimos, savolingizni yoki murojaatingizni shu yerga yozing. Operatorlarimiz sizga tezda javob berishadi! 👩‍💻👨‍💻")
        return
    # Если нажал на переход на сайт
    elif text == "🌐 RAMU Store saytiga o'tish":
        await update.message.reply_text("Saytimizga o'tish uchun ssilka: https://ramubot.onrender.com 🛒")
        return

    # Если клиент написал свой текст/заказ — формируем карточку для админов
    order_info = (
        f"🔔 <b>YANGI MUROJAAT / BUYURTMA</b> 🔔\n\n"
        f"👤 <b>Mijoz:</b> {user.full_name} (@{user.username if user.username else 'yoq'})\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
        f"💬 <b>Xabar matni:</b>\n{text}"
    )

    try:
        # Отправляем в админ-группу Умарбека
        await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=order_info, parse_mode="HTML")
        
        # Подтверждаем клиенту, что всё прошло успешно
        await update.message.reply_text("✅ Xabaringiz adminga muvaffaqiyatli yuborildi! Tez orada javob beramiz. 🚀")
    
    except Exception as e:
        print(f"XATOLIK: {e}")
        # Если бот не в группе или ID неправильный, предупреждаем клиента (и тебя)
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Xabar adminga yetib bormadi (Bot guruhga qo'shilmagan bo'lishi mumkin).")

def main():
    keep_alive() # Запускаем бессмертие
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 BOT ISHGA TUSHDI VA XABAR KUTMOQDA!")
    application.run_polling()

if __name__ == '__main__':
    main()