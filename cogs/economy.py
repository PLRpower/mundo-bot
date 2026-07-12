import discord
from discord.ext import commands
from discord import app_commands
from database.engine import AsyncSessionLocal
from database.models import UserEconomy, Bet, ActiveGame, LinkedAccount
from sqlalchemy import select

async def process_bet(interaction: discord.Interaction, target_discord_id: int, prediction: str, montant: int):
    if interaction.user.id == target_discord_id:
        await interaction.response.send_message("❌ Tu ne peux pas parier sur toi-même.", ephemeral=True)
        return

    if montant <= 0:
        await interaction.response.send_message("❌ Le montant doit être supérieur à 0.", ephemeral=True)
        return
        
    async with AsyncSessionLocal() as session:
        stmt_link = select(LinkedAccount).where(LinkedAccount.discord_id == target_discord_id)
        link = (await session.execute(stmt_link)).scalar_one_or_none()
        if not link or not link.riot_puuid:
            await interaction.response.send_message(f"❌ Ce joueur n'a pas lié de compte Riot.", ephemeral=True)
            return
            
        stmt_game = select(ActiveGame).where(ActiveGame.discord_id == target_discord_id)
        active_game = (await session.execute(stmt_game)).scalars().first()
        
        if not active_game:
            await interaction.response.send_message(f"❌ Ce joueur n'est pas actuellement dans une partie.", ephemeral=True)
            return
            
        stmt_existing_bet = select(Bet).where(
            Bet.game_id == active_game.game_id,
            Bet.bettor_id == interaction.user.id
        )
        if (await session.execute(stmt_existing_bet)).scalar_one_or_none():
            await interaction.response.send_message("❌ Tu as déjà parié sur cette partie.", ephemeral=True)
            return
            
        stmt_eco = select(UserEconomy).where(
            UserEconomy.discord_id == interaction.user.id,
            UserEconomy.guild_id == interaction.guild_id
        )
        eco = (await session.execute(stmt_eco)).scalar_one_or_none()
        
        if not eco:
            eco = UserEconomy(discord_id=interaction.user.id, guild_id=interaction.guild_id, points=100)
            session.add(eco)
            
        if eco.points < montant:
            await interaction.response.send_message(f"❌ Tu n'as pas assez de points. (Solde: {eco.points})", ephemeral=True)
            return
            
        eco.points -= montant
        new_bet = Bet(
            game_id=active_game.game_id,
            bettor_id=interaction.user.id,
            guild_id=interaction.guild_id,
            amount=montant,
            prediction=prediction
        )
        session.add(new_bet)
        await session.commit()
        
        pred_text = "la victoire" if prediction == "win" else "la défaite"
        await interaction.response.send_message(f"🎲 Pari enregistré ! Tu as parié **{montant} points** sur {pred_text} de <@{target_discord_id}>.")

class BetModal(discord.ui.Modal, title='Parier des points'):
    amount = discord.ui.TextInput(
        label='Combien de points veux-tu miser ?',
        style=discord.TextStyle.short,
        placeholder='Exemple: 100',
        required=True
    )

    def __init__(self, target_discord_id: int, prediction: str):
        super().__init__()
        self.target_discord_id = target_discord_id
        self.prediction = prediction

    async def on_submit(self, interaction: discord.Interaction):
        try:
            montant = int(self.amount.value)
        except ValueError:
            await interaction.response.send_message("❌ Montant invalide.", ephemeral=True)
            return
        await process_bet(interaction, self.target_discord_id, self.prediction, montant)

class BetView(discord.ui.View):
    def __init__(self, target_discord_id: int):
        super().__init__(timeout=None)
        self.target_discord_id = target_discord_id

    async def check_timeout(self, interaction: discord.Interaction) -> bool:
        if interaction.message:
            time_elapsed = discord.utils.utcnow() - interaction.message.created_at
            if time_elapsed.total_seconds() > 300:
                await interaction.response.send_message("❌ Les paris sont fermés pour cette partie (5 minutes écoulées).", ephemeral=True)
                return False
        return True

    @discord.ui.button(label="Victoire", style=discord.ButtonStyle.success, emoji="🏆")
    async def btn_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.check_timeout(interaction):
            await interaction.response.send_modal(BetModal(self.target_discord_id, "win"))

    @discord.ui.button(label="Défaite", style=discord.ButtonStyle.danger, emoji="💀")
    async def btn_lose(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self.check_timeout(interaction):
            await interaction.response.send_modal(BetModal(self.target_discord_id, "lose"))

class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Affiche ton solde de points")
    async def balance(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            stmt = select(UserEconomy).where(
                UserEconomy.discord_id == interaction.user.id,
                UserEconomy.guild_id == interaction.guild_id
            )
            eco = (await session.execute(stmt)).scalar_one_or_none()
            
            points = eco.points if eco else 100
            
            await interaction.response.send_message(f"💰 Tu as actuellement **{points} points**.")


    @app_commands.command(name="leaderboard", description="Affiche le classement de l'économie du serveur")
    async def leaderboard(self, interaction: discord.Interaction):
        async with AsyncSessionLocal() as session:
            stmt = select(UserEconomy).where(UserEconomy.guild_id == interaction.guild_id).order_by(UserEconomy.points.desc()).limit(10)
            top_users = (await session.execute(stmt)).scalars().all()
            
            if not top_users:
                await interaction.response.send_message("❌ Aucun joueur n'est classé pour le moment.")
                return
                
            embed = discord.Embed(title="🏆 Classement Économie", color=0x16161a)
            desc = ""
            for idx, u in enumerate(top_users, 1):
                desc += f"**{idx}.** <@{u.discord_id}> - {u.points} points\n"
                
            embed.description = desc
            await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
