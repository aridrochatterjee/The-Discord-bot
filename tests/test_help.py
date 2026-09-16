import pytest
import discord
from bot.cogs.help import HelpSelect


class DummyAuthor:
    id = 123456789
    name = "HorizonDev"


def test_help_select_options():
    dummy = DummyAuthor()
    select = HelpSelect(dummy)
    values = [opt.value for opt in select.options]
    assert "dev_tools" in values
    assert "moderation" in values
    assert "general" in values
    assert "community" in values


def test_help_category_embeds():
    dummy = DummyAuthor()
    select = HelpSelect(dummy)

    for cat in ["dev_tools", "moderation", "general", "community"]:
        embed = select.get_category_embed(cat)
        assert isinstance(embed, discord.Embed)
        assert embed.title is not None
        assert len(embed.fields) > 0
