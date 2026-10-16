import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import ApplicationBuilder, CommandHandler

from config import TOKEN, CHECK_HOUR, CHECK_MINUTE, TIMEZONE, PRESCRIPTION_CHECK_INTERVAL
from handlers.start_handler import start
from handlers.weather_handler import weather_command, daily_check
from handlers.prescription_handler import (
    check_prescription_command, alert_prescription_command, stop_prescription_command, prescriptions_command,
    hourly_check,
)


def main():
    logging.basicConfig(level=logging.INFO)

    app = ApplicationBuilder().token(TOKEN).build()

    # Available commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("check_prescription", check_prescription_command))
    app.add_handler(CommandHandler("alert_prescription", alert_prescription_command))
    app.add_handler(CommandHandler("stop_prescription", stop_prescription_command))
    app.add_handler(CommandHandler("prescriptions", prescriptions_command))

    # Automatic weather check every day
    app.job_queue.run_daily(
        daily_check, time=time(hour=CHECK_HOUR, minute=CHECK_MINUTE, tzinfo=ZoneInfo(TIMEZONE)),
    )

    # Availability check of the watched prescriptions every hour
    app.job_queue.run_repeating(hourly_check, interval=PRESCRIPTION_CHECK_INTERVAL, first=60)

    logging.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
