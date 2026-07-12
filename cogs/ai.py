import discord
from discord.ext import commands
from discord import app_commands
from google import genai
from config import GEMINI_KEY
from database.engine import AsyncSessionLocal
from database.models import LinkedAccount, RiotMatch, PlayerMatch
from sqlalchemy import select
from connectors.riot import RiotConnector
from utils.ui import generate_match_select_options


class ResumeGameSelect(discord.ui.Select):
    def __init__(self, matches, account, target, style, cog):
        self.matches = matches
        self.account = account
        self.target = target
        self.style = style
        self.cog = cog
        
        options = generate_match_select_options(matches, account.riot_puuid)
            
        super().__init__(placeholder="Sélectionnez une partie à résumer...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        
        selected_match_id = self.values[0]
        match = next((m for m in self.matches if str(m.get("info", {}).get("gameId")) == selected_match_id), None)
        
        if not match:
            await interaction.followup.send("❌ Erreur: Partie introuvable.")
            return

        await self.cog.generate_resume(interaction, match, self.account, self.target, self.style)

class ResumeGameSelectView(discord.ui.View):
    def __init__(self, matches, account, target, style, cog):
        super().__init__(timeout=300)
        self.add_item(ResumeGameSelect(matches, account, target, style, cog))

class AI(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.riot = RiotConnector()
        self.gemini_client = None
        if GEMINI_KEY:
            self.gemini_client = genai.Client(api_key=GEMINI_KEY)

    async def _get_matches_from_db_or_api(self, puuid: str, count: int) -> list[dict]:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(RiotMatch.data)
                .join(PlayerMatch, PlayerMatch.match_id == RiotMatch.match_id)
                .where(PlayerMatch.puuid == puuid)
                .order_by(RiotMatch.game_creation.desc())
                .limit(count)
            )
            result = await session.execute(stmt)
            matches = [row[0] for row in result.all()]
            
            if matches:
                return matches
                
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
            return live_matches

    @app_commands.command(name="analyse", description="L'IA résume une partie avec le style de ton choix")
    @app_commands.describe(
        style="Le style de résumé à adopter",
        utilisateur="Le joueur concerné (vous par défaut)"
    )
    @app_commands.choices(style=[
        app_commands.Choice(name="Sarcastique", value="sarcastique"),
        app_commands.Choice(name="Éloge", value="eloge"),
        app_commands.Choice(name="Conseils", value="conseils"),
        app_commands.Choice(name="E-fille", value="e-fille"),
    ])
    async def analyse(self, interaction: discord.Interaction, style: app_commands.Choice[str], utilisateur: discord.Member = None):
        if not GEMINI_KEY:
            await interaction.response.send_message("❌ La clé GEMINI_KEY n'est pas configurée.", ephemeral=True)
            return

        target = utilisateur or interaction.user
        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            stmt = select(LinkedAccount).where(LinkedAccount.discord_id == target.id)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            
        if not account or not account.riot_puuid:
            await interaction.followup.send(f"❌ {target.display_name} n'a pas encore lié de compte Riot Games (utilisez `/link`).")
            return

        matches = await self._get_matches_from_db_or_api(account.riot_puuid, count=15)
        if not matches:
            await interaction.followup.send("❌ Impossible de récupérer l'historique des parties.")
            return

        view = ResumeGameSelectView(matches, account, target, style, self)
        
        embed = discord.Embed(
            title=f"Parties de {target.display_name}",
            description="Veuillez sélectionner la partie que vous souhaitez résumer dans le menu ci-dessous.",
            color=0x16161a
        )
        embed.set_footer(text="Ce bot n'est pas affilié avec Riot Games.")
        
        await interaction.followup.send(embed=embed, view=view)

    async def generate_resume(self, interaction: discord.Interaction, match: dict, account: LinkedAccount, target: discord.Member, style: app_commands.Choice[str]):
        match_id = match.get("metadata", {}).get("matchId")
        info = match.get("info", {})
        
        timeline = match.get("timeline_data")
        if not timeline and match_id:
            timeline = await self.riot.get_match_timeline(match_id)
        elif not timeline:
            timeline = {}
        
        # Trouver le joueur
        player_data = next((p for p in info.get("participants", []) if p.get("puuid") == account.riot_puuid), None)
        if not player_data:
            await interaction.followup.send("❌ Impossible de trouver les données du joueur dans la partie.")
            return

        participant_id = player_data.get("participantId")
        champion = player_data.get("championName")
        win = player_data.get("win", False)
        kills = player_data.get("kills")
        deaths = player_data.get("deaths")
        assists = player_data.get("assists")
        dmg = player_data.get("totalDamageDealtToChampions")
        gold = player_data.get("goldEarned")
        queue_id = info.get("queueId")
        queue_map = {400: "Draft", 420: "Classée Solo/Duo", 430: "Blind", 440: "Classée Flex", 450: "ARAM", 490: "Quickplay", 1700: "Arena"}
        game_mode = queue_map.get(queue_id, info.get("gameMode", "Partie"))
        duration = info.get("gameDuration", 0)
        if duration < 60: duration *= 1000
        duration_min = int(duration / 60)

        position = player_data.get("teamPosition", "Inconnue")
        team_id = player_data.get("teamId")
        
        team_kills = 0
        enemy_kills = 0
        
        teammates = []
        enemy_laner = "Inconnu"
        enemy_laner_id = None
        for p in info.get("participants", []):
            if p.get("teamId") == team_id:
                team_kills += p.get("kills", 0)
                if p.get("puuid") != account.riot_puuid:
                    teammates.append(p)
            else:
                enemy_kills += p.get("kills", 0)
                if p.get("teamPosition") == position and position not in ["", "Invalid", "Inconnue"]:
                    enemy_laner = p.get("championName", "Inconnu")
                    enemy_laner_id = p.get("participantId")
                    
        best_teammate = max(teammates, key=lambda x: x.get("kills", 0) + x.get("assists", 0)) if teammates else None
        worst_teammate = max(teammates, key=lambda x: x.get("deaths", 0)) if teammates else None
        
        best_teammate_str = f"{best_teammate.get('championName')} ({best_teammate.get('kills')}/{best_teammate.get('deaths')}/{best_teammate.get('assists')})" if best_teammate else "Aucun"
        worst_teammate_str = f"{worst_teammate.get('championName')} ({worst_teammate.get('kills')}/{worst_teammate.get('deaths')}/{worst_teammate.get('assists')})" if worst_teammate else "Aucun"

        # Team objectives
        team_dragons = team_barons = enemy_dragons = enemy_barons = 0
        for team in info.get("teams", []):
            if team.get("teamId") == team_id:
                team_dragons = team.get("objectives", {}).get("dragon", {}).get("kills", 0)
                team_barons = team.get("objectives", {}).get("baron", {}).get("kills", 0)
            else:
                enemy_dragons = team.get("objectives", {}).get("dragon", {}).get("kills", 0)
                enemy_barons = team.get("objectives", {}).get("baron", {}).get("kills", 0)

        # Multi-kills & First blood
        fb_kill = player_data.get("firstBloodKill", False)
        fb_text = "A pris le First Blood" if fb_kill else "Non"
        
        mk = []
        if player_data.get("pentaKills"): mk.append(f"{player_data.get('pentaKills')} Pentakill(s)")
        if player_data.get("quadraKills"): mk.append(f"{player_data.get('quadraKills')} Quadrakill(s)")
        if player_data.get("tripleKills"): mk.append(f"{player_data.get('tripleKills')} Triplé(s)")
        if player_data.get("doubleKills"): mk.append(f"{player_data.get('doubleKills')} Doublé(s)")
        multi_kills = ", ".join(mk) if mk else "Aucun"

        # Extraire quelques événements de la timeline et Gold Diff @ 15m
        events_summary = []
        gold_diff_15 = "Inconnue"
        
        if timeline and "info" in timeline:
            frames = timeline["info"].get("frames", [])
            first_blood_found = False
            for frame in frames:
                minute = int(frame.get("timestamp", 0) / 60000)
                
                # Gold Diff à 15 min
                if minute == 15 and enemy_laner_id:
                    p_frames = frame.get("participantFrames", {})
                    my_gold = p_frames.get(str(participant_id), {}).get("totalGold", 0)
                    enemy_gold = p_frames.get(str(enemy_laner_id), {}).get("totalGold", 0)
                    diff = my_gold - enemy_gold
                    gold_diff_15 = f"{'+' if diff > 0 else ''}{diff} gold"
                    
                for event in frame.get("events", []):
                    # Trouver qui a donné le first blood
                    if event.get("type") == "CHAMPION_KILL" and not first_blood_found:
                        first_blood_found = True
                        if event.get("victimId") == participant_id:
                            fb_text = "A donné le First Blood (première mort de la partie)"
                            
                    if event.get("type") == "CHAMPION_KILL":
                        if event.get("killerId") == participant_id:
                            events_summary.append(f"Minute {minute}: A tué un adversaire.")
                        elif event.get("victimId") == participant_id:
                            events_summary.append(f"Minute {minute}: Est mort.")
                    elif event.get("type") == "BUILDING_KILL" and event.get("killerId") == participant_id:
                        events_summary.append(f"Minute {minute}: A détruit une tour.")
                    elif event.get("type") == "ELITE_MONSTER_KILL" and event.get("killerId") == participant_id:
                        events_summary.append(f"Minute {minute}: A sécurisé un monstre épique ({event.get('monsterType')}).")

        # Limiter à 20 événements pour ne pas surcharger le prompt
        if len(events_summary) > 20:
            events_summary = events_summary[:10] + ["..."] + events_summary[-10:]

        events_text = "\n".join(events_summary) if events_summary else "Aucun événement marquant trouvé."

        prompt = f"""
Tu es un bot Discord spécialisé dans League of Legends.
Résume la dernière partie de '{target.display_name}'.
Voici les statistiques du joueur :
- Champion : {champion}
- Poste joué : {position}
- Adversaire direct sur la lane : {enemy_laner}
- Résultat : {'Victoire' if win else 'Défaite'}
- KDA : {kills}/{deaths}/{assists}
- Actions d'éclat (Multi-kills) : {multi_kills}
- Premier sang (First Blood) : {fb_text}
- Dégâts aux champions : {dmg}
- Différence d'or avec {enemy_laner} à 15 minutes : {gold_diff_15}
- Durée : {duration_min} minutes
- Mode : {game_mode}

Voici le contexte de l'équipe :
- Kills de l'équipe : {team_kills} contre {enemy_kills} pour l'équipe ennemie.
- Objectifs Équipe : {team_dragons} Dragons, {team_barons} Barons
- Objectifs Ennemis : {enemy_dragons} Dragons, {enemy_barons} Barons
- Le meilleur allié (selon K+A) : {best_teammate_str}
- Le pire allié (celui qui a le plus donné) : {worst_teammate_str}

Voici un aperçu chronologique de ses actions dans la partie :
{events_text}

Tu dois résumer cette partie en utilisant STRICTEMENT ce style : {style.value}
- Si sarcastique : Sois très moqueur, cynique, fais de l'humour piquant sur le joueur. Raconte une vraie histoire détaillée et brode un scénario exagéré autour de ses actions et de ses morts absurdes. NE critique PAS ses alliés : au contraire, complimente-les lourdement pour mieux rabaisser le joueur en comparaison (ex: "Heureusement que tel allié a fait tout le travail...").
- Si eloge : Sois épique, héroïque, parle de lui comme d'une légende absolue. Brode une aventure glorieuse digne du Seigneur des Anneaux en utilisant les événements de la timeline.
- Si conseils : Agis comme un coach bienveillant, donne des astuces pour s'améliorer en se basant sur ses stats, son matchup, etc.
- Si e-fille : Traîte l'utilisateur comme une princesse, fais lui des éloges d'e-girl, très cute, rappelle-lui à quel point c'est la queen de ce monde. Sois très attentioné, chaleureux avec une ambiance mignonne de princesse magique.

Parle le plus possible de l'utilisateur sans parler (ou parle-en moins) des alliés.
Ta réponse doit être sans introduction générique, et formatée pour Discord. Utilise des emojis pour rendre le texte vivant et amusant (et n'hésite pas à utiliser du gras ou de l'italique pour le rythme). Écris un texte de longueur moyenne (environ 1200 caractères).
"""
    
        try:
            response = await self.gemini_client.aio.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt
            )
            
            embed = discord.Embed(
                title=f"Résumé de partie ({style.name})",
                description=response.text,
                color=0x16161a
            )
            embed.set_footer(text=f"Partie de {target.display_name}   |   Ce bot n'est pas affilié avec Riot Games.")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send("❌ Une erreur est survenue lors de la génération avec l'IA.")

async def setup(bot: commands.Bot):
    await bot.add_cog(AI(bot))
