"""Telegram handlerlari."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict

import anthropic
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from . import config, db, tutor

log = logging.getLogger(__name__)

# Telegram xabar chegarasi 4096; zaxira bilan bo'lamiz.
CHUNK_LIMIT = 3800
# Tahrirlash chastotasi (Telegram tez-tez tahrirlashni cheklaydi).
EDIT_INTERVAL = 1.6

THINKING_PLACEHOLDER = "✍️ o'ylayapman..."

# Har bir o'quvchi uchun bitta so'rov — xabarlar aralashib ketmasin.
_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def split_message(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Uzun matnni Telegram xabarlariga bo'ladi, imkon boricha qator chegarasidan."""
    chunks: list[str] = []
    rest = text.strip()

    while len(rest) > limit:
        window = rest[:limit]
        split_at = window.rfind("\n\n")
        if split_at < limit // 2:
            split_at = window.rfind("\n")
        if split_at < limit // 2:
            split_at = window.rfind(" ")
        if split_at <= 0:
            split_at = limit
        chunks.append(rest[:split_at].strip())
        rest = rest[split_at:].strip()

    if rest:
        chunks.append(rest)
    return chunks or ["..."]


class StreamEditor:
    """Oqim kelayotgan matnni bitta xabarga sekin-asta yozib boradi."""

    def __init__(self, bot, chat_id: int, message_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self._last_edit = 0.0
        self._last_text = ""

    async def _edit(self, text: str) -> None:
        if text == self._last_text or not text.strip():
            return
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id, message_id=self.message_id, text=text
            )
            self._last_text = text
        except BadRequest as exc:
            if "not modified" not in str(exc).lower():
                log.debug("Xabarni tahrirlab bo'lmadi: %s", exc)

    async def update(self, text: str) -> None:
        now = time.monotonic()
        if now - self._last_edit < EDIT_INTERVAL:
            return
        self._last_edit = now
        # Oqim davomida faqat boshini ko'rsatamiz; to'lig'i oxirida bo'lib yuboriladi.
        await self._edit(text[:CHUNK_LIMIT])

    async def finish(self, text: str) -> None:
        chunks = split_message(text)
        await self._edit(chunks[0])
        for chunk in chunks[1:]:
            await self.bot.send_message(chat_id=self.chat_id, text=chunk)


async def _keep_typing(bot, chat_id: int) -> None:
    try:
        while True:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            await asyncio.sleep(4.5)
    except asyncio.CancelledError:
        pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    student = await db.get_or_create_student(user.id, user.username, user.first_name)

    if student["is_new"] or not await db.user_message_count(user.id):
        await update.message.reply_text(config.WELCOME_MESSAGE)
        await db.add_message(user.id, "assistant", config.WELCOME_MESSAGE)
        return

    name = student["first_name"] or "do'stim"
    topic = student["current_topic"]
    davomi = f"\n\nOxirgi marta {topic} ustida ishlayotgan edik." if topic else ""
    await update.message.reply_text(
        f"Xush kelibsan, {name}! 👋{davomi}\n\nDavom etamizmi? Yozaver."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(config.HELP_MESSAGE)


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    student = await db.get_student(update.effective_user.id)
    if not student or not student["plan"]:
        await update.message.reply_text(
            "Hali reja tuzilmagan. Maqsading, vaqting va darajangni aytsang — "
            "sen uchun aniq reja tuzaman. /start deb boshlaymizmi?"
        )
        return
    for chunk in split_message("📚 SENING REJANG\n\n" + student["plan"]):
        await update.message.reply_text(chunk)


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    topics = await db.list_topics(user_id)

    if not topics:
        await update.message.reply_text(
            "Hozircha o'tilgan mavzu yo'q. Boshlaymizmi? 🎯"
        )
        return

    done = sum(1 for t in topics if t["status"] == "tugallandi")
    percent = round(done * 100 / len(topics))
    lines = [f"📊 PROGRESS: {len(topics)} mavzudan {done} tasi tugallandi — {percent}%\n"]
    for t in topics:
        lines.append(f"{tutor.STATUS_LABELS.get(t['status'], t['status'])} — {t['topic']}")

    student = await db.get_student(user_id)
    if student and student["current_topic"]:
        lines.append(f"\nHozirgi mavzu: {student['current_topic']}")

    for chunk in split_message("\n".join(lines)):
        await update.message.reply_text(chunk)


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Ha, o'chir", callback_data="reset:yes"),
                InlineKeyboardButton("Yo'q", callback_data="reset:no"),
            ]
        ]
    )
    await update.message.reply_text(
        "Rostdan ham hammasini o'chiramizmi? Suhbat tarixing, rejang va "
        "progressing yo'qoladi.",
        reply_markup=keyboard,
    )


