from tools import get_weather
from calendar_tool import get_upcoming_events
from gmail_tool import get_unread_emails
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv
import asyncio
import os
import html as html_module

load_dotenv()

def compile_morning_brief():
    today = datetime.now().strftime("%A, %d %B %Y")
    weather = get_weather("Taupo, New Zealand")
    events = get_upcoming_events(max_results=5)
    emails = get_unread_emails(max_results=5)

    brief = f"🌅 <b>Good morning, Jay.</b>\n\n"
    brief += f"<b>📅 {today}</b>\n\n"
    brief += f"<b>🌤 Weather</b>\n{html_module.escape(weather)}\n\n"
    brief += f"<b>📆 Today's Calendar</b>\n{html_module.escape(events)}\n\n"
    brief += f"<b>📬 Unread Emails</b>\n{html_module.escape(emails)}"

    return brief

def send_morning_brief():
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    bot = Bot(token=token)
    brief = compile_morning_brief()
    asyncio.run(bot.send_message(chat_id=chat_id, text=brief, parse_mode="HTML"))
