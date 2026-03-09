from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv
from database import init_db, log_conversation
from memory import store_memory, retrieve_memories
from datetime import datetime
from tools import web_search, get_weather, calculate, get_alfred_preference
import os
import logging
import anthropic

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def ask_claude(message, memories):
    memory_text = "\n".join(
        f"-{m}" for m in memories["documents"][0]
    )
    current_time = datetime.now().strftime(
        "%A, %d %B %Y %H:%M"
    )
    system_prompt = f"""
    Your role is Alfred, personal AI assistant to Jay. 
    You carry yourself like Alfred Pennyworth — composed, precise, and occasionally dry. 
    You address Jay directly, speak with quiet confidence, and never waste words. 
    You are not a chatbot. You are Alfred. 

    Format responses using HTML tags for Telegram:
    <b>bold</b>, <i>italic</i>, <code>code</code>
    Never use markdown asterisks or backticks.

    Relevant memories about Jay:
    {memory_text}
    current date and time: {current_time}
    """

    tools = [
        {
            "name": "web_search",
            "description": "Search the web for current information on any topic.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant information.",
                    }
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_weather",
            "description": "Get current weather information for a specific location.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location to get the weather for (e.g., 'New York City').",
                    }
                },
                "required": ["location"],
            },
        },
        {
            "name": "calculate",
            "description": "Perform a calculation based on a mathematical expression.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The mathematical expression to calculate (e.g., '2 + 2 * (3 - 1)').",
                    }
                },
                "required": ["expression"],
            },
        },
        {
            "name": "get_alfred_preference",
            "description": "Retrieve a specific preference or fact about Jay that Alfred has stored.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The key for the preference to retrieve (e.g., 'favorite_food').",
                    }
                },
                "required": ["key"],
            },
        }
    ]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        tools=tools,
        messages=[{"role": "user", "content": message}],
    )

    messages = [{"role": "user", "content": message}]
    current_response = response

    while current_response.stop_reason == "tool_use":
        tool_results = []
        for block in current_response.content:
            if block.type == "tool_use":
                if block.name == "web_search":
                    tool_result = web_search(block.input["query"])
                elif block.name == "get_weather":
                    tool_result = get_weather(block.input["location"])
                elif block.name == "calculate":
                    tool_result = calculate(block.input["expression"])
                elif block.name == "get_alfred_preference":
                    tool_result = get_alfred_preference(block.input["key"])
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(tool_result),
                })
        messages.append({"role": "assistant", "content": current_response.content})
        messages.append({"role": "user", "content": tool_results})
        current_response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

    for block in current_response.content:
        if hasattr(block, "text"):
            return block.text
    return "I wasn't able to get a response."


async def handle_message(update, context):
    user_message = update.message.text
    logging.info(f"Message received: {user_message}")
    memories = retrieve_memories(user_message)
    claude_response = ask_claude(user_message, memories)
    if is_worth_storing(user_message):
        store_memory(
            user_message,
            {
                "type": "user_message",
                "timestamp": update.message.date.isoformat(),
            },
        )
    if is_worth_storing(claude_response):
        store_memory(
            claude_response,
            {
                "type": "alfred_response",
                "timestamp": update.message.date.isoformat(),
            },
        )
    await update.message.reply_text(
        claude_response, parse_mode="HTML"
    )
    log_conversation(user_message, claude_response)


def run_bot():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(
        MessageHandler(
            filters.TEXT,
            handle_message,
        )
    )
    app.run_polling()


def is_worth_storing(text):
    if len(text) < 10:
        return False
    return True


if __name__ == "__main__":
    run_bot()
