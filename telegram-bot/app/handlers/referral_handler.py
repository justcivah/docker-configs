import asyncio
import html
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from referrals import check_referral, classify_code, normalize_code, BookingError
from config import (
    TAX_CODE, HEALTH_CARD, TIMEZONE, REFERRAL_SLOTS_SHOWN, REFERRAL_NOTIFICATION_RESET,
    REFERRAL_OTHER_PLACES_DIVISOR, REFERRAL_OTHER_PLACES_MAX_MARGIN,
)
from storage import load_referrals, save_referrals


def clean_visit_name(description):
    # Drops details like "(PRIMA VISITA)" from the visit name
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", description or "")).strip()


def capitalize_words(text):
    return re.sub(r"[^\W\d_]+", lambda m: m.group().capitalize(), (text or "").lower())


def format_title(code, description):
    return f"<b>{html.escape(clean_visit_name(description) or code)}</b>\n<code>{code}</code>"


def format_date(value):
    return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M") if value else "none"


def format_slot(slot):
    lines = [f"<b>{slot['date']:%d/%m/%Y - %H:%M}</b>", html.escape(capitalize_words(slot["place"]))]
    if slot["address"]:
        lines.append(f"<i>{html.escape(capitalize_words(slot['address']))}</i>")
    return "\n".join(lines)


def format_booking(booking):
    return f"📅 Booked appointment\n{format_slot(booking)}"


def earliest_per_place(slots):
    """Keeps only the earliest slot of each place, the slots are already sorted by date."""
    places = set()
    earliest = []
    for slot in slots:
        if slot["place"] not in places:
            places.add(slot["place"])
            earliest.append(slot)
    return earliest


def format_results(code, description, slots, booking=None):
    """Returns the HTML messages to send: the visit name, the booked appointment, then one message for each of the
    earliest places."""
    messages = [format_title(code, description)]
    if booking:
        messages.append(format_booking(booking))

    if not slots:
        messages.append("No availability right now")
        return messages

    messages.extend(format_slot(slot) for slot in earliest_per_place(slots)[:REFERRAL_SLOTS_SHOWN])
    return messages


def serialize_booking(booking):
    if booking is None:
        return None
    return {"date": booking["date"].isoformat(), "place": booking["place"], "address": booking["address"]}


def load_booking(data):
    booking = data.get("booking")
    return {**booking, "date": datetime.fromisoformat(booking["date"])} if booking else None


def notifiable_slots(slots, booking, now):
    """Returns the slots worth notifying: with a booking, the ones of its place only if they are earlier, the ones of
    the other places only if they aren't much later."""
    if booking is None:
        return slots

    # The further the visit, the longer it's worth waiting for another place
    margin = min((booking["date"] - now) / REFERRAL_OTHER_PLACES_DIVISOR,
                 timedelta(seconds=REFERRAL_OTHER_PLACES_MAX_MARGIN))
    latest = booking["date"] + margin
    return [s for s in slots if s["date"] < (booking["date"] if s["place"] == booking["place"] else latest)]


def is_expired(notification, now):
    return now - datetime.fromisoformat(notification["at"]) >= timedelta(seconds=REFERRAL_NOTIFICATION_RESET)


def slots_to_notify(notified, slots):
    """Returns the earliest slot of each place, when the place wasn't notified yet or the slot is earlier than the
    notified one, up to the number of slots shown."""
    new_slots = [s for s in earliest_per_place(slots)
                 if s["place"] not in notified or s["date"] < datetime.fromisoformat(notified[s["place"]]["date"])]
    return new_slots[:REFERRAL_SLOTS_SHOWN]


def notifications(slots, now):
    """Returns the notified slots, by place."""
    return {s["place"]: {"date": s["date"].isoformat(), "at": now.isoformat()} for s in slots}


async def run_check(code):
    return await asyncio.to_thread(check_referral, code)


async def parse_code(update: Update, context: ContextTypes.DEFAULT_TYPE, command):
    """Validates the command arguments and returns the referral code, None if they are invalid."""
    if not TAX_CODE or len(HEALTH_CARD) != 5:
        await update.message.reply_text("⚠️ TAX_CODE and HEALTH_CARD must be set in the .env file")
        return None

    if not context.args:
        await update.message.reply_text(f"Usage: /{command} {{referral_code}}")
        return None

    code = normalize_code("".join(context.args))
    if classify_code(code) is None:
        await update.message.reply_text("⚠️ Invalid referral code")
        return None

    return code


