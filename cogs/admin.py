import discord
from discord.ext import commands
from discord import app_commands
from database.engine import AsyncSessionLocal
from database.models import ServerConfig
from sqlalchemy import select

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="set_announcement", description="Définir le salon ou le fil actuel pour les annonces du bot")
    @app_commands.default_permissions(administrator=True)
    async def set_announcement(self, interaction: discord.Interaction):
        target_channel = interaction.channel
        
        permissions = target_channel.permissions_for(interaction.guild.me)
        if not permissions.send_messages:
            await interaction.response.send_message("❌ Je n'ai pas la permission d'envoyer des messages ici.", ephemeral=True)
            return
            
        async with AsyncSessionLocal() as session:
            stmt = select(ServerConfig).where(ServerConfig.guild_id == interaction.guild_id)
            config = (await session.execute(stmt)).scalar_one_or_none()
            
            if not config:
                config = ServerConfig(guild_id=interaction.guild_id)
                session.add(config)
                
            config.announcement_channel_id = target_channel.id
            await session.commit()
            
        await interaction.response.send_message(f"✅ Les annonces du bot seront désormais envoyées ici ({target_channel.mention}).")
    @app_commands.command(name="setup_emojis", description="Télécharge et installe les emojis d'application (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def setup_emojis(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Lancement de la synchronisation des emojis en arrière-plan. Regarde la console pour voir la progression !", ephemeral=True)
        self.bot.loop.create_task(self._sync_emojis())
        
    async def _sync_emojis(self):
        import aiohttp
        import asyncio
        from utils.ddragon import ddragon
        import logging
        logger = logging.getLogger('mundo-bot')
        
        await ddragon.init()
        
        try:
            app_emojis = await self.bot.fetch_application_emojis()
            existing_names = {e.name: e.id for e in app_emojis}
            logger.info(f"Trouvé {len(existing_names)} Application Emojis existants.")
        except Exception as e:
            logger.error(f"Erreur fetch emojis: {e}")
            return
            
        async with aiohttp.ClientSession() as session:
            # 1. Champions
            for champ_name in ddragon.champions.values():
                safe_name = champ_name.replace(" ", "").replace("'", "").replace(".", "")
                if safe_name in existing_names:
                    continue
                url = ddragon.get_champion_url(champ_name)
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            emoji = await self.bot.create_application_emoji(name=safe_name, image=image_bytes)
                            existing_names[safe_name] = emoji.id
                            logger.info(f"Emoji créé : {safe_name}")
                            await asyncio.sleep(2.5) # Anti-rate limit
                except Exception as e:
                    logger.error(f"Error {champ_name}: {e}")
            
            # 2. Items
            for item_id, item_data in ddragon.items.items():
                if not item_data.get("maps", {}).get("11", False): continue
                if not item_data.get("gold", {}).get("purchasable", False): continue
                if "into" in item_data and len(item_data["into"]) > 0: continue
                if "Consumable" in item_data.get("tags", []): continue
                if "Trinket" in item_data.get("tags", []): continue
                if "Jungle" in item_data.get("tags", []): continue
                if item_data.get("gold", {}).get("total", 0) < 1500: continue
                
                name = item_data["name"]
                safe_name = "item_" + "".join(c for c in name if c.isalnum())
                if safe_name in existing_names:
                    continue
                url = ddragon.get_item_url(item_id)
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            emoji = await self.bot.create_application_emoji(name=safe_name, image=image_bytes)
                            existing_names[safe_name] = emoji.id
                            logger.info(f"Emoji créé : {safe_name}")
                            await asyncio.sleep(2.5)
                except Exception as e:
                    logger.error(f"Error item {name}: {e}")
                    
            # 3. Ranks (Emblems)
            ranks = ["iron", "bronze", "silver", "gold", "platinum", "emerald", "diamond", "master", "grandmaster", "challenger"]
            for rank in ranks:
                safe_name = f"rank_{rank}"
                if safe_name in existing_names:
                    continue
                url = f"https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-{rank}.png"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            emoji = await self.bot.create_application_emoji(name=safe_name, image=image_bytes)
                            existing_names[safe_name] = emoji.id
                            logger.info(f"Emoji créé : {safe_name}")
                            await asyncio.sleep(2.5)
                        else:
                            logger.error(f"Error rank {rank}: HTTP {resp.status}")
                except Exception as e:
                    logger.error(f"Error rank {rank}: {e}")
                    
            # 4. Roles
            roles = ["top", "jungle", "mid", "adc", "support"]
            for role in roles:
                safe_name = f"role_{role}"
                if safe_name in existing_names:
                    continue
                file_path = f"{safe_name}.png"
                import os
                if os.path.exists(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            image_bytes = f.read()
                        emoji = await self.bot.create_application_emoji(name=safe_name, image=image_bytes)
                        existing_names[safe_name] = emoji.id
                        logger.info(f"Emoji créé : {safe_name}")
                        await asyncio.sleep(2.5)
                    except Exception as e:
                        logger.error(f"Error role {role}: {e}")
                        
            # 5. Runes
            for tree in ddragon.rune_trees:
                # Arbre (Tree)
                safe_name = "rune_" + "".join(c for c in tree["name"] if c.isalnum())
                if safe_name not in existing_names:
                    url = f"https://ddragon.leagueoflegends.com/cdn/img/{tree['icon']}"
                    try:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                image_bytes = await resp.read()
                                emoji = await self.bot.create_application_emoji(name=safe_name, image=image_bytes)
                                existing_names[safe_name] = emoji.id
                                logger.info(f"Emoji créé : {safe_name}")
                                await asyncio.sleep(2.5)
                    except Exception as e:
                        logger.error(f"Error rune {tree['name']}: {e}")
                
                # Runes individuelles
                for slot in tree["slots"]:
                    for rune in slot["runes"]:
                        safe_rune = "rune_" + "".join(c for c in rune["name"] if c.isalnum())
                        if safe_rune not in existing_names:
                            url = f"https://ddragon.leagueoflegends.com/cdn/img/{rune['icon']}"
                            try:
                                async with session.get(url) as resp:
                                    if resp.status == 200:
                                        image_bytes = await resp.read()
                                        emoji = await self.bot.create_application_emoji(name=safe_rune, image=image_bytes)
                                        existing_names[safe_rune] = emoji.id
                                        logger.info(f"Emoji créé : {safe_rune}")
                                        await asyncio.sleep(2.5)
                            except Exception as e:
                                logger.error(f"Error rune {rune['name']}: {e}")

            logger.info("Synchronisation des emojis terminée !")

    @app_commands.command(name="force_link", description="Lier un compte Riot Games à un utilisateur Discord (Admin)")
    @app_commands.describe(
        user="L'utilisateur Discord",
        account_id="Riot ID 'Pseudo#Tag'"
    )
    @app_commands.default_permissions(administrator=True)
    async def force_link(self, interaction: discord.Interaction, user: discord.Member, account_id: str):
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

        from database.models import LinkedAccount
        async with AsyncSessionLocal() as session:
            stmt = select(LinkedAccount).where(LinkedAccount.discord_id == user.id)
            result = await session.execute(stmt)
            account = result.scalar_one_or_none()
            
            if not account:
                account = LinkedAccount(discord_id=user.id)
                session.add(account)
                
            account.riot_puuid = puuid
            await session.commit()
            
        await interaction.followup.send(f"✅ Compte Riot `{account_id}` validé et lié avec succès pour {user.mention} ! (PUUID: `{puuid[:8]}...`)")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
