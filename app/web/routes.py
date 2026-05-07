"""Public web pages: home, pricing, login, dashboard, checkout."""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.plans import PLANS, get_plan, normalize_tier
from app.db.session import get_session
from app.models.user import User
from app.services.conversation_service import get_or_create_user_conversation
from app.services.integration_service import get_active as get_integration
from app.services.memory_service import forget_memory, recall as recall_memories
from app.services.subscription_service import get_usage_summary
from app.services.whatsapp.client import send_whatsapp_text
from app.web.auth import (
    clear_session_cookie,
    current_user_optional,
    issue_otp,
    issue_session_token,
    load_current_user,
    require_user,
    set_session_cookie,
    verify_otp,
    _normalize_phone,
)
from app.web.billing import create_checkout_session, display_price, is_paid_plan


_THIS_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_THIS_DIR / "templates"))


router = APIRouter(tags=["web"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _public_plans() -> list[dict]:
    return [
        {
            "name": p.name,
            "display_name": p.display_name,
            "model": p.model,
            "messages_per_day": p.messages_per_day,
            "messages_per_month": p.messages_per_month,
            "history_depth": p.history_depth,
            "can_generate_images": p.can_generate_images,
            "can_transform_images": p.can_transform_images,
            "can_transcribe_audio": p.can_transcribe_audio,
            "can_read_documents": p.can_read_documents,
            "tools": sorted(p.tools),
            "price_label": display_price(p.name),
        }
        for p in PLANS.values()
    ]


def _ctx(request: Request, **extra) -> dict:
    """Common Jinja context."""
    return {
        "request": request,
        "app_name": settings.APP_NAME,
        "user": extra.pop("user", None) or None,
        "billing_mode": settings.billing_mode,
        **extra,
    }


# ---------------------------------------------------------------------------
# Home + pricing
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, claims: Optional[dict] = Depends(current_user_optional)):
    return templates.TemplateResponse(
        "landing.html",
        _ctx(request, active="home", user=claims),
    )


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request, claims: Optional[dict] = Depends(current_user_optional)):
    return templates.TemplateResponse(
        "pricing.html",
        _ctx(request, active="pricing", user=claims, plans=_public_plans()),
    )


# ---------------------------------------------------------------------------
# Login flow (phone → OTP → JWT cookie)
# ---------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: Optional[str] = None):
    return templates.TemplateResponse(
        "login.html",
        _ctx(request, active="login", step="phone", next=next or "/dashboard"),
    )


@router.post("/login/start", response_class=HTMLResponse)
async def login_start(
    request: Request,
    phone: str = Form(...),
    next: Optional[str] = Form("/dashboard"),
    session: AsyncSession = Depends(get_session),
):
    cleaned = _normalize_phone(phone)
    if not cleaned or len(cleaned) < 8:
        return templates.TemplateResponse(
            "login.html",
            _ctx(
                request, active="login", step="phone",
                flash="Please enter a valid phone number with country code.",
                flash_kind="error", next=next,
            ),
        )

    # Pre-create the user row so quotas / DB rows exist if they go on to log in.
    user, _ = await get_or_create_user_conversation(cleaned, session)
    await session.commit()

    code = await issue_otp(cleaned)
    if settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_ID:
        await send_whatsapp_text(
            cleaned,
            f"Your {settings.APP_NAME} login code is *{code}*. "
            f"It expires in {settings.OTP_TTL_SECONDS // 60} minutes.",
        )
    flash = f"Code sent to +{cleaned} on WhatsApp."
    if settings.DEBUG:
        flash += f" (debug code: {code})"
    return templates.TemplateResponse(
        "login.html",
        _ctx(
            request, active="login", step="code", phone=cleaned,
            flash=flash, flash_kind="success", next=next,
        ),
    )


