# app/webhook_receiver.py

from aiohttp import web
import aiohttp
import os
import sys

from dotenv import load_dotenv

sys.path.append("/home/tg_bot/hhchecker")

NOTIFY_MAIN_APP_URL = os.getenv("NOTIFY_MAIN_APP_URL", "http://localhost:8080/internal/notify-new-response")


async def webhook_handler(request: web.Request) -> web.Response:
    from app.db import queue_new_response
    from app.hh_api import parse_hh_date
    try:
        data = await request.json()
        print(f"[🔔] Получен POST запрос с данными: {data}")
        payload = data.get("payload")
        subscription_id = data.get("subscription_id")
        created_at = parse_hh_date(payload.get("negotiation_date"))
        if not payload or not all(k in payload for k in ("resume_id", "vacancy_id")):
            return web.Response(status=400, text="Missing payload keys")

        queue_new_response(payload["vacancy_id"], payload["resume_id"], subscription_id, created_at)
        await notify_main_app()
        return web.Response(status=201, text="OK")
    except Exception as e:
        print(f"Ошибка при обработке webhook запроса")
        return web.Response(status=500)


async def notify_main_app():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(NOTIFY_MAIN_APP_URL) as resp:
                print(f"[→] Сообщение отправлено в основное приложение: статус {resp.status}")
    except Exception as e:
        print(f"[!] Не удалось уведомить основное приложение: {e}")


def start_webhook_receiver():
    app = web.Application()
    app.router.add_post("/sub", webhook_handler)
    web.run_app(app, host="0.0.0.0", port=8082)


if __name__ == "__main__":
    load_dotenv()
    print("TEST", os.getenv("TELEGRAM_BOT_TOKEN_TEST"))
    print("TRUE", os.getenv("TELEGRAM_BOT_TOKEN"))
    import asyncio
    # from app.logger import setup_logger

    # asyncio.run(setup_logger())
    start_webhook_receiver()
