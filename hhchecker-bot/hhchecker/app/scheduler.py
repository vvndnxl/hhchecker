from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


import os


def parse_hh_date(date_str: str) -> datetime:
    """Парсит дату из формата HH: 2024-06-10T16:28:04+0300"""
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")


async def check_for_new_responses():
    # from app.db import get_all_subscriptions, update_last_response
    # from app.hh_api import fetch_responses
    # subs = get_all_subscriptions()
    # for sub in subs:
    #     try:
    #         # получаем все отклики (sorted desc)
    #         responses = await fetch_responses(
    #             user_id=sub.user_id,
    #             vacancy_id=sub.vacancy_id,
    #             status="active",
    #             page=0,
    #             per_page=50,  # достаточно первой страницы
    #             order_by="created_at",
    #             order="desc",
    #         )
    #         if not responses:
    #             continue
    #         response = responses[-1]
    #         new_response_date = parse_hh_date(response.get("created_at", ""))
    #         if sub.last_response_date is None:
    #             sub.last_response_date = new_response_date
    #         if new_response_date > sub.last_response_date:
    #             # уведомляем пользователя
    #             resume = response.get("resume", {})
    #             full_name = f"{resume.get('first_name', '???')} {resume.get('last_name', '')}".strip()
    #             await send_notification(
    #                 sub.user_id,
    #                 sub.vacancy_id,
    #                 sub.vacancy_name,
    #                 {
    #                     "name": full_name,
    #                     "created_at": new_response_date
    #                 }
    #             )
    #             # обновляем в БД
    #             update_last_response(sub.vacancy_id, new_response_date)
    #
    #     except Exception as e:
    #         print(f"[!] Ошибка при проверке вакансии {sub.vacancy_id}: {e}")
    pass


def start_scheduler():
    # scheduler = AsyncIOScheduler(timezone="UTC")
    # interval_seconds = int(os.getenv("POLL_INTERVAL", "100"))
    #
    # scheduler.add_job(
    #     check_for_new_responses,
    #     trigger=IntervalTrigger(seconds=interval_seconds),
    #     id="hh_response_check",
    #     replace_existing=True
    # )
    #
    # scheduler.start()
    # print(f"[⏱] Планировщик запущен, проверка каждые {interval_seconds} сек.")
    pass
