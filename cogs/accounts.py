import discord
from discord.ext import commands
from discord import app_commands
from database.engine import AsyncSessionLocal
from database.models import LinkedAccount
from sqlalchemy import select

class Accounts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="link", description="Lier un compte Riot Games à votre profil Discord")
    @app_commands.describe(
        account_id="Riot ID 'Pseudo#Tag'"
    )
    async def link(self, interaction: discord.Interaction, account_id: str):
        discord_id = interaction.user.id
        
        if "#" not in account_id:
            await interaction.response.send_message("❌ Format invalide. Veuillez inclure le tag (ex: Pseudo#Tag).", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        game_name, tag_line = account_id.split("#", 1)
        
        from connectors.riot import RiotConnector
        riot = RiotConnector()
        puuid = await riot.get_puuid(game_name, tag_line)
        
        if not puuid:
            await interaction.followup.send(f"❌ Impossible de trouver le compte Riot `{account_id}`.")
            return

        async with AsyncSessionLocal() as session:
            stmt = select(LinkedAccount).where(LinkedAccount.discord_id == discord_id)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                account = LinkedAccount(discord_id=discord_id)
                session.add(account)
                
            account.riot_puuid = puuid
            await session.commit()
            
        await interaction.followup.send(f"✅ Compte Riot `{account_id}` validé et lié avec succès ! (PUUID: `{puuid[:8]}...`)")
async def setup(bot: commands.Bot):
    await bot.add_cog(Accounts(bot))
