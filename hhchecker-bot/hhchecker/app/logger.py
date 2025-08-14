# app/logger.py

from aiologger import Logger
from aiologger.handlers.files import AsyncFileHandler
from aiologger.handlers.streams import AsyncStreamHandler
import os
import asyncio

# noinspection PyTypeChecker
logger: Logger = None


async def setup_logger():
    global logger
    logger = Logger.with_default_handlers(name="hhchecker", level="INFO")
    file_handler   = AsyncFileHandler(filename="hhchecker.log", mode="a", encoding="utf-8")
    stream_handler = AsyncStreamHandler()
    logger.add_handler(file_handler)
    logger.add_handler(stream_handler)
    return True


async def shutdown_logger():
    await logger.shutdown()