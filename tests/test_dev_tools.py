import pytest
from bot.cogs.dev_tools import (
    clean_code_block,
    LANGUAGE_ALIASES,
    GITHUB_URL_RE,
    ANSI_ESCAPE_RE,
)


def test_clean_code_block_raw():
    code = "print('hello world')"
    assert clean_code_block(code) == "print('hello world')"


def test_clean_code_block_fenced():
    code = "```python\nprint('hello world')\n```"
    assert clean_code_block(code) == "print('hello world')"


def test_clean_code_block_fenced_no_lang():
    code = "```\nprint('hello world')\n```"
    assert clean_code_block(code) == "print('hello world')"


def test_language_aliases():
    assert LANGUAGE_ALIASES.get("py") == "python"
    assert LANGUAGE_ALIASES.get("js") == "javascript"
    assert LANGUAGE_ALIASES.get("ts") == "typescript"
    assert LANGUAGE_ALIASES.get("cpp") == "c++"
    assert LANGUAGE_ALIASES.get("rs") == "rust"
    assert LANGUAGE_ALIASES.get("golang") == "go"
    assert LANGUAGE_ALIASES.get("sh") == "bash"


def test_github_regex_formats():
    # Simple owner/repo
    m1 = GITHUB_URL_RE.search("aridrochatterjee/The-Discord-bot")
    assert m1 is not None
    assert m1.group(1) == "aridrochatterjee"
    assert m1.group(2) == "The-Discord-bot"

    # Full HTTPS URL
    m2 = GITHUB_URL_RE.search("https://github.com/torvalds/linux")
    assert m2 is not None
    assert m2.group(1) == "torvalds"
    assert m2.group(2) == "linux"


def test_ansi_escape_removal():
    colored_text = "\x1b[31mRed Alert\x1b[0m and \x1b[32mGreen\x1b[0m"
    cleaned = ANSI_ESCAPE_RE.sub("", colored_text)
    assert cleaned == "Red Alert and Green"


def test_parse_github_repo():
    from bot.cogs.dev_tools import parse_github_repo
    assert parse_github_repo("owner/repo") == ("owner", "repo")
    assert parse_github_repo("https://github.com/owner/repo.git") == ("owner", "repo")
    assert parse_github_repo("invalid-string") is None
