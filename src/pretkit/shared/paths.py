"""Locate a pret repo's build artifacts, relative to its root.

**How a repo root is recognised, stated because it is a heuristic and not a
fact:** walk up from the starting directory until a `Makefile` and a `main.asm`
sit in the same folder. Neither alone is enough — a `Makefile` is in half the
directories on a developer's machine, and `main.asm` alone would match an
extracted source dump that cannot build. Together they are the pret signature,
and all three trees this repo reads carry both (measured 2026-08-05: pokecrystal,
polishedcrystal, pokeprism). It will still accept any other pret-shaped
checkout, which is the intent — this module knows about *pret*, not about a hack.

**Which ROM, and why that is two questions.** A tree's *candidates* are read
from its `Makefile`, because a target name is a ROM filename and `make` is the
only thing that knows both. Which candidate a caller *wants* is the caller's
business and never this module's: the three trees measured on 2026-08-05 do not
agree on the question, let alone the answer.

    prism      roms := pokeprism.gbc pokeprism_nodebug.gbc
    vanilla    roms := \\ (five ROMs, continued over six lines)
    polished   no `roms :=` at all — make assembles the name from NAME/VERSION

**And no textual rule over those three finds "the debug build".** Prism inverts
the convention: `pokeprism.gbc` *is* the debug ROM and `pokeprism_nodebug.gbc`
is the plain one, so a name test is right in vanilla, absent in polished and
backwards in prism. That preference is a hack's knowledge and crosses the seam
as declared data — :data:`hacks.prism.roms.DEBUG_ROM`, passed in as `prefer`.
This module offers the list and resolves a choice; it does not have opinions.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

class RepoNotFound(RuntimeError):
    pass


#: The `Makefile` assignment listing every ROM `make` can build. One logical
#: line, sometimes spread over several physical ones with trailing backslashes.
_ROMS_ASSIGNMENT = re.compile(r"^\s*roms\s*:=")

_ROM_NAME = re.compile(r"\S+\.gbc")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or cwd) until we find the Makefile."""
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "Makefile").exists() and (candidate / "main.asm").exists():
            return candidate
    raise RepoNotFound(
        f"Could not find a pret repo root from {p} — no Makefile + main.asm "
        "found in any parent directory."
    )


#: Where a checkout is looked for when nothing says. Each is a directory that
#: may hold one, tried in order; `*` matches a single grouping directory, which
#: is the common `~/code/<org>/<repo>` habit. Deliberately not a user's own
#: layout: a default that names one developer's directories is a default that
#: works for one developer.
#:
#: **Every entry is anchored at `~`, never at the working directory.** A
#: relative base resolves against wherever the process happened to start, so the
#: same call answers differently run from a repo root and from its `tests/`, and
#: the wrong answer is an absent tree — which reads as a skip, which reads as a
#: pass. A checkout somewhere else is what the environment variable is for.
CHECKOUT_BASES = ("~/code", "~/src", "~", "~/code/*", "~/src/*",
                  "~/Projects/*", "~/projects/*")


def checkout_env_var(folder: str) -> str:
    """The environment variable that overrides where `folder` is looked for.

    Derived rather than declared, so a caller naming a checkout never has to
    know a second name for it, and a tree this library has never heard of gets
    an override on the same terms as the three it has.
    """
    return folder.upper() + "_TREE"


def checkout_search_path(folder: str) -> tuple[Path, ...]:
    """Every directory `find_checkout` would consider for `folder`, in order.

    Exposed so a caller that found nothing can say where it looked. A skip that
    names no path is indistinguishable from a pass.
    """
    override = os.environ.get(checkout_env_var(folder))
    if override:
        return (Path(override).expanduser(),)
    found: list[Path] = []
    for base in CHECKOUT_BASES:
        if "*" in base:
            head, _, tail = base.partition("/*")
            found.extend(sorted(parent / tail.lstrip("/") / folder
                                for parent in Path(head).expanduser().glob("*")
                                if parent.is_dir()))
        else:
            found.append(Path(base).expanduser() / folder)
    return tuple(found)


def explain_missing_checkout(folder: str) -> str:
    """One line saying `folder` was not found, and how to say where it is.

    For the message a caller prints when it declines to run. A skip that names
    nothing cannot be told from a pass by anyone reading the output later, and
    this repo has already shipped a run that reported a known-red test as fixed
    because of one.
    """
    env = checkout_env_var(folder)
    looked = checkout_search_path(folder)
    if os.environ.get(env):
        return f"no pret checkout at {looked[0]}, which {env} names"
    shown = ", ".join(str(path) for path in looked[:3])
    more = f", and {len(looked) - 3} other places" if len(looked) > 3 else ""
    return (f"no {folder} checkout — set {env}=/path/to/{folder}, "
            f"or put one at {shown}{more}")


