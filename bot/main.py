from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import load_config
from .db import Database
from .handlers import create_router


async def _run() -> None:
    logging.basicConfig(level=logging.INFO)

    config = load_config()
    db = Database(config.db_path)
    await db.connect()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(create_router(db))

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


def run() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    run()
