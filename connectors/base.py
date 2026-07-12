from abc import ABC, abstractmethod

class GameConnector(ABC):
    @property
    @abstractmethod
    def game_name(self) -> str:
        """Le nom du jeu ou de la plateforme (ex: 'Riot Games', 'Steam')"""
        pass

    @abstractmethod
    async def fetch_user_stats(self, account_id: str) -> dict:
        """Récupère les statistiques pour un compte donné"""
        pass
