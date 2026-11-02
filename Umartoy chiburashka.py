import os
import re
import html
import time
import logging
import threading

import requests
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

# ---------------------------------------------------------------
# НАСТРОЙКИ
# Вставьте токен ниже между кавычками (единственное место в файле).
# ---------------------------------------------------------------
BOT_TOKEN = "9244886158:AAHpFQPprvuPtUYGcPOyiXlwX8jkOjyWcT4"

ADMIN_GROUP_ID = int(os.environ.get("ADMIN_GROUP_ID", "-1004328946925"))
SITE_URL = os.environ.get("SITE_URL", "https://ramubot.onrender.com")

BTN_CONTACT = "💬 Admin bilan bog'lanish"
BTN_SITE = "🌐 RAMU Store saytiga o'tish"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
# Эти библиотеки печатают токен в адресах запросов — глушим их
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
log = logging.getLogger("ramu-bot")

# ---------------------------------------------------------------
# ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы сервис не засыпал)
# ---------------------------------------------------------------
flask_app = Flask(__name__)


@flask_app.route("/")
def home():
    return "RAMU Store Bot 24/7 ishlamoqda!"


@flask_app.route("/health")
def health():
    return "ok"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)


def self_ping():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        return
    while True:
        time.sleep(240)
        try:
            requests.get(url, timeout=10)
        except Exception:
            pass


def keep_alive():
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=self_ping, daemon=True).start()


# ---------------------------------------------------------------
# ЛОГИКА БОТА
# ---------------------------------------------------------------
def esc(text) -> str:
    return html.escape(text or "")


async def log_update(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Пишет в лог каждое входящее обновление (для диагностики)."""
    if isinstance(update, Update):
        msg = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        text = (msg.text or msg.caption or "<не текст>") if msg else "<нет сообщения>"
        log.info(
            "ВХОДЯЩЕЕ: chat=%s (%s) user=%s text=%r",
            chat.id if chat else None,
            chat.type if chat else None,
            user.id if user else None,
            text[:60],
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = esc(update.effective_user.first_name)
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CONTACT)], [KeyboardButton(BTN_SITE)]],
        resize_keyboard=True,
    )
    await update.effective_message.reply_html(
        f"Assalomu alaykum, <b>{name}</b>! 🚀\n\n"
        f"Bu <b>RAMU Store</b> do'konining rasmiy qo'llab-quvvatlash xizmati.\n\n"
        f"Istalgan savolingizni yoki buyurtma ma'lumotlarini shu yerda yozib qoldiring. "
        f"Biz 24/7 rejimida ishlaymiz va sizga yordam berishdan xursandmiz! 🕒✨",
        reply_markup=keyboard,
    )


async def client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сообщение клиента (только личка) -> карточка в админ-группу."""
    msg = update.effective_message
    user = update.effective_user
    text = msg.text

    if text == BTN_CONTACT:
        await msg.reply_text(
            "Iltimos, savolingizni yoki murojaatingizni shu yerga yozing. "
            "Operatorlarimiz sizga tezda javob berishadi! 👩‍💻👨‍💻"
        )
        return
    if text == BTN_SITE:
        await msg.reply_text(f"Saytimizga o'tish uchun ssilka: {SITE_URL} 🛒")
        return

    username = f"@{user.username}" if user.username else "yo'q"
    if text:
        body = esc(text[:3500])
    else:
        body = "<i>(matn emas — pastdagi xabarga qarang)</i>"

    card = (
        "🔔 <b>YANGI MUROJAAT / BUYURTMA</b> 🔔\n\n"
        f"👤 <b>Mijoz:</b> {esc(user.full_name)} ({esc(username)})\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n\n"
        f"💬 <b>Xabar:</b>\n{body}"
    )

    try:
        sent = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID, text=card, parse_mode=ParseMode.HTML
        )
        reply_map = context.bot_data.setdefault("reply_map", {})
        reply_map[sent.message_id] = user.id

        # Фото, файлы, голосовые, стикеры и т.д. копируем под карточкой
        if not text:
            copied = await context.bot.copy_message(
                chat_id=ADMIN_GROUP_ID,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
                reply_to_message_id=sent.message_id,
            )
            reply_map[copied.message_id] = user.id

        await msg.reply_text(
            "✅ Xabaringiz adminga muvaffaqiyatli yuborildi! Tez orada javob beramiz. 🚀"
        )
    except TelegramError as e:
        log.error("Не удалось отправить в админ-группу: %s", e)
        await msg.reply_text(
            "⚠️ Xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring."
        )


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ админа (reply на карточку в группе) -> клиенту."""
    msg = update.effective_message
    replied = msg.reply_to_message

    # Реагируем только на ответ на сообщение самого бота
    if not replied or not replied.from_user or replied.from_user.id != context.bot.id:
        return

    reply_map = context.bot_data.get("reply_map", {})
    client_id = reply_map.get(replied.message_id)

    # Запасной вариант (после перезапуска бота): ID из текста карточки
    if client_id is None:
        source = replied.text or replied.caption or ""
        match = re.search(r"ID:\s*(\d+)", source)
        if match:
            client_id = int(match.group(1))

    if client_id is None:
        await msg.reply_text(
            "⚠️ Mijoz ID topilmadi. Iltimos, mijozning kartochkasiga "
            "(YANGI MUROJAAT) javob bering."
        )
        return

    try:
        if msg.text:
            await context.bot.send_message(
                chat_id=client_id,
                text=f"👩‍💻 <b>RAMU Store admini:</b>\n\n{esc(msg.text)}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await context.bot.copy_message(
                chat_id=client_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
            )
        await msg.reply_text("✅ Mijozga yuborildi")
    except Forbidden:
        await msg.reply_text("⚠️ Mijoz botni bloklagan, xabar yetib bormadi.")
    except TelegramError as e:
        log.error("Не удалось отправить клиенту: %s", e)
        await msg.reply_text(f"⚠️ Yuborib bo'lmadi: {e}")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Необработанная ошибка:", exc_info=context.error)


async def post_init(app):
    """Проверка при запуске: бот жив и видит админ-группу."""
    me = await app.bot.get_me()
    log.info("Бот запущен: @%s", me.username)
    try:
        chat = await app.bot.get_chat(ADMIN_GROUP_ID)
        log.info("Админ-группа найдена: %s", chat.title)
    except TelegramError as e:
        log.error(
            "ВНИМАНИЕ: бот не видит админ-группу (%s). "
            "Проверьте ID группы и что бот добавлен в неё.", e
        )


def main():
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Логирование всех входящих (отдельная группа, другие обработчики не блокирует)
    app.add_handler(TypeHandler(Update, log_update), group=-1)

    app.add_handler(
        CommandHandler("start", start, filters=filters.ChatType.PRIVATE)
    )

    # Ответы админов в группе -> клиенту
    app.add_handler(
        MessageHandler(
            filters.UpdateType.MESSAGE
            & filters.Chat(ADMIN_GROUP_ID)
            & filters.REPLY
            & ~filters.COMMAND,
            admin_reply,
        )
    )

    # Сообщения клиентов -> только в личке
    app.add_handler(
        MessageHandler(
            filters.UpdateType.MESSAGE
            & filters.ChatType.PRIVATE
            & ~filters.COMMAND
            & ~filters.StatusUpdate.ALL,
            client_message,
        )
    )

    app.add_error_handler(on_error)

    log.info("🚀 BOT ISHGA TUSHDI VA XABAR KUTMOQDA!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()