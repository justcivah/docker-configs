import asyncio
import html
import logging
import re
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from booking import check_prescription, classify_code, normalize_code, BookingError, PROVINCE_NAMES
from config import TAX_CODE, HEALTH_CARD, PRESCRIPTION_SLOTS_SHOWN
from storage import load_prescriptions, save_prescriptions


def clean_visit_name(description):
    # Drops details like "(PRIMA VISITA)" from the visit name
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", description or "")).strip()


def capitalize_words(text):
    return re.sub(r"[^\W\d_]+", lambda m: m.group().capitalize(), (text or "").lower())


def format_results(code, description, slots):
    """Returns the messages to send: the visit name, then for each province its name followed by one message per slot."""
    messages = [f"{clean_visit_name(description) or code}\nPrescription {code}"]

    if not slots:
        messages.append("No availability right now")
        return messages

    shown = slots[:PRESCRIPTION_SLOTS_SHOWN]
    # Slots are sorted by date, so provinces follow the order of their earliest slot
    for province in dict.fromkeys(s["province"] for s in shown):
        province_slots = [s for s in shown if s["province"] == province]

        messages.append(PROVINCE_NAMES.get(province, province))
        for slot in province_slots:
            lines = [f"- {slot['date']:%d/%m/%Y - %H:%M}", capitalize_words(slot["place"])]
            if slot["address"]:
                lines.append(capitalize_words(slot["address"]))
            messages.append("\n".join(lines))

    return messages


async def run_check(code):
    return await asyncio.to_thread(check_prescription, code)


async def check_from_command(update: Update, context: ContextTypes.DEFAULT_TYPE, command):
    """Validates the command arguments and checks the prescription once, replying with the slots found."""
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

    await update.message.reply_text("🔎 Checking availability...")

    try:
        description, slots = await run_check(code)
    except BookingError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return None
    except Exception as e:
        logging.error("Error checking prescription %s: %r", code, e)
        await update.message.reply_text("⚠️ Unable to reach the booking website, try again later")
        return None

    for message in format_results(code, description, slots):
        await update.message.reply_text(message)
    return code, description, slots


async def check_prescription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await check_from_command(update, context, "check_prescription")


async def alert_prescription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await check_from_command(update, context, "alert_prescription")
    if result is None:
        return
    code, description, slots = result

    prescriptions = load_prescriptions()
    prescriptions[code] = {
        "chat_id": update.effective_chat.id,
        "description": description,
        "earliest": slots[0]["date"].isoformat() if slots else None,
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

    lines = []
    for code, data in prescriptions.items():
        earliest = datetime.fromisoformat(data["earliest"]).strftime("%d/%m/%Y %H:%M") if data.get("earliest") else "none"
        lines.append(f"• <code>{code}</code> {html.escape(clean_visit_name(data.get('description')))}\n  earliest slot: {earliest}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def hourly_check(context: ContextTypes.DEFAULT_TYPE):
    for code, data in load_prescriptions().items():
        chat_id = data["chat_id"]

        try:
            description, slots = await run_check(code)
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

        earliest = slots[0]["date"] if slots else None
        previous = datetime.fromisoformat(data["earliest"]) if data.get("earliest") else None
        logging.info("Prescription %s: earliest=%s previous=%s", code, earliest, previous)

        # Reload, the prescription might have been removed while checking
        prescriptions = load_prescriptions()
        if code not in prescriptions:
            continue
        prescriptions[code].update({
            "description": description,
            "earliest": earliest.isoformat() if earliest else None,
            "last_error": None,
        })
        save_prescriptions(prescriptions)

        if earliest is not None and (previous is None or earliest < previous):
            await context.bot.send_message(chat_id=chat_id, text="🩺 An earlier slot became available!")
            for message in format_results(code, description, slots):
                await context.bot.send_message(chat_id=chat_id, text=message)
