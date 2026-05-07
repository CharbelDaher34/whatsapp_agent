"""Subscription plan configuration.

Three tiers: free, pro, max.
Each tier defines:
- daily/monthly message quotas (-1 means unlimited)
- which built-in tools the user can call
- which input modalities are processed (vs. politely refused)
- the LLM model used for replies
- conversation history depth
"""
from typing import Dict, List, Set, Optional
from pydantic import BaseModel


# Canonical plan ordering. Higher index = higher tier.
TIER_ORDER: List[str] = ["free", "pro", "max"]

# Legacy tier names get auto-mapped so old DB rows still work.
LEGACY_TIER_ALIASES: Dict[str, str] = {
    "plus": "pro",   # old "plus" → new "pro"
    "premium": "pro",
    # old "pro" was the top tier; remap to "max"
    # Note: this is intentionally one-way. Existing "pro" rows become "max".
}


class PlanLimits(BaseModel):
    """Concrete limits and capabilities for a plan."""

    name: str
    display_name: str
    messages_per_day: int          # -1 = unlimited
    messages_per_month: int        # -1 = unlimited
    history_depth: int             # how many past messages to feed the model
    model: str                     # OpenAI model id
    tools: Set[str]                # tool names allowed; {"*"} means all
    inbound_modalities: Set[str]   # input types we actively process
    can_generate_images: bool
    can_transform_images: bool
    can_transcribe_audio: bool
    can_read_documents: bool


PLANS: Dict[str, PlanLimits] = {
    "free": PlanLimits(
        name="free",
        display_name="Free",
        messages_per_day=30,
        messages_per_month=300,
        history_depth=10,
        model="gpt-4o-mini",
        tools={
            "calculator", "ask_buttons", "ask_list", "echo",
            "remember", "recall", "forget", "weather",
        },
        inbound_modalities={
            "text", "image", "interactive", "button", "reaction",
            "location", "contacts", "sticker", "unsupported",
        },
        can_generate_images=False,
        can_transform_images=False,
        can_transcribe_audio=False,
        can_read_documents=False,
    ),
    "pro": PlanLimits(
        name="pro",
        display_name="Pro",
        messages_per_day=500,
        messages_per_month=10_000,
        history_depth=30,
        model="gpt-4o",
        tools={
            "calculator", "ask_buttons", "ask_list", "echo",
            "remember", "recall", "forget", "weather",
            "text_to_image", "image_to_image",
            "gmail_search",
        },
        inbound_modalities={
            "text", "image", "interactive", "button", "reaction",
            "location", "contacts", "sticker", "audio", "voice",
            "video", "document", "unsupported",
        },
        can_generate_images=True,
        can_transform_images=True,
        can_transcribe_audio=True,
        can_read_documents=True,
    ),
    "max": PlanLimits(
        name="max",
        display_name="Max",
        messages_per_day=-1,
        messages_per_month=-1,
        history_depth=80,
        model="gpt-4o",
        tools={"*"},
        inbound_modalities={
            "text", "image", "interactive", "button", "reaction",
            "location", "contacts", "sticker", "audio", "voice",
            "video", "document", "unsupported",
        },
        can_generate_images=True,
        can_transform_images=True,
        can_transcribe_audio=True,
        can_read_documents=True,
    ),
}


def normalize_tier(tier: Optional[str]) -> str:
    """Map legacy / unknown tier names to a canonical tier."""
    if not tier:
        return "free"
    tier = tier.lower().strip()
    tier = LEGACY_TIER_ALIASES.get(tier, tier)
    if tier == "pro" and "pro" not in PLANS:
        # safety: shouldn't happen, but fall back to free
        return "free"
    if tier not in PLANS:
        return "free"
    return tier


def get_plan(tier: Optional[str]) -> PlanLimits:
    """Return the PlanLimits for a tier (with legacy aliasing)."""
    return PLANS[normalize_tier(tier)]


def tier_rank(tier: Optional[str]) -> int:
    """Rank a tier (higher = better). Used for tool gating."""
    canonical = normalize_tier(tier)
    return TIER_ORDER.index(canonical) if canonical in TIER_ORDER else 0


def tool_allowed(tier: Optional[str], tool_name: str) -> bool:
    """Whether a given tool is available on this tier."""
    plan = get_plan(tier)
    return "*" in plan.tools or tool_name in plan.tools
