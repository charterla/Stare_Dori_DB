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

        self.database.createTableForEvent(self.api.recent_event.event_id)

        self.last_updata_time = 0

        self.checkRecentEvent.start()
        self.getRecentEventTop.start()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    # Synchronizing the recent event
    @tasks.loop(time = datetime.strptime('20:05', '%H:%M').time())
    async def checkRecentEvent(self):
        # Getting recent event id
        check_recent_event_id = None
        while check_recent_event_id == None:
            try: check_recent_event_id = await self.api.getRecentEventID()
            except: 
                logger.warning(f"Fail to get recent event id at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.")
                asyncio.sleep(3600); pass
        
        # Syncing the recent event data 
        if check_recent_event_id != self.api.recent_event.event_id:
            await self.api.updateRecentEvent(check_recent_event_id)
            self.database.createTableForEvent(check_recent_event_id)

    # Synchronizing the data about event points
    @tasks.loop(minutes = 1)
    async def getRecentEventTop(self):
        # Stopping update if event has not started yet
        if self.api.recent_event.start_at > datetime.now().timestamp(): return
        
        # Getting recent event top data
        event_top = None
        try: event_top = await self.api.getEventTop(self.api.recent_event.event_id)
        except: pass
        if datetime.now().timestamp() - self.last_updata_time > 90:
            try: event_top = await self.api.getEventTop(self.api.recent_event.event_id, interval = 60000)
            except: pass
        if event_top == None: logger.warning(f"Fail to get recent event top at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."); return
        justify_time = datetime.now().timestamp() - self.last_updata_time if self.last_updata_time > 0 else 0
        self.last_updata_time = datetime.now().timestamp()
        
        # Updataing the database by the recent event top data
        self.database.insertEventPlayers(self.api.recent_event.event_id, 
                                             event_top["users"], int(self.api.recent_event.start_at * 1000))
        self.database.insertEventRanks(self.api.recent_event.event_id, 
                                             event_top["users"], int(self.api.recent_event.start_at * 1000))
        self.database.insertEventPoints(self.api.recent_event.event_id, event_top["points"])

        # Calling the notify cog to notify after new data update
        await self.notify_cog.notifyChannels(justify_time)