async def reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "reset:no":
        await query.edit_message_text("Yaxshi, hammasi joyida qoldi. Davom etamiz 👍")
        return

    await db.reset_student(query.from_user.id)
    await query.edit_message_text("Tozalandi. Noldan boshlaymiz!")
    await context.bot.send_message(chat_id=query.message.chat_id, text=config.WELCOME_MESSAGE)
    await db.add_message(query.from_user.id, "assistant", config.WELCOME_MESSAGE)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    async with _locks[user.id]:
        await db.get_or_create_student(user.id, user.username, user.first_name)
        student = dict(await db.get_student(user.id))
        history = await db.recent_messages(user.id, config.HISTORY_LIMIT)
        topics = [dict(t) for t in await db.list_topics(user.id)]

        placeholder = await update.message.reply_text(THINKING_PLACEHOLDER)
        editor = StreamEditor(context.bot, update.effective_chat.id, placeholder.message_id)
        typing = asyncio.create_task(_keep_typing(context.bot, update.effective_chat.id))

        try:
            reply = await tutor.stream_reply(
                student, topics, history, user_text, editor.update
            )
        except anthropic.RateLimitError:
            await editor.finish(
                "Hozir juda ko'p so'rov bor 😅 Bir daqiqadan keyin yana yozib ko'r."
            )
            return
        except anthropic.APIError as exc:
            log.exception("Claude so'rovi muvaffaqiyatsiz: %s", exc)
            await editor.finish(
                "Kechirasan, texnik nosozlik bo'ldi. Biroz kutib, savolingni "
                "qaytadan yuborasanmi?"
            )
            return
        finally:
            typing.cancel()

        if not reply:
            await editor.finish("Kechirasan, javob chiqmadi. Yana bir bor yozib ko'rasanmi?")
            return

        await editor.finish(reply)

        await db.add_message(user.id, "user", user_text)
        await db.add_message(user.id, "assistant", reply)
        await _refresh_profile(user.id, student, user_text, reply)


async def _refresh_profile(
    user_id: int, student: dict, user_text: str, reply: str
) -> None:
    """Tanishuv tugamaguncha har xabarda, keyin vaqti-vaqti bilan profilni yangilaydi."""
    count = await db.user_message_count(user_id)
    if student.get("onboarding_done") and count % config.PROFILE_REFRESH_EVERY != 0:
        return

    data = await tutor.extract_profile(student, user_text, reply)
    if not data:
        return

    updates = {
        "track": data.get("track"),
        "goal": data.get("goal"),
        "deadline": data.get("deadline"),
        "level": data.get("level"),
        "plan": data.get("plan"),
        "current_topic": data.get("current_topic"),
    }

    minutes = str(data.get("daily_minutes") or "").strip()
    if minutes.isdigit():
        updates["daily_minutes"] = int(minutes)

    if data.get("onboarding_done"):
        updates["onboarding_done"] = True

    await db.update_profile(user_id, updates)

    for item in data.get("topics") or []:
        topic = (item.get("topic") or "").strip()
        status = item.get("status")
        if topic and status in tutor.STATUS_LABELS:
            await db.upsert_topic(user_id, topic, status, (item.get("note") or "").strip() or None)


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hozircha faqat matnni o'qiy olaman 🙂 Misolni matn ko'rinishida yozib "
        "yuborasanmi? Masalan: 2x + 5 = 15"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Handlerda xato:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Kutilmagan xato yuz berdi. Yana bir bor urinib ko'rasanmi?"
            )
        except Exception:  # noqa: BLE001 - xabar yuborib bo'lmasa, jim qolamiz
            pass
