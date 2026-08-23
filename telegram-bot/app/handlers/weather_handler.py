import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from storage import load_chat_id
from weather import build_weather_message


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    messages = build_weather_message()

    if messages is not None:
        await update.message.reply_text("🌧️ Tomorrow might rain in")

        for message in messages:
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    else:
        await update.message.reply_text("☀️ No rain expected tomorrow")


async def daily_check(context: ContextTypes.DEFAULT_TYPE):
    chat_id = load_chat_id()

    if chat_id is None:
        logging.warning("Send /start to start chatting with the bot")
        return

    messages = build_weather_message()

    if messages is not None:
        await context.bot.send_message(chat_id=chat_id, text="🌧️ Tomorrow might rain in")

        for message in messages:
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
