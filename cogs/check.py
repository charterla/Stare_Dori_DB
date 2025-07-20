from discord import Interaction, Button, app_commands, ui
from discord import embeds, Color, ButtonStyle
from discord.ext import commands

from helpers.db_pg import Database
from helpers.api import API
from objects.top_players import TopPlayerInfo, getTopPlayersBriefList, getTopPlayerDetail

from typing import Optional
from datetime import datetime

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
            self.embed.description += f"### 🔽 與後一名分差：{self.info.points_down_delta:,}"
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
        if self.current_page == 3:
            self.embed.description += "### 休息時間："
            for date, stop_intervals in self.info.stop_intervals.items():
                self.embed.add_field(
                    name = f"📅 `{date}`",
                    value = "\n".join([f"⏰ `{stop_interval['start_time']}` ~ " \
                                     + f"⏰ `{stop_interval['end_time']}` - " \
                                     + f"⏳ `{stop_interval['time_delta']}`"
                                       for stop_interval in stop_intervals]),
                    inline = False
                )
        if self.current_page == 4:
            self.embed.description += "### 排名變更記錄："
            for date, rank_changes in self.info.rank_changes.items():
                self.embed.add_field(
                    name = f"📅 `{date}`",
                    value = "\n".join([f"⏰ `{rank_change['update_time']}` " \
                                     + (f":number_{rank_change['from_rank']}: ➔ " if rank_change['from_rank'] > 0 else ":asterisk: ➔ ") \
                                     + (f":number_{rank_change['to_rank']}:" if rank_change['to_rank'] > 0 else ":asterisk:")
                                       for rank_change in rank_changes]),
                    inline = False
                )

    @ui.button(label = "上一頁", style = ButtonStyle.primary)
    async def to_last_page(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page > 0: self.current_page -= 1; self.update_embed()
        await self.update(interaction)

    @ui.button(label = "下一頁", style = ButtonStyle.primary)
    async def to_next_page(self, interaction: Interaction, button: Button):
        await interaction.response.defer()
        if self.current_page < 4: self.current_page += 1; self.update_embed()
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
    @commands.guild_only()
    async def top(self, interaction: Interaction, verbose: Optional[bool] = False):
        # Getting recent event and Checking if event is start or not
        recent_event_id = self.api.recent_event.event_id
        recent_event_at_start = self.api.recent_event.start_at
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
        top_players = getTopPlayersBriefList(recent_event_id, self.database)

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

    @app_commands.command(name = "detail", description = "列出目前前十名中指定名次的玩家細節")
    @app_commands.describe(rank = "提定展示玩家的名次")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @commands.guild_only()
    async def detail(self, interaction: Interaction, rank: app_commands.Range[int, 1, 10], verbose: Optional[bool] = False):
        # Getting recent event and Checking if event is start or not
        if self.api.recent_event.start_at > datetime.now().timestamp():
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
        response_view = PlayerDetailView(getTopPlayerDetail(rank - 1, self.api.recent_event, self.database), verbose)
        await response_view.send(interaction)