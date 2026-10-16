from config import REFERRALS_FILE
import json
import os


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
