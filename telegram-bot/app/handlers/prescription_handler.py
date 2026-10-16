import asyncio
import html
import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from prescriptions import check_prescription, classify_code, normalize_code, BookingError
from config import TAX_CODE, HEALTH_CARD, TIMEZONE, PRESCRIPTION_SLOTS_SHOWN, PRESCRIPTION_NOTIFICATION_RESET
from storage import load_prescriptions, save_prescriptions


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
        lines.append(html.escape(capitalize_words(slot["address"])))
    return "\n".join(lines)


def format_booking(booking):
    return f"📅 Booked appointment\n{format_slot(booking)}"


def format_results(code, description, slots, booking=None):
    """Returns the HTML messages to send: the visit name, the booked appointment, then one message for each of the
    earliest slots."""
    messages = [format_title(code, description)]
    if booking:
        messages.append(format_booking(booking))

    if not slots:
        messages.append("No availability right now")
        return messages

    messages.extend(format_slot(slot) for slot in slots[:PRESCRIPTION_SLOTS_SHOWN])
    return messages


def serialize_booking(booking):
    if booking is None:
        return None
    return {"date": booking["date"].isoformat(), "place": booking["place"], "address": booking["address"]}


def load_booking(data):
    booking = data.get("booking")
    return {**booking, "date": datetime.fromisoformat(booking["date"])} if booking else None


def notifiable_slots(slots, booking):
    """Returns the slots worth notifying: all of them, or only the ones earlier than the booked appointment."""
    return [s for s in slots if booking is None or s["date"] < booking["date"]]


def should_notify(notified, slots, now):
    """Notifies when the earliest slot is earlier than the last notified one, or when that one has expired."""
    if not slots:
        return False
    if notified is None:
        return True
    if now - datetime.fromisoformat(notified["at"]) >= timedelta(seconds=PRESCRIPTION_NOTIFICATION_RESET):
        return True
    return slots[0]["date"] < datetime.fromisoformat(notified["date"])


def new_notified(slots, now):
    return {"date": slots[0]["date"].isoformat(), "at": now.isoformat()} if slots else None


async def run_check(code):
    return await asyncio.to_thread(check_prescription, code)


async def parse_code(update: Update, context: ContextTypes.DEFAULT_TYPE, command):
    """Validates the command arguments and returns the prescription code, None if they are invalid."""
    if not TAX_CODE or len(HEALTH_CARD) != 5:
        await update.message.reply_text("⚠️ TAX_CODE and HEALTH_CARD must be set in the .env file")
        return None

    if not context.args:
        await update.message.reply_text(f"Usage: /{command} {{prescription_code}}")
        return None

    code = normalize_code("".join(context.args))
    if classify_code(code) is None:
        await update.message.reply_text("⚠️ Invalid prescription code")
        return None

    return code


async def check_and_reply(update: Update, code):
    """Checks the prescription once, replying with the booked appointment and the slots found."""
    await update.message.reply_text("🔎 Checking availability...")

    try:
        description, slots, booking = await run_check(code)
    except BookingError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return None
    except Exception as e:
        logging.error("Error checking prescription %s: %r", code, e)
        await update.message.reply_text("⚠️ Unable to reach the booking website, try again later")
        return None

    for message in format_results(code, description, slots, booking):
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    return description, slots, booking


async def check_prescription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = await parse_code(update, context, "check_prescription")
    if code is not None:
        await check_and_reply(update, code)


async def monitor_prescription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = await parse_code(update, context, "monitor_prescription")
    if code is None:
        return

    if code in load_prescriptions():
        await update.message.reply_text("⚠️ This prescription is already being watched")
        return

    result = await check_and_reply(update, code)
    if result is None:
        return
    description, slots, booking = result

    # The slots were just shown, so they count as notified
    prescriptions = load_prescriptions()
    prescriptions[code] = {
        "chat_id": update.effective_chat.id,
        "description": description,
        "earliest": slots[0]["date"].isoformat() if slots else None,
        "booking": serialize_booking(booking),
        "notified": new_notified(notifiable_slots(slots, booking), datetime.now(ZoneInfo(TIMEZONE))),
        "last_error": None,
    }
    save_prescriptions(prescriptions)

    await update.message.reply_text("🔔 You will be notified when an earlier slot becomes available")


async def stop_prescription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stop_prescription {prescription_code}")
        return

    code = normalize_code("".join(context.args))
    prescriptions = load_prescriptions()

    if prescriptions.pop(code, None) is None:
        await update.message.reply_text("⚠️ This prescription is not being watched")
        return

    save_prescriptions(prescriptions)
    await update.message.reply_text(f"🔕 Stopped watching prescription {code}")


async def prescriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prescriptions = load_prescriptions()

    if not prescriptions:
        await update.message.reply_text("No prescription is being watched")
        return

    for code, data in prescriptions.items():
        message = f"{format_title(code, data.get('description'))}\nEarliest slot: {format_date(data.get('earliest'))}"
        if data.get("booking"):
            message += f"\nBooked: {format_date(data['booking']['date'])}"
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def periodic_prescription_check(context: ContextTypes.DEFAULT_TYPE):
    for code, data in load_prescriptions().items():
        chat_id = data["chat_id"]

        try:
            description, slots, booking = await run_check(code)
        except Exception as e:
            logging.error("Error checking prescription %s: %r", code, e)
            error = str(e) if isinstance(e, BookingError) else "Unable to reach the booking website"

            # Only notify errors once, until they change
            prescriptions = load_prescriptions()
            if code in prescriptions and prescriptions[code].get("last_error") != error:
                prescriptions[code]["last_error"] = error
                save_prescriptions(prescriptions)
                await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Prescription {code}: {error}")
            continue

        now = datetime.now(ZoneInfo(TIMEZONE))
        logging.info("Prescription %s: earliest=%s booking=%s", code,
                     slots[0]["date"] if slots else None, booking["date"] if booking else None)

        # Reload, the prescription might have been removed while checking
        prescriptions = load_prescriptions()
        if code not in prescriptions:
            continue
        data = prescriptions[code]
        previous_booking = load_booking(data)

        # Once the visit is done there's nothing left to watch, its appointment might also disappear afterwards
        visit = booking or previous_booking
        if visit and visit["date"] <= now:
            del prescriptions[code]
            save_prescriptions(prescriptions)
            await context.bot.send_message(chat_id=chat_id, text=f"✅ Visit done, stopped watching prescription {code}")
            continue

        messages = []
        booking_changed = serialize_booking(booking) != data.get("booking")
        if booking_changed:
            if booking is None:
                messages.append("❌ The booked appointment was cancelled")
            elif previous_booking is None:
                messages.append("📅 The prescription has been booked")
            else:
                messages.append("📅 The booked appointment has changed")

            # The last notified slot was compared with the old booking, start over
            data["notified"] = None

        candidates = notifiable_slots(slots, booking)
        if should_notify(data.get("notified"), candidates, now):
            data["notified"] = new_notified(candidates, now)
            messages.append("🩺 An earlier slot became available!")
            messages.extend(format_results(code, description, candidates, booking))
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
        save_prescriptions(prescriptions)

        for message in messages:
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
