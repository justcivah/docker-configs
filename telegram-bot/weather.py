import logging
import requests

from config import LOCATIONS, RAIN_PROBABILITY_THRESHOLD, TIMEZONE

API_URL = "https://api.open-meteo.com/v1/forecast"


def check_rain_tomorrow(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_probability_max,precipitation_sum",
        "timezone": TIMEZONE,
        "forecast_days": 2,
    }
    resp = requests.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    daily = resp.json()["daily"]

    # index 0 = today, index 1 = tomorrow
    probability = daily["precipitation_probability_max"][1]
    mm = daily["precipitation_sum"][1]
    return probability, mm


def build_weather_message():
    warning_lines = []

    for name, coords in LOCATIONS.items():
        try:
            probability, mm = check_rain_tomorrow(coords["lat"], coords["lon"])
            logging.info("%s: %d%%, %.1f mm", name, probability, mm)

            if probability >= RAIN_PROBABILITY_THRESHOLD:
                warning_lines.append(f"<b>{name}</b>: {probability}% with {mm:.1f} mm")

        except Exception as e:
            logging.error("Error checking weather for %s: %s", name, e)
            warning_lines.append(f"<b>name}</b>: unable to fetch forecast")

    if warning_lines:
        return warning_lines
    return None
