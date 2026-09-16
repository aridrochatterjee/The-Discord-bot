import pytest
from bot.cogs.bounty import BountySolutionModal, BountyView
from bot.database.queries import create_bounty, accept_bounty, cancel_bounty


def test_bounty_solution_modal_fields():
    modal = BountySolutionModal(bounty_id=42, bounty_title="Fix race condition")
    assert modal.bounty_id == 42
    assert "42" in modal.title
    assert modal.solution_url_input.required is False
    assert modal.explanation_input.required is True



def test_bounty_view_button():
    view = BountyView()
    assert len(view.children) == 1
    btn = view.children[0]
    assert btn.custom_id == "bounty:submit_solution"
    assert "Submit Solution" in btn.label


@pytest.mark.asyncio
async def test_create_bounty_zero_reward():
    success, msg, bounty_id = await create_bounty(
        guild_id=123,
        channel_id=456,
        creator_id=789,
        title="Test Zero Bounty",
        description="Testing zero karma guard",
        reward_karma=0,
    )
    assert success is False
    assert "at least 1" in msg
    assert bounty_id is None


@pytest.mark.asyncio
async def test_create_bounty_negative_reward():
    success, msg, bounty_id = await create_bounty(
        guild_id=123,
        channel_id=456,
        creator_id=789,
        title="Negative Bounty",
        description="Testing negative karma guard",
        reward_karma=-10,
    )
    assert success is False
    assert "at least 1" in msg
    assert bounty_id is None
