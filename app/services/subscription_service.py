"""Subscription service: plan-based quota tracking and enforcement.

Backed by the `usage_record` table. One row per (user_id, day). The service
accepts a SQLAlchemy AsyncSession so callers participate in the same
transaction as the rest of the webhook pipeline.
"""
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PlanLimits, get_plan, normalize_tier
from app.models.user import User
from app.models.usage import UsageRecord
from app.core.logging import logger


class QuotaCheck:
    """Outcome of a quota check."""

    __slots__ = ("allowed", "reason", "plan", "daily_used", "monthly_used")

    def __init__(
        self,
        allowed: bool,
        plan: PlanLimits,
        daily_used: int,
        monthly_used: int,
        reason: Optional[str] = None,
    ):
        self.allowed = allowed
        self.plan = plan
        self.daily_used = daily_used
        self.monthly_used = monthly_used
        self.reason = reason

    def upgrade_message(self) -> str:
        """User-facing message explaining the limit and how to upgrade."""
        if self.plan.name == "max":
            return "You've hit a temporary system limit. Please try again in a few minutes."
        upgrade_to = "Pro" if self.plan.name == "free" else "Max"
        return (
            f"You've reached your {self.plan.display_name} plan limit "
            f"({self.daily_used}/{self.plan.messages_per_day} messages today). "
            f"Upgrade to {upgrade_to} for higher limits — reply 'upgrade' to learn more."
        )


async def _get_daily_usage(session: AsyncSession, user_id: int, day: date) -> Optional[UsageRecord]:
    result = await session.execute(
        select(UsageRecord).where(
            UsageRecord.user_id == user_id,
            UsageRecord.day == day,
        )
    )
    return result.scalar_one_or_none()


async def _get_monthly_count(session: AsyncSession, user_id: int, today: date) -> int:
    month_start = today.replace(day=1)
    result = await session.execute(
        select(func.coalesce(func.sum(UsageRecord.messages), 0)).where(
            UsageRecord.user_id == user_id,
            UsageRecord.day >= month_start,
        )
    )
    return int(result.scalar_one() or 0)


async def check_quota(user: User, session: AsyncSession) -> QuotaCheck:
    """Verify the user is allowed to send another message under their plan."""
    plan = get_plan(user.subscription_tier)

    if not user.is_active:
        return QuotaCheck(
            allowed=False, plan=plan, daily_used=0, monthly_used=0,
            reason="account_inactive",
        )

    today = datetime.utcnow().date()
    daily = await _get_daily_usage(session, user.id, today)
    daily_used = daily.messages if daily else 0
    monthly_used = await _get_monthly_count(session, user.id, today)

    if plan.messages_per_day != -1 and daily_used >= plan.messages_per_day:
        return QuotaCheck(
            allowed=False, plan=plan,
            daily_used=daily_used, monthly_used=monthly_used,
            reason="daily_limit",
        )

    if plan.messages_per_month != -1 and monthly_used >= plan.messages_per_month:
        return QuotaCheck(
            allowed=False, plan=plan,
            daily_used=daily_used, monthly_used=monthly_used,
            reason="monthly_limit",
        )

    return QuotaCheck(
        allowed=True, plan=plan,
        daily_used=daily_used, monthly_used=monthly_used,
    )


async def register_message(
    user: User,
    session: AsyncSession,
    *,
    tool_calls: int = 0,
) -> UsageRecord:
    """Increment today's usage counter for the user."""
    today = datetime.utcnow().date()
    daily = await _get_daily_usage(session, user.id, today)
    if daily is None:
        daily = UsageRecord(user_id=user.id, day=today, messages=1, tool_calls=tool_calls)
        session.add(daily)
    else:
        daily.messages += 1
        daily.tool_calls += tool_calls
        daily.updated_at = datetime.utcnow()
    await session.flush()
    return daily


async def get_usage_summary(user: User, session: AsyncSession) -> dict:
    """Snapshot of the user's current usage for /admin or in-bot status replies."""
    today = datetime.utcnow().date()
    plan = get_plan(user.subscription_tier)
    daily = await _get_daily_usage(session, user.id, today)
    monthly = await _get_monthly_count(session, user.id, today)
    return {
        "plan": plan.name,
        "plan_display": plan.display_name,
        "daily_used": daily.messages if daily else 0,
        "daily_limit": plan.messages_per_day,
        "monthly_used": monthly,
        "monthly_limit": plan.messages_per_month,
        "tools": sorted(plan.tools),
    }


# ---------------------------------------------------------------------------
# Backwards-compatible sync wrappers (kept so older callers don't break).
# Prefer the async API above.
# ---------------------------------------------------------------------------

def can_user_send_message(user: User) -> bool:
    """Legacy hook: only checks `is_active`. Real enforcement is async."""
    return bool(user.is_active)


def register_usage(user: User) -> None:  # pragma: no cover - legacy stub
    """Legacy no-op. Real tracking happens in `register_message` (async)."""
    return None
