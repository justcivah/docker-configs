import os
from dotenv import load_dotenv
 

load_dotenv()


# GENERAL
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# File where the chat id is saved
CHAT_ID_FILE = "data/chat_id.txt"


# WEATHER
# Rain probability threshold that triggers warnings
RAIN_PROBABILITY_THRESHOLD = 50

# Time of the day the check is done
CHECK_HOUR = 20
CHECK_MINUTE = 00
TIMEZONE = "Europe/Rome"

# Locations coordinates
LOCATIONS = {
    "Albavilla": {"lat": 45.80312, "lon": 9.18848},
    "Città Studi": {"lat": 45.47811, "lon": 9.22650},
}
