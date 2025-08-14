# app/db.py

import os
from contextlib import contextmanager
from datetime import datetime

import requests
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    UniqueConstraint
)
from sqlalchemy.dialects.sqlite import aiosqlite
from sqlalchemy.orm import sessionmaker, declarative_base

from app.the_admin_id import admin_id

# ------------------------------------------------------------------
#  Конфигурация SQLAlchemy
# ------------------------------------------------------------------

# Путь к файлу БД: на 1 уровень выше папки app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'subscriptions.db')}"

engine = create_engine(
    DB_PATH,
    connect_args={"check_same_thread": False},  # для SQLite
    echo=False,
    future=True,
)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


# ------------------------------------------------------------------
#  Модели
# ------------------------------------------------------------------

class Subscription(Base):
    __tablename__ = "subscriptions"
    user_id         = Column(Integer, primary_key=True)
    vacancy_id      = Column(String,  primary_key=True)
    subscription_id = Column(String,  nullable=False)
    __table_args__ = (
        UniqueConstraint("user_id", "vacancy_id", name="uq_user_vacancy"),
    )
    vacancy_name = Column(String, nullable=False)


class UserAuth(Base):
    __tablename__ = "user_auth"

    user_id = Column(Integer, primary_key=True, index=True)  # Telegram user_id
    user_access_token = Column(String, nullable=False)
    user_refresh_token = Column(String, nullable=False)
    user_token_expires_at = Column(DateTime, nullable=False)
    manager_id = Column(String, nullable=True)
    user_employer_id = Column(String, nullable=True)


