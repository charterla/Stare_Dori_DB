from discord.ext import commands, tasks

from datetime import datetime
from helpers import api
from helpers.db_pg import Database

class Monitor(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database

        self.recent_event = api.getRecentEvent()
        self.database.createTableForEvent(self.recent_event["event_id"])

        self.last_updata_time = 0

        self.checkRecentEvent.start()
        self.getRecentEventTop.start()

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    @tasks.loop(time = datetime.strptime('20:00', '%H:%M').time())
    async def checkRecentEvent(self):
        check_recent_event = api.getRecentEvent()
        if check_recent_event["event_id"] != self.recent_event["event_id"]:
            self.recent_event = check_recent_event
            self.database.createTableForEvent(check_recent_event["event_id"])

    @tasks.loop(minutes = 1)
    async def getRecentEventTop(self):
        if datetime.now().timestamp() - self.last_updata_time > 90:
            event_top = api.getEventtop(self.recent_event["event_id"], interval = 60000)
        else: event_top = api.getEventtop(self.recent_event["event_id"])
        self.last_updata_time = datetime.now().timestamp()
        
        self.database.insectEventPlayers(self.recent_event["event_id"], event_top["users"])
        self.database.insectEventPoints(self.recent_event["event_id"], event_top["points"])
