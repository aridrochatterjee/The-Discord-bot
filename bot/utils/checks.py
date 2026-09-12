from __future__ import annotations

from typing import Callable, TypeVar

import discord
from discord.ext import commands


T = TypeVar("T")


def is_guild_owner() -> Callable[[T], T]:
    """Check if the command invoker is the server owner."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("This command can only be used in a server.")
        if ctx.author.id != ctx.guild.owner_id:
            raise commands.CheckFailure("You must be the server owner to use this command.")
        return True

    return commands.check(predicate)


def is_admin() -> Callable[[T], T]:
    """Check if the command invoker has administrator permissions."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("This command can only be used in a server.")
        if not isinstance(ctx.author, discord.Member):
            return False
        if not ctx.author.guild_permissions.administrator:
            raise commands.MissingPermissions(["administrator"])
        return True

    return commands.check(predicate)


def has_any_role(*role_names: str) -> Callable[[T], T]:
    """Check if the member has at least one of the specified roles."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            return False
        user_role_names = {r.name.lower() for r in ctx.author.roles}
        if any(name.lower() in user_role_names for name in role_names):
            return True
        raise commands.CheckFailure(f"You require one of these roles: {', '.join(role_names)}")

    return commands.check(predicate)
