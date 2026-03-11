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
            output.append(f"{start}: {summary}")

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
