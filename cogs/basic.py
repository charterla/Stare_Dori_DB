from typing import Optional
from logging import Logger

from discord import Interaction, app_commands, ui
from discord import embeds, Color, SelectOption
from discord.ext import commands
from discord.channel import DMChannel, GroupChannel

from utils.logger import getLogger
from utils.db_pg import Database
from objs.setting import User, getUser, Channel, getChannel
from objs.activity import SERVER_NAME, OBJECT_TYPE

C_INFO = {
    "🔍基礎資訊": {
        "/help": {
            "description": "列出可用指令的描述",
            "points": [
                "- 第一頁將列出指令列表中的分類和分類下的指令簡介",
                "- 其餘頁將列出該指令分類下的指令細節"
            ]
        },
        "/user": {
            "description": "列出操作用戶的設定",
            "points": [
                "- ⏺️ 操作用戶其餘指令展示數據所屬的伺服器 (互動指令可自訂、變動提示固定)",
                "- #️⃣ 操作用戶於不同伺服器追蹤的 UID",
                "- ⏯️ 最近設置的目標分接近提醒",
                "- ↕️ Top 10 變更提醒功能是否被開啟",
                "- ⏏️ Top 10 疑似消 CP 提醒功能是否被開啟"
            ]
        },
        "/channel": {
            "description": "列出當前頻道的設定",
            "points": [
                "- ⏺️ 當前頻道其餘指令展示數據所屬的伺服器 (互動指令可自訂、變動提示固定)"
            ]
        },
        "/server": {
            "description": "改變操作用戶或當前頻道的指定遊戲伺服器",
            "points": [
                "- 可選的有\"日服\", \"國際服\", \"繁中服\", \"簡中服\"",
                "- 預設遊戲伺服器為\"繁中服\", 預設改變對象為\"操作用戶\"",
                "- 改變對象為\"當前頻道\"時只有具有\"管理員\"權限的成員才可使用"
            ]
        }
    },
    "📊活動數據": {
        "/top": {
            "description": "列出目前前十名的總覽",
            "points": [
                "- 前十名每人各一欄，其中：",
                "  - 數字代表當前名字，📊為當前分數，📈為當前最近一小時分數變動及其排名",
                "  - 子資訊依次是`UID`，`Rank`和`留言`"
            ]
        },
        "/detail": {
            "description": "列出目前前十名中指定名次玩家的細節",
            "points": [
                "- 第一頁為指定名次玩家的分數細節",
                "- 第二頁為近期20次的分數變動細節",
                "  - ⏰為變動時間",
                "  - 📈為變動分數量",
                "- 第三頁為最近1小時、2小時、12小時、24小時的分數變動統計",
                "  - ⏰為統計時間區間",
                "  - 🔄為分數變動次數",
                "  - ⏳為平均每次分數變動需時",
                "  - 📈為平均每次分數變動量"
            ]
        },
        "/daily": {
            "description": "列出目前前十名中指定名次玩家的每日狀況",
            "points": [
                "- 每一頁為展示指定名次玩家對應日期的該日狀況，預設為最近一日",
                "- 每頁第一欄為指定名次玩家該日的總獲得分數",
                "- 每頁第二欄為指定名次玩家該日有記錄的總場次數",
                "- 每頁第三欄為指定名次玩家該日有記錄的每小時場次數",
                "- 每頁第四欄為指定名次玩家該日的總休息時間",
                "- 每頁第五欄為指定名次玩家該日有記錄的休息時段 (停止變動20分鐘以上納入統計)",
                "  - 每列資訊依次為開始時間、間隔時間量、結束時間",
                "- 每頁第六欄為指定名次玩家該日的排名變更記錄",
                "  - 每列資訊依次為變更時間、舊活動排名、新活動排名"
            ]
        }, 
        "/monthly": {
            "description": "列出目前月榜前十名的總覽",
            "points": [
                "- 前十名每人各一欄，其中：",
                "  - 數字代表當前名字，📊為當前分數",
                "  - 子資訊依次是`UID`，`Rank`和`留言`"
            ]
        }
    },
    "🔔提醒設定": {
        "/uid": {
            "description": "設定操作用戶於特定伺服器追蹤的 UID",
            "points": [
                "- 預設設定之遊戲伺服服為操作用戶指定之遊戲伺服器"
            ]
        },
        "/target": {
            "description": "設定目標分用於目標分接近提醒",
            "points": [
                "- 預設設定之遊戲伺服服為操作用戶指定之遊戲伺服器",
                "- 將以操作用戶所追蹤的 UID 於設定之遊戲伺服服 Top 10 中尋找對應"
            ]
        },
        "/change": {
            "description": "開啟或關閉 Top 10 變更提醒功能",
            "points": [
                "- 使用相同指令即可切換開關狀態", 
                "- 提示訊息發出於操作用戶指定之遊戲伺服器當前活動 Top 10 發生變更時", 
                "- 提示訊息將發出在操作用戶與本機器人之私訊中"
            ]
        },
        "/cp": {
            "description": "開啟或關閉 Top 10 疑似消 CP 提醒功能",
            "points": [
                "- 使用相同指令即可切換開關狀態", 
                "- 提示訊息發出於操作用戶指定之遊戲伺服器當前活動 Top 10 疑似消 CP 時", 
                "- 提示訊息將發出在操作用戶與本機器人之私訊中"
            ]
        }
    }
}

