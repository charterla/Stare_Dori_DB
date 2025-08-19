from discord.ext import commands, tasks

from datetime import datetime
import asyncio

import logging
logger = logging.getLogger("SDBot")

from helpers.db_pg import Database
from helpers.api import API
from cogs.notify import Notify

class Monitor(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, api: API, notify_cog: Notify):
        self.bot = bot
        self.database = database
        self.api = api
        self.notify_cog = notify_cog

        for server_id, recent_event in enumerate(self.api.recent_events):
            self.database.createTableForEvent(server_id, recent_event.event_id)
        
        self.last_updata_times = [0 for i in range(4)]
        self.fail_counter = [[0, 0] for i in range(4)]

        self.checkRecentEvents.start()
        self.getRecentEventsTop.start()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    # Synchronizing the recent event
    @tasks.loop(time = datetime.strptime('20:05', '%H:%M').time())
    async def checkRecentEvents(self):
        await asyncio.gather(self.checkRecentEvent(0), self.checkRecentEvent(1), 
                             self.checkRecentEvent(2), self.checkRecentEvent(3))

    async def checkRecentEvent(self, server_id: int):
        # Getting recent event id
        check_recent_event_id = None
        while check_recent_event_id == None:
            check_recent_event_id = await self.api.getRecentEventID(server_id)
            if check_recent_event_id == None:
                logger.warning(f"Fail to get recent event id at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} for server {server_id}.")
                asyncio.sleep(3600); pass
        
        # Syncing the recent event data 
        if check_recent_event_id != self.api.recent_events[server_id].event_id:
            await self.api.updateRecentEvent(server_id, check_recent_event_id)
            self.database.createTableForEvent(server_id, check_recent_event_id)

    # Synchronizing the data about event points
    @tasks.loop(minutes = 1)
    async def getRecentEventsTop(self):
        await asyncio.gather(self.getRecentEventTop(0), self.getRecentEventTop(1), 
                             self.getRecentEventTop(2), self.getRecentEventTop(3))

    async def getRecentEventTop(self, server_id: int):
        # Skip update if too much fail try
        if self.fail_counter[server_id][0] > self.fail_counter[server_id][1]:
            self.fail_counter[server_id][1] += 1
            logger.info(f"Skip to update recent event top at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} for server {server_id}"
                      + f" for {self.fail_counter[server_id][1]} time(s) in the round {self.fail_counter[server_id][0]}."); return

        # Stopping update if event has not started yet
        if self.api.recent_events[server_id].start_at > datetime.now().timestamp(): return
        
        # Getting recent event top data
        event_top = await self.api.getEventTop(server_id, self.api.recent_events[server_id].event_id)
        if event_top == None or datetime.now().timestamp() - self.last_updata_times[server_id] > 90:
            event_top = await self.api.getEventTop(server_id, self.api.recent_events[server_id].event_id, interval = 60000)
        if event_top == None: 
            logger.warning(f"Fail to get recent event top at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} for server {server_id}.")
            self.fail_counter[server_id] = [self.fail_counter[server_id][0] + 1, 0]; return
        self.fail_counter[server_id] = [0, 0]
        justify_time = datetime.now().timestamp() - self.last_updata_times[server_id] if self.last_updata_times[server_id] > 0 else 0
        self.last_updata_times[server_id] = datetime.now().timestamp()
        
        # Updataing the database by the recent event top data
        self.database.insertEventPlayers(server_id, self.api.recent_events[server_id].event_id, 
                                             event_top["users"], int(self.api.recent_events[server_id].start_at * 1000))
        self.database.insertEventRanks(server_id, self.api.recent_events[server_id].event_id, 
                                             event_top["users"], int(self.api.recent_events[server_id].start_at * 1000))
        self.database.insertEventPoints(server_id, self.api.recent_events[server_id].event_id, event_top["points"])

        # Calling the notify cog to notify after new data update
        await self.notify_cog.notifyChannels(server_id, justify_time)