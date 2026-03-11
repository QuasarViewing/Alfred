from calendar_tool import get_upcoming_events
from calendar_tool import add_event

result = get_upcoming_events()
print(result)

result = add_event(                                                                                                     
      summary="Test from Alfred",                                                                                         
      start_time="2026-03-13T14:00:00",
      end_time="2026-03-13T15:00:00"
  )
print(result)