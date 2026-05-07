"""Auto-discovery + manifest plugin tests."""
from app.tools.registry import get_all_tools, init_tools


def test_init_tools_picks_up_builtins_and_manifests():
    init_tools()
    names = set(get_all_tools().keys())
    # Built-ins discovered automatically
    for n in ("calculator", "ask_buttons", "ask_list", "echo",
              "remember", "recall", "forget",
              "text_to_image", "image_to_image"):
        assert n in names, f"missing built-in tool: {n}"
    # Manifest plugin discovered automatically
    assert "weather" in names
    # Integration tool discovered (auto-registered, then plan-gated at use)
    assert "gmail_search" in names


def test_init_tools_is_idempotent():
    init_tools()
    first = set(get_all_tools().keys())
    init_tools()
    second = set(get_all_tools().keys())
    assert first == second
