import requests, json
from typing import Optional

header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Referer": "https://www.bilibili.com/"
}

def getRecentEvent(server_id: Optional[int] = 2) -> dict:
    request = requests.get("https://bestdori.com/api/news/dynamic/recent.json", headers = header)
    recent_events = json.loads(request.text)["events"]; result = {}
    for event_id, event in recent_events.items():
        if event["startAt"][server_id] is not None and \
            (result == {} or event["startAt"][server_id] > result["start_at"]):
            result = {
                "event_id": event_id,
                "event_name": event["eventName"][server_id],
                "start_at": event["startAt"][server_id],
                "end_at": event["endAt"][server_id]
            }
    return result

def getEventtop(event_id: int, server_id: Optional[int] = 2, interval: Optional[int] = 864000000):
    request = requests.get(
        f"https://bestdori.com/api/eventtop/data?server={server_id}&event={event_id}&mid=0&interval={interval}",
        headers = header
    )
    return json.loads(request.text)