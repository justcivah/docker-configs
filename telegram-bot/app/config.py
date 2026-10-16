import os
from dotenv import load_dotenv
 

load_dotenv()


# GENERAL
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# File where the chat id is saved
CHAT_ID_FILE = "data/chat_id.txt"


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


# PRESCRIPTIONS
BOOKING_BASE_URL = "https://prenotasalute.regione.lombardia.it/prenotaonline/"

# Provinces where availability is searched (BG, BS, CO, CR, LC, LO, MB, MI, MN, PV, SO, VA)
PROVINCES = ["CO", "VA", "LC", "MB"]

# Credentials used to log in on the booking website
TAX_CODE = (os.getenv("TAX_CODE") or "").strip().upper()
# Only the last 5 digits of the health card are needed
HEALTH_CARD = (os.getenv("HEALTH_CARD") or "").strip()[-5:]

# File where the watched prescriptions are saved
PRESCRIPTIONS_FILE = "data/prescriptions.json"

# Seconds between two availability checks
PRESCRIPTION_CHECK_INTERVAL = 30 * 60

# Number of slots shown, the earliest ones among all provinces
PRESCRIPTION_SLOTS_SHOWN = 3

# Seconds after which the last notified slot expires, then the earliest slot is notified again even if it's later
PRESCRIPTION_NOTIFICATION_RESET = 7 * 24 * 60 * 60
