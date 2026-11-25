# pret-toolkit

**pret-toolkit** is a Python library for building development tools for Pokémon Gen II disassemblies.

It provides reusable utilities for navigating [pret](https://github.com/pret)-style repositories, inspecting compiled ROMs, parsing symbol tables, and safely editing assembly source files. Whether you're building a map editor, a custom linter, or a complete IDE, pret-toolkit provides the foundations without having to reinvent them.

It works with the original [pokecrystal](https://github.com/pret/pokecrystal), an open-source disassembly of *Pokémon Crystal* maintained by the [pret](https://github.com/pret) group, as well as hacks and derivatives such as [polishedcrystal](https://github.com/Rangi42/polishedcrystal) and [pokeprism](https://github.com/ricccec/pokeprism).

This repository also includes two command-line tools built with the library:

- **`pret-usage`** gives you an overview of ROM and RAM usage: how full each bank is, what's stored in it, and where there's room for new data.
- **`pret-sym`** resolves assembly labels to addresses in your built ROM, or tells you which label belongs to a given address.

## Features

- ROM and RAM bank usage analysis.
- Symbol table lookup and address resolution.
- Parsing of assembly enums, the map listing, and the ROMs a repository's `Makefile` builds.
- Structured editing of assembly source files.
- Overworld and save-file manipulation.
- Integration with RGBDS builds and SameBoy.

## Installation

```bash
pip install git+https://github.com/ricccec/pret-toolkit.git
```

The package is not yet published on PyPI.

**Requirements:** Python 3.11 or newer. No dependencies outside the standard library.

## Command-line tools

Both commands can be run from anywhere inside a pret-style repository. You only need to build the ROM first by running `make`.

```bash
pret-usage                   # ROM and RAM usage at a glance
pret-usage free              # the banks with the most free space
pret-sym TryLoadSaveFile     # 05:4ea5 TryLoadSaveFile
pret-sym --addr 05:4ea5      # which label belongs to this address
```

See [docs/commands.md](docs/commands.md) for the full reference.

## Python library

The library provides the foundations for reading and editing files in a pret-style Gen II repository, so you can focus on building your own tools instead of reinventing common functionality.

It can help you build a map viewer, a custom linter, an editor for game objects or NPCs, and much more.

The main components are:

- **Finding things** ([`shared`](src/pret_toolkit/shared)) provides utilities to locate the repository root, built ROMs and their `.sym` and `.map` files. It also parses symbol tables and assembly enums, and provides helpers for running `make` and SameBoy.
- **Editing assembly source** ([`asmedit`](src/pret_toolkit/asmedit)) provides utilities for making changes that must keep multiple files consistent, such as adding a map or deleting a warp. Each operation produces an `Edit` object that you can inspect or display as a diff before applying any changes to disk.
- **Overworld and save manipulation** ([`shared.overworld`](src/pret_toolkit/shared/overworld)) makes it straightforward to patch a `.sav` file so the game boots on a chosen map.

See [docs/library.md](docs/library.md) for a deeper dive into the library, including the custom extensions you need to implement to make it work with your own hack.

> **Note:** The API is not stable before 1.0. Pin a specific commit when depending on pret-toolkit.

## Built with pret-toolkit

Two larger projects already use the library:

- **[Crystal Studio](https://github.com/ricccec/crystal-studio)** — A terminal IDE for pret-style disassemblies.
- **[pokeprism-devtools](https://github.com/ricccec/pokeprism-devtools)** — Adds Pokémon Prism support to Crystal Studio, along with Prism's own command-line tools.

Both can serve as reference implementations when building your own tools.

## Testing

The tests are plain scripts rather than pytest tests: each prints `ok` or `FAIL` lines and exits with a non-zero status on failure.

`pret-test` ships with `pret-toolkit`, so it's available on your `$PATH` once the package is installed. Run it from anywhere inside this repository:

```bash
pret-test               # the whole suite, against pinned upstream versions
```

### Pinned upstream repositories

Several tests need a local copy of a **real disassembly** rather than a fixture. This ensures the library works with actual repositories and hasn't drifted from their structure.

Each upstream repository is pinned to the commit the tests were written against, in `pyproject.toml` under `[tool.pret-test.upstreams]`:

- `pokecrystal` — [pret/pokecrystal](https://github.com/pret/pokecrystal) at `31880ea`
- `polishedcrystal` — [Rangi42/polishedcrystal](https://github.com/Rangi42/polishedcrystal) at `a79dd2a`

If you need the library or its tools to work with newer versions of either repository, update the corresponding commit in `pyproject.toml` and make sure everything still works.

The test runner checks out clean copies of the pinned commits into `~/.cache/pret-toolkit/`. It uses your own checkout if it already contains the required commit; otherwise, it fetches the repository from its upstream URL.

These copies are independent of your working trees, so neither your local edits nor your current branch affect the test results.

Run:

```bash
pret-test --fetch
```

to fetch the pinned repositories and print their locations.

The cached copies contain no build output, so tests that require a built ROM are skipped until you run `make` in the corresponding repository. Skipped tests are counted and reported rather than treated as passed; use `--strict` to fail the run if any tests are skipped.

### Testing your own worktrees

You can also run the tests against your own checkouts:

```bash
pret-test --worktree    # the whole suite, against your own checkouts and edits
```

Your checkout is located using the same rules as the other commands: the corresponding environment variable (e.g. `$POKECRYSTAL_TREE`) or a conventional location such as `~/code/pokecrystal`.

`--worktree` is useful for checking how your own changes affect compatibility. If a test fails because of an intentional edit in your tree, you can record it in `.known-red.json`. This file is git-ignored, and its entries only apply to `--worktree` runs.

## Disclaimer

This project is not affiliated with or endorsed by Nintendo, Game Freak, Creatures, or The Pokémon Company. Pokémon is a trademark of Nintendo.

## License

MIT. See [LICENSE](LICENSE).
