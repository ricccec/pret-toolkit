#!/usr/bin/env python3
"""Tests for `pret-test` — the thing that runs every repo's suite.

A runner that miscounts is worse than no runner: every other test is read
through it, and a classification bug reports a green suite while something is
broken. It also carries facts a person would otherwise have to remember — clear
the bytecode caches, known reds are asserted both ways, a flaky test is re-run
alone, the game trees are the pinned ones — and a fact that stops being enforced
is a fact nobody is told about.

So each is seeded here and checked to be caught, against a **throwaway repo**: a
temp directory with its own `pyproject.toml` and `tests/`, and a throwaway game
tree with two commits and an uncommitted edit. Nothing here reads this repo's
own suite table, so fixing a real known red can never turn this file red.

    python tests/test_runner.py
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pretkit.shared import paths
from pretkit.testing import runner, suite as suite_module
from pretkit.testing.results import FAIL, FIXED, OK, RED, Result, classify_exit_code

_failures = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global _failures
    print(f"  [{'OK  ' if cond else 'FAIL'}] {label}{(': ' + detail) if detail else ''}")
    if not cond:
        _failures += 1


PASSES = "print('  [OK] seeded')\n"
FAILS = "import sys\nprint('  [FAIL] seeded')\nsys.exit(1)\n"
HANGS = "import time\ntime.sleep(60)\n"

#: Fails once, then passes — a batch flake. The marker is not a `test_*.py`, so
#: the runner's own glob never collects it.
FLAKES_ONCE = """
import sys
from pathlib import Path
marker = Path(__file__).with_suffix(".marker")
if marker.exists():
    print('  [OK] passed alone')
    sys.exit(0)
marker.write_text('x')
print('  [FAIL] failed in the batch')
sys.exit(1)
"""

#: Prints what the tree it finds says about itself, so which tree a test was
#: shown is observable rather than inferred.
READS_TREE = """
from pretkit.shared import paths
tree = paths.find_checkout("madeupgame")
version = tree / "VERSION"
print("version=" + version.read_text().strip() if version.exists() else "  --   skipping: no tree")
other = paths.find_checkout("unpinnedgame")
print("unpinned:", "found" if (other / "main.asm").exists() else "absent")
"""


def make_repo(root: Path, table: str, tests: dict[str, str]) -> Path:
    (root / "tests").mkdir(parents=True)
    (root / "pyproject.toml").write_text(f"[project]\nname = 'seeded'\n\n{table}")
    for name, body in tests.items():
        (root / "tests" / f"{name}.py").write_text(body)
    return root


def run_main(argv: list[str]) -> tuple[int, str]:
    """Drive `main()` and capture what it printed — the report is half the
    behaviour, and a status nobody prints is a status nobody acts on."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = runner.main(argv)
    return code, buffer.getvalue()


