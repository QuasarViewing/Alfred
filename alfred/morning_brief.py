from tools import get_weather
from calendar_tool import get_events_for_day
from gmail_tool import get_unread_emails
from database import get_latest_market_brief, log_task
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, TIMEZONE, HOME_LOCATION, VOICE_REPLIES
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Bot
import asyncio
import html as html_module
import logging
import os


def compile_morning_brief():
    today = datetime.now(ZoneInfo(TIMEZONE)).strftime("%A, %d %B %Y")
    weather = get_weather(HOME_LOCATION)
    events = get_events_for_day()
    emails = get_unread_emails(max_results=5)
    market = get_latest_market_brief()

    brief = f"🌅 <b>Good morning, Jay.</b>\n\n"
    brief += f"<b>📅 {today}</b>\n\n"
    brief += f"<b>🌤 Weather</b>\n{html_module.escape(weather)}\n\n"
    brief += f"<b>📆 Today's Calendar</b>\n{html_module.escape(events)}\n\n"
    brief += f"<b>📬 Unread Emails</b>\n{html_module.escape(emails)}"
    if market:
        # Already Telegram HTML — written by Claude in market_pipeline.py
        brief += f"\n\n<b>📈 Markets</b>\n{market}"

    # Phase 3: one gentle question, only if he hasn't already told us
    from health import checkins_enabled, logged_today, MORNING_QUESTION
    if checkins_enabled() and not logged_today(["sleep_hours", "sleep_quality", "energy"]):
        brief += f"\n\n<i>{MORNING_QUESTION}</i>"

    return brief


def compile_spoken_brief(brief):
    """The full brief has email snippets that sound awful read aloud.
    The spoken version keeps weather, calendar and markets only."""
    spoken = brief.split("<b>📬 Unread Emails</b>")[0]
    if "<b>📈 Markets</b>" in brief:
        spoken += brief.split("<b>📈 Markets</b>")[1]
    return spoken


async def _send(text, voice_path=None):
    # `async with` initialises the Bot's HTTP connection and closes it after
    async with Bot(token=TELEGRAM_TOKEN) as bot:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="HTML")
        if voice_path:
            with open(voice_path, "rb") as audio:
                await bot.send_voice(chat_id=TELEGRAM_CHAT_ID, voice=audio)


def send_telegram_message(text, voice_path=None):
    """For code that runs outside the bot's event loop (APScheduler jobs)."""
    asyncio.run(_send(text, voice_path))


def send_morning_brief():
    try:
        brief = compile_morning_brief()
        voice_path = None
        if VOICE_REPLIES:
            from tts_handler import speak
            voice_path = speak(compile_spoken_brief(brief))
        send_telegram_message(brief, voice_path)
        if voice_path:
            os.remove(voice_path)
        log_task("morning_brief", "sent", "success")
    except Exception as e:
        logging.exception("Morning brief failed")
        log_task("morning_brief", str(e), "failed")
