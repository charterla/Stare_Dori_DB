from discord.ext import commands, tasks

from datetime import datetime
from helpers.db_pg import Database
from helpers.api import API

class Monitor(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, api: API):
        self.bot = bot
        self.database = database
        self.api = api

        self.database.createTableForEvent(self.api.recent_event.event_id)

        self.last_updata_time = 0

        self.checkRecentEvent.start()
        # self.getRecentEventTop.start()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    # Synchronizing the recent event
    @tasks.loop(time = datetime.strptime('04:00', '%H:%M').time())
    async def checkRecentEvent(self):
        check_recent_event_id = self.api.getRecentEventID()
        if check_recent_event_id != self.api.recent_event.event_id:
            await self.api.updateRecentEvent(check_recent_event_id)
            self.database.createTableForEvent(check_recent_event_id)

    # Synchronizing the data about event points
    @tasks.loop(minutes = 1)
    async def getRecentEventTop(self):
        try:
            if datetime.now().timestamp() - self.last_updata_time > 90:
                event_top = self.api.getEventTop(self.api.recent_event.event_id, interval = 60000)
            else: event_top = self.api.getEventTop(self.api.recent_event.event_id)
            self.last_updata_time = datetime.now().timestamp()
            
            self.database.insertEventPlayers(self.api.recent_event.event_id, 
                                             event_top["users"], int(self.api.recent_event.start_at * 1000))
            self.database.insertEventPoints(self.api.recent_event.event_id, event_top["points"])
        except: return
