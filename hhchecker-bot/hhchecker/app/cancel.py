import aiohttp


async def cancel_subscription(subscription_id: str, user_id):

    print(f"отменяем подписку {subscription_id}")
    from app.auth import get_headers
    async with aiohttp.ClientSession() as session:
        async with session.delete(
                f"https://api.hh.ru/webhook/subscriptions/{subscription_id}",
                headers=await get_headers(user_id)
        ) as resp:
            if resp.status != 204:
                text = await resp.text()
                raise Exception(f"Не удалось удалить подписку: {resp.status} {text}")