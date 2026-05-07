"""Plan / quota / tier-gating tests."""
import pytest

from app.core.plans import (
    PLANS,
    TIER_ORDER,
    get_plan,
    normalize_tier,
    tier_rank,
    tool_allowed,
)


def test_three_canonical_tiers():
    assert TIER_ORDER == ["free", "pro", "max"]
    assert set(PLANS) == {"free", "pro", "max"}


def test_legacy_aliases_normalized():
    assert normalize_tier("plus") == "pro"
    assert normalize_tier("PLUS") == "pro"
    assert normalize_tier("premium") == "pro"
    assert normalize_tier(None) == "free"
    assert normalize_tier("garbage") == "free"


def test_tier_ranking_is_monotonic():
    assert tier_rank("free") == 0
    assert tier_rank("pro") == 1
    assert tier_rank("max") == 2
    assert tier_rank("free") < tier_rank("pro") < tier_rank("max")


def test_free_tier_blocks_image_tools():
    assert tool_allowed("free", "calculator")
    assert tool_allowed("free", "ask_buttons")
    assert tool_allowed("free", "ask_list")
    assert not tool_allowed("free", "text_to_image")
    assert not tool_allowed("free", "image_to_image")


def test_pro_tier_unlocks_image_tools():
    assert tool_allowed("pro", "text_to_image")
    assert tool_allowed("pro", "image_to_image")


def test_max_tier_allows_everything():
    assert tool_allowed("max", "text_to_image")
    assert tool_allowed("max", "image_to_image")
    assert tool_allowed("max", "anything_new_we_add_later")


def test_quota_unlimited_marker():
    max_plan = get_plan("max")
    assert max_plan.messages_per_day == -1
    assert max_plan.messages_per_month == -1


def test_capability_flags_per_tier():
    free = get_plan("free")
    pro = get_plan("pro")
    mx = get_plan("max")

    assert not free.can_generate_images
    assert pro.can_generate_images
    assert mx.can_generate_images

    assert not free.can_transcribe_audio
    assert pro.can_transcribe_audio
    assert mx.can_transcribe_audio

    assert not free.can_read_documents
    assert pro.can_read_documents
    assert mx.can_read_documents
