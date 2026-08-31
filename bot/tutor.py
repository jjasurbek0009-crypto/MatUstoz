"""Claude qatlami: javob oqimi (streaming) va o'quvchi profilini yangilash."""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

import anthropic

from . import config

log = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic()

# Server tomonidagi zaxira model (refusal bo'lganda). Agar akkauntda beta yoqilmagan
# bo'lsa, birinchi xatodan keyin o'chiriladi va oddiy so'rov yuboriladi.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
_fallbacks_enabled = True

# O'quvchi holatini suhbat oxirida `role: "system"` xabari sifatida yuboramiz —
# shunda keshlangan prefiks buzilmaydi. Model buni qo'llamasa, holat oddiy user
# xabariga qo'shib yuboriladi.
_system_role_supported = True

STATUS_LABELS = {
    "tugallandi": "✅ tugallandi",
    "jarayonda": "🔄 jarayonda",
    "qiynalyapti": "⚠️ qiynalyapti",
}

# Tizim promptini keshlaymiz — u hech qachon o'zgarmaydi, shuning uchun
# har so'rovda qayta hisoblanmaydi (~90% arzonroq kirish tokenlari).
SYSTEM_BLOCKS: list[dict[str, Any]] = [
    {
        "type": "text",
        "text": config.SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }
]

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "track": {
            "type": "string",
            "enum": ["", "poydevor", "imtihon", "milliy", "sat"],
            "description": "O'quvchi tanlagan yo'nalish. Noma'lum bo'lsa bo'sh satr.",
        },
        "goal": {"type": "string", "description": "Maqsad, o'quvchining so'zi bilan."},
        "deadline": {"type": "string", "description": "Muddat, masalan '2 oy' yoki '15-may'."},
        "daily_minutes": {
            "type": "string",
            "description": "Kuniga necha daqiqa shug'ullanadi, faqat raqam. Noma'lum bo'lsa bo'sh satr.",
        },
        "level": {
            "type": "string",
            "enum": ["", "nol", "boshlangich", "orta", "yaxshi"],
            "description": "Hozirgi matematik daraja.",
        },
        "plan": {
            "type": "string",
            "description": "Tuzilgan o'quv rejasining to'liq matni. Yangi reja tuzilmagan bo'lsa bo'sh satr.",
        },
        "current_topic": {"type": "string", "description": "Hozir o'tilayotgan mavzu."},
        "onboarding_done": {
            "type": "boolean",
            "description": "Maqsad, vaqt va daraja — uchalasi ham aniq bo'lsa true.",
        },
        "topics": {
            "type": "array",
            "description": "Shu suhbatda holati o'zgargan mavzular. O'zgarish bo'lmasa bo'sh ro'yxat.",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["jarayonda", "tugallandi", "qiynalyapti"],
                    },
                    "note": {"type": "string"},
                },
                "required": ["topic", "status", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "track",
        "goal",
        "deadline",
        "daily_minutes",
        "level",
        "plan",
        "current_topic",
        "onboarding_done",
        "topics",
    ],
    "additionalProperties": False,
}

EXTRACTOR_SYSTEM = (
    "Sen matematika repetitori botining xotira moduli sansan. Senga o'quvchining "
    "hozirgi profili va oxirgi suhbat parchasi beriladi. Vazifang — profilni "
    "yangilash uchun JSON qaytarish.\n\n"
    "Qoidalar:\n"
    "- Faqat suhbatdan ANIQ bilinadigan narsani yoz. Taxmin qilma.\n"
    "- Ma'lumot yangilanmagan bo'lsa, eski qiymatni o'zgarishsiz qaytar.\n"
    "- Hech qachon bilinmagan maydonni bo'sh satr bilan ALMASHTIRMA — eskisi qolsin.\n"
    "- plan maydonini faqat ustoz yangi o'quv reja bergan bo'lsa to'ldir.\n"
    "- topics ro'yxatiga faqat shu parchada holati o'zgargan mavzularni qo'sh."
)


def profile_block(student: dict[str, Any], topics: list[dict[str, Any]]) -> str:
    """Modelga uzatiladigan o'quvchi holati (mid-conversation system message)."""
    lines = ["[O'QUVCHI HAQIDA — tizim ma'lumoti, bu blokni o'quvchiga ko'rsatma]"]

    def add(label: str, value: Any) -> None:
        if value not in (None, ""):
            lines.append(f"{label}: {value}")

    add("Ism", student.get("first_name"))
    add("Yo'nalish", student.get("track"))
    add("Maqsad", student.get("goal"))
    add("Muddat", student.get("deadline"))
    if student.get("daily_minutes"):
        lines.append(f"Kunlik vaqti: {student['daily_minutes']} daqiqa")
    add("Daraja", student.get("level"))
    add("Hozirgi mavzu", student.get("current_topic"))

    if topics:
        done = sum(1 for t in topics if t["status"] == "tugallandi")
        lines.append(f"Mavzular: {done}/{len(topics)} tugallangan")
        for t in topics[-12:]:
            note = f" — {t['note']}" if t.get("note") else ""
            lines.append(f"  • {t['topic']}: {STATUS_LABELS.get(t['status'], t['status'])}{note}")

    if student.get("plan"):
        lines.append("\nO'QUV REJASI:\n" + str(student["plan"]))

    if student.get("onboarding_done"):
        lines.append(
            "\nTanishuv tugagan. Yuqoridagi ma'lumotni bilgan holda davom et — "
            "maqsad, vaqt yoki darajani qayta so'rama."
        )
    else:
        missing = [
            name
            for name, value in (
                ("maqsad", student.get("goal")),
                ("vaqt", student.get("deadline") or student.get("daily_minutes")),
                ("daraja", student.get("level")),
            )
            if not value
        ]
        lines.append(
            "\nTanishuv hali tugamagan. Yetishmayotgani: "
            + ", ".join(missing)
            + ". Shu savollarni BITTALAB so'ra, reja tuzishga shoshilma."
        )

    return "\n".join(lines)


