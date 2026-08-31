"""Sozlamalar: .env fayldan o'qiladi."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} o'rnatilmagan. .env.example dan nusxa olib .env yarating."
        )
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
DATABASE_URL = _require("DATABASE_URL")

# Anthropic kaliti SDK tomonidan muhitdan o'qiladi; bu yerda faqat tekshiramiz.
_require("ANTHROPIC_API_KEY")

MODEL = os.getenv("MATUSTOZ_MODEL", "claude-opus-5")
EFFORT = os.getenv("MATUSTOZ_EFFORT", "high")
MAX_TOKENS = int(os.getenv("MATUSTOZ_MAX_TOKENS", "16000"))

# Har so'rovda modelga uzatiladigan oxirgi xabarlar soni.
HISTORY_LIMIT = int(os.getenv("MATUSTOZ_HISTORY_LIMIT", "40"))

# Profil (maqsad/daraja/reja) har necha xabarda bir yangilansin.
PROFILE_REFRESH_EVERY = int(os.getenv("MATUSTOZ_PROFILE_REFRESH_EVERY", "4"))

SYSTEM_PROMPT = (BASE_DIR / "prompts" / "system_prompt.md").read_text(encoding="utf-8")
SCHEMA_SQL = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")

WELCOME_MESSAGE = (
    "Assalomu alaykum! 👋 Men — MatUstoz, sening shaxsiy matematika repetitoringman.\n\n"
    "Matematikani mutlaqo bilmasang ham xavotir olma — men seni noldan, sabr bilan "
    "o'rgataman. Maqsad — sen matematikadan qo'rqmaydigan, aksincha uni yaxshi "
    "ko'radigan odam bo'lishing.\n\n"
    "Boshlashdan oldin seni bir oz tanishtirib olay.\n"
    "Ayt-chi, nima uchun matematika o'rganmoqchisan?\n\n"
    "— Maktab yoki kollej imtihoniga tayyorlanyapsanmi?\n"
    "— Milliy sertifikat olmoqchimisan?\n"
    "— SAT topshirmoqchimisan?\n"
    "— Yoki shunchaki matematikani noldan puxta o'rganmoqchimisan?"
)

HELP_MESSAGE = (
    "📚 MatUstoz buyruqlari:\n\n"
    "/start — boshlash yoki qaytib kelish\n"
    "/reja — o'quv rejangni ko'rish\n"
    "/progress — qaysi mavzularni o'tganingni ko'rish\n"
    "/reset — hammasini o'chirib, noldan boshlash\n"
    "/help — shu ro'yxat\n\n"
    "Qolgan vaqtda shunchaki yozaver — savol ber, misol yubor, "
    "tushunmagan joyingni ayt. Men yoningdaman 🎯"
)
