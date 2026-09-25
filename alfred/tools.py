from ddgs import DDGS
from database import get_preference, save_preference, get_all_preferences
import ast
import logging
import math
import operator
import httpx


def web_search(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        return results
    except Exception as e:
        logging.error(f"Web search failed: {e}")
        return []

def get_weather(location):
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"https://wttr.in/{location}?format=3")
            response.raise_for_status()
            return response.text
    except Exception as e:
        logging.error(f"Failed to get weather for {location}: {e}")
        return "Sorry, I couldn't retrieve the weather information."


# The calculator used to call eval(), which runs ANY Python code.
# Instead we parse the expression into a tree (ast) and only allow
# numbers, maths operators and a short list of safe functions.
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_FUNCTIONS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
}

_CONSTANTS = {"pi": math.pi, "e": math.e}


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left = _evaluate(node.left)
        right = _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("Exponent too large")
        return _OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_evaluate(node.operand))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCTIONS
    ):
        args = [_evaluate(arg) for arg in node.args]
        return _FUNCTIONS[node.func.id](*args)
    raise ValueError(f"Unsupported expression: {ast.dump(node)[:60]}")


def calculate(expression):
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
        return str(_evaluate(tree))
    except Exception as e:
        logging.error(f"Calculation error: {e}")
        return "Sorry, I couldn't calculate that."

def get_alfred_preference(key):
    try:
        value = get_preference(key)
        if value:
            return f"{key}: {value}"
        stored = get_all_preferences()
        if stored:
            keys = ", ".join(k for k, _ in stored)
            return f"No preference found for {key}. Stored keys: {keys}"
        return f"No preference found for {key}."
    except Exception as e:
        logging.error(f"Error retrieving preference for {key}: {e}")
        return "Sorry, I couldn't retrieve that preference."


def save_alfred_preference(key, value):
    try:
        save_preference(key.strip().lower().replace(" ", "_"), value)
        return f"Saved: {key} = {value}"
    except Exception as e:
        logging.error(f"Error saving preference {key}: {e}")
        return "Sorry, I couldn't save that preference."



if __name__ == "__main__":
    results = web_search("latest news on AI agents")
    for r in results:
          print(r["title"])
          print(r["body"])
          print()
