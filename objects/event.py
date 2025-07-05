from typing import Optional

EVENT_TYPE = {
    "challenge": 0,
    "versus": 1,
    "live_try": 2,
    "mission_live": 3,
    "festival": 4,
    "medley": 5
}

class EventInfo():
    def __init__(self, event_id: int, info: dict, server_id: Optional[int] = 2):
        # Initializing object with data provided
        self.event_id = event_id
        self.event_name = info["eventName"][server_id]
        self.event_type = EVENT_TYPE[info["eventType"]]
        self.start_at = int(info["startAt"][server_id]) / 1000
        self.end_at = int(info["endAt"][server_id]) / 1000