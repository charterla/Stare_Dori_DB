from discord import Interaction, app_commands
from discord import embeds, Color
from discord.ext import commands

from helpers.db_pg import Database
from helpers.api import API
from objects.top_players import getTopPlayersBriefList
from objects.channel import getChannelStatus

from typing import Optional
from datetime import datetime

import logging
logger = logging.getLogger("SDBot")

SERVER_NAME = ["日服", "國際服", "繁中服", "簡中服"]

class Notify(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, api: API):
        self.bot = bot
        self.database = database
        self.api = api

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    # Notifing the channels
    async def notifyChannels(self, server_id: int, justify_time: float):
        # Getting recent event and Checking if event is start or not
        recent_event_id = self.api.recent_events[server_id].event_id

        # Notifing the rank change to the channels which have set
        recent_rank_changes = self.database.getEventPlayersRankChangesAtTimeAfter(
            server_id, recent_event_id, int(justify_time * 1000))
        if recent_rank_changes != ():
            recent_rank_changes = [{
                    "name": self.database.getEventPlayerName(server_id, recent_event_id, recent_rank_change[0]),
                    "uid": recent_rank_change[0],
                    "from_rank": (recent_rank_change[1] if recent_rank_change[1] <= 10 else -1),
                    "to_rank": (recent_rank_change[2] if recent_rank_change[2] <= 10 else -1)
                } for recent_rank_change in recent_rank_changes 
            ]
            embed = embeds.Embed(
                title = f"**排名變更提醒** *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
                description = "\n".join([
                    "### " \
                  + (f":number_{recent_rank_change['from_rank']}:" if recent_rank_change['from_rank'] > 0 else ":asterisk:") + " ➔ " \
                  + (f":number_{recent_rank_change['to_rank']}:" if recent_rank_change['to_rank'] > 0 else ":asterisk:") + " " \
                  + f"**{recent_rank_change['name']}** *#{recent_rank_change['uid']}*"
                    for recent_rank_change in recent_rank_changes]),
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
            channels_to_notify_change = self.database.getChannelsToNotifyChange(server_id)
            for channel_id in channels_to_notify_change:
                try:
                    channel = await self.bot.fetch_channel(channel_id[0])
                    await channel.send(embed = embed)
                except:
                    logger.warning(f"Fail to send change notify to channel {channel_id[0]} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} for server {server_id}.")
        
        # Notifing the rank change to the channels which have set when recent event type is "challenge"
        if self.api.recent_events[server_id].event_type != 0: return
        texts = []; top_players = getTopPlayersBriefList(server_id, recent_event_id, self.database)
        for top_player in top_players:
            player_rank_up_to_top_times = [rank_change[0] for rank_change in 
                                           self.database.getEventPlayerRankUpToTopTimes(server_id, recent_event_id, top_player.uid)]
            player_recent_points = \
                self.database.getEventPlayerRecentPointsAtTimeAfter(
                    server_id, recent_event_id, top_player.uid, int(justify_time * 1000)) + \
                ((0, self.database.getEventPlayerPointsAtTimeBefore(
                    server_id, recent_event_id, top_player.uid, int(justify_time * 1000))), )
            for i in range(len(player_recent_points) - 1):
                if player_recent_points[i][0] in player_rank_up_to_top_times: continue
                if player_recent_points[i][1] - player_recent_points[i + 1][1] > 16000:
                    texts.append(f"### **:number_{top_player.now_rank}:** **{top_player.name}** *#{top_player.uid}* | "\
                               + f"📈 {player_recent_points[i][1] - player_recent_points[i + 1][1]}")
                    break
        if texts != []:
            embed = embeds.Embed(
                title = f"**疑似消 CP 提醒** *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
                description = "\n".join(texts),
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
            channels_to_notify_CP = self.database.getChannelsToNotifyCP(server_id)
            for channel_id in channels_to_notify_CP:
                try:
                    channel = await self.bot.fetch_channel(channel_id[0])
                    await channel.send(embed = embed)
                except: 
                    logger.warning(f"Fail to send cp notify to channel {channel_id[0]} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} for server {server_id}.")

    @app_commands.command(name = "server", description = "改變當前頻道的指定遊戲伺服器")
    @app_commands.describe(server = "改變後的指定遊戲伺服器")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    @commands.guild_only()
    @commands.has_guild_permissions(administrator = True)
    async def server(self, interaction: Interaction, server: app_commands.Choice[int]):
        # Getting channel status
        channel_status = getChannelStatus(interaction.channel_id, self.database)

        # Changing the default server
        if channel_status.server_id == server.value:
            embed = embeds.Embed(
                title = f"頻道`{interaction.channel.name}`已經指定遊戲伺服器為 \"{server.name}\"",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ); await interaction.response.send_message(embed = embed, ephemeral = True, delete_after = 300)
        else:
            self.database.updateChannelStatus(interaction.channel_id, server_id = server.value)
            embed = embeds.Embed(
                title = f"頻道`{interaction.channel.name}`指定遊戲伺服器已改為 \"{server.name}\"",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ); await interaction.response.send_message(embed = embed, ephemeral = True, delete_after = 300)

    @app_commands.command(name = "change", description = "開啟或關閉 Top 10 變更提醒功能")
    @commands.guild_only()
    @commands.has_guild_permissions(administrator = True)
    async def change(self, interaction: Interaction):
        # Getting channel status
        channel_status = getChannelStatus(interaction.channel_id, self.database)

        # Changing the setting about notifing the rank change
        if channel_status.is_change_nofity:
            self.database.updateChannelStatus(interaction.channel_id, is_change_notify = False)
            embed = embeds.Embed(
                title = f"頻道`{interaction.channel.name}`已關閉 Top 10 變更提醒功能",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ); await interaction.response.send_message(embed = embed, ephemeral = True, delete_after = 300)
        else:
            self.database.updateChannelStatus(interaction.channel_id, is_change_notify = True)
            embed = embeds.Embed(
                title = f"頻道`{interaction.channel.name}`已開啟 Top 10 變更提醒功能",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ); await interaction.response.send_message(embed = embed, ephemeral = True, delete_after = 300)

    @app_commands.command(name = "cp", description = "開啟或關閉 Top 10 疑似消 CP 提醒功能")
    @commands.guild_only()
    @commands.has_guild_permissions(administrator = True)
    async def cp(self, interaction: Interaction):
        # Getting channel status
        channel_status = getChannelStatus(interaction.channel_id, self.database)

        # Changing the setting about notifing the CP consume
        if channel_status.is_CP_nofity:
            self.database.updateChannelStatus(interaction.channel_id, is_CP_notify = False)
            embed = embeds.Embed(
                title = f"頻道`{interaction.channel.name}`已關閉 Top 10 疑似消 CP 提醒功能",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ); await interaction.response.send_message(embed = embed, ephemeral = True, delete_after = 300)
        else:
            self.database.updateChannelStatus(interaction.channel_id, is_CP_notify = True)
            embed = embeds.Embed(
                title = f"頻道`{interaction.channel.name}`已開啟 Top 10 疑似消 CP 提醒功能",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ); await interaction.response.send_message(embed = embed, ephemeral = True, delete_after = 300)
