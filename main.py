import discord
from discord.ext import commands
import logging
import asyncio
from config import DISCORD_TOKEN
from database.engine import init_db

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('mundo-bot')

class MundoStatsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Initialisation de la base de données
        logger.info("Initialisation de la base de données SQLite...")
        await init_db()
        
        # Chargement des cogs
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.accounts")
        await self.load_extension("cogs.stats")
        await self.load_extension("cogs.roles")
        await self.load_extension("cogs.ai")
        await self.load_extension("cogs.crawler")
        await self.load_extension("cogs.admin")
        await self.load_extension("cogs.economy")
        await self.load_extension("cogs.randomizer")
        await self.load_extension("cogs.deskbird")
        
        # Enregistrement des vues persistantes
        from cogs.roles import RoleSetupView
        self.add_view(RoleSetupView())
        
        # Synchronisation des slash commands
        logger.info("Synchronisation des commandes slash...")
        await self.tree.sync()
        logger.info("Commandes synchronisées !")

    async def on_ready(self):
        logger.info(f"Bot connecté en tant que {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="Analyser des stats"))

async def main():
    if not DISCORD_TOKEN:
        logger.error("Le token Discord est introuvable. Avez-vous créé le fichier .env et ajouté DISCORD_TOKEN ?")
        return

    bot = MundoStatsBot()
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
