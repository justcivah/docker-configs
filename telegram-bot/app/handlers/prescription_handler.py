import asyncio
import html
import logging
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from booking import check_prescription, classify_code, normalize_code, BookingError
from config import TAX_CODE, HEALTH_CARD, PRESCRIPTION_SLOTS_SHOWN
from storage import load_prescriptions, save_prescriptions


def format_slots(code, description, slots):
    header = f"<b>{html.escape(description or code)}</b>\nPrescription <code>{code}</code>"

    if not slots:
        return f"{header}\n\nNo availability right now"

    lines = []
    for slot in slots[:PRESCRIPTION_SLOTS_SHOWN]:
        line = f"• <b>{slot['date']:%d/%m/%Y %H:%M}</b> - {html.escape(slot['place'])}"
        if slot["address"]:
            line += f"\n  {html.escape(slot['address'])}"
        lines.append(line)

    return f"{header}\n\n" + "\n".join(lines)


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

    await update.message.reply_text(format_slots(code, description, slots), parse_mode=ParseMode.HTML)
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
        lines.append(f"• <code>{code}</code> {html.escape(data.get('description') or '')}\n  earliest slot: {earliest}")

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
            await context.bot.send_message(chat_id=chat_id, text=format_slots(code, description, slots),
                                           parse_mode=ParseMode.HTML)
