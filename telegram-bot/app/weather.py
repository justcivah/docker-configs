import logging
import requests
import time

from config import LOCATIONS, RAIN_PROBABILITY_THRESHOLD, TIMEZONE, API_URL


def check_rain_tomorrow(lat, lon, retries=5, backoff=3):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_probability_max,precipitation_sum",
        "timezone": TIMEZONE,
        "forecast_days": 2,
    }

    for attempt in range(retries + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=20)
            resp.raise_for_status()
            daily = resp.json()["daily"]
            return daily["precipitation_probability_max"][1], daily["precipitation_sum"][1]
        
        except Exception as e:
            logging.warning("Attempt %d failed for (%s,%s): %r", attempt + 1, lat, lon, e)

            if attempt < retries:
                time.sleep(backoff)
            else:
                raise


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
            warning_lines.append(f"<b>{name}</b>: unable to fetch forecast")

    if warning_lines:
        return warning_lines
    return None
