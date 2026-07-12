import discord
from discord.ext import commands, tasks
from database.engine import AsyncSessionLocal
from database.models import LinkedAccount, RiotMatch, PlayerMatch, ActiveGame, Bet, UserEconomy, ServerConfig
from sqlalchemy import select
from connectors.riot import RiotConnector
import logging
import time
import asyncio

logger = logging.getLogger('mundo-bot.crawler')

class Crawler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.riot = RiotConnector()
        self.app_emojis_cache = {}
        self.riot_crawler.start()

    async def get_emoji(self, safe_name: str) -> str:
        if not self.app_emojis_cache:
            try:
                emojis = await self.bot.fetch_application_emojis()
                self.app_emojis_cache = {e.name.lower(): f"<:{e.name}:{e.id}>" for e in emojis}
            except:
                pass
        return self.app_emojis_cache.get(safe_name.lower(), "")

    def cog_unload(self):
        self.riot_crawler.cancel()

    @tasks.loop(minutes=2.0, seconds=10.0)
    async def riot_crawler(self):
        logger.info("Début du crawl des données Riot...")
        async with AsyncSessionLocal() as session:
            stmt = select(LinkedAccount).where(LinkedAccount.riot_puuid.isnot(None))
            result = await session.execute(stmt)
            linked_accounts = result.scalars().all()

            if not linked_accounts:
                logger.info("Aucun compte Riot lié trouvé pour le crawl.")
                return

            active_games_data = {}

            # 1. Check Active Games pour tous les comptes liés
            for acc in linked_accounts:
                puuid = acc.riot_puuid
                try:
                    active = await self.riot.get_active_game(puuid)
                    if active:
                        game_id = f"{active['platformId']}_{active['gameId']}"
                        
                        if game_id not in active_games_data:
                            active_games_data[game_id] = {
                                'raw': active,
                                'tracked_players': []
                            }
                        
                        champion_id = 0
                        for participant in active.get("participants", []):
                            if participant.get("puuid") == puuid:
                                champion_id = participant.get("championId")
                                break
                                
                        active_games_data[game_id]['tracked_players'].append({
                            'puuid': puuid,
                            'discord_id': acc.discord_id,
                            'champion_id': champion_id
                        })
                except Exception as e:
                    logger.error(f"Erreur active game pour {puuid}: {e}")

            # 1.1 Annoncer les nouvelles parties et sauvegarder
            for game_id, data in active_games_data.items():
                active = data['raw']
                players = data['tracked_players']

                try:
                    stmt_active = select(ActiveGame).where(ActiveGame.game_id == game_id)
                    already_tracked = (await session.execute(stmt_active)).scalars().all()
                    
                    if not already_tracked:
                        # Nouvelle partie, on ajoute tous les joueurs trackés
                        for p in players:
                            new_active = ActiveGame(
                                game_id=game_id,
                                puuid=p['puuid'],
                                discord_id=p['discord_id'],
                                champion_id=p['champion_id']
                            )
                            session.add(new_active)
                        
                        stmt_configs = select(ServerConfig).where(ServerConfig.announcement_channel_id.isnot(None))
                        configs = (await session.execute(stmt_configs)).scalars().all()
                        
                        for conf in configs:
                            guild = self.bot.get_guild(conf.guild_id)
                            if guild:
                                channel = guild.get_channel(conf.announcement_channel_id) or guild.get_thread(conf.announcement_channel_id)
                                if channel:
                                    try:
                                        queue_id = active.get('gameQueueConfigId')
                                        queue_map = {
                                            400: "Normal Draft",
                                            420: "Classée Solo/Duo",
                                            430: "Normal Blind",
                                            440: "Classée Flex",
                                            450: "ARAM",
                                            490: "Quickplay",
                                            1700: "Arena",
                                            2400: "Arena"
                                        }
                                        queue_name = queue_map.get(queue_id, f"Mode inconnu ({queue_id})")
                                        from utils.ddragon import ddragon
                                        await ddragon.init()
                                        
                                        allowed_queues_for_bet = [400, 420, 430, 440, 490]
                                        is_bet_allowed = queue_id in allowed_queues_for_bet
                                        
                                        mentions = [f"<@{p['discord_id']}>" for p in players]
                                        if len(mentions) == 1:
                                            desc = f"{mentions[0]} a lancé en **{queue_name}**."
                                        elif len(mentions) == 2:
                                            desc = f"{mentions[0]} et {mentions[1]} ont lancé en **{queue_name}**."
                                        else:
                                            desc = ", ".join(mentions[:-1]) + f" et {mentions[-1]} ont lancé en **{queue_name}**."
                                        
                                        if is_bet_allowed:
                                            closing_time = int(time.time() + 300)
                                            desc += f"\n\nFaites vos jeux en utilisant les boutons ci-dessous. (Fermeture des paris dans <t:{closing_time}:R>)"

                                        embed = discord.Embed(
                                            title="Nouvelle partie lancée !",
                                            description=desc,
                                            color=0x16161a
                                        )
                                        
                                        champ_name_1 = ddragon.get_champion_name(players[0]['champion_id'])
                                        embed.set_thumbnail(url=ddragon.get_champion_url(champ_name_1))
                                        
                                        roles = ["Top", "Jungle", "Mid", "ADC", "Support"]
                                        
                                        async def get_participant_info(idx, p):
                                            c_id = p.get("championId")
                                            c_name = ddragon.get_champion_name(c_id)
                                            safe_c_name = c_name.replace(" ", "").replace("'", "").replace(".", "")
                                            champ_emoji = await self.get_emoji(safe_c_name)
                                            p_puuid = p.get("puuid")
                                            p_sum_id = p.get("summonerId")
                                            
                                            if p_sum_id:
                                                p_rank = await self.riot.get_summoner_rank_by_id(p_sum_id)
                                            else:
                                                p_rank = await self.riot.get_summoner_rank(p_puuid) if p_puuid else "Unranked"
                                            
                                            p_discord_id = next((tp['discord_id'] for tp in players if tp['puuid'] == p_puuid), None)
                                            name_str = f"<@{p_discord_id}>" if p_discord_id else (p.get("riotId") or p.get("riotIdGameName") or p.get("summonerName") or "Inconnu")
                                            
                                            role_str = ""
                                            if queue_id in [400, 420, 430, 440, 490] and idx < 5:
                                                role_str = f"[{roles[idx]}] "
                                                
                                            return f"{role_str}{champ_emoji} **{c_name}** - {name_str} ({p_rank})"
                                            
                                        team100_parts = [p for p in active.get("participants", []) if p.get("teamId") == 100]
                                        team200_parts = [p for p in active.get("participants", []) if p.get("teamId") == 200]
                                        
                                        tasks_100 = [get_participant_info(i, p) for i, p in enumerate(team100_parts)]
                                        tasks_200 = [get_participant_info(i, p) for i, p in enumerate(team200_parts)]
                                        
                                        team100_res = await asyncio.gather(*tasks_100)
                                        team200_res = await asyncio.gather(*tasks_200)
                                        
                                        if team100_res:
                                            embed.add_field(name="Équipe Bleue", value="\n".join(team100_res), inline=False)
                                        if team200_res:
                                            embed.add_field(name="Équipe Rouge", value="\n".join(team200_res), inline=False)

                                        if is_bet_allowed:
                                            from cogs.economy import BetView
                                            # On utilise l'ID du premier joueur traqué comme référence pour le pari
                                            await channel.send(embed=embed, view=BetView(players[0]['discord_id']))
                                        else:
                                            await channel.send(embed=embed)
                                    except Exception as e:
                                        logger.error(f"Erreur d'envoi d'annonce dans {channel.id}: {e}")
                    await session.commit()
                except Exception as e:
                    logger.error(f"Erreur lors du traitement active game {game_id}: {e}")
                    await session.rollback()

            # 2. Check Match History et Résolution des paris
            for acc in linked_accounts:
                puuid = acc.riot_puuid
                try:
                    match_ids = await self.riot.get_match_ids(puuid, count=5)
                    for match_id in match_ids:
                        stmt_link = select(PlayerMatch).where(PlayerMatch.puuid == puuid, PlayerMatch.match_id == match_id)
                        link_exists = (await session.execute(stmt_link)).scalar_one_or_none()
                        
                        if not link_exists:
                            new_link = PlayerMatch(puuid=puuid, match_id=match_id)
                            session.add(new_link)
                            
                        stmt_match = select(RiotMatch).where(RiotMatch.match_id == match_id)
                        match_exists = (await session.execute(stmt_match)).scalar_one_or_none()
                        
                        if not match_exists:
                            details = await self.riot.get_match_details(match_id)
                            if details and "info" in details:
                                timeline = await self.riot.get_match_timeline(match_id)
                                details["timeline_data"] = timeline
                                game_creation = details["info"].get("gameCreation", 0)
                                new_match = RiotMatch(match_id=match_id, data=details, game_creation=game_creation)
                                session.add(new_match)
                                
                                # Résolution des paris si la partie était suivie
                                stmt_active = select(ActiveGame).where(ActiveGame.game_id == match_id)
                                active_game_records = (await session.execute(stmt_active)).scalars().all()
                                
                                if active_game_records:
                                    win = False
                                    record_for_bet = active_game_records[0]
                                    for participant in details["info"]["participants"]:
                                        if participant["puuid"] == record_for_bet.puuid:
                                            win = participant["win"]
                                            break
                                            
                                    stmt_bets = select(Bet).where(Bet.game_id == match_id)
                                    bets = (await session.execute(stmt_bets)).scalars().all()
                                    
                                    for bet in bets:
                                        correct = (bet.prediction == "win" and win) or (bet.prediction == "lose" and not win)
                                        stmt_eco = select(UserEconomy).where(UserEconomy.discord_id == bet.bettor_id, UserEconomy.guild_id == bet.guild_id)
                                        eco = (await session.execute(stmt_eco)).scalar_one_or_none()
                                        
                                        if eco and correct:
                                            eco.points += bet.amount * 2
                                            
                                        # Annoncer le résultat du pari
                                        stmt_conf = select(ServerConfig).where(ServerConfig.guild_id == bet.guild_id)
                                        conf = (await session.execute(stmt_conf)).scalar_one_or_none()
                                        if conf and conf.announcement_channel_id:
                                            guild = self.bot.get_guild(bet.guild_id)
                                            if guild:
                                                channel = guild.get_channel(conf.announcement_channel_id) or guild.get_thread(conf.announcement_channel_id)
                                                if channel:
                                                    try:
                                                        bettor = guild.get_member(bet.bettor_id)
                                                        bettor_name = bettor.mention if bettor else "Un parieur"
                                                        res_text = f"✅ gagné {bet.amount * 2} points" if correct else f"❌ perdu {bet.amount} points"
                                                        target_member = "le groupe" if len(active_game_records) > 1 else f"<@{record_for_bet.discord_id}>"
                                                        await channel.send(f"🎲 Pari de {bettor_name} : {res_text} sur le match de {target_member} !")
                                                    except:
                                                        pass
                                                        
                                    # Récompenser tous les joueurs trackés de la partie et préparer l'annonce de fin
                                    mentions_end = []
                                    for record in active_game_records:
                                        player_win = False
                                        for participant in details["info"]["participants"]:
                                            if participant["puuid"] == record.puuid:
                                                player_win = participant["win"]
                                                break
                                        if player_win:
                                            stmt_player_eco = select(UserEconomy).where(UserEconomy.discord_id == record.discord_id)
                                            player_ecos = (await session.execute(stmt_player_eco)).scalars().all()
                                            for peco in player_ecos:
                                                peco.points += 50
                                        mentions_end.append(f"<@{record.discord_id}>")
                                        await session.delete(record)
                                        
                                    # Annonce globale de fin de partie
                                    result_title = "🏆 Victoire !" if win else "💀 Défaite..."
                                    result_color = 0x00FF00 if win else 0xFF0000
                                    
                                    desc_end = f"{' '.join(mentions_end)} {'ont gagné' if len(mentions_end) > 1 else 'a gagné'} la partie !" if win else f"{' '.join(mentions_end)} {'ont perdu' if len(mentions_end) > 1 else 'a perdu'} la partie."
                                    if win:
                                        desc_end += "\n(+50 points d'économie chacun)"
                                        
                                    embed_end = discord.Embed(
                                        title=f"Fin de partie : {result_title}",
                                        description=desc_end,
                                        color=result_color
                                    )
                                    
                                    stmt_configs_end = select(ServerConfig).where(ServerConfig.announcement_channel_id.isnot(None))
                                    configs_end = (await session.execute(stmt_configs_end)).scalars().all()
                                    for conf in configs_end:
                                        guild = self.bot.get_guild(conf.guild_id)
                                        if guild:
                                            channel = guild.get_channel(conf.announcement_channel_id) or guild.get_thread(conf.announcement_channel_id)
                                            if channel:
                                                try:
                                                    await channel.send(" ".join(mentions_end), embed=embed_end)
                                                except:
                                                    pass
                                        
                    await session.commit()
                except Exception as e:
                    logger.error(f"Erreur lors du crawl history pour {puuid}: {e}")
                    await session.rollback()
                    
        logger.info("Fin du crawl Riot.")

    @riot_crawler.before_loop
    async def before_riot_crawler(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Crawler(bot))
