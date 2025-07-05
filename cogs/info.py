from discord import Interaction, app_commands, ui
from discord import embeds, Color, SelectOption
from discord.ext import commands

from typing import Optional

C_INFO = {
    "🔍基礎資訊": {
        "/help": {
            "description": "列出可用指令的描述",
            "points": [
                "- 第一頁將列出指令列表中的分類和分類下的指令簡介",
                "- 其餘頁將列出該指令分類下的指令細節"
            ]
        },
        "/setting": {
            "description": "列出當前頻道的設定",
            "points": [
                "- #️⃣ 當前頻道其餘指令展示數據所屬的伺服器 (切換功能暫未開發，目前只有繁中服)",
                "- ↕️ Top 10 變更提醒功能是否被開啟",
                "- ⏏️ Top 10 疑似消 CP 提醒功能是否被開啟"
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
            "description": "列出目前前十名中指定名次的玩家細節",
            "points": [
                "- 第一頁為指定名次玩家的分數細節",
                "- 第二頁為近期20次的分數變動細節",
                "  - ⏰為變動時間",
                "  - 📈為變動分數量",
                "- 第三頁為最近1小時、2小時、12小時、24小時的分數變動統計",
                "  - ⏰為統計時間區間",
                "  - 🔄為分數變動次數",
                "  - ⏳為平均每次分數變動需時",
                "  - 📈為平均每次分數變動量",
                "- 第四頁為指定名次玩家的活動內有記錄的休息時段 (停止變動7分鐘以上納入統計)",
                "  - 📅為休息時段開始時間所在的日期，以此分欄",
                "  - 每欄中每列資訊依次為開始時間、間隔時間量、結束時間"
            ]
        }
    },
    "🔔變動警報": {
        "/change": {
            "description": "開啟或關閉 Top 10 變更提醒功能",
            "points": [
                "- 使用相同指令即可切換開關狀態"
            ]
        },
        "/cp": {
            "description": "開啟或關閉 Top 10 疑似消 CP 提醒功能",
            "points": [
                "- 使用相同指令即可切換開關狀態"
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
        SelectOption(label = "基礎資訊", value = 1, emoji = "🔍"),
        SelectOption(label = "活動數據", value = 2, emoji = "📊"),
        SelectOption(label = "變動警報", value = 3, emoji = "🔔"),
    ])
    async def to_page(self, interaction: Interaction, select: ui.Select):
        await interaction.response.defer()
        self.current_page = int(select.values[0])
        await self.update(interaction)

class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{__name__} is on ready!")

    @app_commands.command(name = "help", description = "列出可用指令的描述")
    @app_commands.describe(verbose = "是否公開展示給所有人")
    @commands.guild_only()
    async def help(self, interaction: Interaction, verbose: Optional[bool] = False):
        # Generating the response to the user
        reponse_view = CommandsDetailView(verbose)
        await reponse_view.send(interaction)