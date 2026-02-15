from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError as e:
        raise RuntimeError(f"Env {name} must be int, got: {val!r}") from e

@dataclass(frozen=True)
class IDs:
    # Guilds
    PUBLIC_GUILD_ID: int = 1287197183954784296
    PRIVATE_GUILD_ID: int = 1454836789331230842

    # Roles
    PUBLIC_ROLE_SH_ID: int = 1299444337658171422
    PUBLIC_ROLE_FUN_SH_ID: int = 1315028367044513876
    PRIVATE_ROLE_SH_ID: int = 1454842309421170719

@dataclass(frozen=True)
class Settings:
    token: str
    log_level: str = "INFO"
    sync_interval_minutes: int = 10

IDS = IDs()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is empty. Put token into .env (see .env.example).")

SETTINGS = Settings(
    token=TOKEN,
    log_level=os.getenv("LOG_LEVEL", "INFO").strip() or "INFO",
    sync_interval_minutes=_env_int("SYNC_INTERVAL_MINUTES", 10),
)
