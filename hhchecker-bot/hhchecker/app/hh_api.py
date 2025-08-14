from datetime import datetime

import requests
from typing import List, Dict, Optional
import aiohttp

from app.auth import get_headers
import os


from app.db import get_user_ids_by_vacancy, get_subscription_id_by_vacancy, get_queued_responses, clear_queued_responses, \
    clear_subs, remove_queued_response
from app.the_admin_id import admin_id

BASE_URL = "https://api.hh.ru"

USER_AGENT = "hhcheckbot.ru (343454nbg@gmail.com)"


def parse_hh_date(date_str: str) -> datetime:
    """Парсит дату из формата HH: 2024-06-10T16:28:04+0300"""
    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")


async def fetch_responses_by_resume_id(user_id, vacancy_id: str, resume_id: str, created_at):
    """
    Возвращает отклик на вакансию с заданным resume_id, если найден.
    """

    url = f"{BASE_URL}/resumes/{resume_id}"
    # params = {
    #     "vacancy_id": vacancy_id,
    #     "order_by": "created_at",
    #     "page": 0,
    #     "per_page": 50
    # }
    print(resume_id)
    phone = "номер не доступен"
    resp = requests.get(url, headers=await get_headers(user_id))
    # print(">>> response  ", resp.text)
    if resp.status_code == 200:
        print("200")
        resume = resp.json()
        # print(f"data {resume}")
        contact_field = resume.get("contact")
        print(contact_field)
        try :
            for i in contact_field:
                if i.get("type").get("id") == "cell":
                    phone = i.get("value").get("formatted")
                    if i.get("preferred"):
                        break
        except Exception as ex:
            try:
                phone = ""
                for i in contact_field:
                    if i.get("type").get("id") == "cell":
                        phone += str(i.get("value").get("formatted")) + "\n"
                    else:
                        phone += str(i.get("value")) + "\n"
            except Exception as ex:
                if resume.get("contact"):
                    phone = str(resume.get("contact"))
                else:
                    phone = "номер не доступен"
        full_name = " ".join(filter(None, [
            resume.get("first_name"),
            resume.get("last_name")
        ]))
        print(full_name, created_at, phone)
        return [full_name, created_at, phone]

    return {
        "full_name": "неизвестно",
        "created_at": "..."
    }


# def get_new_responses(vacancy_id: int, last_update: datetime) -> List[Dict]:
#     """
#     Возвращает только новые отклики на вакансию с момента last_update.
#     """
#     all_responses = fetch_responses(vacancy_id)
#     return [
#         r for r in all_responses
#         if parse_hh_date(r["created_at"]) > last_update
#     ]


# def check_all_subscriptions(subscriptions):
#     """
#     Проверяет все вакансии и возвращает словарь с новыми откликами:
#     { vacancy_id: [response1, response2, ...], ... }
#     """
#     result = {}
#     for sub in subscriptions:
#         vid = sub.vacancy_id
#         try:
#             new = get_new_responses(vid, sub.last_update)
#             if new:
#                 result[vid] = new
#         except Exception as e:
#             print(f"[!] Ошибка при проверке {vid}: {e}")
#     return result

async def create_subscription(user_id: int, vacancy_id: str, again=True):
    async with aiohttp.ClientSession() as session:
        async with session.post(
                "https://api.hh.ru/webhook/subscriptions",
                json={
                    "actions": [
                        {
                            "settings": {
                                "vacancies_only_mine": True
                            },
                            "type": "NEW_NEGOTIATION_VACANCY"
                        }
                    ],
                    "url": "http://hhcheckbot.ru/sub"
                },
                headers=await get_headers(user_id)
        ) as resp:

            text = await resp.text()
            print(text)
            print("already_exist:", "already_exist" in str(text))
            if "already_exist" in str(text):
                async with aiohttp.ClientSession() as session2:
                    async with session2.get(
                            "https://api.hh.ru/webhook/subscriptions",
                            headers=await get_headers(user_id)
                    ) as resp2:
                        if resp2.status != 200:
                            raise Exception(f">>> Ошибка запроса подписок: {resp.status} {text}")
                        all_sub = (await resp2.json())["items"]
                        _ = await clear_subs()
                        for i in all_sub:
                            sub_id = i["id"]
                            from app.cancel import cancel_subscription
                            await cancel_subscription(sub_id, user_id)
                        if again:
                            return await create_subscription(user_id, vacancy_id, again=False)
            if resp.status != 201:
                raise Exception(f"Ошибка при создании подписки: {resp.status} {text}")

            data = await resp.json()
            return data["id"]


