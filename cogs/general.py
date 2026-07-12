import discord
from discord.ext import commands
from discord import app_commands
from database.engine import AsyncSessionLocal
from database.models import ServerConfig
from sqlalchemy import select

class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @app_commands.command(name="set_language", description="Configure la langue du bot pour ce serveur.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(langue=[
        app_commands.Choice(name="Français", value="fr"),
        app_commands.Choice(name="English", value="en")
    ])
    async def set_language(self, interaction: discord.Interaction, langue: app_commands.Choice[str]):
        async with AsyncSessionLocal() as session:
            stmt = select(ServerConfig).where(ServerConfig.guild_id == interaction.guild_id)
            result = await session.execute(stmt)
            config = result.scalar_one_or_none()
            
            if not config:
                config = ServerConfig(guild_id=interaction.guild_id, language=langue.value)
                session.add(config)
            else:
                config.language = langue.value
                
            await session.commit()
            
        await interaction.response.send_message(f"✅ Langue du serveur configurée sur : {langue.name}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
