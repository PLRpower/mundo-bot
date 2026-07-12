import discord
from discord.ext import commands
from discord import app_commands
from database.engine import AsyncSessionLocal
from database.models import LinkedAccount, RiotMatch, PlayerMatch, ServerConfig
from sqlalchemy import select
from connectors.riot import RiotConnector
from utils.ui import generate_match_select_options


class MatchSelect(discord.ui.Select):
    def __init__(self, matches, target_puuid, target_display_name, lang, cog):
        self.matches = matches
        self.target_puuid = target_puuid
        self.target_display_name = target_display_name
        self.lang = lang
        self.cog = cog
        
        options = generate_match_select_options(matches, target_puuid)
            
        super().__init__(placeholder="Sélectionnez une partie à analyser...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        
        selected_match_id = self.values[0]
        selected_match = next((m for m in self.matches if str(m.get("info", {}).get("gameId")) == selected_match_id), None)
        
        if not selected_match:
            await interaction.followup.send("❌ Erreur: Partie introuvable.")
            return
            
        from utils.image_generator import MatchImageGenerator
        import os
        
        generator = MatchImageGenerator()
        image_path = await generator.generate_match_scoreboard(selected_match, self.target_display_name, target_puuid=self.target_puuid, lang=self.lang)
        
        try:
            file = discord.File(image_path, filename="match.png")
            game_mode = selected_match.get("info", {}).get("gameMode", "Inconnu")
            embed = discord.Embed(
                title=f"Détails de la partie de {self.target_display_name} - {game_mode}",
                color=0x16161a
            )
            embed.set_footer(text="Ce bot n'est pas affilié avec Riot Games.")
            embed.set_image(url="attachment://match.png")
            await interaction.followup.send(embed=embed, file=file)
        finally:
            if os.path.exists(image_path):
                os.remove(image_path)

class MatchSelectView(discord.ui.View):
    def __init__(self, matches, target_puuid, target_display_name, lang, cog):
        super().__init__(timeout=300)
        self.add_item(MatchSelect(matches, target_puuid, target_display_name, lang, cog))

class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.riot = RiotConnector()

    async def _get_matches_from_db_or_api(self, puuid: str, count: int) -> list[dict]:
        async with AsyncSessionLocal() as session:
            # 1. On interroge l'API pour s'assurer d'avoir les dernières parties à jour
            try:
                live_matches = await self.riot.get_last_matches(puuid, count=count)
                for match in live_matches:
                    match_id = match.get("metadata", {}).get("matchId")
                    if not match_id: continue
                    
                    stmt_link = select(PlayerMatch).where(PlayerMatch.puuid == puuid, PlayerMatch.match_id == match_id)
                    if not (await session.execute(stmt_link)).scalar_one_or_none():
                        session.add(PlayerMatch(puuid=puuid, match_id=match_id))
                        
                    stmt_match = select(RiotMatch).where(RiotMatch.match_id == match_id)
                    if not (await session.execute(stmt_match)).scalar_one_or_none():
                        timeline = await self.riot.get_match_timeline(match_id)
                        match["timeline_data"] = timeline
                        game_creation = match.get("info", {}).get("gameCreation", 0)
                        session.add(RiotMatch(match_id=match_id, data=match, game_creation=game_creation))
                await session.commit()
            except Exception as e:
                pass # Si l'API échoue, on se rabat sur la BDD locale silencieusement
                
            # 2. On récupère les parties depuis la BDD locale (garantie d'être à jour)
            stmt = (
                select(RiotMatch.data)
                .join(PlayerMatch, PlayerMatch.match_id == RiotMatch.match_id)
                .where(PlayerMatch.puuid == puuid)
                .order_by(RiotMatch.game_creation.desc())
                .limit(count)
            )
            result = await session.execute(stmt)
            return [row[0] for row in result.all()]

    @app_commands.command(name="last_games", description="Affiche les dernières parties LoL d'un joueur")
    @app_commands.describe(utilisateur="Le membre du serveur (vous par défaut)")
    async def last_games(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        
        await interaction.response.defer()
        
        async with AsyncSessionLocal() as session:
            stmt = select(LinkedAccount).where(LinkedAccount.discord_id == target.id)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            
            stmt_lang = select(ServerConfig).where(ServerConfig.guild_id == interaction.guild_id)
            config = (await session.execute(stmt_lang)).scalar_one_or_none()
            lang = config.language if config else "fr"
            
        if not account or not account.riot_puuid:
            await interaction.followup.send(f"❌ {target.display_name} n'a pas encore lié de compte Riot Games (utilisez `/link`).")
            return
            
        # Récupérer les 5 derniers matchs depuis la DB ou l'API
        matches = await self._get_matches_from_db_or_api(account.riot_puuid, count=5)
        
        if not matches:
            await interaction.followup.send("❌ Impossible de récupérer l'historique (rate limit, ou aucune partie trouvée).")
            return
            
        # Generation de l'image
        from utils.image_generator import MatchImageGenerator
        import os
        
        generator = MatchImageGenerator()
        image_path = await generator.generate_last_games_history(matches, target.display_name, account.riot_puuid, lang=lang)
        
        try:
            file = discord.File(image_path, filename="last_games.png")
            embed = discord.Embed(
                title=f"Dernières parties de {target.display_name}",
                color=0x16161a
            )
            embed.set_footer(text="Ce bot n'est pas affilié avec Riot Games.")
            embed.set_image(url="attachment://last_games.png")
            await interaction.followup.send(embed=embed, file=file)
        finally:
            if os.path.exists(image_path):
                os.remove(image_path)


    @app_commands.command(name="match", description="Sélectionnez et affichez les statistiques d'une partie")
    @app_commands.describe(utilisateur="Le membre du serveur (vous par défaut)")
    async def match_command(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        
        await interaction.response.defer(ephemeral=True)
        
        async with AsyncSessionLocal() as session:
            stmt = select(LinkedAccount).where(LinkedAccount.discord_id == target.id)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            
            stmt_lang = select(ServerConfig).where(ServerConfig.guild_id == interaction.guild_id)
            config = (await session.execute(stmt_lang)).scalar_one_or_none()
            lang = config.language if config else "fr"
            
        if not account or not account.riot_puuid:
            await interaction.followup.send(f"❌ {target.display_name} n'a pas encore lié de compte Riot Games (utilisez `/link`).")
            return
            
        # Récupérer les 15 derniers matchs
        matches = await self._get_matches_from_db_or_api(account.riot_puuid, count=15)
        
        if not matches:
            await interaction.followup.send("❌ Impossible de récupérer l'historique (rate limit, ou aucune partie trouvée).")
            return
            
        view = MatchSelectView(matches, account.riot_puuid, target.display_name, lang, self)
        
        embed = discord.Embed(
            title=f"Dernières parties de {target.display_name}",
            description="Veuillez sélectionner la partie que vous souhaitez consulter dans le menu ci-dessous.",
            color=0x16161a
        )
        embed.set_footer(text="Ce bot n'est pas affilié avec Riot Games.")
        
        await interaction.followup.send(embed=embed, view=view)

    # @app_commands.command(name="steam_recent", description="Affiche les jeux récemment joués sur Steam")
    # @app_commands.describe(utilisateur="Le membre du serveur (vous par défaut)")
    async def steam_recent(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        
        await interaction.response.defer()
        
        async with AsyncSessionLocal() as session:
            stmt = select(LinkedAccount).where(LinkedAccount.discord_id == target.id)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            
        if not account or not account.steam_id64:
            await interaction.followup.send(f"❌ {target.display_name} n'a pas encore lié de compte Steam (utilisez `/link`).")
            return
            
        from connectors.steam import SteamConnector
        steam = SteamConnector()
        games = await steam.get_recently_played_games(account.steam_id64, count=5)
        
        if not games:
            await interaction.followup.send("❌ Aucun jeu récent trouvé (ou profil privé).")
            return
            
        embed = discord.Embed(
            title=f"Jeux récemment joués par {target.display_name}",
            color=0x16161a
        )
        
        for game in games:
            name = game.get("name", "Jeu inconnu")
            playtime_2weeks = game.get("playtime_2weeks", 0) / 60  # en heures
            playtime_forever = game.get("playtime_forever", 0) / 60
            
            embed.add_field(
                name=name,
                value=f"⏳ Dernières 2 semaines: **{playtime_2weeks:.1f}h**\n🕒 Temps total: **{playtime_forever:.1f}h**",
                inline=False
            )
            
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