@router.post("/login/verify", response_class=HTMLResponse)
async def login_verify(
    request: Request,
    phone: str = Form(...),
    code: str = Form(...),
    next: Optional[str] = Form("/dashboard"),
    session: AsyncSession = Depends(get_session),
):
    cleaned = _normalize_phone(phone)
    code = (code or "").strip()
    if not await verify_otp(cleaned, code):
        return templates.TemplateResponse(
            "login.html",
            _ctx(
                request, active="login", step="code", phone=cleaned,
                flash="Wrong or expired code. Try again.", flash_kind="error",
                next=next,
            ),
        )

    user, _ = await get_or_create_user_conversation(cleaned, session)
    await session.commit()

    token = issue_session_token(user)
    target = next or "/dashboard"
    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, token)
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    claims: dict = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user = await load_current_user(claims, session)
    plan = get_plan(user.subscription_tier)
    usage = await get_usage_summary(user, session)

    # Integrations are gated by plan. Show real connection status when allowed.
    integrations_enabled = plan.name in ("pro", "max")
    google_integration = (
        await get_integration(session, user.id, "google") if integrations_enabled else None
    )

    memories = await recall_memories(session, user.id, None, limit=20)

    return templates.TemplateResponse(
        "dashboard.html",
        _ctx(
            request, active="dashboard", user=claims,
            db_user=user, plan=plan, usage=usage,
            integrations_enabled=integrations_enabled,
            google_integration=google_integration,
            memories=memories,
        ),
    )


@router.post("/account/forget")
async def account_forget(
    memory_id: int = Form(...),
    claims: dict = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete one memory belonging to the current user."""
    await forget_memory(session, int(claims["sub"]), memory_id=memory_id)
    await session.commit()
    return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/account/downgrade-free")
async def downgrade_free(
    claims: dict = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    user = await load_current_user(claims, session)
    user.subscription_tier = "free"
    session.add(user)
    await session.commit()
    return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

@router.get("/checkout/start")
async def checkout_start_get(plan: str, claims: dict = Depends(require_user)):
    plan = normalize_tier(plan)
    if not is_paid_plan(plan):
        raise HTTPException(400, detail="Plan is not purchasable")
    url = await create_checkout_session(int(claims["sub"]), plan)
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/checkout/start")
async def checkout_start_post(plan: str = Form(...), claims: dict = Depends(require_user)):
    plan = normalize_tier(plan)
    if not is_paid_plan(plan):
        raise HTTPException(400, detail="Plan is not purchasable")
    url = await create_checkout_session(int(claims["sub"]), plan)
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/checkout/success", response_class=HTMLResponse)
async def checkout_success(
    request: Request,
    plan: str,
    claims: dict = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """In live mode the upgrade is applied via the Stripe webhook.
    Here we only confirm the page; we don't trust the query string."""
    return templates.TemplateResponse(
        "checkout_done.html",
        _ctx(
            request, user=claims,
            heading="Thanks! Your upgrade is processing.",
            body="It can take a few seconds for your plan to update. Refresh the dashboard if it hasn't yet.",
        ),
    )


@router.get("/checkout/cancel", response_class=HTMLResponse)
async def checkout_cancel(request: Request, claims: dict = Depends(require_user)):
    return templates.TemplateResponse(
        "checkout_done.html",
        _ctx(
            request, user=claims,
            heading="Checkout cancelled",
            body="No charge was made. You can pick a plan any time from the pricing page.",
        ),
    )


@router.get("/checkout/mock-success")
async def checkout_mock_success(
    plan: str,
    user_id: int,
    claims: dict = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Dev-only path used when Stripe is not configured. Upgrades the
    *currently logged-in* user (we ignore the user_id query param if it
    doesn't match the cookie) immediately and redirects to the dashboard."""
    if settings.billing_mode != "mock":
        raise HTTPException(403, detail="Mock checkout disabled")
    plan = normalize_tier(plan)
    if not is_paid_plan(plan):
        raise HTTPException(400, detail="Plan is not purchasable")

    user = await load_current_user(claims, session)
    user.subscription_tier = plan
    session.add(user)
    await session.commit()

    logger.info(f"🧪 Mock upgrade applied: user_id={user.id} → {plan}")
    return RedirectResponse(
        f"/checkout/success?plan={plan}", status_code=status.HTTP_303_SEE_OTHER,
    )
