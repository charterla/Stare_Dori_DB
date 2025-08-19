import requests, json, asyncio
from typing import Optional
from datetime import datetime

import logging
logger = logging.getLogger("SDBot")

from objects.event import EventInfo

HEADER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}

class API():
    def __init__(self):
        self.recent_events: list[EventInfo] = []
        for server_id in range(4):
            self.recent_events.append(None)
            recent_event_id = asyncio.run(self.getRecentEventID(server_id))
            asyncio.run(self.updateRecentEvent(server_id, recent_event_id))

    async def getData(self, url: str):
        time: int = 0
        while True:
            try: return json.loads(requests.get(url, headers = HEADER, timeout = 2).text)
            except:
                if time == 4: logger.error(f"Bestdori API has not responsed ({url})."); return None
                time += 1; logger.warning(f"Bestdori API has not responsed ({url}) for {time} time(s). Retrying after 2s...")
                await asyncio.sleep(2); pass

    async def getRecentEventID(self, server_id: int) -> int:
        recent_events = await self.getData("https://bestdori.com/api/news/dynamic/recent.json")
        if recent_events == None: return None
        for event_id, event in recent_events["events"].items():
            if event["endAt"][server_id] is not None and \
                int(event["endAt"][server_id]) > int(datetime.now().timestamp() * 1000):
                return int(event_id)
        recent_event_id = None
        for event_id, event in recent_events["events"].items():
            if event["startAt"][server_id] is not None and \
                int(event["startAt"][server_id]) < int(datetime.now().timestamp() * 1000):
                recent_event_id = event_id
        return recent_event_id

    async def getEvent(self, event_id: int):
        event = await self.getData(f"https://bestdori.com/api/events/{event_id}.json")
        return event

    async def getEventTop(self, server_id: int, event_id: int, interval: Optional[int] = 864000000):
        event_top = await self.getData(
            f"https://bestdori.com/api/eventtop/data?server={server_id}&event={event_id}&mid=0&interval={interval}")
        return event_top

    async def updateRecentEvent(self, server_id: int, recent_event_id: int):
        while True:
            recent_event_info = await self.getEvent(recent_event_id)
            if recent_event_info != None: break
            logger.warning(f"Fail to update recent event at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} for server {server_id}.")
            await asyncio.sleep(600)
        self.recent_events[server_id] = EventInfo(server_id, recent_event_id, recent_event_info)