def find_checkout(folder: str) -> Path:
    """A pret checkout named `folder`, from its variable or a conventional place.

    Answers the question `find_repo_root` does not: that one asks *which tree am
    I standing in*, this one asks *where on this machine is the tree called
    `pokecrystal`*. A tool that reads several trees at once can never be standing
    in all of them.

    The variable wins outright and is returned unexamined, so a path a caller set
    explicitly fails by its own name rather than being silently passed over for
    a different tree that happens to be well-formed. Otherwise the conventional
    locations are tried in order and the first with the pret signature wins.

    Returns a path that may not exist, because the caller — usually a test that
    must skip rather than fail — needs something to name either way.
    """
    candidates = checkout_search_path(folder)
    for candidate in candidates:
        if (candidate / "Makefile").exists() and (candidate / "main.asm").exists():
            return candidate
    return candidates[0]


def read_built_roms(root: Path | None = None) -> tuple[str, ...]:
    """Every ROM this tree can build, in the `Makefile`'s own order.

    Read from source rather than guessed, so the list cannot drift from what
    `make` will accept — and so a tool serves a tree it has never been told
    about. The `Makefile`'s order is the tree author's own preference, and the
    first entry is what a caller with no opinion gets.

    **A tree with no `roms :=` falls back to what is on disk**, which is
    polishedcrystal: its ROM name is assembled by make from `$(NAME)`,
    `$(MODIFIERS)` and `$(VERSION)`, so there is no list to read and the only
    evidence is the `.gbc` a build left behind. That makes the answer weaker
    there — a ROM that exists rather than a target that could — and the
    weakness is the honest one, because the alternative is inventing a name.

    An unreadable `Makefile` (a tree mid-edit, a binary file) yields `()`: "I
    cannot see the build", which callers degrade around. Cheap enough — one
    small file, scanned to the block's end — to re-read every call rather than
    cache a file a person may be editing.
    """
    root = root or find_repo_root()
    out: list[str] = []
    collecting = False
    for raw in _read_makefile_lines(root):
        if _ROMS_ASSIGNMENT.match(raw):
            collecting = True
        if collecting:
            out += _ROM_NAME.findall(raw)
            if not raw.rstrip().endswith("\\"):
                break
    if out:
        return tuple(out)
    return tuple(sorted(p.name for p in root.glob("*.gbc")))


def _read_makefile_lines(root: Path) -> list[str]:
    try:
        return (root / "Makefile").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def find_built_rom(root: Path | None = None, *,
                   prefer: tuple[str, ...] = (), fallback: bool = True) -> Path:
    """Resolve one built ROM: the first of `prefer` on disk, else the first
    candidate on disk.

    `prefer` names ROM filenames, in the caller's order of preference — the
    caller's, not the `Makefile`'s. A caller with no opinion passes nothing and
    gets whatever is lying around, which is what a reader wants.

    **`fallback=False` if you just built one of them.** The fallback exists for
    a reader — `pret-usage` wants whichever ROM is there and either will do. It
    is wrong for anybody who *chose* a target: build one while a stale sibling
    is still on disk and a falling-back caller hands back the sibling, so you
    would patch a save against one game and play the other, with your new map
    missing from it and nothing on screen to say why.
    """
    root = root or find_repo_root()
    # `fallback=False` means the caller's list is the *whole* list. Appending
    # the candidates to it and then refusing afterwards would be no refusal at
    # all: the stale sibling is a candidate too, and it is the thing being
    # refused.
    candidates = read_built_roms(root)
    for name in (prefer if prefer and not fallback else (*prefer, *candidates)):
        if (rom := root / name).exists():
            return rom

    if prefer and not fallback:
        raise FileNotFoundError(
            f"No ROM at {root / prefer[0]}. Build it first.")
    known = ", ".join(candidates) if candidates else "none that this Makefile names"
    raise FileNotFoundError(
        f"No built ROM in {root}. Run `make` first — this tree builds: {known}.")


def find_built_sym(root: Path | None = None, *,
             prefer: tuple[str, ...] = (), fallback: bool = True) -> Path:
    """The `.sym` beside the resolved ROM."""
    return _find_sibling_artifact(
        find_built_rom(root, prefer=prefer, fallback=fallback), ".sym")


def find_built_map(root: Path | None = None, *,
             prefer: tuple[str, ...] = ()) -> Path:
    """The `.map` beside the resolved ROM."""
    return _find_sibling_artifact(find_built_rom(root, prefer=prefer), ".map")


def count_rom_banks(rom: Path) -> int:
    """Total number of 16 KiB ROM banks the cartridge declares — i.e. what the
    hardware sees, including the trailing padding banks rgbfix appends.

    Reads the ROM-size byte at $0148 (banks = 2 << code for codes $00–$08).
    Falls back to the file size if the byte is unreadable or non-standard;
    rgbfix always pads to a whole number of banks, so that's exact too.
    """
    try:
        with rom.open("rb") as f:
            f.seek(0x0148)
            code = f.read(1)
        if len(code) == 1 and code[0] <= 0x08:
            return 2 << code[0]
        return max(1, rom.stat().st_size // 16_384)
    except OSError:
        return 0


def _find_sibling_artifact(rom: Path, suffix: str) -> Path:
    candidate = rom.with_suffix(suffix)
    if not candidate.exists():
        raise FileNotFoundError(
            f"Expected {candidate} alongside {rom.name}. Rebuild to regenerate it."
        )
    return candidate
