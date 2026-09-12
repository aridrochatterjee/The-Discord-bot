import pytest
import discord
from bot.cogs.community import ShowcaseModal, TechRolesView, TECH_ROLES


def test_tech_roles_definitions():
    assert len(TECH_ROLES) == 8
    labels = [r[0] for r in TECH_ROLES]
    assert any("Frontend" in l for l in labels)
    assert any("Backend" in l for l in labels)
    assert any("Python" in l for l in labels)
    assert any("Rust" in l for l in labels)


def test_tech_roles_view_buttons():
    view = TechRolesView()
    # 8 roles defined -> 8 buttons in view
    assert len(view.children) == 8
    for button in view.children:
        assert isinstance(button, discord.ui.Button)
        assert button.custom_id.startswith("techrole:")


def test_showcase_modal_inputs():
    modal = ShowcaseModal()
    assert modal.project_title is not None
    assert modal.tech_stack is not None
    assert modal.description is not None
    assert modal.project_title.required is True
    assert modal.description.required is True
    assert modal.github_url.required is False


def test_normalize_url():
    from bot.cogs.community import normalize_url
    assert normalize_url("github.com/test/repo") == "https://github.com/test/repo"
    assert normalize_url("https://example.com") == "https://example.com"
    assert normalize_url("   ") is None
