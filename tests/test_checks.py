import pytest
from bot.utils.checks import is_guild_owner, is_admin, has_any_role


def test_checks_exist():
    # Verify decorators can be instantiated
    owner_check = is_guild_owner()
    admin_check = is_admin()
    role_check = has_any_role("Admin", "Moderator")

    assert callable(owner_check)
    assert callable(admin_check)
    assert callable(role_check)
