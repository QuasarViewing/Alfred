from googleapiclient.discovery import build
from google_auth import get_google_credentials
from datetime import datetime, date, time, timezone
from zoneinfo import ZoneInfo
from config import TIMEZONE

NZ = ZoneInfo(TIMEZONE)


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
                "timeZone": TIMEZONE,
            },
            "end": {
                "dateTime": end_time,
                "timeZone": TIMEZONE,
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

def find_free_slots(busy_slots, day_start, day_end):
    """Pure logic, no Google calls — so it can be tested on its own.

    busy_slots: list of (start, end) timezone-aware datetimes.
    Returns a list of (start, end) gaps between day_start and day_end.
    """
    free_slots = []
    cursor = day_start
    for event_start, event_end in sorted(busy_slots):
        if event_end <= cursor:
            continue
        if cursor < event_start:
            free_slots.append((cursor, min(event_start, day_end)))
        cursor = max(cursor, event_end)
        if cursor >= day_end:
            break
    if cursor < day_end:
        free_slots.append((cursor, day_end))
    return [(s, e) for s, e in free_slots if s < e]


def get_free_slots(date_str):
    try:
        creds = get_google_credentials()
        service = build(
            "calendar", "v3", credentials=creds
        )
        # zoneinfo knows when NZ daylight saving starts and ends,
        # so this is +13:00 in summer and +12:00 in winter automatically.
        day = date.fromisoformat(date_str)
        day_start = datetime.combine(day, time(8, 0), tzinfo=NZ)
        day_end = datetime.combine(day, time(22, 0), tzinfo=NZ)
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=datetime.combine(day, time(0, 0), tzinfo=NZ).isoformat(),
                timeMax=datetime.combine(day, time(23, 59), tzinfo=NZ).isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return f"You are completely free on {date_str}."

        busy_slots = []
        for event in events:
            if "dateTime" not in event["start"]:
                # All-day event (birthday, holiday) — doesn't block time
                continue
            busy_slots.append((
                datetime.fromisoformat(event["start"]["dateTime"]),
                datetime.fromisoformat(event["end"]["dateTime"]),
            ))

        free_slots = find_free_slots(busy_slots, day_start, day_end)
        if not free_slots:
            return f"No free time found on {date_str}."
        lines = [
            f"{s.astimezone(NZ).strftime('%H:%M')} - {e.astimezone(NZ).strftime('%H:%M')}"
            for s, e in free_slots
        ]
        return f"Free slots on {date_str}:\n" + "\n".join(lines)
    except Exception as e:
        return f"An error occurred while fetching free slots: {e}"


def get_events_for_day(date_str=None):
    """Events for one NZ calendar day (default today) — used by the morning brief."""
    try:
        creds = get_google_credentials()
        service = build("calendar", "v3", credentials=creds)
        day = date.fromisoformat(date_str) if date_str else datetime.now(NZ).date()
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=datetime.combine(day, time(0, 0), tzinfo=NZ).isoformat(),
                timeMax=datetime.combine(day, time(23, 59), tzinfo=NZ).isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return "Nothing scheduled."
        output = []
        for event in events:
            summary = event.get("summary", "No Title")
            if "dateTime" in event["start"]:
                start = datetime.fromisoformat(event["start"]["dateTime"]).astimezone(NZ)
                output.append(f"{start.strftime('%H:%M')} {summary}")
            else:
                output.append(f"All day: {summary}")
        return "\n".join(output)
    except Exception as e:
        return f"An error occurred: {e}"