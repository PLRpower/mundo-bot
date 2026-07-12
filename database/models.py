from datetime import datetime, timezone
from sqlalchemy import BigInteger, String, DateTime, JSON, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class LinkedAccount(Base):
    __tablename__ = "linked_accounts"
    
    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    riot_puuid: Mapped[str | None] = mapped_column(String, nullable=True)
    steam_id64: Mapped[str | None] = mapped_column(String, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

class RiotMatch(Base):
    __tablename__ = "riot_matches"
    
    match_id: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    game_creation: Mapped[int] = mapped_column(BigInteger)

class PlayerMatch(Base):
    __tablename__ = "player_matches"
    
    puuid: Mapped[str] = mapped_column(String, primary_key=True)
    match_id: Mapped[str] = mapped_column(String, primary_key=True)

class ServerConfig(Base):
    __tablename__ = "server_configs"
    
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    language: Mapped[str] = mapped_column(String, default="fr")
    announcement_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

class UserEconomy(Base):
    __tablename__ = "user_economy"
    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    points: Mapped[int] = mapped_column(Integer, default=100)

class ActiveGame(Base):
    __tablename__ = "active_games"
    game_id: Mapped[str] = mapped_column(String, primary_key=True)
    puuid: Mapped[str] = mapped_column(String, primary_key=True)
    discord_id: Mapped[int] = mapped_column(BigInteger)
    champion_id: Mapped[int] = mapped_column(Integer)

class Bet(Base):
    __tablename__ = "bets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(String)
    bettor_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(Integer)
    prediction: Mapped[str] = mapped_column(String)
