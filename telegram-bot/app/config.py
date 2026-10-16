import os
from dotenv import load_dotenv
 

load_dotenv()


# GENERAL
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Telegram user allowed to use the bot, every other user is ignored (all of them if it's not set)
ALLOWED_USER_ID = int((os.getenv("ALLOWED_USER_ID") or "").strip() or 0) or None


# WEATHER
API_URL = "https://api.open-meteo.com/v1/forecast"

# Rain probability threshold that triggers warnings
RAIN_PROBABILITY_THRESHOLD = 60

# Time of the day the check is done
CHECK_HOUR = 19
CHECK_MINUTE = 55
TIMEZONE = "Europe/Rome"

# Locations coordinates
LOCATIONS = {
    "Albavilla": {"lat": 45.80312, "lon": 9.18848},
    "Città Studi": {"lat": 45.47811, "lon": 9.22650},
}


# REFERRALS
BOOKING_BASE_URL = "https://prenotasalute.regione.lombardia.it/prenotaonline/"

# Provinces where availability is searched (BG, BS, CO, CR, LC, LO, MB, MI, MN, PV, SO, VA)
PROVINCES = ["CO", "VA", "LC", "MB"]

# Credentials used to log in on the booking website
TAX_CODE = (os.getenv("TAX_CODE") or "").strip().upper()
# Only the last 5 digits of the health card are needed
HEALTH_CARD = (os.getenv("HEALTH_CARD") or "").strip()[-5:]

# File where the watched referrals are saved
REFERRALS_FILE = "data/referrals.json"

# Seconds between two availability checks
REFERRAL_CHECK_INTERVAL = 30 * 60

# Number of slots shown, the earliest of each place among all provinces
REFERRAL_SLOTS_SHOWN = 3

# Seconds after which the last notified slot of a place expires, then its earliest slot is notified again even if
# it's later
REFERRAL_NOTIFICATION_RESET = 7 * 24 * 60 * 60

# Seconds after the booked appointment within which the slots of other places are still notified
REFERRAL_OTHER_PLACES_MARGIN = 30 * 24 * 60 * 60
