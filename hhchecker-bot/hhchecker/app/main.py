import asyncio

from app.hh_api import process_queued_responses
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.the_bot import bot
from app.handlers import register_handlers, router
from app.db import init_db
from app.webhook import start_webhook_app, setup_webhook


# noinspection PyUnboundLocalVariable
async def main():
    init_db()

    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация хэндлеров
    register_handlers(dp)

    # Инициализация базы данных

    dp.include_router(router)

    # Запуск планировщика
    # start_scheduler()
    await process_queued_responses()
    runner = start_webhook_app()
    await setup_webhook(runner)

    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
