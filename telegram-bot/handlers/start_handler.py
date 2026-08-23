from telegram import Update
from telegram.ext import ContextTypes

from storage import save_chat_id


async def start(update, context):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)

    await update.message.reply_text("✅ Bot started")
