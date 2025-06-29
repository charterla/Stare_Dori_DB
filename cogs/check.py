from discord import Interaction, Button, app_commands, ui
from discord import embeds, Color, ButtonStyle
from discord.ext import commands

from helpers.db_pg import Database
from cogs.monitor import Monitor

from typing import Optional
from datetime import datetime, timedelta

class TopPlayerInfo():
    def __init__(self, top_player: list, recent_points_deltas: list, interval_details: list, stop_intervals: list):
        self.uid = top_player[0]
        self.name = top_player[1]
        self.introduction = top_player[2]
        self.rank = top_player[3]
        self.now_points = top_player[4]
        self.last_update_time = top_player[5]
        self.speed = top_player[6]
        self.speed_rank = top_player[7]
        self.now_rank = top_player[8]
        self.points_up_delta = top_player[9]
        self.points_down_delta = top_player[10]
        self.recent_points_deltas = [
            {"change_time": recent_points_delta[0], "change_points": recent_points_delta[1]}
            for recent_points_delta in recent_points_deltas
        ]
        self.interval_details = [{
            "time_interval_start": interval_detail[0],
            "time_interval_end": interval_detail[1],
            "change_num": interval_detail[2],
            "average_change_interval": interval_detail[3],
            "average_change_points": interval_detail[4]
            } for interval_detail in interval_details
        ]
        self.stop_intervals = [{
            "start_time": datetime.fromtimestamp(stop_interval[0] / 1000).strftime("%m-%d %H:%M"),
            "end_time": datetime.fromtimestamp(stop_interval[1] / 1000).strftime("%m-%d %H:%M")
            } for stop_interval in stop_intervals if stop_interval[2] < 130000
        ]

