import pytest
from bot.cogs.challenge import ChallengeSubmissionModal, ChallengeView
from bot.utils.checks import is_admin_or_owner


def test_challenge_submission_modal_fields():
    modal = ChallengeSubmissionModal(challenge_id=8, challenge_title="BUILD YOUR OWN CHATBOT")
    assert modal.challenge_id == 8
    assert "BUILD YOUR OWN CHATBOT" in modal.title
    assert modal.github_url_input.required is True
    assert modal.demo_url_input.required is False
    assert modal.difficulty_input.default == "Medium"
    assert modal.notes_input.required is False



def test_challenge_view_button():
    view = ChallengeView()
    assert len(view.children) == 1
    btn = view.children[0]
    assert btn.custom_id == "challenge:submit"
    assert "Submit Solution" in btn.label


def test_challenge_admin_check_structure():
    check = is_admin_or_owner()
    assert callable(check)
