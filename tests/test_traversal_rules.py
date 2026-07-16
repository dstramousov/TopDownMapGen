from top_down_worldgen.tactical.traversal import DEFAULT_TRAVERSAL_RULES


def test_natural_delta_is_shared_and_limited_to_one() -> None:
    """Natural traversal must allow only same-level and one-level steps."""
    assert DEFAULT_TRAVERSAL_RULES.allows_step(4, 4)
    assert DEFAULT_TRAVERSAL_RULES.allows_step(4, 5)
    assert not DEFAULT_TRAVERSAL_RULES.allows_step(4, 6)


def test_structural_transition_allows_larger_delta() -> None:
    """Explicit structural transitions may bridge larger elevation deltas."""
    assert DEFAULT_TRAVERSAL_RULES.allows_step(
        4,
        7,
        transition_allowed=True,
    )
