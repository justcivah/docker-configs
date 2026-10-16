import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import ApplicationBuilder, CommandHandler

from config import TOKEN, CHECK_HOUR, CHECK_MINUTE, TIMEZONE, REFERRAL_CHECK_INTERVAL
from handlers.start_handler import start
from handlers.weather_handler import weather_command, daily_check
from handlers.referral_handler import (
    check_referral_command, monitor_referral_command, stop_referral_command, referrals_command,
    periodic_referral_check,
)


def main():
    logging.basicConfig(level=logging.INFO)

    app = ApplicationBuilder().token(TOKEN).build()

    # Available commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("check_referral", check_referral_command))
    app.add_handler(CommandHandler("monitor_referral", monitor_referral_command))
    app.add_handler(CommandHandler("stop_referral", stop_referral_command))
    app.add_handler(CommandHandler("referrals", referrals_command))

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
