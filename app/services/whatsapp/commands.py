"""Slash-command shortcuts handled by the bot before the AI runs.

These let a user check or change their plan/usage directly from WhatsApp.
Recognised commands (case-insensitive, with or without leading ``/``):

  /help         List available commands.
  /plan         Show the user's current plan and capabilities.
  /usage        Show today + month-to-date usage and remaining quota.
  /upgrade      Send the upgrade list and a checkout link.
  /pro          Direct shortcut to the Pro checkout link.
  /max          Direct shortcut to the Max checkout link.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import PLANS, get_plan
from app.models.user import User
from app.services.subscription_service import get_usage_summary
from app.services.whatsapp.client import send_whatsapp_text
from app.services.whatsapp.interactive import send_button_message, send_list_message


_COMMAND_ALIASES = {
    "help": "help",
    "menu": "help",
    "commands": "help",
    "plan": "plan",
    "myplan": "plan",
    "status": "plan",
    "usage": "usage",
    "quota": "usage",
    "upgrade": "upgrade",
    "buy": "upgrade",
    "subscribe": "upgrade",
    "pro": "pro",
    "max": "max",
}


def parse_command(text: str) -> Optional[str]:
    """Return the canonical command name for an inbound message, or None."""
    if not text:
        return None
    stripped = text.strip()
    if not stripped:
        return None
    if stripped[0] in "/!":
        stripped = stripped[1:]
    word = stripped.split(maxsplit=1)[0].lower()
    return _COMMAND_ALIASES.get(word)


def _checkout_link(plan: str) -> str:
    """Public web URL the user can open to upgrade to ``plan``."""
    base = settings.WEB_BASE_URL.rstrip("/")
    return f"{base}/checkout/start?plan={plan}"


def _plan_summary(user: User) -> str:
    plan = get_plan(user.subscription_tier)
    bullets = [
        f"📦 Plan: *{plan.display_name}*",
        f"🤖 Model: {plan.model}",
        f"📨 Daily limit: {'unlimited' if plan.messages_per_day == -1 else plan.messages_per_day}",
        f"📅 Monthly limit: {'unlimited' if plan.messages_per_month == -1 else plan.messages_per_month}",
        f"🧠 History depth: {plan.history_depth} messages",
        "",
        f"🖼️ Image generation: {'✅' if plan.can_generate_images else '❌'}",
        f"🎨 Image editing: {'✅' if plan.can_transform_images else '❌'}",
        f"🎙️ Voice transcription: {'✅' if plan.can_transcribe_audio else '❌'}",
        f"📄 Document analysis: {'✅' if plan.can_read_documents else '❌'}",
    ]
    return "\n".join(bullets)


async def _handle_help(phone: str) -> None:
    text = (
        "🤖 *Commands*\n"
        "/plan – your current plan & capabilities\n"
        "/usage – your usage today & this month\n"
        "/upgrade – upgrade to Pro or Max\n"
        "/help – this list\n\n"
        "Or just chat normally — I'm happy to help."
    )
    await send_whatsapp_text(phone, text)


async def _handle_plan(phone: str, user: User) -> None:
    await send_whatsapp_text(phone, _plan_summary(user))


async def _handle_usage(phone: str, user: User, session: AsyncSession) -> None:
    summary = await get_usage_summary(user, session)
    daily_limit = "unlimited" if summary["daily_limit"] == -1 else summary["daily_limit"]
    monthly_limit = "unlimited" if summary["monthly_limit"] == -1 else summary["monthly_limit"]
    text = (
        f"📊 *Usage* — {summary['plan_display']}\n"
        f"Today: {summary['daily_used']} / {daily_limit}\n"
        f"This month: {summary['monthly_used']} / {monthly_limit}"
    )
    await send_whatsapp_text(phone, text)


async def _handle_upgrade(phone: str, user: User) -> None:
    rows = []
    for tier in ("pro", "max"):
        plan = PLANS[tier]
        price_label = (
            settings.PRICE_PRO_LABEL if tier == "pro" else settings.PRICE_MAX_LABEL
        )
        rows.append({
            "id": f"upgrade:{tier}",
            "title": f"{plan.display_name} – {price_label}",
            "description": f"{'Unlimited' if plan.messages_per_day == -1 else plan.messages_per_day}/day, model {plan.model}",
        })
    sections = [{"title": "Plans", "rows": rows}]

    sent_list = await send_list_message(
        to=phone,
        body_text="Pick a plan to upgrade. I'll send you a secure checkout link.",
        button_text="Plans",
        sections=sections,
        header_text="Upgrade",
    )
    base = settings.WEB_BASE_URL.rstrip("/")
    fallback = (
        "Upgrade options:\n"
        f"• Pro – {settings.PRICE_PRO_LABEL}: {_checkout_link('pro')}\n"
        f"• Max – {settings.PRICE_MAX_LABEL}: {_checkout_link('max')}\n\n"
        f"Or visit: {base}/pricing"
    )
    if not sent_list:
        await send_whatsapp_text(phone, fallback)
    else:
        # Always include the link in plain text too — interactive lists
        # aren't tappable in some WhatsApp clients (e.g. Web).
        await send_whatsapp_text(phone, fallback)


async def _handle_direct_upgrade(phone: str, target: str) -> None:
    plan = PLANS[target]
    price = settings.PRICE_PRO_LABEL if target == "pro" else settings.PRICE_MAX_LABEL
    await send_whatsapp_text(
        phone,
        f"Upgrade to *{plan.display_name}* ({price}):\n{_checkout_link(target)}",
    )


async def maybe_handle_command(
    text: str,
    user: User,
    phone: str,
    session: AsyncSession,
) -> bool:
    """Try to handle ``text`` as a slash command. Returns True if handled."""
    cmd = parse_command(text)
    if cmd is None:
        return False

    if cmd == "help":
        await _handle_help(phone)
    elif cmd == "plan":
        await _handle_plan(phone, user)
    elif cmd == "usage":
        await _handle_usage(phone, user, session)
    elif cmd == "upgrade":
        await _handle_upgrade(phone, user)
    elif cmd in ("pro", "max"):
        await _handle_direct_upgrade(phone, cmd)
    else:
        return False
    return True
