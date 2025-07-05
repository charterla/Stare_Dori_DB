import discord
from discord.ext import commands
from helpers.db_pg import Database

from cogs.info import Info
from cogs.monitor import Monitor
from cogs.check import Check
class SDBot(commands.Bot):
    def __init__(self, database: Database, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database = database
    
    async def setup_hook(self) -> None:
        await self.add_cog(Info(self))
        monitor = Monitor(self, self.database)
        await self.add_cog(monitor)
        await self.add_cog(Check(self, self.database, monitor))
        self.synced = await self.tree.sync()

    async def on_ready(self) -> None:
        print("SDBot is online.")

import os
from environs import Env
if __name__ == "__main__":
    # Loading environmental variables
    env = Env()
    BASE_DIR = os.path.dirname(__file__)
    env.read_env(os.path.join(BASE_DIR, ".env"))

    # Setting up the connection to database
    database = Database(
        host = env.str("DB_HOST"),
        name = env.str("DB_NAME"),
        user = env.str("DB_USER"),
        password = env.str("DB_PASSWORD"),
        port = env.int("DB_PORT")
    )

    # Loading and Running the Discord Bot
    intents = discord.Intents.default()
    intents.message_content = True
    bot = SDBot(
        database = database,
        command_prefix = "sd ",
        intents = intents, 
        help_command = None
    )
    bot.run(token = env.str("TOKEN"))