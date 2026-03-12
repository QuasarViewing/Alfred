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