from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv
from database import init_db, log_conversation
from memory import store_memory, retrieve_memories
from datetime import datetime
from tools import (
    web_search,
    get_weather,
    calculate,
    get_alfred_preference,
)
from calendar_tool import (
    get_upcoming_events,
    add_event,
    delete_event,
    edit_event,
    get_free_slots
)
from gmail_tool import (
    get_unread_emails,
    search_emails,
    create_draft,
    send_email
)
import os
import logging
import anthropic

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(
    api_key=ANTHROPIC_API_KEY
)


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
        },
        {
            "name": "get_upcoming_events",
            "description": "Get a list of upcoming events from the user's calendar.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "The maximum number of events to retrieve.",
                    }
                },
                "required": [],
            },
        },
        {
            "name": "add_event",
            "description": "Add a new event to the user's calendar.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "The title of the event.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "The start time of the event in ISO 8601 format.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "The end time of the event in ISO 8601 format.",
                    },
                    "description": {
                        "type": "string",
                        "description": "A description of the event.",
                    },
                },
                "required": [
                    "summary",
                    "start_time",
                    "end_time",
                ],
            },
        },
        {
            "name": "get_unread_emails",
            "description": "Retrieve a list of unread emails from the user's Gmail account.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "The maximum number of unread emails to retrieve.",
                    }
                },
                "required": [],
            },
            
        },
        {
            "name": "search_emails",
            "description": "Search for emails in the user's Gmail account that match a specific query.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant emails (e.g., 'from:alice subject:meeting').",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "The maximum number of matching emails to retrieve.",
                    },
                },
                "required": ["query"],
            },

        },
        {
            "name": "create_draft",
            "description": "Create a draft email in the user's Gmail account.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The recipient's email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the email.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The body content of the email.",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "send_email",
            "description": "Send an email from the user's Gmail account.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "The recipient's email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the email.",
                    },
                    "body": {
                        "type": "string",
                        "description": "The body content of the email.",
                    },
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "delete_event",
            "description": "Delete an event from the user's calendar.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The ID of the event to delete.",
                    }
                },
                "required": ["event_id"],
            },
        },
        {
            "name": "edit_event",
            "description": "Edit an existing event in the user's calendar.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The ID of the event to edit.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "The new title of the event.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "The new start time of the event in ISO 8601 format.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "The new end time of the event in ISO 8601 format.",
                    },
                    "description": {
                        "type": "string",
                        "description": "A new description of the event.",
                    },
                },
                "required": ["event_id"],
            },
        },
        {
            "name": "get_free_slots",
            "description": "Get free time slots in the user's calendar for a specific date.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "The date to check for free slots in ISO 8601 format (e.g., '2026-03-13').",
                    }
                },
                "required": ["date"],
            },
        }
    ]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        tools=tools,
        messages=[
            {"role": "user", "content": message}
        ],
    )

    messages = [
        {"role": "user", "content": message}
    ]
    current_response = response

    while (
        current_response.stop_reason == "tool_use"
    ):
        tool_results = []
        for block in current_response.content:
            if block.type == "tool_use":
                if block.name == "web_search":
                    tool_result = web_search(
                        block.input["query"]
                    )
                elif block.name == "get_weather":
                    tool_result = get_weather(
                        block.input["location"]
                    )
                elif block.name == "calculate":
                    tool_result = calculate(
                        block.input["expression"]
                    )
                elif (
                    block.name
                    == "get_alfred_preference"
                ):
                    tool_result = (
                        get_alfred_preference(
                            block.input["key"]
                        )
                    )
                elif (
                    block.name
                    == "get_upcoming_events"
                ):
                    tool_result = (
                        get_upcoming_events(
                            block.input.get(
                                "max_results", 10
                            )
                        )
                    )
                elif block.name == "add_event":
                    tool_result = add_event(
                        summary=block.input[
                            "summary"
                        ],
                        start_time=block.input[
                            "start_time"
                        ],
                        end_time=block.input[
                            "end_time"
                        ],
                        description=block.input.get(
                            "description", ""
                        ),
                    )
                elif block.name == "get_unread_emails":
                    tool_result = get_unread_emails(
                        block.input.get(
                            "max_results", 10
                        )
                    )
                elif block.name == "search_emails":
                    tool_result = search_emails(
                        query=block.input["query"],
                        max_results=block.input.get(
                            "max_results", 10
                        ),
                    )
                elif block.name == "create_draft":
                    tool_result = create_draft(
                        to=block.input["to"],
                        subject=block.input["subject"],
                        body=block.input["body"],
                    )
                elif block.name == "send_email":
                    tool_result = send_email(
                        to=block.input["to"],
                        subject=block.input["subject"],
                        body=block.input["body"],
                    )
                elif block.name == "delete_event":
                    tool_result = delete_event(
                        event_id=block.input["event_id"]
                    )
                elif block.name == "edit_event":
                    tool_result = edit_event(
                        event_id=block.input["event_id"],
                        summary=block.input.get(
                            "summary"
                        ),
                        start_time=block.input.get(
                            "start_time"
                        ),
                        end_time=block.input.get(
                            "end_time"
                        ),
                        description=block.input.get(
                            "description"
                        ),
                    )
                elif block.name == "get_free_slots":
                    tool_result = get_free_slots(
                        date_str=block.input["date"]
                    )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(
                            tool_result
                        ),
                    }
                )
        messages.append(
            {
                "role": "assistant",
                "content": current_response.content,
            }
        )
        messages.append(
            {
                "role": "user",
                "content": tool_results,
            }
        )
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
    logging.info(
        f"Message received: {user_message}"
    )
    memories = retrieve_memories(user_message)
    claude_response = ask_claude(
        user_message, memories
    )
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
    log_conversation(
        user_message, claude_response
    )


def run_bot():
    init_db()
    app = (
        ApplicationBuilder().token(TOKEN).build()
    )
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
