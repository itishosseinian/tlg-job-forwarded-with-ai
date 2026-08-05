import asyncio
from clients import user_client, bot_client
from config import PHONE, BOT_TOKEN
import bot
import forwarder


async def main() -> None:
    await user_client.start(phone=PHONE)
    await bot_client.start(bot_token=BOT_TOKEN)

    me = await user_client.get_me()
    print(f"✅ Userbot    : {me.first_name} (@{me.username})  id={me.id}")

    bot_me = await bot_client.get_me()
    print(f"✅ Bot        : @{bot_me.username}")

    bot.register_all(admin_id=me.id)
    forwarder.register()

    print(f"\nReady — open @{bot_me.username} on Telegram and tap /start.\n")

    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected(),
    )


if __name__ == "__main__":
    asyncio.run(main())
