import os
from dotenv import load_dotenv

load_dotenv()

API_ID    = int(os.environ["TELEGRAM_API_ID"])
API_HASH  = os.environ["TELEGRAM_API_HASH"]
PHONE     = os.environ["TELEGRAM_PHONE"]
BOT_TOKEN    = os.environ["BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# The single AI model used to classify every message (override in .env if you like).
MODEL = os.environ.get("OPENAI_MODEL", "o4-mini")
