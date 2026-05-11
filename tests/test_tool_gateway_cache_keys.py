from backend.app.tool_gateway.cache_keys import build_tool_cache_key


def test_same_payload_with_different_dict_order_has_same_cache_key() -> None:
    first = {"query": "museum", "filters": {"child_friendly": True, "radius_km": 5}}
    second = {"filters": {"radius_km": 5, "child_friendly": True}, "query": "museum"}

    assert build_tool_cache_key("search_poi", "fake", first) == build_tool_cache_key(
        "search_poi",
        "fake",
        second,
    )


def test_different_payload_changes_cache_key() -> None:
    first = build_tool_cache_key("search_poi", "fake", {"query": "museum"})
    second = build_tool_cache_key("search_poi", "fake", {"query": "park"})

    assert first != second


def test_cache_key_contains_tool_and_provider_but_not_raw_payload_text() -> None:
    key = build_tool_cache_key(
        "search_poi",
        "fake",
        {"query": "family museum", "marker": "do-not-leak"},
    )

    assert key.startswith("tool:fake:search_poi:")
    assert "family museum" not in key
    assert "do-not-leak" not in key
