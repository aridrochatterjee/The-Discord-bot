import pytest
import discord
from bot.cogs.community import ShowcaseModal, ShowcaseView, ShowcaseVoteButton, normalize_url


def test_showcase_modal_inputs():
    modal = ShowcaseModal()
    assert modal.project_title is not None
    assert modal.tech_stack is not None
    assert modal.description is not None
    assert modal.project_title.required is True
    assert modal.description.required is True
    assert modal.github_url.required is False


def test_showcase_view_button():
    view = ShowcaseView(showcase_id=42, upvotes=5)
    assert len(view.children) == 1
    button = view.children[0]
    assert isinstance(button, ShowcaseVoteButton)
    assert button.custom_id == "showcase:vote:42"
    assert "5" in button.label


def test_normalize_url():
    assert normalize_url("github.com/test/repo") == "https://github.com/test/repo"
    assert normalize_url("https://example.com") == "https://example.com"
    assert normalize_url("   ") is None
