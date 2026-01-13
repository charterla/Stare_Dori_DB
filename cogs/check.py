from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
from logging import Logger

from discord import Interaction, Button, app_commands, ui
from discord import embeds, Color, ButtonStyle, SelectOption
from discord.ext import commands
from discord.channel import DMChannel, GroupChannel

from utils.logger import getLogger
from utils.db_pg import Database
from objs.setting import getUser, getChannel
from objs.activity import SERVER_NAME, EventInfo, getRecentEvent, MonthlyInfo, getRecentMonthly
from objs.player import EventPlayer, getEventTopPlayers, EventPlayerDetail, getEventTopPlayerDetail, \
                        EventPlayerDaily, getEventTopPlayerDaily, MonthlyPlayer, getMonthlyTopPlayers
from cogs.basic import C_INFO

class EventPlayerDetailView(ui.View):
    def __init__(self, info: EventPlayerDetail, server_id: int, request_time: int, timezone: ZoneInfo, verbose: bool):
        super().__init__()
        self.info: EventPlayerDetail = info; self.server_id = server_id
        self.request_time: int = request_time; self.timezone: ZoneInfo = timezone
        self.verbose: bool = verbose

        self.current_page: int = 0
        self.embed: embeds.Embed = embeds.Embed(
            title = f"**:number_{self.info.point_rank}:** **{self.info.name}**", 
            color = Color.from_rgb(r = 51, g = 51, b = 255),
        ).set_footer(text \
            = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
            + f" | 數據所屬：{SERVER_NAME[server_id]}")
        
        recent_point_changes: list[str] \
            = [f"⏰`{datetime.fromtimestamp(point_change[0], tz = self.timezone).strftime('%H:%M')}` " \
             + f"📈`{(str(point_change[1])).rjust(6)}`" for point_change in self.info.recent_point_changes]
        self.recent_point_changes: list[str] \
            = ["\n".join(recent_point_changes), ""] if len(recent_point_changes) <= 10 \
              else ["\n".join(recent_point_changes[:10]), "\n".join(recent_point_changes[10:])]
        self.recent_ranges_detail: str = "\n".join([
            f"⏰`{datetime.fromtimestamp(range_detail[0], tz = self.timezone).strftime('%H:%M')}" \
          + f"~{datetime.fromtimestamp(self.request_time, tz = self.timezone).strftime('%H:%M')}` " \
          + f"🔄`{str(range_detail[1]).rjust(3)}` " \
          + f"⏳`" + ('--:--' if range_detail[2] == 0 else (
                str(int(timedelta(seconds = range_detail[2]).seconds // 60)).zfill(2) \
              + ":" + str(timedelta(seconds = range_detail[2]).seconds % 60).zfill(2))) + "` " \
          + f"📈`{'------' if range_detail[3] == 0 else str(range_detail[3]).rjust(6)}`"
            for range_detail in self.info.recent_ranges_detail])
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
            self.embed.description += f"### 📊 目前分數：{self.info.point:,}\n"
            self.embed.description += f"### 📈 目前時速：{self.info.speed:,} :number_{self.info.speed_rank}:\n"
            self.embed.description += f"### 🔼 與前一名分差：{self.info.point_up_delta:,}\n"
            self.embed.description += f"### 🔽 與後一名分差：{self.info.point_down_delta:,}\n"
            self.embed.description += f"### 🔄 有記錄場次數：{self.info.point_change_times:,}"
        if self.current_page == 1:
            self.embed.description += "### 近期20次變動："
            self.embed.add_field(name = "", value = self.recent_point_changes[0], inline = True)
            if self.recent_point_changes[1] != "": 
                self.embed.add_field(name = "", value = self.recent_point_changes[1], inline = True)
        if self.current_page == 2:
            self.embed.description += "### 近期統計："
            self.embed.add_field(name = "", value = self.recent_ranges_detail, inline = False)

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

class EventPlayerDailyView(ui.View):
    def __init__(self, info: EventPlayerDaily, server_id: int, day_split: list[int], 
                 request_time: int, timezone: ZoneInfo, verbose: bool):
        super().__init__()
        self.info: EventPlayerDaily = info; self.server_id = server_id; self.day_split: list[int] = day_split
        self.request_time: int = request_time; self.timezone: ZoneInfo = timezone
        self.verbose: bool = verbose

        self.current_page: int = len(self.day_split) - 2
        self.embed: embeds.Embed = embeds.Embed(
            title = f"**:number_{self.info.point_rank}:** **{self.info.name}** ", 
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        ).set_footer(text \
            = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
            + f" | 數據所屬：{SERVER_NAME[server_id]}")
        
        self.point_change_times_hourly: list[str] = []
        for split, change_times in zip(self.day_split, self.info.point_change_times_hourly):
            change_times_text: list[str] = [
                f"⏰`{(datetime.fromtimestamp(split, tz = self.timezone) + timedelta(hours = delta)).strftime('%H')}` " \
              + f"🔄`{str(change_time).rjust(2)}`" for delta, change_time in enumerate(change_times)
            ] + ["" for _ in range((3 - (len(change_times) % 3)) % 3)]
            change_times_text: list[list[str]] = [
                change_times_text[i:i + int(len(change_times_text) / 3)] 
                for i in range(0, len(change_times_text), int(len(change_times_text) / 3))]
            self.point_change_times_hourly.append("\n".join(
                ["　".join(change_times_sub_text) for change_times_sub_text in list(zip(*change_times_text))]))
        self.stop_total: list[str] = []
        for stop in self.info.stop_total:
            time = timedelta(seconds = stop); hours = int(time.seconds // 3600); minutes = int((time.seconds % 3600) // 60)
            self.stop_total.append(f"`{str(hours).rjust(2)}h{str(minutes).rjust(2)}m`")
        self.stop_intervals: list[list[str]] = []
        for intervals in self.info.stop_intervals:
            intervals_text: list[str] = [
                f"⏰`{datetime.fromtimestamp(start, tz = self.timezone).strftime('%H:%M')}` ~ " 
              + f"⏰`{datetime.fromtimestamp(end, tz = self.timezone).strftime('%H:%M')}` - " 
              + f"⏳`{str(int(timedelta(seconds = delta).seconds // 3600)).rjust(2)}h" 
              + f"{str(int((timedelta(seconds = delta).seconds % 3600) // 60)).rjust(2)}m`"
                for (start, end), delta in intervals]; intervals_text = intervals_text[::-1]
            self.stop_intervals.append([])
            for i in range(0, min(144, len(intervals_text)), 16):
                self.stop_intervals[-1].append("\n".join(intervals_text[i:min(i + 16, len(intervals_text))]))
        self.rank_changes: list[list[str]] = []
        for rank_changes in self.info.rank_changes:
            rank_changes_text: list[str] = [
                f"⏰`{datetime.fromtimestamp(time, tz = self.timezone).strftime('%H:%M')}` "
             + (f":number_{from_rank}: ➔ " if from_rank > 0 else ":asterisk: ➔ ")
             + (f":number_{to_rank}:" if to_rank > 0 else ":asterisk:")
                for time, (from_rank, to_rank) in rank_changes]; rank_changes_text = rank_changes_text[::-1]
            self.rank_changes.append([])
            for i in range(0, min(144, len(rank_changes_text)), 16):
                self.rank_changes[-1].append("\n".join(rank_changes_text[i:min(i + 16, len(rank_changes_text))]))
        self.update_embed()

        self.children[0].options = [
            SelectOption(label = datetime.fromtimestamp(split, tz = self.timezone).strftime("%m-%d"), 
                         value = i, emoji = "📅") for i, split in enumerate(self.day_split[:-1])]

    async def send(self, interaction: Interaction):
        await interaction.response.send_message(
            embed = self.embed, view = self, ephemeral = not self.verbose, delete_after = 300)
        
    async def update(self, interaction: Interaction):
        await interaction.edit_original_response(embed = self.embed, view = self)

    def update_embed(self):
        self.embed.description = f"-# **#{self.info.uid}** | Rank.{self.info.rank} | {self.info.introduction}\n"
        self.embed.description += f"### 📅 選擇日期：{datetime.fromtimestamp(self.day_split[self.current_page], tz = self.timezone).strftime('%m-%d')}"
        self.embed.clear_fields()
        self.embed.add_field(name = f"本日總獲得分數：{self.info.point_delta[self.current_page]}", value = "", inline = False)
        self.embed.add_field(name = f"本日有記錄的總場次數：{self.info.point_change_times[self.current_page]}", value = "", inline = False)
        self.embed.add_field(name = f"本日有記錄的每小時場次數：", 
                             value = self.point_change_times_hourly[self.current_page], inline = False)
        self.embed.add_field(name = f"本日總休息時間：{self.stop_total[self.current_page]}", value = "", inline = False)
        if len(self.stop_intervals[self.current_page]) > 0:
            for now_field, stop_interval in enumerate(self.stop_intervals[self.current_page]):
                self.embed.add_field(name = ("本日休息時間：" if now_field == 0 else ""), value = stop_interval, inline = False)
        if len(self.rank_changes[self.current_page]) > 0:
            for now_field, range_changes in enumerate(self.rank_changes[self.current_page]):
                self.embed.add_field(name = ("本日排名變更：" if now_field == 0 else ""), value = range_changes, inline = True)

    @ui.select(placeholder = "選擇日期以列出指定名次玩家的該日狀況")
    async def change_display_day(self, interaction: Interaction, select: ui.Select):
        await interaction.response.defer()
        self.current_page = int(select.values[0]); self.update_embed()
        await self.update(interaction)

class Check(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot: commands.Bot = bot
        self.database: Database = database
        self.logger: Logger = getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{__name__} is on ready")

    @app_commands.command(name = "top", description = list(C_INFO.values())[1]["/top"]["description"])
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @app_commands.describe(server = "指定指令展示數據的遊戲伺服器，不指定將以頻道預設為準")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    async def top(self, interaction: Interaction, verbose: Optional[bool] = False, 
                  server: Optional[app_commands.Choice[int]] = None):
        # Checking which object setting should be apply
        if isinstance(interaction.channel, (DMChannel, GroupChannel)):
            if server == None: server_id = getUser(self.database, interaction.user.id).server_id
            else: server_id = server.value
        else:
            if verbose and self.bot.get_guild(interaction.guild_id) is None:
                await interaction.response.send_message("該指令無法在機器人不在的伺服器中使用", 
                                                        ephemeral = True, delete_after = 300); return
            if server == None: server_id = getChannel(self.database, interaction.channel.id).server_id
            else: server_id = server.value
        
        # Getting basic event data for further operation
        recent_event: EventInfo = getRecentEvent(self.database, server_id)
        request_time: int = int(datetime.now().timestamp()); timezone: ZoneInfo = ZoneInfo("Asia/Hong_Kong")
        if recent_event == None:
            await interaction.response.send_message("目前沒有相關活動的資訊", 
                                                    ephemeral = True, delete_after = 300); return
        if recent_event.start_at > datetime.now().timestamp():
            embed: embeds.Embed = embeds.Embed(title = f"{recent_event.name} 前十名總覽", description = "當前活動尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ).set_footer(text \
                = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
                + f" | 數據所屬：{SERVER_NAME[server_id]}")
            await interaction.response.send_message(embed = embed, ephemeral = not verbose, delete_after = 300); return

        # Collecting the infomation about all top 10 players
        top_players: list[EventPlayer] = getEventTopPlayers(self.database, server_id, recent_event, request_time)
        
        # Generating the response to the user
        texts = [
            f"### **:number_{top_player.point_rank}:** **{top_player.name}** | " \
          + f"📊 **{top_player.point:,}** | 📈 **{top_player.speed:,}** ({top_player.speed_rank})\n" \
          + f"-# **#{top_player.uid}** | Rank.{top_player.rank} | {top_player.introduction}"
            for top_player in top_players]
        embed: embeds.Embed = embeds.Embed(title = f"{recent_event.name} 前十名總覽", description = "\n".join(texts), 
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        ).set_footer(text \
            = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
            + f" | 數據所屬：{SERVER_NAME[server_id]}")
        await interaction.response.send_message(embed = embed, ephemeral = not verbose, delete_after = 300)

    @app_commands.command(name = "detail", description = list(C_INFO.values())[1]["/detail"]["description"])
    @app_commands.describe(rank = "提定展示玩家的名次")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @app_commands.describe(server = "指定指令展示數據的遊戲伺服器，不指定將以頻道預設為準")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    async def detail(self, interaction: Interaction, rank: app_commands.Range[int, 1, 10], verbose: Optional[bool] = False, 
                     server: Optional[app_commands.Choice[int]] = None):
        # Checking which object setting should be apply
        if isinstance(interaction.channel, (DMChannel, GroupChannel)):
            if server == None: server_id = getUser(self.database, interaction.user.id).server_id
            else: server_id = server.value
        else:
            if verbose and self.bot.get_guild(interaction.guild_id) is None:
                await interaction.response.send_message("該指令無法在機器人不在的伺服器中使用", 
                                                        ephemeral = True, delete_after = 300); return
            if server == None: server_id = getChannel(self.database, interaction.channel.id).server_id
            else: server_id = server.value
        
        # Getting basic event data for further operation
        recent_event: EventInfo = getRecentEvent(self.database, server_id)
        request_time: int = int(datetime.now().timestamp()); timezone: ZoneInfo = ZoneInfo("Asia/Hong_Kong")
        if recent_event == None:
            await interaction.response.send_message("目前沒有相關活動的資訊", 
                                                    ephemeral = True, delete_after = 300); return
        if recent_event.start_at > datetime.now().timestamp():
            embed: embeds.Embed = embeds.Embed(title = f"前十名總覽", description = "當前活動尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ).set_footer(text \
                = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
                + f" | 數據所屬：{SERVER_NAME[server_id]}")
            await interaction.response.send_message(embed = embed, ephemeral = not verbose, delete_after = 300); return

        # Generating the response to the user
        top_player_detail: EventPlayerDetail = getEventTopPlayerDetail(self.database, server_id, recent_event, request_time, rank)
        response_view = EventPlayerDetailView(top_player_detail, server_id, request_time, timezone, verbose)
        await response_view.send(interaction)

    @app_commands.command(name = "daily", description = list(C_INFO.values())[1]["/daily"]["description"])
    @app_commands.describe(rank = "提定展示玩家的名次")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @app_commands.describe(server = "指定指令展示數據的遊戲伺服器，不指定將以頻道預設為準")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    async def daily(self, interaction: Interaction, rank: app_commands.Range[int, 1, 10], verbose: Optional[bool] = False, 
                    server: Optional[app_commands.Choice[int]] = None):
        # Checking which object setting should be apply
        if isinstance(interaction.channel, (DMChannel, GroupChannel)):
            if server == None: server_id = getUser(self.database, interaction.user.id).server_id
            else: server_id = server.value
        else:
            if verbose and self.bot.get_guild(interaction.guild_id) is None:
                await interaction.response.send_message("該指令無法在機器人不在的伺服器中使用", 
                                                        ephemeral = True, delete_after = 300); return
            if server == None: server_id = getChannel(self.database, interaction.channel.id).server_id
            else: server_id = server.value
        
        # Getting basic event data for further operation
        recent_event: EventInfo = getRecentEvent(self.database, server_id)
        request_time: int = int(datetime.now().timestamp()); timezone: ZoneInfo = ZoneInfo("Asia/Hong_Kong")
        if recent_event == None:
            await interaction.response.send_message("目前沒有相關活動的資訊", 
                                                    ephemeral = True, delete_after = 300); return
        if recent_event.start_at > datetime.now().timestamp():
            embed: embeds.Embed = embeds.Embed(title = f"前十名總覽", description = "當前活動尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ).set_footer(text \
                = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
                + f" | 數據所屬：{SERVER_NAME[server_id]}")
            await interaction.response.send_message(embed = embed, ephemeral = not verbose, delete_after = 300); return

        # Generating the response to the user
        top_player_daily, day_split = getEventTopPlayerDaily(self.database, server_id, recent_event, request_time, timezone, rank)
        response_view = EventPlayerDailyView(top_player_daily, server_id, day_split, request_time, timezone, verbose)
        await response_view.send(interaction)
        
    @app_commands.command(name = "monthly", description = list(C_INFO.values())[1]["/monthly"]["description"])
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @app_commands.describe(server = "指定指令展示數據的遊戲伺服器，不指定將以頻道預設為準")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    async def monthly(self, interaction: Interaction, verbose: Optional[bool] = False, 
                      server: Optional[app_commands.Choice[int]] = None):
        # Checking which object setting should be apply
        if isinstance(interaction.channel, (DMChannel, GroupChannel)):
            if server == None: server_id = getUser(self.database, interaction.user.id).server_id
            else: server_id = server.value
        else:
            if verbose and self.bot.get_guild(interaction.guild_id) is None:
                await interaction.response.send_message("該指令無法在機器人不在的伺服器中使用", 
                                                        ephemeral = True, delete_after = 300); return
            if server == None: server_id = getChannel(self.database, interaction.channel.id).server_id
            else: server_id = server.value
        
        # Getting basic monthly data for further operation
        recent_monthly: MonthlyInfo = getRecentMonthly(self.database, server_id)
        request_time: int = int(datetime.now().timestamp()); timezone: ZoneInfo = ZoneInfo("Asia/Hong_Kong")
        if recent_monthly == None:
            await interaction.response.send_message("目前沒有相關月榜活動的資訊", 
                                                    ephemeral = True, delete_after = 300); return
        if recent_monthly.start_at > datetime.now().timestamp():
            embed: embeds.Embed = embeds.Embed(title = f"{recent_monthly.name} 前十名總覽", description = "當前月榜尚未開始",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            ).set_footer(text \
                = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
                + f" | 數據所屬：{SERVER_NAME[server_id]}")
            await interaction.response.send_message(embed = embed, ephemeral = not verbose, delete_after = 300); return

        # Collecting the infomation about all top 10 players
        top_players: list[MonthlyPlayer] = getMonthlyTopPlayers(self.database, server_id, recent_monthly)
        
        # Generating the response to the user
        texts = [
            f"### **:number_{top_player.point_rank}:** **{top_player.name}** | 📊 **{top_player.point:,}**\n" \
          + f"-# **#{top_player.uid}** | Rank.{top_player.rank} | {top_player.introduction}"
            for top_player in top_players]
        embed: embeds.Embed = embeds.Embed(title = f"{recent_monthly.name} 前十名總覽", description = "\n".join(texts), 
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        ).set_footer(text \
            = f"數據獲取時間：{datetime.fromtimestamp(request_time, tz = timezone).strftime('%Y-%m-%d %H:%M:%S')}"
            + f" | 數據所屬：{SERVER_NAME[server_id]}")
        await interaction.response.send_message(embed = embed, ephemeral = not verbose, delete_after = 300)