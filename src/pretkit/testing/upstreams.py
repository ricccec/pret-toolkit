"""Pinned game trees: one clean checkout per commit, in one cache every repo shares.

A test that reads a real disassembly is only reproducible against a fixed commit
of it, so each repo pins the trees it reads. This module turns a pin into a
directory holding exactly that commit — no working-copy edits, no build output —
and gathers a suite's pins into one *view*: a directory of links named the way
`shared.paths` looks for checkouts, so pointing `$PRET_CHECKOUT_BASES` at it
hands a process those trees and no others.

A copy is fetched from the local checkout of the same name when that one has the
commit, which costs no network, and from the pin's URL otherwise. Copies are
written once and never changed: building in one (`make`) is the only thing
anyone should do there.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

#: Overrides where the cache lives. Otherwise `$XDG_CACHE_HOME/pretkit`, and
#: `~/.cache/pretkit` when that is unset too.
CACHE_VAR = "PRETKIT_CACHE"

#: A full SHA-1 commit id. A short one is refused: it is a prefix that can stop
#: being unique, and a pin is the one place that must never become ambiguous.
COMMIT_LENGTH = 40


class FetchFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class Pin:
    #: The checkout's conventional folder name, as `paths.find_checkout` takes it.
    folder: str
    url: str
    commit: str

    @property
    def label(self) -> str:
        return f"{self.folder}@{self.commit[:9]}"


def find_cache_root() -> Path:
    if os.environ.get(CACHE_VAR):
        return Path(os.environ[CACHE_VAR]).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "pretkit"


def find_snapshot_path(pin: Pin) -> Path:
    return find_cache_root() / "upstreams" / f"{pin.folder}@{pin.commit}"


def find_view_path(pins: tuple[Pin, ...]) -> Path:
    """Where the view of exactly these pins lives — the same pins, the same view."""
    key: str = "\n".join(sorted(f"{p.folder}@{p.commit}" for p in pins))
    digest: str = hashlib.sha256(key.encode()).hexdigest()[:12]
    return find_cache_root() / "views" / digest


def ensure_snapshot(pin: Pin, local: Path | None) -> Path:
    """The clean copy of `pin`, fetched now if the cache does not hold it yet.

    Built in a staging directory and renamed into place, so an interrupted fetch
    leaves nothing a later run would mistake for a finished copy, and two runs
    racing to fetch the same pin both end up reading the one that landed first.
    """
    target: Path = find_snapshot_path(pin)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{pin.folder}-", dir=target.parent))
    try:
        fetch_commit_into(staging, pin, local)
        try:
            staging.rename(target)
        except OSError:
            if not target.exists():
                raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def fetch_commit_into(folder: Path, pin: Pin, local: Path | None) -> None:
    """Check out `pin.commit` alone into an empty `folder`, from the first source
    that has it: the local checkout, then the URL."""
    run_git(folder, "init", "-q")
    sources: list[str] = [str(local)] if local and (local / ".git").exists() else []
    sources.append(pin.url)
    errors: list[str] = []
    for source in sources:
        fetched = subprocess.run(
            ["git", "-C", str(folder), "fetch", "-q", "--depth", "1", source,
             pin.commit], capture_output=True, text=True)
        if fetched.returncode == 0:
            break
        errors.append(f"{source}: {fetched.stderr.strip() or 'fetch failed'}")
    else:
        raise FetchFailed(f"cannot fetch {pin.label} — " + "; ".join(errors))
    run_git(folder, "-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD")


def run_git(folder: Path, *args: str) -> None:
    done = subprocess.run(["git", "-C", str(folder), *args],
                          capture_output=True, text=True)
    if done.returncode:
        raise FetchFailed(f"git {' '.join(args)} in {folder}: {done.stderr.strip()}")


def ensure_view(pins: tuple[Pin, ...]) -> Path:
    """A directory holding one link per pin, named for its folder.

    A link whose copy could not be fetched still points where the copy would
    be, so a test looking for that tree finds nothing and says so — the view
    never falls back to a live checkout.
    """
    view: Path = find_view_path(pins)
    if view.exists():
        return view
    view.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".view-", dir=view.parent))
    for pin in pins:
        (staging / pin.folder).symlink_to(find_snapshot_path(pin))
    try:
        staging.rename(view)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        if not view.exists():
            raise
    return view
