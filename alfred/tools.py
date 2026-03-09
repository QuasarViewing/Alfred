from ddgs import DDGS
from database import get_preference
import logging
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
        with httpx.Client() as client:
            response = client.get(f"https://wttr.in/{location}?format=3")
            response.raise_for_status()
            return response.text
    except Exception as e:
        logging.error(f"Failed to get weather for {location}: {e}")
        return "Sorry, I couldn't retrieve the weather information."

def calculate(expression):
    try:
        # WARNING: Using eval can be dangerous. In production, consider using a safe math parser.
        return str(eval(expression))
    except Exception as e:
        logging.error(f"Calculation error: {e}")
        return "Sorry, I couldn't calculate that."

def get_alfred_preference(key):
    try:
        value = get_preference(key)
        if value:
            return f"{key}: {value}"
        return f"No preference found for {key}."
    except Exception as e:
        logging.error(f"Error retrieving preference for {key}: {e}")
        return "Sorry, I couldn't retrieve that preference."



if __name__ == "__main__":
    results = web_search("latest news on AI agents")                                                       
    for r in results:                                                                                      
          print(r["title"])
          print(r["body"])
          print()
