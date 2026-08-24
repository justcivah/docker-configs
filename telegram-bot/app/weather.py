import logging
import requests
import time

from config import LOCATIONS, RAIN_PROBABILITY_THRESHOLD, TIMEZONE, API_URL


def format_hour_ranges(hours):
    if not hours:
        return ""

    hours = sorted(set(hours))
    ranges = []
    start = prev = hours[0]

    for h in hours[1:]:
        if h == prev + 1:
            prev = h
            continue
        ranges.append((start, prev))
        start = prev = h
    ranges.append((start, prev))

    return ", ".join(f"{s:02d}:00-{e + 1:02d}:00" for s, e in ranges)


def check_rain_tomorrow(lat, lon, retries=5, backoff=3):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_probability_max,precipitation_sum",
        "hourly": "precipitation_probability",
        "timezone": TIMEZONE,
        "forecast_days": 2,
    }

    for attempt in range(retries + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            daily = data["daily"]
            hourly = data["hourly"]

            tomorrow_date = daily["time"][1]

            rain_hours = [
                int(t.split("T")[1].split(":")[0])
                for t, p in zip(hourly["time"], hourly["precipitation_probability"])
                if t.startswith(tomorrow_date) and p >= RAIN_PROBABILITY_THRESHOLD
            ]

            probability = daily["precipitation_probability_max"][1]
            mm = daily["precipitation_sum"][1]

            return probability, mm, rain_hours

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
            probability, mm, rain_hours = check_rain_tomorrow(coords["lat"], coords["lon"])
            logging.info("%s: %d%%, %.1f mm, hours=%s", name, probability, mm, rain_hours)

            if probability >= RAIN_PROBABILITY_THRESHOLD:
                line = f"<b>{name}</b>: {probability}% with {mm:.1f} mm"

                hours_str = format_hour_ranges(rain_hours)
                if hours_str:
                    line += f"\n• {hours_str}"

                warning_lines.append(line)

        except Exception as e:
            logging.error("Error checking weather for %s: %s", name, e)
            warning_lines.append(f"<b>{name}</b>: unable to fetch forecast")

    if warning_lines:
        return warning_lines
    return None