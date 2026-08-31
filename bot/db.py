"""PostgreSQL qatlami (asyncpg)."""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

from . import config

log = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# Profilda yangilanishi mumkin bo'lgan ustunlar — SQL ga faqat shular tushadi.
PROFILE_FIELDS = (
    "track",
    "goal",
    "deadline",
    "daily_minutes",
    "level",
    "plan",
    "current_topic",
    "onboarding_done",
)


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Ma'lumotlar bazasi hali ochilmagan (init chaqirilmagan).")
    return _pool


async def init() -> None:
    """Pool ochadi va sxemani qo'llaydi (idempotent)."""
    global _pool
    _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=10)
    async with _pool.acquire() as conn:
        await conn.execute(config.SCHEMA_SQL)
    log.info("Ma'lumotlar bazasi tayyor.")


async def close() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_or_create_student(
    telegram_id: int, username: str | None, first_name: str | None
) -> asyncpg.Record:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO students (telegram_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO UPDATE
                SET username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
            RETURNING *, (xmax = 0) AS is_new
            """,
            telegram_id,
            username,
            first_name,
        )
    return row


async def get_student(telegram_id: int) -> asyncpg.Record | None:
    async with pool().acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM students WHERE telegram_id = $1", telegram_id
        )


async def update_profile(telegram_id: int, updates: dict[str, Any]) -> None:
    """Faqat bo'sh bo'lmagan, ruxsat etilgan maydonlarni yangilaydi."""
    clean = {
        key: value
        for key, value in updates.items()
        if key in PROFILE_FIELDS and value not in (None, "")
    }
    if not clean:
        return

    assignments = ", ".join(f"{key} = ${i}" for i, key in enumerate(clean, start=2))
    async with pool().acquire() as conn:
        await conn.execute(
            f"UPDATE students SET {assignments}, updated_at = now() WHERE telegram_id = $1",
            telegram_id,
            *clean.values(),
        )


async def add_message(telegram_id: int, role: str, content: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (telegram_id, role, content) VALUES ($1, $2, $3)",
            telegram_id,
            role,
            content,
        )


async def recent_messages(telegram_id: int, limit: int) -> list[dict[str, str]]:
    """Oxirgi xabarlar, vaqt bo'yicha to'g'ri tartibda."""
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content FROM (
                SELECT id, role, content
                FROM messages
                WHERE telegram_id = $1
                ORDER BY id DESC
                LIMIT $2
            ) AS recent
            ORDER BY id ASC
            """,
            telegram_id,
            limit,
        )
    history = [{"role": row["role"], "content": row["content"]} for row in rows]

    # Messages API birinchi xabar 'user' bo'lishini talab qiladi.
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


async def user_message_count(telegram_id: int) -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM messages WHERE telegram_id = $1 AND role = 'user'",
            telegram_id,
        )


async def upsert_topic(
    telegram_id: int, topic: str, status: str, note: str | None = None
) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO topics (telegram_id, topic, status, note)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id, topic) DO UPDATE
                SET status = EXCLUDED.status,
                    note = COALESCE(EXCLUDED.note, topics.note),
                    updated_at = now()
            """,
            telegram_id,
            topic.strip()[:200],
            status,
            note,
        )


async def list_topics(telegram_id: int) -> list[asyncpg.Record]:
    async with pool().acquire() as conn:
        return await conn.fetch(
            """
            SELECT topic, status, note
            FROM topics
            WHERE telegram_id = $1
            ORDER BY updated_at ASC
            """,
            telegram_id,
        )


async def reset_student(telegram_id: int) -> None:
    """Suhbat tarixi, mavzular va profilni tozalaydi (o'quvchi yozuvi qoladi)."""
    async with pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM messages WHERE telegram_id = $1", telegram_id)
            await conn.execute("DELETE FROM topics WHERE telegram_id = $1", telegram_id)
            await conn.execute(
                """
                UPDATE students
                SET track = NULL, goal = NULL, deadline = NULL, daily_minutes = NULL,
                    level = NULL, plan = NULL, current_topic = NULL,
                    onboarding_done = FALSE, updated_at = now()
                WHERE telegram_id = $1
                """,
                telegram_id,
            )
