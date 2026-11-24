"""Run a repo's test suite against the game trees it pins, and know which
failures are already known.

    pret-test                 # every test in this repo, in parallel
    pret-test --fast          # everything except the ones the repo calls slow
    pret-test -k family       # just the ones whose name matches
    pret-test --worktree      # read your own checkouts instead of the pins
    pret-test --fetch         # fetch the pinned trees, print where, run nothing
    pret-test --strict        # a skip fails the run too

The tests are plain scripts, not pytest: each prints `ok`/`FAIL` lines and exits
non-zero. This is a loop plus the facts a person otherwise has to remember, each
of which has cost somebody time:

**The trees are pinned.** A test reading a real disassembly is a test of that
commit, so by default every test sees a clean copy of the commit its repo pins
and nothing else: not your checkout's edits, not its branch, not a tree the repo
does not pin. `--worktree` hands the tests your own checkouts instead, as they
are — the way to see what your edits do.

**The bytecode cache must be cleared first.** A stale `.pyc` once faked a
passing result, with matching size and mtime, and cost half a day.

**Some tests fail intermittently in a batch and pass alone.** The cause is
unidentified — separate processes should not share anything — so the rule is
empirical: a flaky test that fails is re-run by itself after every other test
has finished, and the second answer is the one reported. Both are printed,
because "passed on retry" is a fact about the suite worth seeing.
"""

from __future__ import annotations

import argparse
import dataclasses
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..shared import paths
from .report import format_result_line, print_report
from .results import FAIL, OK, Result, classify_exit_code
from .suite import (LOCAL_RED_NAME, Suite, SuiteError, find_names_not_in_repo,
                    find_suite_repo, load_suite)
from .upstreams import FetchFailed, ensure_snapshot, ensure_view

DEFAULT_TIMEOUT = 600

#: The per-tree overrides `shared.paths` honours. Dropped in a pinned run, since
#: each would win over the pins for its own tree.
_TREE_VAR = re.compile(r"[A-Z0-9_]+_TREE")


def find_interpreter(repo: Path) -> Path:
    """`<repo>/.venv/bin/python` when the repo has one, else this interpreter."""
    conventional = repo / ".venv" / "bin" / "python"
    return conventional if conventional.exists() else Path(sys.executable)


def prepare_pinned_trees(suite: Suite) -> tuple[dict[str, str], list[str]]:
    """The environment that shows the tests the pinned trees and no others,
    and one line per pin saying where it is or why it is missing."""
    lines: list[str] = []
    for pin in suite.upstreams:
        local: Path = paths.find_checkout(pin.folder)
        try:
            lines.append(f"  {pin.label}  {ensure_snapshot(pin, local)}")
        except FetchFailed as missing:
            lines.append(f"  {pin.label}  NOT FETCHED — {missing}")
    view: Path = ensure_view(suite.upstreams)
    env = {k: v for k, v in os.environ.items() if not _TREE_VAR.fullmatch(k)}
    env[paths.CHECKOUT_BASES_VAR] = str(view)
    return env, lines or ["  (this repo pins no game tree)"]


def clear_bytecode_caches(repo: Path) -> int:
    """Delete every `__pycache__` outside the venv. Returns how many."""
    removed = 0
    for cache in repo.rglob("__pycache__"):
        if ".venv" in cache.parts:
            continue
        shutil.rmtree(cache, ignore_errors=True)
        removed += 1
    return removed


def select_test_files(suite: Suite, pattern: str | None, skip_slow: bool) -> list[Path]:
    chosen = sorted(suite.tests_dir.glob("test_*.py"))
    if pattern:
        chosen = [p for p in chosen if pattern in p.stem]
    if skip_slow:
        chosen = [p for p in chosen if p.stem not in suite.slow]
    return chosen


