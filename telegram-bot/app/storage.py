from config import CHAT_ID_FILE, REFERRALS_FILE
import json
import os


def save_chat_id(chat_id):
    os.makedirs(os.path.dirname(CHAT_ID_FILE), exist_ok=True)
    with open(CHAT_ID_FILE, "w") as f:
        f.write(str(chat_id))


def load_chat_id():
    try:
        with open(CHAT_ID_FILE) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def load_referrals():
    try:
        with open(REFERRALS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def save_referrals(referrals):
    os.makedirs(os.path.dirname(REFERRALS_FILE), exist_ok=True)
    with open(REFERRALS_FILE, "w") as f:
        json.dump(referrals, f, indent=2)
