from discord import Interaction, Button, SelectMenu, app_commands, ui
from discord import embeds, Color, ButtonStyle, SelectOption
from discord.ext import commands

from helpers.db_pg import Database
from helpers.api import API
from objects.top_players import TopPlayerInfo, getTopPlayersBriefList, getTopPlayerDetail, getTopPlayerDaily
from objects.channel import getChannelStatus

from typing import Optional
from datetime import datetime

SERVER_NAME = ["日服", "國際服", "繁中服", "簡中服"]

class PlayerDetailView(ui.View):
    def __init__(self, info: TopPlayerInfo, verbose: bool):
        super().__init__()
        self.info = info
        self.verbose = verbose

        self.current_page = 0
        self.embed = embeds.Embed(
            title = f"**:number_{self.info.now_rank}:** **{self.info.name}** " + \
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
        self.embed.clear_fields()
        if self.current_page == 0:
            self.embed.description += f"### 📊 目前分數：{self.info.now_points:,}\n"
            self.embed.description += f"### 📈 目前時速：{self.info.speed:,} :number_{self.info.speed_rank}:\n"
            self.embed.description += f"### 🔼 與前一名分差：{self.info.points_up_delta:,}\n"
            self.embed.description += f"### 🔽 與後一名分差：{self.info.points_down_delta:,}\n"
            self.embed.description += f"### 🔄 有記錄場次數：{self.info.points_change_times_total}"
        if self.current_page == 1:
            self.embed.description += "### 近期20次變動：\n"
            self.embed.description += "\n".join([f"⏰`{recent_points_delta['change_time']}`  " \
                                               + f"📈`{(str(recent_points_delta['change_points'])).rjust(6)}`" 
                                                 for recent_points_delta in self.info.recent_points_deltas])
        if self.current_page == 2:
            self.embed.description += "### 近期統計：\n"
            self.embed.description += "\n".join([f"⏰`{interval_detail['time_interval_start']}~{interval_detail['time_interval_end']}`  " \
                                               + f"🔄`{str(interval_detail['change_num']).rjust(3)}`  "\
                                               + f"⏳`{interval_detail['average_change_interval']}`  "\
                                               + f"📈`{str(interval_detail['average_change_points']).rjust(6)}`"
                                                 for interval_detail in self.info.interval_details])

    @ui.button(label = "上一頁", style = ButtonStyle.primary)
    async def to_last_page(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page > 0: self.current_page -= 1; self.update_embed()
        await self.update(interaction)

    @ui.button(label = "下一頁", style = ButtonStyle.primary)
    async def to_next_page(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page < 2: self.current_page += 1; self.update_embed()
        await self.update(interaction)

class PlayerDailyView(ui.View):
    def __init__(self, info: TopPlayerInfo, verbose: bool):
        super().__init__()
        self.info = info
        self.verbose = verbose

        self.current_page = len(self.info.points_deltas_daily) - 1
        self.embed = embeds.Embed(
            title = f"**:number_{self.info.now_rank}:** **{self.info.name}** " + \
                    f"*[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
            color = Color.from_rgb(r = 51, g = 51, b = 255))
        self.update_embed()

        self.children[0].options = [
            SelectOption(label = event_day, value = i, emoji = "📅")
            for i, event_day in enumerate(self.info.points_deltas_daily.keys())]

    async def send(self, interaction: Interaction):
        await interaction.response.send_message(
            embed = self.embed, view = self, ephemeral = not self.verbose, delete_after = 300)
        
    async def update(self, interaction: Interaction):
        await interaction.edit_original_response(embed = self.embed, view = self)

    def update_embed(self):
        current_day = list(self.info.points_deltas_daily.keys())[self.current_page]
        self.embed.description = f"-# **#{self.info.uid}** | Rank.{self.info.rank} | {self.info.introduction}\n" \
                               + f"### 📅 選擇日期：{current_day}"
        self.embed.clear_fields()
        self.embed.add_field(name = f"本日總獲得分數：{self.info.points_deltas_daily[current_day]}", value = "", inline = False)
        self.embed.add_field(name = f"本日有記錄的總場次數：{self.info.points_change_times_total_daily[current_day]}", value = "", inline = False)
        points_change_times_in_hours = [f"⏰ `{str(hour).zfill(2)}` 🔄 `{str(points_change_times).rjust(2)}`"
                                        for hour, points_change_times in enumerate(self.info.points_change_times_total[current_day])
                                        if points_change_times >= 0]
        points_change_times_in_hours = [points_change_times_in_hours[i:i + (int(len(points_change_times_in_hours) / 3))] 
                                        for i in range(0, len(points_change_times_in_hours), (int(len(points_change_times_in_hours) / 3)))]
        points_change_times_in_hours[-1] += ["" for i in range(len(points_change_times_in_hours) % 3)]
        self.embed.add_field(
            name = f"本日有記錄的每小時場次數：",
            value = "\n".join(["　".join(points_change_times_in_hours_text)
                                   for points_change_times_in_hours_text in list(zip(*points_change_times_in_hours))]),
            inline = False)
        self.embed.add_field(name = f"本日總休息時間：{self.info.stop_total_daily[current_day]}", value = "", inline = False)
        for now_field, i in enumerate(range(0, len(self.info.stop_intervals[current_day]), 16)):
            if now_field == 9: break
            self.embed.add_field(
                name = "" if now_field > 0 else "本日休息時間：",
                value = "\n".join([f"⏰ `{stop_interval['start_time']}` ~ " \
                                 + f"⏰ `{stop_interval['end_time']}` - " \
                                 + f"⏳ `{stop_interval['time_delta']}`"
                                   for stop_interval in self.info.stop_intervals[current_day][i:i + 16]]),
                inline = False)
        for now_field, i in enumerate(range(-1, len(self.info.rank_changes[current_day]), 16)):
            if now_field == 9: break
            if len(self.info.rank_changes[current_day]) == 0: break
            self.embed.add_field(
                name = "　" if now_field > 0 else "本日排名變更：",
                value = "\n".join([f"⏰ `{rank_change['update_time']}` " \
                                 + (f":number_{rank_change['from_rank']}: ➔ " if rank_change['from_rank'] > 0 else ":asterisk: ➔ ") \
                                 + (f":number_{rank_change['to_rank']}:" if rank_change['to_rank'] > 0 else ":asterisk:")
                                   for rank_change in self.info.rank_changes[current_day][max(0, i):i + 16]]),
                inline = True)

    @ui.select(placeholder = "選擇日期以列出指定名次玩家的該日狀況")
    async def change_display_day(self, interaction: Interaction, select: ui.Select):
        await interaction.response.defer()
        self.current_page = int(select.values[0]); self.update_embed()
        await self.update(interaction)

class Check(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, api: API):
        self.bot = bot
        self.database = database
        self.api = api

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    @app_commands.command(name = "top", description = "列出目前前十名的總覽")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @app_commands.describe(server = "指定指令展示數據的遊戲伺服器，不指定將以頻道預設為準")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    @commands.guild_only()
    async def top(self, interaction: Interaction, verbose: Optional[bool] = False, 
                  server: Optional[app_commands.Choice[int]] = None):
        # Comfirming which server id to process
        if server == None: server_id = getChannelStatus(interaction.channel_id, self.database).server_id
        else: server_id = server.value

        # Getting recent event and Checking if event is start or not
        recent_event_id = self.api.recent_events[server_id].event_id
        recent_event_at_start = self.api.recent_events[server_id].start_at
        if recent_event_at_start > datetime.now().timestamp():
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
        top_players = getTopPlayersBriefList(server_id, recent_event_id, self.database)

        # Generating the response to the user
        texts = [
            f"### **:number_{top_player.now_rank}:** **{top_player.name}** | "\
          + f"📊 **{top_player.now_points:,}** | 📈 **{top_player.speed:,}** ({top_player.speed_rank})\n"\
          + f"-# **#{top_player.uid}** | Rank.{top_player.rank} | {top_player.introduction}"
            for top_player in top_players
        ]
        embed = embeds.Embed(
            title = f"前十名總覽 *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
            description = "\n".join(texts),
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        )
        await interaction.response.send_message(
            embed = embed, ephemeral = not verbose, delete_after = 300
        )

    @app_commands.command(name = "detail", description = "列出目前前十名中指定名次玩家的細節")
    @app_commands.describe(rank = "提定展示玩家的名次")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @app_commands.describe(server = "指定指令展示數據的遊戲伺服器，不指定將以頻道預設為準")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    @commands.guild_only()
    async def detail(self, interaction: Interaction, rank: app_commands.Range[int, 1, 10], verbose: Optional[bool] = False, 
                     server: Optional[app_commands.Choice[int]] = None):
        # Comfirming which server id to process
        if server == None: server_id = getChannelStatus(interaction.channel_id, self.database).server_id
        else: server_id = server.value

        # Getting recent event and Checking if event is start or not
        if self.api.recent_events[server_id].start_at > datetime.now().timestamp():
            embed = embeds.Embed(
                title = f"玩家細節 *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
                description = "目前活動尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
            await interaction.response.send_message(
                embed = embed, ephemeral = not verbose, delete_after = 300
            )
            return

        # Generating the response to the user
        response_view = PlayerDetailView(getTopPlayerDetail(server_id, rank - 1, self.api.recent_events[server_id], self.database), verbose)
        await response_view.send(interaction)

    @app_commands.command(name = "daily", description = "列出目前前十名中指定名次玩家的每日狀況")
    @app_commands.describe(rank = "提定展示玩家的名次")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @app_commands.describe(server = "指定指令展示數據的遊戲伺服器，不指定將以頻道預設為準")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    @commands.guild_only()
    async def daily(self, interaction: Interaction, rank: app_commands.Range[int, 1, 10], verbose: Optional[bool] = False, 
                    server: Optional[app_commands.Choice[int]] = None):
        # Comfirming which server id to process
        if server == None: server_id = getChannelStatus(interaction.channel_id, self.database).server_id
        else: server_id = server.value

        # Getting recent event and Checking if event is start or not
        if self.api.recent_events[server_id].start_at > datetime.now().timestamp():
            embed = embeds.Embed(
                title = f"玩家每日狀況 *[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]*",
                description = "目前活動尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
            await interaction.response.send_message(
                embed = embed, ephemeral = not verbose, delete_after = 300
            )
            return

        # Generating the response to the user
        response_view = PlayerDailyView(getTopPlayerDaily(server_id, rank - 1, self.api.recent_events[server_id], self.database), verbose)
        await response_view.send(interaction)