import aiohttp
import time
import datetime
import unicodedata
from typing import Optional
from config import DESKBIRD_REFRESH_TOKEN, DESKBIRD_API_KEY

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def normalize_text(text: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    ).lower()


class DeskbirdConnector:
    def __init__(self):
        self.refresh_token = DESKBIRD_REFRESH_TOKEN
        self.api_key = DESKBIRD_API_KEY
        self.base_url = "https://api.deskbird.com"
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._planning_cache: dict[str, list[dict]] = {}
        self._cache_expiry: dict[str, float] = {}
        self.known_colleagues: list[dict] = []

    async def get_access_token(self) -> Optional[str]:
        if not self.refresh_token or not self.api_key:
            return None

        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        url = f"https://securetoken.googleapis.com/v1/token?key={self.api_key}"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                self._access_token = data.get("id_token") or data.get("access_token")
                expires_in = int(data.get("expires_in", 3600))
                self._token_expiry = time.time() + expires_in - 60
                return self._access_token

    async def get_staff_planning(self, monday_date: datetime.date, favorites_only: bool = False) -> list[dict]:
        cache_key = f"{monday_date.isoformat()}_{'fav' if favorites_only else 'all'}"
        now = time.time()

        if cache_key in self._planning_cache and now < self._cache_expiry.get(cache_key, 0):
            return self._planning_cache[cache_key]

        token = await self.get_access_token()
        if not token:
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT
        }
        query = "favorites=1" if favorites_only else "all=true"
        url = f"{self.base_url}/v2/scheduling/staffPlanning?startDate={monday_date.isoformat()}&days=7&{query}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                users = data.get("selectedUsers", {}).get("users", [])
                my_sched = data.get("mySchedule", [])
                if my_sched and not any(str(u.get("userId")) == "765046" for u in users):
                    users.append({
                        "userId": "765046",
                        "firstName": "Paul",
                        "lastName": "THOMAS",
                        "email": "pthomas@cesi.fr",
                        "days": my_sched
                    })
                self._planning_cache[cache_key] = users
                self._cache_expiry[cache_key] = now + 180  # cache 3 min
                return users

    def format_entry(self, scheduling_entries: list[dict]) -> str:
        if not scheduling_entries:
            return "⚪ *Non renseigné*"

        parts = []
        for s in scheduling_entries:
            op_type = s.get("optionType")
            custom_name = s.get("optionName")

            if op_type == "office":
                parts.append("👺 **Au bureau**")
            elif op_type == "mobile_work":
                parts.append("😴 **Télétravail**")
            elif op_type == "travel":
                parts.append("✈️ **En déplacement**")
            elif op_type == "absent":
                parts.append(f"🌴 **{custom_name or 'Absent / Congé'}**")
            else:
                label = custom_name or op_type or "Planifié"
                parts.append(f"📌 **{label}**")

        return " / ".join(parts)


deskbird_connector = DeskbirdConnector()
