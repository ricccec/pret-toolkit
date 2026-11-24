"""Emptying every cache in the toolchain, for when the repo changed underneath it.

Half a dozen modules here memoise their reads with `@lru_cache`, keyed by the
repo root — the item constants, the charmap, the landmarks, the tileset swatches,
the textbox metrics. That is right: they are read constantly and they change
almost never, and a `Session` that re-parsed `item_constants.asm` on every
keystroke would be a `Session` nobody could type into.

But an `lru_cache` lives on the *function*, which lives on the *module*, which
lives for the whole process. So it outlives any object that might think it owns
it. `Session.reload()` can drop its own caches all it likes; if `consts.names`
still has last hour's items in it, the studio will go on offering last hour's
items, and it will do so with total confidence. That is the bug this module
exists to prevent, and it is one I shipped before writing this: `reload()` looked
right, tested wrong, and the test is the only reason it isn't still wrong.

:func:`clear` finds the caches instead of naming them. A hardcoded list is a list
somebody adds the seventh cache to and forgets — and the failure is silent, and
it is *stale data*, which is the failure you notice last and trust the most.

It finds the *packages* the same way. The caches that go stale live in this
library, in the IDE, and in whichever hack adapter is mounted — three or more
distributions, each its own top-level package, and this library may not name any
of the others. What they share is that each depends on this one, directly or
through another that does, so the installed metadata says which they are.
"""

from __future__ import annotations

import re
import sys
from importlib import metadata

#: The distribution every package whose caches matter depends on, at the end
#: of some chain of requirements. This one.
_FLOOR = "pret-toolkit"

_REQUIREMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def find_family_packages() -> set[str]:
    """Top-level packages of this distribution and of every installed one that
    depends on it, however indirectly."""
    requires: dict[str, set[str]] = {}
    packages: dict[str, set[str]] = {}
    for dist in metadata.distributions():
        name: str = normalize_distribution_name(dist.metadata["Name"] or "")
        needed = {normalize_distribution_name(m.group(0))
                  for r in dist.requires or [] if (m := _REQUIREMENT_NAME.match(r))}
        requires[name] = needed
        packages[name] = set((dist.read_text("top_level.txt") or "").split())
    family = {_FLOOR}
    grown = True
    while grown:
        joining = {n for n, needed in requires.items() if needed & family} - family
        family |= joining
        grown = bool(joining)
    found: set[str] = set().union(*(packages.get(n, set()) for n in family))
    return found | {__name__.split(".")[0]}


def clear() -> int:
    """Empty every `lru_cache` in every loaded module of the family's packages.

    Returns how many it emptied, which is worth having: "0" means the discovery
    stopped working, and a cache-clearing function that silently clears nothing
    is worse than no cache-clearing function at all.

    Only *imported* modules are walked, which is exactly the set that could be
    holding anything — a module nobody has imported has no cache to hold.
    """
    roots: set[str] = find_family_packages()
    cleared = 0
    for name, module in list(sys.modules.items()):
        if name.split(".")[0] not in roots or module is None:
            continue
        for obj in vars(module).values():
            # `cache_clear` is the whole signature of an lru_cache-wrapped
            # function. Duck typing is the right tool here precisely because the
            # point is to catch the ones nobody remembered to register.
            if callable(obj) and callable(getattr(obj, "cache_clear", None)):
                obj.cache_clear()
                cleared += 1
    return cleared
