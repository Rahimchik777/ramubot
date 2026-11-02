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
    filters,
)

# ---------------------------------------------------------------
# НАСТРОЙКИ
# BOT_TOKEN обязательно задайте в Render -> Environment (не в коде!)
# ---------------------------------------------------------------
BOT_TOKEN = os.environ.get("9244886158:AAEof79CZ7_LKOTX-ExtqGDrgXc365HHifs")
if not BOT_TOKEN:
    raise RuntimeError("Переменная окружения BOT_TOKEN не задана!")

ADMIN_GROUP_ID = int(os.environ.get("ADMIN_GROUP_ID", "-1004328946925"))
SITE_URL = os.environ.get("SITE_URL", "https://ramubot.onrender.com")

BTN_CONTACT = "💬 Admin bilan bog'lanish"
BTN_SITE = "🌐 RAMU Store saytiga o'tish"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO
)
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
    flask_app.run(host="0.0.0.0", port=port)


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
def esc(text: str) -> str:
    return html.escape(text or "")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = esc(update.effective_user.first_name)
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_CONTACT)], [KeyboardButton(BTN_SITE)]],
        resize_keyboard=True,
    )
    await update.message.reply_html(
        f"Assalomu alaykum, <b>{name}</b>! 🚀\n\n"
        f"Bu <b>RAMU Store</b> do'konining rasmiy qo'llab-quvvatlash xizmati.\n\n"
        f"Istalgan savolingizni yoki buyurtma ma'lumotlarini shu yerda yozib qoldiring. "
        f"Biz 24/7 rejimida ishlaymiz va sizga yordam berishdan xursandmiz! 🕒✨",
        reply_markup=keyboard,
    )


async def client_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сообщение клиента (только личка) -> карточка в админ-группу."""
    msg = update.message
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
    body = esc(text[:3500]) if text else "<i>(matn emas — pastdagi xabarga qarang)</i>"

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

        # Фото, файлы, голосовые и т.д. копируем под карточкой
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
        log.error("Админ-группаға yuborishda xatolik: %s", e)
        await msg.reply_text(
            "⚠️ Xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring."
        )


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ответ админа (reply на карточку в группе) -> клиенту."""
    msg = update.message
    replied = msg.reply_to_message

    # Реагируем только на ответ на сообщение самого бота
    if not replied or not replied.from_user or replied.from_user.id != context.bot.id:
        return

    reply_map = context.bot_data.get("reply_map", {})
    client_id = reply_map.get(replied.message_id)

    # Запасной вариант (после перезапуска бота): достаём ID из текста карточки
    if client_id is None:
        source = replied.text or replied.caption or ""
        match = re.search(r"ID:\s*(\d+)", source)
        if match:
            client_id = int(match.group(1))

    if client_id is None:
        await msg.reply_text(
            "⚠️ Mijoz ID topilmadi. Iltimos, mijozning kartochkasiga (YANGI MUROJAAT) javob bering."
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
        log.error("Mijozga yuborishda xatolik: %s", e)
        await msg.reply_text(f"⚠️ Yuborib bo'lmadi: {e}")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Необработанная ошибка:", exc_info=context.error)


def main():
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start, filters=filters.ChatType.PRIVATE))

    # Ответы админов в группе -> клиенту
    app.add_handler(
        MessageHandler(
            filters.Chat(ADMIN_GROUP_ID) & filters.REPLY & ~filters.COMMAND,
            admin_reply,
        )
    )

    # Сообщения клиентов -> только в личке
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
            client_message,
        )
    )

    app.add_error_handler(on_error)

    log.info("🚀 BOT ISHGA TUSHDI VA XABAR KUTMOQDA!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()