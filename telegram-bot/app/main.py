import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from config import TOKEN, ALLOWED_USER_ID, CHECK_HOUR, CHECK_MINUTE, TIMEZONE, REFERRAL_CHECK_INTERVAL
from handlers.start_handler import start
from handlers.weather_handler import weather_command, daily_check
from handlers.referral_handler import (
    check_referral_command, monitor_referral_command, stop_referral_command, referrals_command,
    periodic_referral_check,
)


async def log_ignored(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logging.warning("Ignored message from user %s (@%s)", user.id if user else None, user.username if user else None)


def main():
    logging.basicConfig(level=logging.INFO)

    if ALLOWED_USER_ID is None:
        logging.warning("ALLOWED_USER_ID is not set, every message is ignored")

    app = ApplicationBuilder().token(TOKEN).build()

    # Only the allowed user can use the commands, the others get no reply
    allowed = filters.User(user_id=ALLOWED_USER_ID)

    # Available commands
    app.add_handler(CommandHandler("start", start, filters=allowed))
    app.add_handler(CommandHandler("weather", weather_command, filters=allowed))
    app.add_handler(CommandHandler("check_referral", check_referral_command, filters=allowed))
    app.add_handler(CommandHandler("monitor_referral", monitor_referral_command, filters=allowed))
    app.add_handler(CommandHandler("stop_referral", stop_referral_command, filters=allowed))
    app.add_handler(CommandHandler("referrals", referrals_command, filters=allowed))

    # Logs who else writes to the bot, also useful to find out your own user id
    app.add_handler(MessageHandler(~allowed, log_ignored))

    # Automatic weather check every day
    app.job_queue.run_daily(
        daily_check, time=time(hour=CHECK_HOUR, minute=CHECK_MINUTE, tzinfo=ZoneInfo(TIMEZONE)),
    )

    # Periodic availability check of the watched referrals
    app.job_queue.run_repeating(periodic_referral_check, interval=REFERRAL_CHECK_INTERVAL, first=60)

    logging.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