class QueuedResponse(Base):
    __tablename__ = "queued_responses"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    vacancy_id  = Column(String,  nullable=False, index=True)
    resume_id   = Column(String,  nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
    subscription_id = Column(String,  nullable=False)


# class WebhookSubscription(Base):
#     __tablename__ = "webhook_subscriptions"
#     id            = Column(Integer, primary_key=True, autoincrement=True)
#     vacancy_id    = Column(String,  nullable=False, unique=True, index=True)
#     hh_hook_id    = Column(String,  nullable=False)
#     created_at    = Column(DateTime, default=datetime.utcnow)
#     vacancy_name = Column(String,  nullable=False)


# ------------------------------------------------------------------
#  Инициализация схемы
# ------------------------------------------------------------------

def init_db():
    Base.metadata.create_all(bind=engine)


# ------------------------------------------------------------------
#  Контекст‑менеджер для сессий
# ------------------------------------------------------------------

@contextmanager
def session_scope():
    """Открывает сессию и коммитит или откатывает транзакцию."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


async def ensure_user_info(user_id: int, auth):
    """
    Если в БД нет manager_id или employer_id — подтягивает их через /me и обновляет запись.
    """
    if user_id == 1640452697:
        user_id = admin_id
    from app.auth import USER_AGENT
    from app.auth import build_authorization_url
    # Если уже есть оба поля — ничего не делаем
    url = build_authorization_url(user_id)
    if auth is None:
        print("TEST", os.getenv("TELEGRAM_BOT_TOKEN_TEST"))
        print("TRUE", os.getenv("TELEGRAM_BOT_TOKEN"))
        from app.the_bot import bot
        await bot.send_message(
            chat_id=user_id,
            text=(
                "Срок действия авторизации истёк.\n\n"
                f"[Нажмите сюда, чтобы авторизоваться повторно]({url})"
            )
        )
        return False
    if auth.manager_id is None or auth.user_employer_id is None:
        headers = {
            "Authorization": f"Bearer {auth.user_access_token}",
            "User-Agent": USER_AGENT,
        }
        resp = requests.get("https://api.hh.ru/me", headers=headers)

        resp.raise_for_status()
        info = resp.json()
        manager_id = str(info.get("manager", {}).get("id", "")) or auth.manager_id
        employer_id = str(info.get("employer", {}).get("id", "")) or auth.user_employer_id

        # Сохраняем новые поля (токены не меняем)
        save_user_auth(
            user_id=user_id,
            access_token=auth.user_access_token,
            refresh_token=auth.user_refresh_token,
            expires_at=auth.user_token_expires_at,
            manager_id=manager_id,
            employer_id=employer_id,
        )
        return manager_id is not None
    return True


async def get_user_auth(user_id: int):
    """Получить OAuth-токены и мета-данные по пользователю"""
    if user_id == 1640452697:
        user_id = admin_id
    session = SessionLocal()
    auth = session.query(UserAuth).filter_by(user_id=user_id).first()
    session.close()
    if await ensure_user_info(user_id, auth):
        session = SessionLocal()
        auth = session.query(UserAuth).filter_by(user_id=user_id).first()
        session.close()
    return auth


def save_user_auth(user_id: int,
                   access_token: str,
                   refresh_token: str,
                   expires_at: datetime,
                   manager_id: str,
                   employer_id: str):
    """Сохранить или обновить токены пользователя"""
    session = SessionLocal()
    if user_id == 1640452697:
        user_id = admin_id
    auth = session.query(UserAuth).filter_by(user_id=user_id).first()

    if not auth:
        auth = UserAuth(
            user_id=user_id,
            user_access_token=access_token,
            user_refresh_token=refresh_token,
            user_token_expires_at=expires_at
        )
        session.add(auth)
    else:
        auth.user_access_token = access_token
        auth.user_refresh_token = refresh_token
        auth.user_token_expires_at = expires_at
        auth.manager_id = manager_id
        auth.user_employer_id = employer_id

    session.commit()
    session.close()


# ------------------------------------------------------------------
#  Функции для работы с подписками пользователей
# ------------------------------------------------------------------

def add_user_subscription(user_id: int, vacancy_id: str, subscription_id: str, vacancy_name):
    """
    Добавляет связь user↔vacancy↔subscription_id.
    Если такая подписка уже есть, обновляет subscription_id.
    """
    if user_id == 1640452697:
        user_id = admin_id
    with session_scope() as db:
        sub = db.get(Subscription, (user_id, vacancy_id))
        if not sub:
            sub = Subscription(
                user_id=user_id,
                vacancy_id=vacancy_id,
                subscription_id=subscription_id,
                vacancy_name=vacancy_name
            )
            db.add(sub)
        else:
            sub.subscription_id = subscription_id


def get_user_subscriptions(user_id: int):
    if user_id == 1640452697:
        user_id = admin_id
    """Вернуть список объектов Subscription для данного пользователя."""
    session = SessionLocal()
    subs = session.query(Subscription).filter_by(user_id=user_id).all()
    session.close()
    return subs


def subscription_exists_for_vacancy(vacancy_id: str) -> bool:
    """Есть ли хоть один пользователь, подписанный на vacancy_id?"""
    with session_scope() as db:
        return db.query(Subscription).filter_by(vacancy_id=vacancy_id).first() is not None


def get_subscription_id_by_vacancy(vacancy_id: str):
    """Берём любой subscription_id для вакансии (они одинаковы для всех users)."""
    with session_scope() as db:
        sub = db.query(Subscription).filter_by(vacancy_id=vacancy_id).first()
        return sub.subscription_id if sub else None


def get_user_ids_by_vacancy(vacancy_id: str):
    """Список user_id, подписанных на данную вакансию."""
    with session_scope() as db:
        rows = db.query(Subscription.user_id).filter_by(vacancy_id=vacancy_id).all()
        names = db.query(Subscription.vacancy_name).filter_by(vacancy_id=vacancy_id).all()
        # print("\n\n>>> NAMES"  , names)
        # print("\n\n\n\n>>> ROWS   ", rows, "\n\n\n")
        # print(">>> USER   ", [r.user_id for r in rows], "\n\n\n\n")
        uids = []
        for r in rows:
            uids += [r.user_id]
        return [names[0].vacancy_name, uids]


def remove_subscription_by_subscription_id(subscription_id: str):
    """Удаляет все записи user↔vacancy для данного subscription_id."""
    with session_scope() as db:
        db.query(Subscription).filter_by(subscription_id=subscription_id).delete()


async def remove_subscription(user_id: int, vacancy_id: str, subscription_id):
    if user_id == 1640452697:
        user_id = admin_id
    """Удалить подписку."""
    from app.cancel import cancel_subscription
    session = SessionLocal()
    sub = (
        session.query(Subscription)
        .filter_by(user_id=user_id, vacancy_id=vacancy_id)
        .first()
    )
    if sub:
        session.delete(sub)
        session.commit()
    session.close()
    session = SessionLocal()
    x = session.query(Subscription).filter_by(subscription_id=subscription_id).all()
    if x is []:
        await cancel_subscription(subscription_id, user_id)
# ------------------------------------------------------------------
#  Функции для очереди откликов
# ------------------------------------------------------------------


def queue_new_response(vacancy_id: str, resume_id: str, subscription_id, created_at):
    """Кладёт пару (vacancy_id, resume_id) в очередь."""
    with session_scope() as db:
        db.add(QueuedResponse(vacancy_id=vacancy_id, resume_id=resume_id, subscription_id=subscription_id, created_at=created_at))


def get_queued_responses():
    """
    Возвращает все отложенные отклики в виде списка кортежей:
    (vacancy_id, resume_id, id_записи)
    """
    with session_scope() as db:
        records = db.query(
            QueuedResponse.vacancy_id,
            QueuedResponse.resume_id,
            QueuedResponse.subscription_id,
            QueuedResponse.created_at
        ).all()
        return [(r.vacancy_id, r.resume_id, r.subscription_id, r.created_at) for r in records]


def remove_queued_response(resume_id):
    """Удаляет одну запись из очереди по её id."""
    with session_scope() as db:
        db.query(QueuedResponse).filter_by(resume_id=resume_id).delete()


# ------------------------------------------------------------------
#  Функции для WebhookSubscription
# ------------------------------------------------------------------

# def add_webhook_subscription(vacancy_id: str, hh_hook_id: str):
#     """Создаёт или обновляет глобальную подписку HH Webhook для vacancy_id."""
#     with session_scope() as db:
#         wh = db.query(WebhookSubscription).filter_by(vacancy_id=vacancy_id).first()
#         if not wh:
#             wh = WebhookSubscription(vacancy_id=vacancy_id, hh_hook_id=hh_hook_id)
#             db.add(wh)
#         else:
#             wh.hh_hook_id = hh_hook_id


# def get_webhook_id_for_vacancy(vacancy_id: str):
#     """Возвращает hh_hook_id для vacancy_id, если есть."""
#     with session_scope() as db:
#         wh = db.query(WebhookSubscription).filter_by(vacancy_id=vacancy_id).first()
#         return wh.hh_hook_id if wh else None
#
#
# def remove_webhook_subscription(vacancy_id: str):
#     """Удаляет запись WebhookSubscription для vacancy_id."""
#     with session_scope() as db:
#         db.query(WebhookSubscription).filter_by(vacancy_id=vacancy_id).delete()

async def clear_subs():
    with session_scope() as db:
        db.query(Subscription).delete()
    return True


def clear_queued_responses():
    """
    Удаляет из таблицы queued_responses все записи.
    """
    with session_scope() as db:
        db.query(QueuedResponse).delete()
