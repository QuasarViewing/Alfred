from googleapiclient.discovery import build
from google_auth import get_google_credentials
from datetime import datetime, timezone


def get_upcoming_events(max_results=10):
    try:
        creds = get_google_credentials()
        service = build(
            "calendar", "v3", credentials=creds
        )
        now = datetime.now(
            timezone.utc
        ).isoformat()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return "No upcoming events found."
        output = []
        for event in events:
            start = event["start"].get(
                "dateTime",
                event["start"].get("date"),
            )
            summary = event.get(
                "summary", "No Title"
            )
            event_id = event.get("id")
            output.append(f"[{event_id}] {start}: {summary}")

        return "\n".join(output)
    except Exception as e:
        return f"An error occurred: {e}"


def add_event(
    summary, start_time, end_time, description=""
):
    try:
        creds = get_google_credentials()
        service = build(
            "calendar", "v3", credentials=creds
        )
        event = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time,
                "timeZone": "Pacific/Auckland",
            },
            "end": {
                "dateTime": end_time,
                "timeZone": "Pacific/Auckland",
            },
        }
        created_event = (
            service.events()
            .insert(
                calendarId="primary", body=event
            )
            .execute()
        )
        return f"Event created: {created_event.get('htmlLink')}"
    except Exception as e:
        return f"An error occurred while creating the event: {e}"

def delete_event(event_id):
    try:
        creds = get_google_credentials()
        service = build(
            "calendar", "v3", credentials=creds
        )
        service.events().delete(
            calendarId="primary", eventId=event_id
        ).execute()
        return f"Event with ID {event_id} deleted successfully."
    except Exception as e:
        return f"An error occurred while deleting the event: {e}"

def edit_event(event_id, summary=None, start_time=None, end_time=None, description=None):
    try:
        creds = get_google_credentials()
        service = build(
            "calendar", "v3", credentials=creds
        )
        event = service.events().get(
            calendarId="primary", eventId=event_id
        ).execute()

        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if start_time is not None:
            event["start"]["dateTime"] = start_time
        if end_time is not None:
            event["end"]["dateTime"] = end_time

        updated_event = (
            service.events()
            .update(
                calendarId="primary", eventId=event_id, body=event
            )
            .execute()
        )
        return f"Event updated: {updated_event.get('htmlLink')}"
    except Exception as e:
        return f"An error occurred while editing the event: {e}"

def get_free_slots(date_str):
    try:
        creds = get_google_credentials()
        service = build(
            "calendar", "v3", credentials=creds
        )
        date_start = f"{date_str}T00:00:00Z"
        date_end = f"{date_str}T23:59:59Z"
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=date_start,
                timeMax=date_end,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        busy_slots = []
        for event in events:
            start = event["start"].get(
                "dateTime",
                event["start"].get("date"),
            )
            end = event["end"].get(
                "dateTime",
                event["end"].get("date"),
            )
            busy_slots.append((start, end))
        if not events:
            return f"You are completely free on {date_str}."
        
        day_start = datetime.fromisoformat(f"{date_str}T08:00:00+13:00")
        day_end = datetime.fromisoformat(f"{date_str}T22:00:00+13:00")

        free_slots = []
        cursor = day_start

        for start, end in busy_slots:
            event_start = datetime.fromisoformat(start)
            event_end = datetime.fromisoformat(end)
            if cursor < event_start:
                free_slots.append(f"{cursor.strftime('%H:%M')} - {event_start.strftime('%H:%M')}")
            cursor = event_end
        
        if cursor < day_end:
            free_slots.append(f"{cursor.strftime('%H:%M')} - {day_end.strftime('%H:%M')}")
        
        if not free_slots:
            return f"No free time found on {date_str}."
        return f"Free slots on {date_str}:\n" + "\n".join(free_slots)
    except Exception as e:
        return f"An error occurred while fetching free slots: {e}"