async def stream_reply(
    student: dict[str, Any],
    topics: list[dict[str, Any]],
    history: list[dict[str, str]],
    user_text: str,
    on_delta: Callable[[str], Awaitable[None]],
) -> str:
    """Javobni oqim bilan oladi, har bo'lakda on_delta ni chaqiradi, to'liq matnni qaytaradi."""
    global _fallbacks_enabled, _system_role_supported

    state = profile_block(student, topics)

    # Ikkita imkoniyat modelga bog'liq (beta fallback va mid-conversation system
    # xabari). Ishlamasa, bir marta o'chirib qayta urinamiz.
    for _ in range(3):
        kwargs: dict[str, Any] = {
            "model": config.MODEL,
            "max_tokens": config.MAX_TOKENS,
            "system": SYSTEM_BLOCKS,
            "messages": _build_messages(history, user_text, state),
            "output_config": {"effort": config.EFFORT},
        }
        if _fallbacks_enabled:
            kwargs |= {"betas": [FALLBACK_BETA], "fallbacks": "default"}

        try:
            return await _run_stream(on_delta, beta=_fallbacks_enabled, **kwargs)
        except anthropic.BadRequestError as exc:
            message = str(exc).lower()
            if _fallbacks_enabled and ("fallback" in message or "beta" in message):
                log.warning("Server-side fallback o'chirildi: %s", exc)
                _fallbacks_enabled = False
                continue
            if _system_role_supported and "system" in message:
                log.warning("Mid-conversation system xabari o'chirildi: %s", exc)
                _system_role_supported = False
                continue
            raise

    raise RuntimeError("Claude so'rovi sozlamalarga moslasha olmadi.")


def _build_messages(
    history: list[dict[str, str]], user_text: str, state: str
) -> list[dict[str, Any]]:
    if _system_role_supported:
        return [
            *history,
            {"role": "user", "content": user_text},
            # O'zgaruvchan holat oxirida turadi — keshlangan prefiks buzilmaydi.
            {"role": "system", "content": state},
        ]
    return [*history, {"role": "user", "content": f"{state}\n\n---\n\n{user_text}"}]


async def _run_stream(
    on_delta: Callable[[str], Awaitable[None]], *, beta: bool, **kwargs: Any
) -> str:
    api = client.beta.messages if beta else client.messages
    chunks: list[str] = []

    async with api.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            chunks.append(text)
            await on_delta("".join(chunks))
        final = await stream.get_final_message()

    if final.stop_reason == "refusal":
        return (
            "Kechirasan, bu savolga javob bera olmadim. Matematika bo'yicha "
            "boshqacha qilib so'rab ko'rasanmi?"
        )

    return "".join(chunks).strip()


async def extract_profile(
    student: dict[str, Any], user_text: str, reply_text: str
) -> dict[str, Any] | None:
    """Oxirgi suhbat parchasidan profil yangilanishini ajratib oladi."""
    current = {
        "track": student.get("track") or "",
        "goal": student.get("goal") or "",
        "deadline": student.get("deadline") or "",
        "daily_minutes": str(student.get("daily_minutes") or ""),
        "level": student.get("level") or "",
        "plan": student.get("plan") or "",
        "current_topic": student.get("current_topic") or "",
        "onboarding_done": bool(student.get("onboarding_done")),
    }

    prompt = (
        "HOZIRGI PROFIL (JSON):\n"
        + json.dumps(current, ensure_ascii=False, indent=2)
        + "\n\nSUHBAT PARCHASI:\n"
        + f"O'quvchi: {user_text}\n\nUstoz: {reply_text}"
    )

    try:
        response = await client.messages.create(
            model=config.MODEL,
            max_tokens=4000,
            system=EXTRACTOR_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": PROFILE_SCHEMA},
            },
        )
    except anthropic.APIError as exc:
        log.warning("Profilni yangilab bo'lmadi: %s", exc)
        return None

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        log.warning("Profil JSON o'qilmadi: %r", text[:200])
        return None
