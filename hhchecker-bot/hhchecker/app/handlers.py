from datetime import datetime

from aiogram import Dispatcher, types, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command



import os

from app.db import get_subscription_id_by_vacancy, add_user_subscription, subscription_exists_for_vacancy
from app.hh_api import create_subscription

router = Router()


@router.message(Command("add"))
async def cmd_add(message: Message):
    from app.db import get_user_subscriptions
    from app.hh_api import fetch_active_vacancies
    user_id = message.from_user.id
    # Получаем все опубликованные вакансии
    vacancies = await fetch_active_vacancies(user_id)
    # vacancies = [{"id":0}, {"id":1}, {"id":2}]
    # Существующие подписки этого пользователя
    existing = {sub.vacancy_id for sub in get_user_subscriptions(user_id)}
    buttons = []
    if vacancies:
        for v in vacancies:
            if str(v["id"]) not in existing:
                buttons.append(InlineKeyboardButton(text=f"{v['id']}: {v['name']}",
                                                    callback_data=f"subscribe^{v['id']}^{v['name']}"))

    # Формируем кнопки только для новых вакансий
    if buttons:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])
        await message.answer(
            "Выберите вакансию для подписки:",
            reply_markup=keyboard
        )
    else:
        await message.answer("Вы уже подписаны на все опубликованные вакансии.")


@router.callback_query(F.data.startswith("subscribe^"))
async def process_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    vacancy_id = str(callback.data.split("^")[1])
    vacancy_name = str(callback.data.split("^")[2])
    if not subscription_exists_for_vacancy(vacancy_id):
        subscription_id = await create_subscription(user_id, vacancy_id)
    else:
        subscription_id = get_subscription_id_by_vacancy(vacancy_id)
    add_user_subscription(user_id, vacancy_id, subscription_id, vacancy_name)
    await callback.message.edit_text(f" Вы подписались на вакансию #{vacancy_id}: {vacancy_name}")
    await callback.answer()


@router.message(Command("list"))
async def cmd_list(message: Message):
    from app.db import get_user_subscriptions
    text_lines = ["Ваши подписки:\n"]
    user_id = message.from_user.id
    subs = get_user_subscriptions(user_id)
    for sub in subs:
        name = sub.vacancy_name
        text_lines.append(f"• {sub.vacancy_id}: {name}")
    if not subs:
        return await message.answer("У вас пока нет подписок. Используйте /add для добавления.")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"Удалить", callback_data=f"remove_true")]])
        await message.answer("\n".join(text_lines), reply_markup=kb)

    # noinspection PyShadowingNames
    @router.callback_query(F.data.startswith("remove_true"))
    async def remove(callback: CallbackQuery):
        pre_kb = []
        kb2 = InlineKeyboardMarkup(inline_keyboard=[[]])
        for sub in subs:
            pre_kb += [InlineKeyboardButton(text=f"Удалить {sub.vacancy_name}",
                                            callback_data=f"remove_confirm^{sub.vacancy_id}^{sub.vacancy_name}")]
        kb2.inline_keyboard.append(pre_kb)
        await callback.message.edit_reply_markup(reply_markup=kb2)

    @router.callback_query(F.data == "remove_cancel")
    async def cancel_remove(callback: CallbackQuery):
        await callback.message.edit_text("\n".join(text_lines), reply_markup=kb)


@router.callback_query(F.data.startswith("remove^"))
async def process_remove(callback: CallbackQuery):
    from app.db import get_user_subscriptions,  remove_subscription
    vacancy_id = str(callback.data.split("^")[1])
    vc_name = int(callback.data.split("^")[2])
    user_id = callback.from_user.id
    sub_id = get_subscription_id_by_vacancy(vacancy_id)
    await remove_subscription(user_id, vacancy_id, sub_id)

    text_lines = ["Ваши подписки:\n"]
    subs = get_user_subscriptions(user_id)
    for sub in subs:
        name = sub.vacancy_name
        text_lines.append(f"• {sub.vacancy_id}: {name}")
    if not subs:
        await callback.message.edit_text("Вес подписки удалены. Используйте /add для добавления.")
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"Удалить", callback_data=f"remove_true")]])
        await callback.message.edit_text("\n".join(text_lines), reply_markup=kb)
    await callback.message.answer(f"❌ Вы отписались от вакансии #{vacancy_id}: {vc_name}")


@router.callback_query(F.data.startswith("remove_confirm^"))
async def confirm_remove(callback: CallbackQuery):
    vacancy_id = int(callback.data.split("^")[1])
    vacancy_name = int(callback.data.split("^")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data=f"remove^{vacancy_id}^{vacancy_name}"),
            InlineKeyboardButton(text="Нет", callback_data="remove_cancel")
        ]
    ])
    await callback.message.edit_text(
        f"Вы уверены, что хотите отписаться от вакансии #{vacancy_id}: {vacancy_name}?",
        reply_markup=kb
    )
    await callback.answer()


@router.message()
async def cmd_start(message: Message):
    await message.answer(
        f"Я бот для отслеживания откликов на ваши вакансии.\n\n"
        f"Команды:\n"
        f"/add — подписаться на вакансии\n"
        f"/list — показать текущие подписки или отписаться\n")


def register_handlers(dp: Dispatcher):
    dp.message.register(cmd_start, Command(commands=["start"]))
    dp.message.register(cmd_add, Command(commands=["add"]))
    dp.message.register(cmd_list, Command(commands=["list"]))
