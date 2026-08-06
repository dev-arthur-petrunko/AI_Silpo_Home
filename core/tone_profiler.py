"""Тон-профіль переписки групи.

- Бот збирає повідомлення груп у таблицю `messages` (тільки останні ~100,
  старі видаляються — прозорість для сусідів).
- Коли в групі назбиралось >= tone_min_messages, профіль тону рахується
  ОДНОРАЗОВО через LLM (Groq) і зберігається в groups.tone_profile.
- Cold start: поки профілю немає — пост іде за нейтральним шаблоном.
- Готовий профіль повертає вступну/фінальну фразу під тон переписки.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from core.config import Settings
from core.llm import LLMError, llm_json
from db.models import Group, GroupMessage

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

TONE_SYSTEM = (
    "Ти — аналітик тону переписки жителів будинку в Telegram-групі. "
    "Прочитай повідомлення сусідів і визнач стиль спілкування групи. "
    "Поверни ТІЛЬКИ JSON без пояснень, такої форми:\n"
    '{"tone": "<дружній/нейтральний/діловий/жартівливий>", '
    '"formality": "<неформальний/нейтральний/формальний>", '
    '"emoji": true, "exclamations": true, '
    '"post_intro": "<коротка вступна фраза (до 90 символів) для посту про знижку на продукти, '
    'у стилі цієї групи>", '
    '"post_outro": "<коротка фінальна фраза-заклик (до 90 символів)>"}'
)


async def store_message(
    session: "AsyncSession", group_id: int, user_id: int, text: str, keep: int = 100
) -> None:
    """Зберігає одне повідомлення групи і обрізає до `keep` найновіших."""
    if not text or not text.strip():
        return
    session.add(
        GroupMessage(group_id=group_id, telegram_user_id=user_id, text=text.strip())
    )
    await session.flush()
    await prune_messages(session, group_id, keep)


async def prune_messages(session: "AsyncSession", group_id: int, keep: int = 100) -> None:
    """Видаляє старі повідомлення групи, лишаючи `keep` найновіших."""
    row = (
        await session.execute(
            select(func.count(GroupMessage.id)).where(GroupMessage.group_id == group_id)
        )
    ).scalar_one()
    total = int(row)
    if total <= keep:
        return
    excess = total - keep
    old_ids = (
        await session.execute(
            select(GroupMessage.id)
            .where(GroupMessage.group_id == group_id)
            .order_by(GroupMessage.created_at.asc(), GroupMessage.id.asc())
            .limit(excess)
        )
    ).scalars().all()
    if old_ids:
        await session.execute(
            delete(GroupMessage).where(GroupMessage.id.in_(old_ids))
        )


async def message_count(session: "AsyncSession", group_id: int) -> int:
    row = (
        await session.execute(
            select(func.count(GroupMessage.id)).where(GroupMessage.group_id == group_id)
        )
    ).scalar_one()
    return int(row)


async def _recent_messages(session: "AsyncSession", group_id: int, limit: int = 60) -> list[str]:
    rows = (
        await session.execute(
            select(GroupMessage.text)
            .where(GroupMessage.group_id == group_id)
            .order_by(GroupMessage.created_at.desc(), GroupMessage.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(reversed(rows))


async def analyze_group_tone(
    session: "AsyncSession", settings: Settings, group: Group, force: bool = False
) -> dict | None:
    """Одноразовий розрахунок профілю тону групи через LLM.

    Повертає профіль (dict) або None (ще не вистачає повідомлень / не вдалось).
    Готовий профіль кешується в groups.tone_profile.
    """
    if group.tone_profile and not force:
        return group.tone_profile

    if await message_count(session, group.id) < settings.tone_min_messages:
        return group.tone_profile if group.tone_profile else None

    messages = await _recent_messages(session, group.id)
    user_text = "Повідомлення групи (кожне з нового рядка):\n\n" + "\n".join(messages[:60])
    try:
        profile = await llm_json(
            settings,
            system=TONE_SYSTEM,
            user=user_text,
            temperature=0.5,
            max_tokens=400,
        )
    except LLMError as exc:
        logger.warning("tone analysis for group %s failed: %s", group.id, exc)
        return group.tone_profile if group.tone_profile else None

    if not isinstance(profile, dict) or not profile.get("post_intro"):
        logger.warning("tone analysis for group %s returned unusable profile", group.id)
        return group.tone_profile if group.tone_profile else None

    group.tone_profile = profile
    await session.commit()
    logger.info("tone profile computed for group %s: %s", group.id, profile.get("tone"))
    return profile


def tone_intro(profile: dict | None) -> str | None:
    """Вступна фраза посту під тон групи (None = нейтральний шаблон)."""
    if not profile:
        return None
    return (profile.get("post_intro") or "").strip() or None


def tone_outro(profile: dict | None) -> str | None:
    """Фінальна фраза посту під тон групи (None = без заклику)."""
    if not profile:
        return None
    return (profile.get("post_outro") or "").strip() or None