class CommandsDetailView(ui.View):
    def __init__(self, verbose: bool):
        super().__init__()
        self.verbose = verbose

        self.embeds = [
            embeds.Embed(
                title = "**Stare Dori** 指令列表 - 📑指令總覽",
                description = "-# 列出指令列表中的分類和分類下的指令簡介",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
        ]
        for fleid_name, commands_info in C_INFO.items():
            commands_brief = []
            new_embed = embeds.Embed(
                title = f"**Stare Dori** 指令列表 - {fleid_name}",
                color = Color.from_rgb(r = 51, g = 51, b = 255)
            )
            for command, command_detail in commands_info.items():
                commands_brief.append(f"`{command}`: {command_detail['description']}")
                new_embed.add_field(
                    name = command,
                    value = f"-# {command_detail['description']}\n" + "\n".join(command_detail["points"]),
                    inline = False
                )
            self.embeds[0].add_field(
                name = fleid_name, 
                value = "\n".join(commands_brief), 
                inline = False
            )
            self.embeds.append(new_embed)

        self.current_page = 0

    async def send(self, interaction: Interaction):
        await interaction.response.send_message(
            embed = self.embeds[self.current_page], view = self, 
            ephemeral = not self.verbose, delete_after = 300
        )
        
    async def update(self, interaction: Interaction):
        await interaction.edit_original_response(embed = self.embeds[self.current_page], view = self)

    @ui.select(placeholder = "選擇要列出指令細節的指令類別", options = [
        SelectOption(label = "指令總覽", value = 0, emoji = "📑"),
        SelectOption(label = list(C_INFO.keys())[0][1:], value = 1, emoji = list(C_INFO.keys())[0][0]),
        SelectOption(label = list(C_INFO.keys())[1][1:], value = 2, emoji = list(C_INFO.keys())[1][0]),
        SelectOption(label = list(C_INFO.keys())[2][1:], value = 3, emoji = list(C_INFO.keys())[2][0]),
    ])
    async def to_page(self, interaction: Interaction, select: ui.Select):
        await interaction.response.defer()
        self.current_page = int(select.values[0])
        await self.update(interaction)

class Basic(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database):
        self.bot = bot
        self.database = database
        self.logger: Logger = getLogger(__name__)

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"{__name__} is on ready")

    @app_commands.command(name = "help", description = list(C_INFO.values())[0]["/help"]["description"])
    @app_commands.describe(verbose = "是否公開展示給所有人")
    async def help(self, interaction: Interaction, verbose: Optional[bool] = False) -> None:
        # Generating the response to the user
        reponse_view = CommandsDetailView(verbose)
        await reponse_view.send(interaction)

    @app_commands.command(name = "user", description = list(C_INFO.values())[0]["/user"]["description"])
    @app_commands.describe(verbose = "是否公開展示給所有人")
    async def user(self, interaction: Interaction, verbose: Optional[bool] = False) -> None:
        # Check if it is appropriate to verbose on server channel
        if verbose and not isinstance(interaction.channel, (DMChannel, GroupChannel)) \
            and self.bot.get_guild(interaction.guild_id) is None:
                await interaction.response.send_message("指令結果並不能公開展示在機器人不在的伺服器", 
                                                        ephemeral = True, delete_after = 300); return
                
        # Getting user status
        user_status: User = getUser(self.database, interaction.user.id)

        # Generating the response to the user
        embed = embeds.Embed(
            title = f"用戶`{interaction.user.name}`的當前設定",
            description = "",
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        )
        embed.description += f"⏺️ 展示數據所屬的伺服器： {SERVER_NAME[user_status.server_id]}\n"
        uid_list_str: str = "\n- ".join([f"`{uid} ({SERVER_NAME[i]})`" for i, uid 
                                         in enumerate(user_status.uid) if uid != None])
        embed.description += f"#️⃣ 追蹤的 UID ： {'無' if uid_list_str == '' else uid_list_str}\n"
        target_list_str: str = "\n- ".join([f"`{target[0]} [{target[1]}] ({SERVER_NAME[i]})`" for i, target 
                                            in enumerate(user_status.recent_target_point) if target != None])
        embed.description += f"⏯️ 最近設置的目標分接近提醒： {'無' if target_list_str == '' else target_list_str}\n"
        embed.description += f"↕️ Top 10 變更提醒功能： {'✅' if user_status.is_change_nofity else '❌'}\n"
        embed.description += f"⏏️ Top 10 疑似消 CP 提醒功能： {'✅' if user_status.is_CP_nofity else '❌'}"
        await interaction.response.send_message(
            embed = embed, ephemeral = not verbose, delete_after = 300
        )

    @app_commands.command(name = "channel", description = list(C_INFO.values())[0]["/channel"]["description"])
    @app_commands.describe(verbose = "是否公開展示給所有人")
    async def channel(self, interaction: Interaction, verbose: Optional[bool] = False) -> None:
        # Check if it is appropriate to used this command
        if isinstance(interaction.channel, (DMChannel, GroupChannel)):
            await interaction.response.send_message("該指令無法在私聊頻道中使用", 
                                                    ephemeral = True, delete_after = 300); return
        if self.bot.get_guild(interaction.guild_id) is None: 
            await interaction.response.send_message("該指令無法在機器人不在的伺服器中使用", 
                                                    ephemeral = True, delete_after = 300); return
                
        # Getting channel status
        channel_status: Channel = getChannel(self.database, interaction.channel.id)

        # Generating the response to the user
        embed = embeds.Embed(
            title = f"頻道`{interaction.channel.name}`的當前設定",
            description = "",
            color = Color.from_rgb(r = 51, g = 51, b = 255)
        )
        embed.description += f"⏺️ 展示數據所屬的伺服器： {SERVER_NAME[channel_status.server_id]}"
        await interaction.response.send_message(
            embed = embed, ephemeral = not verbose, delete_after = 300
        )

    @app_commands.command(name = "server", description = list(C_INFO.values())[0]["/server"]["description"])
    @app_commands.describe(server = "改變後的指定遊戲伺服器")
    @app_commands.choices(server = [app_commands.Choice(name = server_name, value = server_id)
                                    for server_id, server_name in enumerate(SERVER_NAME)])
    @app_commands.describe(object = "改變指定遊戲伺服器設定的對象")
    @app_commands.choices(object = [app_commands.Choice(name = object_type, value = object_id)
                                    for object_id, object_type in enumerate(OBJECT_TYPE)])
    async def server(self, interaction: Interaction, server: app_commands.Choice[int], 
                     object: Optional[app_commands.Choice[int]] = None) -> None:
        # Identifing the object type to change server setting
        if object == None or object.value == 0:
            # Getting user status
            user_status: User = getUser(self.database, interaction.user.id)

            # Changing the default server
            if user_status.server_id == server.value:
                result = f"用戶`{interaction.user.name}`已經指定遊戲伺服器為 \"{server.name}\""
            else:
                self.database.insertUserSetting(interaction.user.id, server_id = server.value)
                result = f"用戶`{interaction.user.name}`指定遊戲伺服器已改為 \"{server.name}\""
        else:
            # Check if it is appropriate to used this command
            if isinstance(interaction.channel, (DMChannel, GroupChannel)):
                await interaction.response.send_message("該指令無法在私聊頻道中使用", 
                                                        ephemeral = True, delete_after = 300); return
            if self.bot.get_guild(interaction.guild_id) is None: 
                await interaction.response.send_message("該指令無法在機器人不在的伺服器中使用", 
                                                        ephemeral = True, delete_after = 300); return
            if not interaction.user.guild_permissions.administrator: 
                await interaction.response.send_message("您沒有權限使用該指令", 
                                                        ephemeral = True, delete_after = 300); return
            
            # Getting channel status
            channel_status: Channel = getChannel(self.database, interaction.channel.id)

            # Changing the default server
            if channel_status.server_id == server.value:
                result = f"頻道`{interaction.channel.name}`已經指定遊戲伺服器為 \"{server.name}\""
            else:
                self.database.insertChannelSetting(interaction.channel.id, server_id = server.value)
                result = f"頻道`{interaction.channel.name}`指定遊戲伺服器已改為 \"{server.name}\""
        
        # Generating the response to the user
        embed = embeds.Embed(title = result, color = Color.from_rgb(r = 51, g = 51, b = 255))
        await interaction.response.send_message(embed = embed, ephemeral = True, delete_after = 300)