def git(tree: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(tree), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def make_game_tree(root: Path) -> tuple[Path, str]:
    """A pret-shaped repo whose first commit says `pinned`, whose second says
    `newer`, and whose working copy says `edited`. Returns it and commit one."""
    root.mkdir(parents=True)
    git(root, "init", "-q")
    git(root, "config", "user.email", "seed@example.invalid")
    git(root, "config", "user.name", "seed")
    for name in ("Makefile", "main.asm"):
        (root / name).write_text("")
    (root / "VERSION").write_text("pinned\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "one")
    first = git(root, "rev-parse", "HEAD")
    (root / "VERSION").write_text("newer\n")
    git(root, "commit", "-q", "-am", "two")
    (root / "VERSION").write_text("edited\n")
    return root, first


def test_classification() -> None:
    """All four corners, and both directions of the known-red list."""
    print("\nclassify_exit_code")
    red = {"test_red": "seeded"}
    check("an unknown test exiting 0 is ok", classify_exit_code("test_x", 0, red) == OK)
    check("an unknown test exiting 1 is a FAIL", classify_exit_code("test_x", 1, red) == FAIL)
    check("a known red exiting 1 is expected", classify_exit_code("test_red", 1, red) == RED)
    check("a known red exiting 0 is FIXED, not silence",
          classify_exit_code("test_red", 0, red) == FIXED)
    for status, unexpected in ((FAIL, True), (FIXED, True), (RED, False), (OK, False)):
        check(f"{status} is {'' if unexpected else 'not '}unexpected",
              Result("x", status, 0.0, "").is_unexpected is unexpected)


def test_failures_and_rows(tmp: Path) -> None:
    print("\na failing test, a fixed row, a hung test")
    repo = make_repo(tmp / "fails", '[tool.pret-test]\nknown-red = { test_fixed = "seeded" }\n',
                     {"test_seeded": FAILS, "test_fixed": PASSES, "test_hung": HANGS})
    code, report = run_main(["--repo", str(repo), "-k", "seeded"])
    check("a failure exits non-zero", code == 1)
    check("and names the test", "FAIL: test_seeded" in report)
    check("and prints its output, unasked", "[FAIL] seeded" in report)

    code, report = run_main(["--repo", str(repo), "-k", "fixed"])
    check("a known red that passes fails the run", code == 1)
    check("and says to delete the row", "delete its row from known-red" in report, report[-200:])

    code, report = run_main(["--repo", str(repo), "-k", "hung", "--timeout", "2"])
    check("a timeout is a FAIL, not a pass", code == 1 and "after 2s" in report)


def test_local_red_is_about_your_checkouts(tmp: Path) -> None:
    """A `.known-red.json` row forgives a failure in a `--worktree` run, which
    reads your edited checkouts, and nowhere else: a pinned run never sees
    those edits, so a red there is a red."""
    print("\nthe local known-red file")
    repo = make_repo(tmp / "local", "[tool.pret-test]\n", {"test_drifted": FAILS})
    (repo / ".known-red.json").write_text('{"test_drifted": "my tree, not yours"}')
    code, report = run_main(["--repo", str(repo), "--worktree"])
    check("under --worktree it is an expected red", code == 0 and "known red (local)" in report)
    code, report = run_main(["--repo", str(repo)])
    check("in a pinned run it is a failure, and the run says why",
          code == 1 and "applies to --worktree runs only" in report)


def test_flaky_retry(tmp: Path) -> None:
    print("\na test that fails in the batch and passes alone")
    repo = make_repo(tmp / "flaky", '[tool.pret-test]\nflaky-in-batch = ["test_flaky"]\n',
                     {"test_flaky": FLAKES_ONCE})
    code, report = run_main(["--repo", str(repo)])
    check("the retry is announced, not hidden", "re-running it alone" in report)
    check("and the second answer is reported", "passed alone" in report and code == 0)

    (repo / "tests" / "test_flaky.py").write_text(FAILS)
    code, report = run_main(["--repo", str(repo)])
    check("a retry that fails too is called real", "failed alone too" in report and code == 1)


def test_selection_and_lists(tmp: Path) -> None:
    print("\nselection, and lists that name absent tests")
    repo = make_repo(tmp / "select", '[tool.pret-test]\nslow = ["test_slowpoke"]\n',
                     {"test_alpha": PASSES, "test_beta": PASSES, "test_slowpoke": PASSES})
    seeded = suite_module.load_suite(repo)
    every = {p.stem for p in runner.select_test_files(seeded, None, False)}
    fast = {p.stem for p in runner.select_test_files(seeded, None, True)}
    check("a full run collects every test file", every == {"test_alpha", "test_beta", "test_slowpoke"})
    check("--fast drops the slow ones and nothing else", every - fast == {"test_slowpoke"})
    check("-k filters by filename",
          [p.stem for p in runner.select_test_files(seeded, "beta", False)] == ["test_beta"])

    typo = make_repo(tmp / "typo", '[tool.pret-test]\nslow = ["test_slowpok"]\n', {"test_a": PASSES})
    code, report = run_main(["--repo", str(typo)])
    check("a list naming an absent test refuses to run", code == 2 and "test_slowpok" in report)

    (typo / ".known-red.json").write_text("{not json")
    (typo / "pyproject.toml").write_text("[tool.pret-test]\n")
    code, report = run_main(["--repo", str(typo)])
    check("a malformed .known-red.json refuses rather than reads as empty",
          code == 2 and "not valid JSON" in report)


def test_pinned_trees(tmp: Path) -> None:
    """The pin is what a test sees — not the checkout's later commit, not its
    uncommitted edit, not a tree the repo does not pin — and `--worktree` is the
    one way to see the checkout as it is."""
    print("\npinned trees")
    tree, first = make_game_tree(tmp / "checkouts" / "madeupgame")
    unpinned, _ = make_game_tree(tmp / "checkouts" / "unpinnedgame")
    table = (f'[tool.pret-test]\n\n[tool.pret-test.upstreams.madeupgame]\n'
             f'url = "file:///nowhere"\ncommit = "{first}"\n')
    repo = make_repo(tmp / "pinned", table, {"test_reads_tree": READS_TREE})
    saved = dict(os.environ)
    os.environ.update({"PRETKIT_CACHE": str(tmp / "cache"),
                       "MADEUPGAME_TREE": str(tree), "UNPINNEDGAME_TREE": str(unpinned)})
    try:
        code, report = run_main(["--repo", str(repo), "-v"])
        check("the test sees the pinned commit, not a later one or the edit",
              "version=pinned" in report and "version=newer" not in report
              and "version=edited" not in report)
        check("and not a tree its repo does not pin", "unpinned: absent" in report)
        check("the pin came from the local checkout, not the URL", code == 0)
        check("and the checkout itself was left alone",
              (tree / "VERSION").read_text() == "edited\n")

        code, report = run_main(["--repo", str(repo), "-v", "--worktree"])
        check("--worktree shows the checkout as it is, edits and all", "version=edited" in report)
        check("including trees nobody pinned", "unpinned: found" in report)

        bad = f'[tool.pret-test.upstreams.lostgame]\nurl = "file:///nowhere"\ncommit = "{"0" * 40}"\n'
        (repo / "pyproject.toml").write_text(f"[tool.pret-test]\n\n{bad}")
        code, report = run_main(["--repo", str(repo), "--fetch"])
        check("a pin nobody can fetch is named, and fails --fetch",
              code == 1 and "lostgame@000000000  NOT FETCHED" in report)
        code, report = run_main(["--repo", str(repo), "--strict"])
        check("its tree is then absent, which --strict fails on", code == 1 and "--strict" in report)

        (repo / "pyproject.toml").write_text(table.replace(first, first[:12]))
        code, report = run_main(["--repo", str(repo)])
        check("a short SHA is refused", code == 2 and "full 40-character SHA" in report)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def test_relative_bases_refused() -> None:
    print("\n$PRET_CHECKOUT_BASES")
    saved = os.environ.get(paths.CHECKOUT_BASES_VAR)
    os.environ[paths.CHECKOUT_BASES_VAR] = "relative/dir"
    try:
        paths.read_checkout_bases()
        refused = False
    except ValueError as stop:
        refused = "relative/dir" in str(stop)
    finally:
        if saved is None:
            del os.environ[paths.CHECKOUT_BASES_VAR]
        else:
            os.environ[paths.CHECKOUT_BASES_VAR] = saved
    check("a relative base is refused by name", refused)


if __name__ == "__main__":
    test_classification()
    test_relative_bases_refused()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        test_failures_and_rows(tmp)
        test_local_red_is_about_your_checkouts(tmp)
        test_flaky_retry(tmp)
        test_selection_and_lists(tmp)
        test_pinned_trees(tmp)
    print(f"\n{'FAILURES: ' + str(_failures) if _failures else 'all ok'}")
    sys.exit(1 if _failures else 0)
