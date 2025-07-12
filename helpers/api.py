import requests, json, asyncio
from typing import Optional
from datetime import datetime

import logging
logger = logging.getLogger("SDBot")

from objects.event import EventInfo

HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Referer": "https://www.bilibili.com/"
}

class API():
    def __init__(self):
        self.recent_event: EventInfo
        recent_event_id = asyncio.run(self.getRecentEventID())
        asyncio.run(self.updateRecentEvent(recent_event_id))

    async def getData(self, url: str):
        time: int = 0
        while True:
            try: return json.loads(requests.get(url, headers = HEADER).text)
            except:
                if time == 8: raise Exception(f"Bestdori API has not responsed ({url}).")
                time += 1; logger.warning(f"Bestdori API has not responsed ({url}). Retrying after {1 << time}s...")
                await asyncio.sleep(1 << time); pass

    async def getRecentEventID(self, server_id: Optional[int] = 2) -> int:
        recent_events = await self.getData("https://bestdori.com/api/news/dynamic/recent.json")
        for event_id, event in recent_events["events"].items():
            if event["endAt"][server_id] is not None and \
                int(event["endAt"][server_id]) > int(datetime.now().timestamp() * 1000):
                return int(event_id)

    async def getEvent(self, event_id: int):
        event = await self.getData(f"https://bestdori.com/api/events/{event_id}.json")
        return event

    async def getEventTop(self, event_id: int, server_id: Optional[int] = 2, interval: Optional[int] = 864000000):
        event_top = await self.getData(
            f"https://bestdori.com/api/eventtop/data?server={server_id}&event={event_id}&mid=0&interval={interval}")
        return event_top

    async def updateRecentEvent(self, recent_event_id: int):
        recent_event_info = await self.getEvent(recent_event_id)
        self.recent_event = EventInfo(recent_event_id, recent_event_info)