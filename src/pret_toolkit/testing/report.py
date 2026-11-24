"""What a run prints once every test has answered."""

from __future__ import annotations

from .results import FAIL, FIXED, OK, RED, Result
from .suite import LOCAL_RED_NAME, Suite


def format_result_line(result: Result) -> str:
    return (f"  [{result.status:>7}] {result.name}  {result.seconds:.1f}s"
            f"{'  — ' + result.note if result.note else ''}")


def print_report(results: list[Result], suite: Suite, verbose: bool,
                 skipped_slow: list[str], wall: float) -> None:
    for r in results:
        if r.output and (verbose or r.is_unexpected):
            print(f"\n{'=' * 70}\n{r.name} [{r.status}]\n{'=' * 70}\n{r.output}")

    tally = {s: [r.name for r in results if r.status == s]
             for s in (OK, RED, FAIL, FIXED)}
    print(f"\n{len(tally[OK])}/{len(results)} ok in {wall:.1f}s"
          f" — {len(tally[RED])} known red")
    print_skipped_checks(results)
    if skipped_slow:
        print(f"  not run (--fast): {', '.join(skipped_slow)}")
    for name in tally[RED]:
        where = "local" if name in suite.local_red else "committed"
        print(f"  known red ({where}): {name} — {suite.expected_red[name]}")
    for r in results:
        if r.note:
            print(f"  re-run alone: {r.name} — {r.note}")
    for name in tally[FIXED]:
        source = LOCAL_RED_NAME if name in suite.local_red else "known-red"
        print(f"  FIXED: {name} passes now — delete its row from {source}")
    for name in tally[FAIL]:
        print(f"  FAIL: {name}")


def print_skipped_checks(results: list[Result]) -> None:
    partial = [r for r in results if r.checks_skipped]
    if not partial:
        return
    total = sum(r.checks_skipped for r in partial)
    print(f"  {total} checks skipped inside {len(partial)} file(s) — a pass "
          f"here means the checks that ran passed, not that they all ran:")
    for r in sorted(partial, key=lambda r: -r.checks_skipped):
        print(f"    {r.name}: {r.checks_skipped}")
