import os
from datetime import datetime

import requests
from aiogram import Bot
from aiohttp import web
from app.auth import exchange_code_for_tokens_for_user, USER_AGENT
from dotenv import load_dotenv


load_dotenv()

REDIRECT_PATH = "/tg"
PORT = int(os.getenv("WEBHOOK_PORT", "8080"))
HOST = "127.0.0.1"  # слушаем на всех интерфейсах


async def handle_tg(request):
    """
    Обрабатывает редирект от hh.ru с параметрами code и state.
    Всегда редиректит на Telegram‑бота.
    """
    params = request.rel_url.query
    code = params.get("code")
    state = params.get("state")

    if code and state:
        try:
            redirect_uri = os.getenv("REDIRECT_URI")
            exchange_code_for_tokens_for_user(
                user_id=int(state),
                code=code,
                redirect_uri=redirect_uri
            )
            print(f"✅ Авторизация прошла успешно для user_id={state}")
        except Exception as e:
            print(f"❌ Ошибка авторизации user_id={state}: {e}")

    # В любом случае перенаправляем на Telegram‑бота
    raise web.HTTPFound("https://t.me/hh_response_checker_bot")


# async def handle_new_negotiation(request: web.Request):
#     try:
#         data = await request.json()
#         payload = data.get("payload", {})
#         vacancy_id = payload.get("vacancy_id")
#         resume_id = payload.get("resume_id")
#
#         if not vacancy_id:
#             return web.Response(status=400, text="Missing vacancy_id")
#
#         data_result = await get_user_ids_by_vacancy(vacancy_id)
#         vacancy_name = data_result[0]
#         user_ids = data_result[1]
#         if not user_ids:
#             # Удаление подписки, если нет подписчиков
#             subscription_id = await get_subscription_id_by_vacancy(vacancy_id)
#             if subscription_id:
#                 await delete_subscription(subscription_id)
#             return web.Response(status=201, text="No subscribers")
#
#         data = await fetch_responses_by_resume_id(user_ids[0], vacancy_id, resume_id)
#         full_name = data["full_name"]
#         created_at = data["created_at"]
#
#         for user_id in user_ids:
#             await send_notification(
#                                 str(user_id),
#                                 vacancy_id,
#                                 vacancy_name,
#                                 {
#                                     "name": full_name,
#                                     "created_at": created_at
#                                 }
#                             )
#         return web.Response(status=201, text="OK")
#
#     except Exception as e:
#         return web.Response(status=500, text=f"Internal error: {str(e)}")


async def internal_notify_new_response(_: web.Request) -> web.Response:
    print(f"получен новый отклик {''}")
    from app.hh_api import process_queued_responses
    await process_queued_responses()
    return web.Response(status=200, text="Processed")


def start_webhook_app():
    """
    Запускает aiohttp‑сервер для приёма redirect с hh.ru.
    Вызывать в on_startup бота.
    """
    app = web.Application()
    app.router.add_get("/tg", handle_tg)
    app.router.add_post("/internal/notify-new-response", internal_notify_new_response)
    # app.router.add_post("/sub", handle_new_negotiation)
    runner = web.AppRunner(app)
    return runner


async def setup_webhook(runner):
    await runner.setup()
    site = web.TCPSite(runner, HOST, 8080)
    await site.start()
    print(f"Webhook server listening on http://{HOST}:{PORT}{REDIRECT_PATH}")