def run_one_test(path: Path, suite: Suite, env: dict[str, str], timeout: int) -> Result:
    started = time.monotonic()
    try:
        done = subprocess.run(
            [str(find_interpreter(suite.repo)), str(path)], cwd=suite.repo,
            env={**env, "PYTHONDONTWRITEBYTECODE": "1"}, timeout=timeout,
            capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return Result(path.stem, FAIL, time.monotonic() - started, "",
                      f"no result after {timeout}s")
    status: str = classify_exit_code(path.stem, done.returncode, suite.expected_red)
    return Result(path.stem, status, time.monotonic() - started,
                  done.stdout + done.stderr)


def run_all_tests(test_files: list[Path], suite: Suite, env: dict[str, str],
                  jobs: int, timeout: int) -> list[Result]:
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_one_test, p, suite, env, timeout) for p in test_files]
        results = []
        for future in futures:
            result = future.result()
            print(format_result_line(result))
            results.append(result)
    return results


def rerun_flaky_alone(results: list[Result], suite: Suite, env: dict[str, str],
                      timeout: int) -> None:
    """Re-run failed flaky tests one at a time, in place, and keep the second
    answer. The retry prints its own line: the batch line is already on screen
    saying the test failed."""
    for i, r in enumerate(results):
        if r.name not in suite.flaky_in_batch or not r.is_unexpected:
            continue
        print(f"  … {r.name} failed in the batch — re-running it alone")
        retry = run_one_test(suite.tests_dir / f"{r.name}.py", suite, env, timeout)
        retry.note = ("passed alone, so the batch failure was the flake"
                      if retry.status == OK else "failed alone too — real")
        print(format_result_line(retry))
        results[i] = retry


def count_skips(results: list[Result]) -> int:
    return sum(r.checks_skipped for r in results)


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pret-test", description=__doc__.splitlines()[0])
    parser.add_argument("-k", dest="pattern", metavar="TEXT",
                        help="only tests whose filename contains TEXT")
    parser.add_argument("--fast", action="store_true", help="skip the repo's slow tests")
    parser.add_argument("-j", dest="jobs", type=int, default=os.cpu_count(),
                        help="tests to run at once (default: one per core)")
    parser.add_argument("-v", dest="verbose", action="store_true",
                        help="print output from every test, not just failures")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"seconds before a test is called hung (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--worktree", action="store_true",
                        help="read your own checkouts, edits and all, instead of the pins")
    parser.add_argument("--fetch", action="store_true",
                        help="fetch the pinned trees, print where they are, run nothing")
    parser.add_argument("--strict", action="store_true",
                        help="fail the run if any check was skipped")
    parser.add_argument("--repo", type=Path, default=None,
                        help="the repo whose suite to run (default: the one you are in)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    try:
        suite: Suite = load_suite(args.repo or find_suite_repo(Path.cwd()))
    except SuiteError as bad:
        print(bad)
        return 2
    absent = find_names_not_in_repo(suite)
    if absent:
        rows = "\n".join(f"  {where}: {', '.join(names)}" for where, names in sorted(absent.items()))
        print(f"these name tests this repo does not have, under {suite.tests_dir}:\n{rows}\n"
              f"A list that names an absent test is filtered away in silence, "
              f"so it can never be wrong out loud.")
        return 2

    if args.worktree:
        env, tree_lines = dict(os.environ), ["  your own checkouts, as they are (--worktree)"]
    else:
        env, tree_lines = prepare_pinned_trees(suite)
        if suite.local_red:
            tree_lines.append(f"  ({LOCAL_RED_NAME} is about your own checkouts, so it "
                              f"applies to --worktree runs only)")
            suite = dataclasses.replace(suite, local_red={})
    print("game trees:\n" + "\n".join(tree_lines))
    if args.fetch:
        return 1 if any("NOT FETCHED" in line for line in tree_lines) else 0

    test_files = select_test_files(suite, args.pattern, args.fast)
    if not test_files:
        print(f"No test matches {args.pattern!r}.")
        return 2
    print(f"cleared {clear_bytecode_caches(suite.repo)} __pycache__ directories")
    print(f"running {len(test_files)} tests, {args.jobs} at a time\n")

    started = time.monotonic()
    results = run_all_tests(test_files, suite, env, args.jobs, args.timeout)
    rerun_flaky_alone(results, suite, env, args.timeout)
    skipped_slow = sorted(suite.slow) if args.fast else []
    print_report(results, suite, args.verbose, skipped_slow, time.monotonic() - started)

    if any(r.is_unexpected for r in results):
        return 1
    if args.strict and count_skips(results):
        print(f"  --strict: {count_skips(results)} skipped, so the run fails")
        return 1
    return 0
