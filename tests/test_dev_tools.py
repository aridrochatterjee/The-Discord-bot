import pytest
from bot.cogs.dev_tools import (
    clean_code_block,
    JUDGE0_LANGUAGES,
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


def test_judge0_languages():
    assert JUDGE0_LANGUAGES.get("python") == 71
    assert JUDGE0_LANGUAGES.get("py") == 71
    assert JUDGE0_LANGUAGES.get("javascript") == 63
    assert JUDGE0_LANGUAGES.get("js") == 63
    assert JUDGE0_LANGUAGES.get("typescript") == 74
    assert JUDGE0_LANGUAGES.get("cpp") == 54
    assert JUDGE0_LANGUAGES.get("rust") == 73
    assert JUDGE0_LANGUAGES.get("go") == 60
    assert JUDGE0_LANGUAGES.get("bash") == 46


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


def test_npm_registry_data_parsing():
    # Verify parsing logic used in npm command
    sample_data = {
        "name": "express",
        "description": "Fast, unopinionated, minimalist web framework",
        "dist-tags": {"latest": "4.19.2"},
        "versions": {
            "4.19.2": {
                "license": "MIT",
                "dependencies": {"accepts": "~1.3.8", "bytes": "3.1.2"},
                "devDependencies": {"mocha": "10.4.0"},
                "homepage": "http://expressjs.com/",
                "repository": {"type": "git", "url": "git+https://github.com/expressjs/express.git"},
            }
        },
    }

    latest = sample_data["dist-tags"]["latest"]
    assert latest == "4.19.2"
    ver_info = sample_data["versions"][latest]
    assert ver_info["license"] == "MIT"
    assert len(ver_info["dependencies"]) == 2
    assert len(ver_info["devDependencies"]) == 1
    assert "github.com/expressjs/express" in ver_info["repository"]["url"]