async def check_and_reply(update: Update, code):
    """Checks the referral once, replying with the booked appointment and the slots found."""
    await update.message.reply_text("🔎 Checking availability...")

    try:
        description, slots, booking = await run_check(code)
    except BookingError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return None
    except Exception as e:
        logging.error("Error checking referral %s: %r", code, e)
        await update.message.reply_text("⚠️ Unable to reach the booking website, try again later")
        return None

    for message in format_results(code, description, slots, booking):
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    return description, slots, booking


async def check_referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = await parse_code(update, context, "check_referral")
    if code is not None:
        await check_and_reply(update, code)


async def monitor_referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = await parse_code(update, context, "monitor_referral")
    if code is None:
        return

    if code in load_referrals():
        await update.message.reply_text("⚠️ This referral is already being watched")
        return

    result = await check_and_reply(update, code)
    if result is None:
        return
    description, slots, booking = result

    # The slots were just shown, so they count as notified
    shown = earliest_per_place(slots)[:REFERRAL_SLOTS_SHOWN]
    now = datetime.now(ZoneInfo(TIMEZONE))
    referrals = load_referrals()
    referrals[code] = {
        "chat_id": update.effective_chat.id,
        "description": description,
        "earliest": slots[0]["date"].isoformat() if slots else None,
        "booking": serialize_booking(booking),
        "notified": notifications(notifiable_slots(shown, booking, now), now),
        "last_error": None,
    }
    save_referrals(referrals)

    await update.message.reply_text("🔔 You will be notified when an earlier slot becomes available")


async def stop_referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stop_referral {referral_code}")
        return

    code = normalize_code("".join(context.args))
    referrals = load_referrals()

    if referrals.pop(code, None) is None:
        await update.message.reply_text("⚠️ This referral is not being watched")
        return

    save_referrals(referrals)
    await update.message.reply_text(f"🔕 Stopped watching referral {code}")


async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    referrals = load_referrals()

    if not referrals:
        await update.message.reply_text("No referral is being watched")
        return

    for code, data in referrals.items():
        message = f"{format_title(code, data.get('description'))}\nEarliest slot: {format_date(data.get('earliest'))}"
        if data.get("booking"):
            message += f"\nBooked: {format_date(data['booking']['date'])}"
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def periodic_referral_check(context: ContextTypes.DEFAULT_TYPE):
    for code, data in load_referrals().items():
        chat_id = data["chat_id"]

        try:
            description, slots, booking = await run_check(code)
        except Exception as e:
            logging.error("Error checking referral %s: %r", code, e)
            error = str(e) if isinstance(e, BookingError) else "Unable to reach the booking website"

            # Only notify errors once, until they change
            referrals = load_referrals()
            if code in referrals and referrals[code].get("last_error") != error:
                referrals[code]["last_error"] = error
                save_referrals(referrals)
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Referral {code}: {error}")
            continue

        now = datetime.now(ZoneInfo(TIMEZONE))
        logging.info("Referral %s: earliest=%s booking=%s", code,
                     slots[0]["date"] if slots else None, booking["date"] if booking else None)

        # Reload, the referral might have been removed while checking
        referrals = load_referrals()
        if code not in referrals:
            continue
        data = referrals[code]
        previous_booking = load_booking(data)

        # Once the visit is done there's nothing left to watch, its appointment might also disappear afterwards
        visit = booking or previous_booking
        if visit and visit["date"] <= now:
            del referrals[code]
            save_referrals(referrals)
            await context.bot.send_message(chat_id=chat_id, text=f"✅ Visit done, stopped watching referral {code}")
            continue

        messages = []
        booking_changed = serialize_booking(booking) != data.get("booking")
        if booking_changed:
            if booking is None:
                messages.append("❌ The booked appointment was cancelled")
            elif previous_booking is None:
                messages.append("📅 The referral has been booked")
            else:
                messages.append("📅 The booked appointment has changed")

        # The notified slots were compared with the old booking, so they start over when it changes. Otherwise each
        # place expires on its own, then its earliest slot is notified again even if it's later
        if booking_changed:
            notified = {}
        else:
            notified = {p: n for p, n in (data.get("notified") or {}).items() if not is_expired(n, now)}

        new_slots = slots_to_notify(notified, notifiable_slots(slots, booking, now))
        notified.update(notifications(new_slots, now))
        data["notified"] = notified

        if new_slots:
            messages.append("🩺 New slots available!")
            messages.extend(format_results(code, description, new_slots, booking))
        elif booking_changed:
            messages.append(format_title(code, description))
            if booking:
                messages.append(format_booking(booking))

        data.update({
            "description": description,
            "earliest": slots[0]["date"].isoformat() if slots else None,
            "booking": serialize_booking(booking),
            "last_error": None,
        })
        save_referrals(referrals)

        for message in messages:
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
