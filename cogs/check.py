from discord import Interaction, app_commands, channel
from discord import embeds, Color, AllowedMentions
from discord.ext import commands

from helpers.db_pg import Database
from cogs.monitor import Monitor

from typing import Optional
from datetime import datetime, timedelta

class Check(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, monitor: Monitor):
        self.bot = bot
        self.database = database
        self.monitor = monitor

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    @app_commands.command(name = "top", description = "列出目前前十名的總覽")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @commands.guild_only()
    async def top(self, interaction: Interaction, verbose: Optional[bool] = False):
        recent_event_id = self.monitor.recent_event["event_id"]
        top_players = self.database.getEventTopPlayers(recent_event_id); speeds = []
        for i in range(len(top_players)):
            speeds.append([
                i, top_players[i][4] - self.database.\
                    getEventPlayerPointsAtTimeBefore(recent_event_id, top_players[i][0])
            ])
        speeds = sorted(speeds, key = lambda x: x[1], reverse = True)
        for i in range(len(speeds)):
            if i == 0: speeds[i].append(1)
            elif speeds[i][1] == speeds[i - 1][1]: speeds[i].append(speeds[i - 1][2])
            else: speeds[i].append(speeds[i - 1][2] + 1)
        for speed in speeds:
            top_players[speed[0]].append(speed[1])
            top_players[speed[0]].append(speed[2])

        texts = [
            f"### :number_{i + 1}: **{top_players[i][1]}** | "\
          + f"📊 **{top_players[i][4]}** | 📈 **{top_players[i][5]}** ({top_players[i][6]})\n"\
          + f"-# **#{top_players[i][0]}** *{top_players[i][2]}* __*Lv.{top_players[i][3]}*__"
            for i in range(len(top_players))
        ]
        embed = embeds.Embed(
            title = f"前十名總覽 *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
            description = "\n".join(texts),
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        )
        await interaction.response.send_message(
            embed = embed, ephemeral = not verbose, delete_after = 300
        )

    @app_commands.command(name = "detail", description = "列出目前前十名中指定名次的玩家細節")
    @app_commands.describe(rank = "提定展示玩家的名次")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @commands.guild_only()
    async def detail(self, interaction: Interaction, rank: app_commands.Range[int, 1, 10], verbose: Optional[bool] = False):
        recent_event_id = self.monitor.recent_event["event_id"]
        recent_event_at_start = self.monitor.recent_event["start_at"]
        top_player = self.database.getEventTopPlayers(recent_event_id)[rank - 1]
        recent_points = self.database.getEventPlayerRecentPoints(recent_event_id, top_player[0])
        recent_points_deltas = [[
            datetime.fromtimestamp(recent_points[i][0] / 1000).strftime("%H:%M"), 
            recent_points[i][1] - recent_points[i + 1][1]
        ] for i in range(20)]
        ele = [1, 2, 12, 24]; interval_details = [[
            (datetime.now() - timedelta(minutes = 60 * i)).strftime("%H:%M"),
            datetime.now().strftime("%H:%M"),
            self.database.getEventPlayerPointsNumAtTimeBefore(recent_event_id, top_player[0], 3600000 * i),
            self.database.getEventPlayerPointsAtTimeBefore(recent_event_id, top_player[0], 3600000 * i)
            ] for i in ele
        ]
        for i in range(4):
            interval_details[i].append(int((top_player[4] - interval_details[i][3]) / interval_details[i][2]))
            interval_details[i][3] = \
                datetime.fromtimestamp(3600 * ele[i] / interval_details[i][2]).strftime("%M:%S")

        embed = embeds.Embed(
            title = f"**{top_player[1]}** | 📊 **{str(top_player[4]).rjust(10)}** *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
            description = f"-# **#{top_player[0]}** *{top_player[2]}* __*Lv.{top_player[3]}*__",
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        )
        embed.add_field(
            name = "近期20次變動",
            value = "\n".join([f"⏰{recent_points_delta[0]} 📈{recent_points_delta[1]}" 
                               for recent_points_delta in recent_points_deltas]),
            inline = True
        )
        embed.add_field(
            name = "近期統計",
            value = "\n".join([f"⏰{interval_detail[0]}~{interval_detail[1]} 🔄{interval_detail[2]} "\
                             + f"⏳{interval_detail[3]} 📈{interval_detail[4]}"
                               for interval_detail in interval_details]),
            inline = True
        )
        await interaction.response.send_message(
            embed = embed, ephemeral = not verbose, delete_after = 300
        )
