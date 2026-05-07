"""Integration model + service unit tests (no live OAuth)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.models import Conversation, Integration, Memory, Message, User  # noqa: F401
from app.services.integration_service import (
    get_active,
    list_for_user,
    revoke,
    upsert_google,
)
from app.web.crypto import decrypt_token, encrypt_token


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        user = User(phone="999", subscription_tier="pro")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.user_id = user.id  # type: ignore[attr-defined]
        yield session
    await engine.dispose()


def test_token_round_trip():
    enc = encrypt_token("hello-secret")
    assert enc and enc != "hello-secret"
    assert decrypt_token(enc) == "hello-secret"
    assert decrypt_token(None) is None
    assert decrypt_token("totally-broken-token") is None


async def test_upsert_google_creates_then_updates(async_session):
    user_id = async_session.user_id  # type: ignore[attr-defined]
    row = await upsert_google(
        async_session, user_id,
        access_token="aaa", refresh_token="rrr", expires_in=3600,
        scope="gmail.readonly", account_email="alex@example.com",
    )
    assert row.id and row.account_email == "alex@example.com"
    assert decrypt_token(row.access_token_enc) == "aaa"

    # Upsert again — should not duplicate
    row2 = await upsert_google(
        async_session, user_id,
        access_token="bbb", refresh_token=None, expires_in=600,
        scope="gmail.readonly", account_email="alex@example.com",
    )
    assert row2.id == row.id
    assert decrypt_token(row2.access_token_enc) == "bbb"
    # Refresh token preserved
    assert decrypt_token(row2.refresh_token_enc) == "rrr"

    rows = await list_for_user(async_session, user_id)
    assert len(rows) == 1


async def test_revoke_deletes_row(async_session):
    user_id = async_session.user_id  # type: ignore[attr-defined]
    await upsert_google(
        async_session, user_id,
        access_token="x", refresh_token="y", expires_in=60,
        scope="s", account_email="a@b.com",
    )
    removed = await revoke(async_session, user_id, "google")
    assert removed == 1
    assert await get_active(async_session, user_id, "google") is None
