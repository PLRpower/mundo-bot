import discord
from discord.ext import commands
from discord import app_commands
import datetime
import asyncio
import os
import json
from connectors.deskbird import deskbird_connector, normalize_text

DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

EMBED_COLOR = 0x242429
COLLEAGUES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "colleagues.json")


def load_colleagues() -> list[dict]:
    if os.path.exists(COLLEAGUES_FILE):
        try:
            with open(COLLEAGUES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_target_monday() -> tuple[datetime.date, bool]:
    today = datetime.date.today()
    if today.weekday() >= 5:
        days_ahead = 7 - today.weekday()
        return today + datetime.timedelta(days=days_ahead), True
    return today - datetime.timedelta(days=today.weekday()), False


class DeskbirdCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        asyncio.create_task(self._preload_planning())

    async def _preload_planning(self):
        try:
            monday, _ = get_target_monday()
            await deskbird_connector.get_staff_planning(monday, favorites_only=False)
        except Exception:
            pass

    async def nom_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        colleagues = load_colleagues()
        norm_query = normalize_text(current.strip())
        choices = []
        for c in colleagues:
            norm_name = normalize_text(c.get("name", ""))
            if not norm_query or all(tok in norm_name for tok in norm_query.split()):
                choices.append(app_commands.Choice(name=c.get("name", ""), value=c.get("userId", "")))
        return choices[:25]

    @app_commands.command(
        name="planning",
        description="Affiche le planning Deskbird de la semaine pour un collègue."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(nom="Nom du collègue")
    @app_commands.autocomplete(nom=nom_autocomplete)
    async def planning(self, interaction: discord.Interaction, nom: str):
        await interaction.response.defer()

        colleagues = load_colleagues()
        target_ids = {c.get("userId") for c in colleagues}
        id_to_name = {c.get("userId"): c.get("name") for c in colleagues}

        target_id = None
        if nom in target_ids:
            target_id = nom
        else:
            norm_input = normalize_text(nom.strip())
            for c in colleagues:
                if norm_input in normalize_text(c.get("name", "")):
                    target_id = c.get("userId")
                    break

        if not target_id:
            await interaction.followup.send(
                f"❌ Collègue **{nom}** introuvable dans la liste configurée.",
                ephemeral=True
            )
            return

        monday, is_next_week = get_target_monday()
        all_users = await deskbird_connector.get_staff_planning(monday, favorites_only=False)

        user = next((u for u in all_users if str(u.get("userId")) == target_id), None)
        if not user:
            await interaction.followup.send(
                f"❌ Données de planning indisponibles pour **{id_to_name.get(target_id, nom)}**.",
                ephemeral=True
            )
            return

        display_name = id_to_name.get(target_id, nom)
        profile_img = user.get("profileImage")

        title_suffix = " (Semaine suivante)" if is_next_week else ""
        embed = discord.Embed(
            title=f"📅 Planning de {display_name}{title_suffix}",
            color=EMBED_COLOR
        )

        if profile_img:
            embed.set_thumbnail(url=profile_img)

        # Indexer les entrées de jours par date ISO (YYYY-MM-DD)
        user_days_map = {d.get("day"): d.get("scheduling", []) for d in user.get("days", [])}

        # Afficher strictement 5 jours du lundi au vendredi
        for i in range(5):
            current_day = monday + datetime.timedelta(days=i)
            iso_key = current_day.isoformat()
            day_label = f"{DAYS_FR[i]} {current_day.day} {MONTHS_FR[current_day.month - 1]}"

            sched_entries = user_days_map.get(iso_key, [])
            entry_text = deskbird_connector.format_entry(sched_entries)
            embed.add_field(name=day_label, value=entry_text, inline=False)

        friday = monday + datetime.timedelta(days=4)
        prefix = "Semaine suivante du" if is_next_week else "Semaine du"
        embed.set_footer(
            text=f"{prefix} {monday.day} {MONTHS_FR[monday.month - 1]} au {friday.day} {MONTHS_FR[friday.month - 1]}"
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(DeskbirdCog(bot))