class PlayerDetailView(ui.View):
    def __init__(self, info: TopPlayerInfo, verbose: bool):
        super().__init__()
        self.info = info
        self.verbose = verbose

        self.current_page = 0
        self.embed = embeds.Embed(
            title = f":number_{self.info.now_rank}: **{self.info.name}** " + \
                    f"*[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        )
        self.update_embed()

    async def send(self, interaction: Interaction):
        await interaction.response.send_message(
            embed = self.embed, view = self, ephemeral = not self.verbose, delete_after = 300
        )
        
    async def update(self, interaction: Interaction):
        await interaction.edit_original_response(embed = self.embed, view = self)

    def update_embed(self):
        self.embed.description = f"-# **#{self.info.uid}** | Rank.{self.info.rank} | {self.info.introduction}\n"
        if self.current_page == 0:
            self.embed.description += f"### 📊 目前分數：{self.info.now_points}\n"
            self.embed.description += f"### 📈 目前時速：{self.info.speed} :number_{self.info.speed_rank}:\n"
            self.embed.description += f"### 🔼 與前一名分差：{self.info.points_up_delta}\n"
            self.embed.description += f"### 🔽 與後一名分差：{self.info.points_down_delta}"
        if self.current_page == 1:
            self.embed.description += "### 近期20次變動：\n"
            self.embed.description += "\n".join([f"⏰`{recent_points_delta['change_time']}`  " \
                                               + f"📈`{str(recent_points_delta['change_points']).zfill(5)}`" 
                                                 for recent_points_delta in self.info.recent_points_deltas])
        if self.current_page == 2:
            self.embed.description += "### 近期統計：\n"
            self.embed.description += "\n".join([f"⏰`{interval_detail['time_interval_start']}~{interval_detail['time_interval_end']}`  " \
                                               + f"🔄`{str(interval_detail['change_num']).zfill(3)}`  "\
                                               + f"⏳`{interval_detail['average_change_interval']}`  "\
                                               + f"📈`{str(interval_detail['average_change_points']).zfill(5)}`"
                                                 for interval_detail in self.info.interval_details])
        if self.current_page == 3:
            self.embed.description += "### 休息時間：\n"
            self.embed.description += "\n".join([f"⏰`{stop_interval['start_time']}` `~` ⏰`{stop_interval['end_time']}`"
                                                 for stop_interval in self.info.stop_intervals])

    @ui.button(label = "上一頁", style = ButtonStyle.primary)
    async def to_last_page(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page > 0: self.current_page -= 1; self.update_embed()
        await self.update(interaction)

    @ui.button(label = "下一頁", style = ButtonStyle.primary)
    async def to_next_page(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page < 3: self.current_page += 1; self.update_embed()
        await self.update(interaction)

class Check(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, monitor: Monitor):
        self.bot = bot
        self.database = database
        self.monitor = monitor

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    def getTopPlayers(self, recent_event_id: int) -> list:
        top_players = self.database.getEventTopPlayers(recent_event_id); speeds = []
        for i in range(len(top_players)):
            player_recent_interval = \
                self.database.getEventPlayerIntervals(recent_event_id, top_players[i][0])[0]
            if player_recent_interval[2] > 130000 and (datetime.now().timestamp() - \
                (player_recent_interval[2] / 1000)) <= 3600:
                speed.append([i, -1])
            else: speeds.append([ i, top_players[i][4] - self.database.\
                      getEventPlayerPointsAtTimeBefore(recent_event_id, top_players[i][0])])
        speeds = sorted(speeds, key = lambda x: x[1], reverse = True)
        for i in range(len(speeds)):
            if i == 0: speeds[i].append(1)
            elif speeds[i][1] == speeds[i - 1][1]: speeds[i].append(speeds[i - 1][2])
            else: speeds[i].append(speeds[i - 1][2] + 1)
        for speed in speeds:
            top_players[speed[0]].append(speed[1])
            top_players[speed[0]].append(speed[2])
        return top_players

    @app_commands.command(name = "top", description = "列出目前前十名的總覽")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @commands.guild_only()
    async def top(self, interaction: Interaction, verbose: Optional[bool] = False):
        # Getting recent event and Checking if event is start or not
        recent_event_id = self.monitor.recent_event["event_id"]
        recent_event_at_start = int(self.monitor.recent_event["start_at"])
        if recent_event_at_start > int(datetime.now().timestamp() * 1000):
            embed = embeds.Embed(
                title = f"前十名總覽 *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
                description = "目前活動尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
            await interaction.response.send_message(
                embed = embed, ephemeral = not verbose, delete_after = 300
            )
            return

        # Collecting the infomation about all top 10 players 
        top_players = self.getTopPlayers(recent_event_id)

        # Generating the response to the user
        texts = [
            f"### :number_{i + 1}: **{top_players[i][1]}** | "\
          + f"📊 **{top_players[i][4]}** | 📈 **{top_players[i][6]}** ({top_players[i][7]})\n"\
          + f"-# **#{top_players[i][0]}** | Rank.{top_players[i][3]} | {top_players[i][2]}"
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
        # Getting recent event and Checking if event is start or not
        recent_event_id = self.monitor.recent_event["event_id"]
        recent_event_at_start = int(self.monitor.recent_event["start_at"])
        if recent_event_at_start > int(datetime.now().timestamp() * 1000):
            embed = embeds.Embed(
                title = f"玩家細節 *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
                description = "目前活動尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
            await interaction.response.send_message(
                embed = embed, ephemeral = not verbose, delete_after = 300
            )
            return
        
        # Collecting the infomation about the specified top 10 player
        top_players = self.getTopPlayers(recent_event_id)
        top_player = top_players[rank - 1]; top_player.append(rank)
        if rank == 1: top_player.append(0)
        else: top_player.append(top_players[rank - 2][4] - top_player[4])
        if rank == 10: top_player.append(0)
        else: top_player.append(top_player[4] - top_players[rank][4])

        # Collecting the data about the specified top 10 player
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
            if interval_details[i][2] == 0: 
                interval_details[i].append("-----"); interval_details[i][3] = "--:--"
            else: 
                interval_details[i].append(int((top_player[4] - interval_details[i][3]) / interval_details[i][2]))
                interval_details[i][3] = \
                    datetime.fromtimestamp(3600 * ele[i] / interval_details[i][2]).strftime("%M:%S")
        stop_intervals = self.database.getEventPlayerIntervals(recent_event_id, top_player[0])
        top_player_info = TopPlayerInfo(top_player, recent_points_deltas, interval_details, stop_intervals)

        # Generating the response to the user
        response_view = PlayerDetailView(top_player_info, verbose)
        await response_view.send(interaction)