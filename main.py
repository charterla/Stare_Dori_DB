from typing import Optional
from pathlib import Path
from environs import Env
from logging import Logger

import gc
from multiprocessing import Process

import discord
from discord.ext import commands
from discord import app_commands

from utils.db_pg import Database
from utils.api import API
from utils.logger import getLogger
from objs.activity import SERVER_NAME

from cogs.basic import Basic
class SDBot(commands.Bot):
    def __init__(self, env: Env, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Setting up main logger
        self.logger: Logger = getLogger("main")
        
        # Setting up the connection to database
        self.database: Database = Database(
            host = env.str("DB_HOST"), name = env.str("DB_NAME"), user = env.str("DB_USER"),
            password = env.str("DB_PASSWORD"), port = env.int("DB_PORT"), logger = self.logger)
        self.database.createTableForUsers()
        self.database.createTableForChannels()
        self.database.createTableForEvents()
        self.database.createTableForMonthlys()
        
        # Setting up the connection to fetch game data
        self.apis: list[Process] = [Process(target = API, args = (index, Path("../.env"), Path("../.log"), )) 
                                    for index in range(4)]
        for api in self.apis: api.start()
        return
    
    async def setup_hook(self) -> None:
        await self.add_cog(Basic(self, self.database))
        self.synced = await self.tree.sync()
        return

    async def on_ready(self) -> None:
        self.logger.info("SDBot is online")
        return

if __name__ == "__main__":
    # Loading environmental variables
    env = Env(); env.read_env(Path("./.env"))

    # Loading the Discord Bot
    intents = discord.Intents.default()
    intents.message_content = True
    bot = SDBot(env = env, command_prefix = "sd ", intents = intents, help_command = None)
    
    # Defining command for bot owner to reload API
    @app_commands.check(lambda interaction: interaction.user.id == int(env.str("OWNER")))
    @bot.tree.command(name = "reload", description = "重新加載收集資料的API")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                for server_id, server_name in enumerate(SERVER_NAME)])
    async def reload(interaction: discord.Interaction, server: app_commands.Choice[int]) -> None:
        server_id = server.value
        bot.apis[server_id].terminate(); bot.apis[server_id].join()
        bot.apis[server_id] = Process(target = API, args = (server_id, Path("../.env"), Path("../.log"), ))
        gc.collect(); bot.apis[server_id].start()
        await interaction.response.send_message(f"收集**{server.name}**資料的API已重新加載", ephemeral = True); return
    
    # Defining command for bot owner to inform user with bot status
    @app_commands.check(lambda interaction: interaction.user.id == int(env.str("OWNER")))
    @bot.tree.command(name = "infrom", description = "通過機器人狀態廣播通知")
    @app_commands.describe(message = "欲通知之訊息，不輸入即清除廣播")
    async def inform(interaction: discord.Interaction, message: Optional[str] = None) -> None:
        if message == None:
            await bot.change_presence(activity = None, status = discord.Status.online)
            await interaction.response.send_message(f"通知訊息已被清除", ephemeral = True)
        else:
            await bot.change_presence(activity = discord.Game(name = message), status = discord.Status.online)
            await interaction.response.send_message(f"通知訊息`{message}`已被廣播", ephemeral = True)
        return
        
    # Defining error handler
    @bot.tree.error
    async def on_command_error(interaction: discord.Interaction, error: commands.CommandError) -> None:
        await interaction.response.send_message("您無法使用該指令", ephemeral = True, delete_after = 300); return
    
    # Running the Discord Bot
    bot.run(token = env.str("TOKEN"))