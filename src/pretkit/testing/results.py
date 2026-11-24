"""One test file's outcome, and how an exit code becomes one.

**Known reds are asserted in both directions.** A runner that only forgives
known failures rots: the entry outlives the bug, and the day the test starts
passing nobody notices. So a known-red test that goes green fails the run, and
the fix is to delete its row deliberately.

**A skip is counted, never read as a pass.** A file whose real half never ran —
almost always because a game tree was not there — still prints `all checks
passed` and still exits 0. The skip lines it printed are the only evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

OK, RED, FAIL, FIXED = "ok", "red", "FAIL", "FIXED"

#: A line a test prints when it declines to run a check.
_SKIP_LINE = re.compile(r"\bskip(?:ped|ping)?\b", re.I)

#: A line reporting one check's verdict, in either spelling the suites use.
#: Excluded from the skip count because a check *about* skipping is a check
#: that ran: a test asserting an absent tree skips says the word in its own
#: passing output, and that is not a skip of its own.
_VERDICT_LINE = re.compile(r"^\s*(\[\s*(?:OK|FAIL)\s*\]|ok\s|FAIL\s)")


@dataclass
class Result:
    name: str
    status: str
    seconds: float
    output: str
    note: str = ""

    @property
    def is_unexpected(self) -> bool:
        return self.status in (FAIL, FIXED)

    @property
    def checks_skipped(self) -> int:
        """How many checks this file said it was not running."""
        return sum(1 for line in self.output.splitlines()
                   if _SKIP_LINE.search(line) and not _VERDICT_LINE.match(line))


def classify_exit_code(name: str, code: int, expected_red: dict[str, str]) -> str:
    """Both directions: an unexpected failure and an unexpected pass both fail."""
    if name in expected_red:
        return RED if code else FIXED
    return FAIL if code else OK
