import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import ALLOWED_USER_ID
from weather import build_weather_message


async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Runs in a thread, the requests and their retries would block the bot
    messages = await asyncio.to_thread(build_weather_message)

    if messages is not None:
        await update.message.reply_text("🌧️ Tomorrow might rain in")

        for message in messages:
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    else:
        await update.message.reply_text("☀️ No rain expected tomorrow")


async def daily_check(context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_USER_ID is None:
        logging.warning("ALLOWED_USER_ID is not set, the weather can't be sent")
        return

    messages = await asyncio.to_thread(build_weather_message)

    # In a private chat the chat id is the same as the user id
    if messages is not None:
        await context.bot.send_message(chat_id=ALLOWED_USER_ID, text="🌧️ Tomorrow might rain in")

        for message in messages:
            await context.bot.send_message(chat_id=ALLOWED_USER_ID, text=message, parse_mode=ParseMode.HTML)
