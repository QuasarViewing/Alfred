"""One shared Claude client for the whole app.

bot.py, the market pipeline and anything else that talks to Claude
imports `client` and `CLAUDE_MODEL` from here instead of each
creating its own.
"""
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def ask_once(system, prompt, max_tokens=1024):
    """Single question → single text answer. No tools, no loop."""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def ask_structured(system, prompt, tool_name, tool_description, schema, max_tokens=4096):
    """Get DATA back from Claude, not prose.

    We define one tool whose input_schema is the shape we want, and
    make Claude call it. The tool never "runs" — its input IS the answer.
    Returns the dict Claude filled in, or None.
    """
    tool = {"name": tool_name, "description": tool_description, "input_schema": schema}
    request = dict(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        response = client.messages.create(**request, tool_choice={"type": "tool", "name": tool_name})
    except anthropic.BadRequestError:
        # Some newer models reject forced tool choice — ask nicely instead
        request["messages"][0]["content"] += f"\n\nRespond by calling the {tool_name} tool."
        response = client.messages.create(**request, tool_choice={"type": "auto"})

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    return None
