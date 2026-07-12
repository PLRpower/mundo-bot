import discord
from discord.ext import commands
from discord import app_commands

# Liste des rôles/jeux disponibles. Format : "Nom du jeu": "ID de l'émoji"
AVAILABLE_GAMES = {
    "Borderlands (Martin)": "🔫",
    "League of Legends": "⚔️",
    "Valorant": "🎯",
    "Outer Wilds": "🪐",
    "Rocket League": "🚗",
    "Rivals": "🥊",
    "Minecraft": "⛏️",
    "Among Us": "👽"
}

class RoleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=game,
                emoji=emoji,
                description=f"Être notifié pour jouer à {game}"
            ) for game, emoji in AVAILABLE_GAMES.items()
        ]
        
        super().__init__(
            placeholder="Choisis tes jeux (coche TOUS tes jeux)...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="role_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        
        roles_added = []
        roles_removed = []
        
        for game in AVAILABLE_GAMES.keys():
            # Le nom du rôle est exactement le nom du jeu
            role = discord.utils.get(guild.roles, name=game)
            if not role:
                try:
                    role = await guild.create_role(name=game, reason="Création automatique pour le menu des rôles")
                except discord.Forbidden:
                    await interaction.response.send_message("❌ Je n'ai pas les permissions de gérer les rôles.", ephemeral=True)
                    return

            if game in self.values:
                if role not in member.roles:
                    await member.add_roles(role)
                    roles_added.append(role.mention)
            else:
                if role in member.roles:
                    await member.remove_roles(role)
                    roles_removed.append(role.mention)
                    
        msg = "✅ Tes rôles ont été mis à jour !\n"
        if roles_added:
            msg += f"**Ajoutés :** {', '.join(roles_added)}\n"
        if roles_removed:
            msg += f"**Retirés :** {', '.join(roles_removed)}\n"
        if not roles_added and not roles_removed:
            msg = "Tu n'as fait aucun changement."
            
        await interaction.response.send_message(msg, ephemeral=True)

class RoleSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Ce menu reste actif indéfiniment
        self.add_item(RoleSelect())

class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_roles", description="[Admin] Fait apparaître le menu de sélection de rôles")
    @app_commands.default_permissions(administrator=True)
    async def setup_roles(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 Choisis tes jeux !",
            description=(
                "Sélectionne les jeux auxquels tu joues dans le menu déroulant ci-dessous.\n\n"
                "Tu recevras le rôle correspondant pour pouvoir être mentionné (ping) "
                "quand d'autres joueurs cherchent du monde pour jouer !"
            ),
            color=0x16161a
        )
        embed.set_footer(text="Tu peux modifier tes choix à tout moment.")
        
        await interaction.channel.send(embed=embed, view=RoleSetupView())
        await interaction.response.send_message("✅ Menu des rôles créé avec succès !", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
