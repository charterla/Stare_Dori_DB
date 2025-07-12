from discord.ext import commands, tasks

from datetime import datetime
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
    @tasks.loop(time = datetime.strptime('04:05', '%H:%M').time())
    async def checkRecentEvent(self):
        check_recent_event_id = await self.api.getRecentEventID()
        if check_recent_event_id != self.api.recent_event.event_id:
            await self.api.updateRecentEvent(check_recent_event_id)
            self.database.createTableForEvent(check_recent_event_id)

    # Synchronizing the data about event points
    @tasks.loop(minutes = 1)
    async def getRecentEventTop(self):
        event_top = await self.api.getEventTop(self.api.recent_event.event_id)
        if datetime.now().timestamp() - self.last_updata_time > 90:
            event_top = await self.api.getEventTop(self.api.recent_event.event_id, interval = 60000)
        justify_time = datetime.now().timestamp() - self.last_updata_time if self.last_updata_time > 0 else 0
        self.last_updata_time = datetime.now().timestamp()
            
        self.database.insertEventPlayers(self.api.recent_event.event_id, 
                                             event_top["users"], int(self.api.recent_event.start_at * 1000))
        self.database.insertEventRanks(self.api.recent_event.event_id, 
                                             event_top["users"], int(self.api.recent_event.start_at * 1000))
        self.database.insertEventPoints(self.api.recent_event.event_id, event_top["points"])

        # Calling the notify cog to notify after new data update
        await self.notify_cog.notifyChannels(justify_time)