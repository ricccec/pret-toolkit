"""A repo's own description of its suite, read from `[tool.pret-test]`.

Each repo defines its tests — the files under `tests/` — and the facts about
them this table holds: which fail for a reason true in every clone, which flake
in a batch, which are slow, and which commit of each game tree they were written
against. The runner holds none of that, so one runner serves every repo.

    [tool.pret-test]
    known-red = { test_name = "why it fails in every clone" }
    flaky-in-batch = ["test_name"]
    slow = ["test_name"]

    [tool.pret-test.upstreams.pokecrystal]
    url = "https://github.com/pret/pokecrystal"
    commit = "<40-character SHA>"

A working copy's own reds — a live tree carrying an edit — go in `.known-red.json`
beside `pyproject.toml`, which is git-ignored: committed, a row tells every other
clone that a test it will watch pass is expected to fail. It counts only in a
`--worktree` run, since a pinned run never sees a working copy's edits.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .upstreams import COMMIT_LENGTH, Pin

TABLE = "pret-test"
LOCAL_RED_NAME = ".known-red.json"

_COMMIT = re.compile(rf"[0-9a-f]{{{COMMIT_LENGTH}}}")


class SuiteError(ValueError):
    pass


@dataclass(frozen=True)
class Suite:
    repo: Path
    known_red: dict[str, str]
    local_red: dict[str, str]
    flaky_in_batch: frozenset[str]
    slow: frozenset[str]
    upstreams: tuple[Pin, ...]

    @property
    def tests_dir(self) -> Path:
        return self.repo / "tests"

    @property
    def expected_red(self) -> dict[str, str]:
        return {**self.known_red, **self.local_red}

    def list_test_names(self) -> set[str]:
        return {path.stem for path in self.tests_dir.glob("test_*.py")}


def find_suite_repo(start: Path) -> Path:
    """The nearest directory at or above `start` whose `pyproject.toml` has the table."""
    for candidate in [start.resolve(), *start.resolve().parents]:
        pyproject = candidate / "pyproject.toml"
        if pyproject.exists() and TABLE in read_tool_tables(pyproject):
            return candidate
    raise SuiteError(f"no pyproject.toml with a [tool.{TABLE}] table at or above {start}")


def read_tool_tables(pyproject: Path) -> dict:
    return tomllib.loads(pyproject.read_text()).get("tool", {})


def load_suite(repo: Path) -> Suite:
    table: dict = read_tool_tables(repo / "pyproject.toml").get(TABLE, {})
    known_red: dict[str, str] = read_reasons(table.get("known-red", {}), "known-red")
    local_red: dict[str, str] = read_local_red(repo / LOCAL_RED_NAME)
    upstreams: tuple[Pin, ...] = read_pins(table.get("upstreams", {}))
    return Suite(repo=repo, known_red=known_red, local_red=local_red,
                 flaky_in_batch=read_names(table.get("flaky-in-batch", []), "flaky-in-batch"),
                 slow=read_names(table.get("slow", []), "slow"),
                 upstreams=upstreams)


def read_reasons(rows: object, where: str) -> dict[str, str]:
    if not isinstance(rows, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in rows.items()):
        raise SuiteError(f"{where} must map a test name to the reason it fails")
    return dict(rows)


def read_names(names: object, where: str) -> frozenset[str]:
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise SuiteError(f"{where} must be a list of test names")
    return frozenset(names)


def read_local_red(path: Path) -> dict[str, str]:
    """Reds recorded for this working copy, or none if the file is absent."""
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text())
    except json.JSONDecodeError as bad:
        raise SuiteError(f"{path} is not valid JSON: {bad}") from bad
    return read_reasons(rows, f"{path.name}, as an object of test name -> reason,")


def read_pins(table: object) -> tuple[Pin, ...]:
    if not isinstance(table, dict):
        raise SuiteError("upstreams must be a table of folder -> {url, commit}")
    pins: list[Pin] = []
    for folder, row in sorted(table.items()):
        if not isinstance(row, dict) or set(row) != {"url", "commit"}:
            raise SuiteError(f"upstreams.{folder} must hold exactly url and commit")
        if not _COMMIT.fullmatch(str(row["commit"])):
            raise SuiteError(f"upstreams.{folder}.commit must be a full "
                             f"{COMMIT_LENGTH}-character SHA, not {row['commit']!r}")
        pins.append(Pin(folder=folder, url=str(row["url"]), commit=row["commit"]))
    return tuple(pins)


def find_names_not_in_repo(suite: Suite) -> dict[str, list[str]]:
    """Every list's names that are not a test file here, by list.

    A list naming an absent test is filtered away in silence, so a typo, a row
    about another repo's test and a correct row would be indistinguishable.
    """
    present: set[str] = suite.list_test_names()
    declared = {"known-red": set(suite.known_red), LOCAL_RED_NAME: set(suite.local_red),
                "flaky-in-batch": set(suite.flaky_in_batch), "slow": set(suite.slow)}
    return {where: sorted(names - present)
            for where, names in declared.items() if names - present}
