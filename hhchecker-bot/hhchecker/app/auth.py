import asyncio
import os
import time
import requests
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://api.hh.ru/token"
USER_AGENT = os.getenv("HH_USER_AGENT", "hhcheckbot.ru (343454nbg@gmail.com)")


def parse_iso8601(s: str) -> datetime:
    """Парсит дату из строки ISO 8601"""
    return datetime.fromisoformat(s)


# def save_tokens(access_token: str, refresh_token: str, expires_in: int):
#     """Сохраняет токены и срок действия в .env"""
#     expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
#     os.environ["HHRU_ACCESS_TOKEN"] = access_token
#     os.environ["HHRU_REFRESH_TOKEN"] = refresh_token
#     os.environ["HHRU_TOKEN_EXPIRES_AT"] = expires_at.isoformat()
#
#     # Обновим .env файл (если нужно)
#     with open("../.env", "r") as f:
#         lines = f.readlines()
#
#     def update_line(key: str, value: str):
#         for i, line in enumerate(lines):
#             if line.startswith(key + "="):
#                 lines[i] = f"{key}={value}\n"
#                 return
#         lines.append(f"{key}={value}\n")
#
#     update_line("HHRU_ACCESS_TOKEN", access_token)
#     update_line("HHRU_REFRESH_TOKEN", refresh_token)
#     update_line("HHRU_TOKEN_EXPIRES_AT", expires_at.isoformat())
#
#     with open("../.env", "w") as f:
#         f.writelines(lines)


async def get_headers(user_id: int):
    """
    Возвращает заголовки для запросов HH API:
    - Обновлённый access_token
    - User-Agent
    Перед этим гарантируем, что в БД есть employer_id и manager_id.
    """

    # 1) Обновляем токен (или шлём ссылку на авторизацию)
    token = await get_access_token_for_user(user_id)
    print(f">>> TOKEN {token}")
    return {
        "Authorization": f"Bearer {token}",
        "HH-User-Agent": USER_AGENT
    }


def exchange_code_for_tokens_for_user(user_id: int, code: str, redirect_uri: str):
    """
    Один раз: обменять authorization_code на access+refresh и сохранить в БД.
    """
    from app.db import save_user_auth
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp.raise_for_status()
    js = resp.json()

    expires_in = js["expires_in"]
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    user_info_resp = requests.get(
        "https://api.hh.ru/me",
        headers={
            "Authorization": f"Bearer {js['access_token']}",
            "User-Agent": os.getenv("HH_USER_AGENT", "hhcheckbot.ru (343454nbg@gmail.com)")})

    user_info_resp.raise_for_status()
    user_info = user_info_resp.json()

    manager_id = str(user_info.get("manager", {}).get("id", ""))
    employer_id = str(user_info.get("employer", {}).get("id", ""))

    # Сохраняем в таблицу user_auth
    save_user_auth(
        user_id=user_id,
        access_token=js["access_token"],
        refresh_token=js["refresh_token"],
        expires_at=expires_at,
        manager_id=manager_id,
        employer_id=employer_id,
    )


async def refresh_tokens_for_user(user_id: int):
    """
    Обновить токены по refresh_token и сохранить в БД.
    """
    from app.db import save_user_auth, get_user_auth
    auth = await get_user_auth(user_id)
    if not auth:
        raise ValueError(f"user_id={user_id} не зарегистрирован для OAuth")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": auth.user_refresh_token,
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
    }
    resp = requests.post(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp.raise_for_status()
    js = resp.json()

    expires_in = js["expires_in"]
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    save_user_auth(
        user_id=user_id,
        access_token=js["access_token"],
        refresh_token=js["refresh_token"],
        expires_at=expires_at,
        manager_id=auth.manager_id,
        employer_id=auth.user_employer_id,
    )
    return js["access_token"] is not None


def build_authorization_url(user_id: int) -> str:
    """Генерирует ссылку на hh.ru/oauth/authorize"""
    client_id = os.getenv("CLIENT_ID")
    redirect_uri = os.getenv("REDIRECT_URI")
    return (
        f"https://hh.ru/oauth/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={user_id}"
    )


async def get_access_token_for_user(user_id: int) -> str:
    """
    Получает access_token из базы или обновляет его.
    Если обновить нельзя — отправляет ссылку пользователю.
    """
    from app.the_bot import bot
    from app.db import get_user_auth
    auth = await get_user_auth(user_id)
    if not auth:
        raise ValueError(f"user_id={user_id} не зарегистрирован (нет OAuth данных)")

    now = datetime.utcnow()
    if auth.user_token_expires_at <= now + timedelta(seconds=60):
        try:
            if await refresh_tokens_for_user(user_id):
                auth = await get_user_auth(user_id)  # обновим
        except Exception as ex:
            # Ошибка при обновлении — отправляем ссылку на авторизацию
            url = build_authorization_url(user_id)
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "Срок действия авторизации истёк.\n\n"
                    f"[Нажмите сюда, чтобы авторизоваться повторно]({url})"
                )
            )
    return auth.user_access_token
