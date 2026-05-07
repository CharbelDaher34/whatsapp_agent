"""Stripe Checkout integration with a mock fallback for dev.

When ``STRIPE_SECRET_KEY`` is unset, calling ``create_checkout_session`` returns
a synthetic URL pointing at our own ``/checkout/mock-success`` endpoint, so
the full upgrade flow can be exercised end-to-end without Stripe credentials.
"""
from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from app.core.plans import PLANS, normalize_tier


_PRICE_LOOKUP = {
    "pro": lambda: settings.STRIPE_PRICE_PRO,
    "max": lambda: settings.STRIPE_PRICE_MAX,
}


def is_paid_plan(plan: str) -> bool:
    return normalize_tier(plan) in ("pro", "max")


def display_price(plan: str) -> str:
    plan = normalize_tier(plan)
    if plan == "free":
        return settings.PRICE_FREE_LABEL
    if plan == "pro":
        return settings.PRICE_PRO_LABEL
    return settings.PRICE_MAX_LABEL


async def create_checkout_session(user_id: int, plan: str) -> str:
    """Return a checkout URL for ``user_id`` upgrading to ``plan``.

    In live mode this hits Stripe's API; in mock mode it returns a local URL
    that our own ``/checkout/mock-success`` route consumes.
    """
    plan = normalize_tier(plan)
    if plan not in PLANS or plan == "free":
        raise ValueError(f"Plan {plan!r} is not purchasable")

    base = settings.WEB_BASE_URL.rstrip("/")
    success_url = f"{base}/checkout/success?plan={plan}"
    cancel_url = f"{base}/checkout/cancel"

    if settings.billing_mode == "mock":
        # Skip Stripe entirely; the success page will upgrade the user.
        logger.warning("💸 Stripe not configured — using mock checkout")
        return f"{base}/checkout/mock-success?plan={plan}&user_id={user_id}"

    import stripe  # type: ignore

    stripe.api_key = settings.STRIPE_SECRET_KEY
    price_id = _PRICE_LOOKUP[plan]()
    if not price_id:
        raise ValueError(f"Stripe price id for plan {plan!r} is not configured")

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{success_url}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=cancel_url,
        client_reference_id=str(user_id),
        metadata={"plan": plan, "user_id": str(user_id)},
        allow_promotion_codes=True,
    )
    return session.url


def verify_stripe_webhook(payload: bytes, signature: str) -> Optional[dict]:
    """Verify and parse a Stripe webhook event. Returns the event or None."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set; rejecting webhook")
        return None
    import stripe  # type: ignore
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET,
        )
        return event
    except Exception as e:
        logger.error(f"Stripe webhook signature failed: {e}")
        return None