async def fetch_active_vacancies(user_id: int, page: int = 0, per_page: int = 50) -> Optional[List[Dict]]:
    """
    Асинхронно получает список активных вакансий работодателя через aiohttp.
    """
    from app.db import get_user_auth
    print(f"Fetching vacancies for user_id={user_id}")
    auth = await get_user_auth(user_id)
    if auth:
        print(auth.user_access_token, auth.user_employer_id)
        url = f"{BASE_URL}/employers/{auth.user_employer_id}/vacancies/active"
        params = {"page": page, "per_page": per_page}

        headers = await get_headers(user_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                text = await resp.text()
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])
                elif resp.status == 404:
                    return []
                else:
                    raise Exception(f"Не удалось получить вакансии: {resp.status} {text}")


async def process_queued_responses():
    clear = True
    queued = get_queued_responses()
    if not queued:
        print("Нет новых откликов в очереди.")
        return
    done = []
    print("есть новые отклики")
    for vacancy_id, resume_id, s_id, created_at in queued:
        if resume_id in done:
            continue
        print("v, r, si", vacancy_id, resume_id, s_id)
        data_result = get_user_ids_by_vacancy(vacancy_id)
        print(f"n+ids {data_result}")
        vacancy_name = data_result[0]
        user_ids = data_result[1]
        if not user_ids:
            # Удаление подписки, если нет подписчиков
            from app.cancel import cancel_subscription
            print("удаление ненужной подписки")
            await cancel_subscription(s_id, user_ids[0])
        try:
            print("чтение responses")
            response = await fetch_responses_by_resume_id(user_ids[0], vacancy_id, resume_id, created_at)
        #     responses = await fetch_responses(user_ids[0], vacancy_id)
        #     print(f"responses {responses}")
        #     response_data = next(
        #         (item for item in responses if item.get("resume", {}).get("id") == resume_id),
        #         None
        #     )
        #     print(f"response_data {response_data}")
        #     if not response_data:
        #         continue
        #
        #     name = response_data["resume"].get("first_name", "неизвестно")
        #     created = response_data.get("created_at", "неизвестно")
            name = response[0]
            created = response[1]
            phone = response[2]
            print(name, created)
            if phone != "+7 (939) 731-38-36":
                for user_id in user_ids:
                    print(f"notification send to {user_id}")
                    await send_notification(user_id, vacancy_id, vacancy_name, name, created, phone)
                    done += [resume_id]
                    remove_queued_response(resume_id)

                    if user_id == admin_id:
                        await send_notification(str(1640452697), vacancy_id, vacancy_name, name, created, phone)
        #
        except Exception as e:
            clear = False
            print(f"Ошибка при обработке отклика по {vacancy_id}: {e}")
    if clear:
        # clear_queued_responses()
        print("Очередь откликов очищена")
    else:
        print("Ошибка очищения откликов")


async def send_notification(chat_id: str, vacancy_id: str, vc_name, name, creared_at, phone):
    from app.the_bot import bot
    date_format = "%d.%m.%y %H:%M"
    created = datetime.strftime(creared_at, date_format)
    if not name:
        name = "имя неизвестно"
    msg = (f"новый отклик! #{'_'.join(vc_name.split())}\n"
           f"{created}\n"
           f"{name}\n"
           f"{phone}")
    await bot.send_message(chat_id, msg)


# def fetch_vacancy(vacancy_id: int) -> Dict:
#     resp = requests.get(url, headers=headers)
#     if resp.status_code != 200:
#         raise Exception(f"Не удалось получить вакансию {vacancy_id}: {resp.status_code}")
#     return resp.json()

# async def fetch_response_items_from_collection(url: str, user_id) -> List[Dict]:
#     """
#     Получает список откликов по ссылке из поля collection.url
#     """
#     response = requests.get(url, headers=await get_headers(user_id), params={
#         "page": 0,
#         "per_page": 20,
#         "order_by": "id",
#     })
#     response.raise_for_status()
#     return response.json().get("items", [])


async def fetch_responses(user_id, vacancy_id: str):
    url = "https://api.hh.ru/negotiations/response"
    headers = await get_headers(user_id)
    params = {
        "vacancy_id": vacancy_id,
        "page": 0,
        "per_page": 50,
        "order_by": "created_at"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                raise Exception(f"Не удалось получить отклики: {response.status}")
            data = await response.json()

            if not data.get("items"):
                return []

            latest_response = data["items"][0]
            resume = latest_response.get("resume", {})
            full_name = " ".join(filter(None, [
                resume.get("first_name"),
                resume.get("last_name")
            ]))
            created_at = latest_response.get("created_at")

            return [{
                "full_name": full_name,
                "created_at": created_at
            }]
