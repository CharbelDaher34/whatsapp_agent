"""Stripe webhook receiver that applies plan changes."""
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select

from app.core.logging import logger
from app.core.plans import normalize_tier
from app.db.session import get_session
from app.models.user import User
from app.web.billing import verify_stripe_webhook


router = APIRouter(prefix="/stripe", tags=["billing"])


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
):
    body = await request.body()
    if not stripe_signature:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Missing signature")

    event = verify_stripe_webhook(body, stripe_signature)
    if not event:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid signature")

    event_type = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    logger.info(f"Stripe event: {event_type}")

    # We care about completed checkout sessions and subscription cancels.
    if event_type == "checkout.session.completed":
        user_id = (obj.get("client_reference_id")
                   or (obj.get("metadata") or {}).get("user_id"))
        plan = normalize_tier((obj.get("metadata") or {}).get("plan", ""))
        if user_id and plan in ("pro", "max"):
            await _apply_plan(int(user_id), plan)
    elif event_type in ("customer.subscription.deleted", "customer.subscription.canceled"):
        user_id = (obj.get("metadata") or {}).get("user_id")
        if user_id:
            await _apply_plan(int(user_id), "free")

    return {"status": "ok"}


async def _apply_plan(user_id: int, plan: str) -> None:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"Stripe webhook: user {user_id} not found")
            return
        user.subscription_tier = plan
        session.add(user)
        await session.commit()
        logger.info(f"✅ Plan updated via Stripe: user {user_id} → {plan}")
