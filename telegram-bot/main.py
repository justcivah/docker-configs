import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import ApplicationBuilder, CommandHandler

from config import TOKEN, CHECK_HOUR, CHECK_MINUTE, TIMEZONE
from handlers.start_handler import start
from handlers.weather_handler import weather_command, daily_check


def main():
    logging.basicConfig(level=logging.INFO)

    app = ApplicationBuilder().token(TOKEN).build()

    # Available commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", weather_command))

    # Automatic weather check every day
    app.job_queue.run_daily(
        daily_check, time=time(hour=CHECK_HOUR, minute=CHECK_MINUTE, tzinfo=ZoneInfo(TIMEZONE)),
    )

    logging.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
