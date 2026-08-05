from telethon import TelegramClient
from config import API_ID, API_HASH

# Runs as your Telegram account — used to read groups, fetch messages
user_client = TelegramClient("smart_telegram_session", API_ID, API_HASH)

# The bot — receives your commands
bot_client = TelegramClient("bot_session", API_ID, API_HASH)
