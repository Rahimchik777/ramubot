import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ==========================================
# ⚙️ НАСТРОЙКИ И ДАННЫЕ
# ==========================================
BOT_TOKEN = "9244886158:AAE9IMYFokxS2DIPHMyAPSCudoNZi6494FA"
ADMIN_GROUP_ID = -1004328946925

# Включаем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Хранилище связок: { message_id_in_group: user_id }
reply_mapping = {}

# ==========================================
# 🤖 ЛОГИКА ДЛЯ ПОЛЬЗОВАТЕЛЕЙ (В БОТЕ)
# ==========================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реакция на команду /start"""
    user = update.effective_user
    first_name = user.first_name if user.first_name else "дорогой гость"
    
    welcome_text = (
        f"Здравствуйте, {first_name}!\n\n"
        f"Тут вы сможете написать по любым вопросам поддержки. "
        f"Наша поддержка работает очень быстро, 24/7!\n\n"
        f"Нажмите на кнопку ниже, чтобы задать вопрос."
    )
    
    keyboard = [[KeyboardButton("📝 Написать в поддержку")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений от пользователя"""
    text = update.message.text
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Игнорируем сообщения из админской группы
    if chat_id == ADMIN_GROUP_ID:
        return

    # Нажатие на кнопку поддержки
    if text == "📝 Написать в поддержку":
        await update.message.reply_text("Напишите, по какому вопросу вы обращаетесь.")
        return

    # Если клиент отправляет вопрос
    await update.message.reply_text("Ожидайте, скоро вам ответят.")

    forwarded_text = (
        f"📩 <b>НОВОЕ ОБРАЩЕНИЕ В ПОДДЕРЖКУ</b>\n\n"
        f"👤 <b>От кого:</b> {user.full_name} (@{user.username if user.username else 'нет_юзернейма'})\n"
        f"🆔 <b>ID пользователя:</b> <code>{user.id}</code>\n\n"
        f"💬 <b>Текст вопроса:</b>\n{text}\n\n"
        f"<i>⚠️ Чтобы ответить клиенту, нажмите «Ответить» (Reply) на ЭТО сообщение!</i>"
    )

    group_msg = await context.bot.send_message(
        chat_id=ADMIN_GROUP_ID,
        text=forwarded_text,
        parse_mode="HTML"
    )

    reply_mapping[group_msg.message_id] = user.id


# ==========================================
# 👑 ЛОГИКА ДЛЯ АДМИНОВ (ОТВЕТЫ ИЗ ГРУППЫ)
# ==========================================

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка ответа из группы в чат бота с клиентом"""
    message = update.effective_message
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_GROUP_ID:
        return

    if not message.reply_to_message:
        return

    original_msg_id = message.reply_to_message.message_id

    if original_msg_id in reply_mapping:
        target_user_id = reply_mapping[original_msg_id]
        admin_reply_text = message.text

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"👨‍💻 <b>Ответ поддержки RAMU:</b>\n\n{admin_reply_text}",
                parse_mode="HTML"
            )
            await message.reply_text("✅ Ответ успешно отправлен клиенту!")
        except Exception as e:
            await message.reply_text(f"❌ Ошибка отправки: {e}")
    else:
        await message.reply_text("⚠️ Не удалось найти клиента для этого сообщения.")


# ==========================================
# 🚀 ЗАПУСК БОТА
# ==========================================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 БОТ ПОДДЕРЖКИ RAMU STORE УСПЕШНО ЗАПУЩЕН!")
    print("🤖 Бот ожидает сообщений...")
    print("=" * 50)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Исправленные фильтры без filters.CHAT
    app.add_handler(CommandHandler("start", start_command))
    
    app.add_handler(MessageHandler(
        filters.Chat(ADMIN_GROUP_ID) & filters.REPLY & filters.TEXT,
        handle_admin_reply
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Chat(ADMIN_GROUP_ID),
        handle_user_messages
    ))

    app.run_polling()