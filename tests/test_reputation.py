import pytest
from bot.cogs.reputation import format_progress_bar, get_karma_tier


def test_karma_tiers():
    tier0, next0 = get_karma_tier(0)
    assert "Junior Helper" in tier0
    assert next0 == 5

    tier4, next4 = get_karma_tier(4)
    assert "Junior Helper" in tier4
    assert next4 == 5

    tier5, next5 = get_karma_tier(5)
    assert "Code Contributor" in tier5
    assert next5 == 15

    tier15, next15 = get_karma_tier(15)
    assert "Community Mentor" in tier15
    assert next15 == 30

    tier30, next30 = get_karma_tier(30)
    assert "Lead Architect" in tier30
    assert next30 == 50

    tier50, next50 = get_karma_tier(55)
    assert "Tech Sage" in tier50
    assert next50 is None


def test_progress_bar_format():
    bar_partial = format_progress_bar(5, 10, length=10)
    assert "5/10 points" in bar_partial
    assert "█" in bar_partial
    assert "░" in bar_partial

    bar_max = format_progress_bar(100, None)
    assert "Max Tier" in bar_max
