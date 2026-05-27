from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class Config:
    bot_token: str
    db_path: Path


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is missing. Add it to your .env file.")

    db_path = Path(os.getenv("DB_PATH", "data/bot.db")).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Config(bot_token=token, db_path=db_path)
