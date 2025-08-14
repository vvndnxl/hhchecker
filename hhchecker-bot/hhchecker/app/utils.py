# import functools
# import asyncio
#
# import aiohttp
#
#
# class HHAPIError(Exception):
#     """Базовое исключение для ошибок hh.ru API."""
#
#
# class AuthError(HHAPIError):
#     """Ошибка авторизации (401/403)."""
#
#
# class NotFoundError(HHAPIError):
#     """Ресурс не найден (404)."""
#
#
# class BadRequestError(HHAPIError):
#     """Некорректный запрос (400)."""
#
#
# class DBError(Exception):
#     """Ошибки доступа к базе данных."""
#
#
# class ConfigError(Exception):
#     """Ошибка конфигурации (например, отсутствует переменная окружения)."""
#
#
# def catch_and_log(exc_type=Exception, reraise=True):
#     """
#     Декоратор для асинхронных функций: ловит exc_type,
#     логирует и (опционально) повторно бросает.
#     """
#     def deco(fn):
#         @functools.wraps(fn)
#         async def wrapper(*args, **kwargs):
#             try:
#                 return await fn(*args, **kwargs)
#             except exc_type as e:
#                 print(f"Exception in {fn.__name__}: {e}")
#                 if reraise:
#                     raise
#         return wrapper
#     return deco
