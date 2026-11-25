# pret-toolkit

**A Python toolkit for building development tools for Pokémon Gen II disassemblies.**

Streamline the development of tools for [pokecrystal](https://github.com/pret/pokecrystal) and its derivatives, without reinventing the foundations.

## What can you build with it?

| If you're building… | pret-toolkit gives you |
|---|---|
| **A map viewer** | The tree's map listing, and each map's blocks and connections read from the built ROM |
| **A map or event editor** | Edits that keep several asm files consistent, such as adding a map or deleting a warp, each previewable as a diff |
| **A linter or build check** | Parsed `.sym` and `.map` files, assembly enums, and per-bank usage |
| **A playtest launcher** | Builds with `make`, SameBoy launching, and save files patched to boot on any map |

The repository also includes two command-line tools built on the library:

- **`pret-usage`** — ROM and RAM usage analysis.
- **`pret-sym`** — Assembly label and address lookup.

## Supported projects

Works with the original [pokecrystal](https://github.com/pret/pokecrystal), an open-source disassembly of *Pokémon Crystal* maintained by the [pret](https://github.com/pret) group, and its derivatives, including:

- [polishedcrystal](https://github.com/Rangi42/polishedcrystal)
- [pokeprism](https://github.com/ricccec/pokeprism)

## Installation

```bash
pip install git+https://github.com/ricccec/pret-toolkit.git
```

**Requirements:** Python 3.11 or newer. No dependencies outside the standard library.

The package is not yet published on PyPI.

## Command-line tools

Both commands can be run from anywhere inside a pret-style repository. You only need to build the ROM first with `make`.

```bash
pret-usage                   # ROM and RAM usage at a glance
pret-usage free              # the banks with the most free space
pret-sym TryLoadSaveFile     # 05:4ea5 TryLoadSaveFile
pret-sym --addr 05:4ea5      # which label belongs to this address
```

See [docs/commands.md](docs/commands.md) for the full reference.

## Python library

Want to create a map viewer, a custom linter or editor for game objects and NPCs? `pret-toolkit`'s Python library provides the foundations for reading and editing files in a pret-style Gen II repository, so you can focus on building your own tools instead of reinventing common functionality.

Its main modules are:

- **[`shared`](src/pret_toolkit/shared)** — Repository discovery, ROM and symbol table parsing, assembly enums, and utilities for running `make` and SameBoy.
- **[`asmedit`](src/pret_toolkit/asmedit)** — Structured source editing. Operations that affect multiple files (such as adding a map or deleting a warp) produce `Edit` objects that can be inspected as diffs before being applied.
- **[`shared.overworld`](src/pret_toolkit/shared/overworld)** — Save-file manipulation, including patching a `.sav` to make the game boot on a chosen map.

See [docs/library.md](docs/library.md) for the full library reference, including the custom extensions required to support your own hack.

> **API stability:** The API is not stable before 1.0. Pin a specific commit when depending on pret-toolkit.

## Built with pret-toolkit

Two larger projects already use the library:

- **[Crystal Studio](https://github.com/ricccec/crystal-studio)** — A terminal IDE for pret-style disassemblies.
- **[pokeprism-devtools](https://github.com/ricccec/pokeprism-devtools)** — Adds Pokémon Prism support to Crystal Studio, along with Prism's own command-line tools.

Both can serve as reference implementations when building your own tools.

## Testing

Each test is a plain Python script rather than a pytest test: it prints `ok` or `FAIL` lines and exits with a non-zero status on failure. `pret-test` ships with the `pret-toolkit` package and is available on your `$PATH` after installation. Run it from anywhere inside this repository, and it runs this repository's suite.

```bash
pret-test               # the whole suite, against pinned upstream versions
pret-test --fetch       # fetch the pinned upstreams and print where they are
```

### Pinned upstreams

Tests run against clean copies of real disassemblies, rather than relying exclusively on fixtures. This helps catch compatibility regressions against actual game repositories.

The upstream commits are pinned in `pyproject.toml`, under `[tool.pret-test.upstreams]`:

| Repository | Pinned commit |
|---|---|
| [pret/pokecrystal](https://github.com/pret/pokecrystal) | `31880ea` |
| [Rangi42/polishedcrystal](https://github.com/Rangi42/polishedcrystal) | `a79dd2a` |

To test against newer upstream versions, update the corresponding commits in `pyproject.toml`. Moving a pin is a deliberate change: a test that goes red afterwards needs checking against the new tree before the new commit is accepted.

The test runner checks out clean copies into `~/.cache/pret-toolkit/`, using your existing checkout if it contains the required commit, or fetching it from the upstream URL otherwise. These copies are independent of your working trees.

Cached copies contain no build output, so checks that need a built ROM are skipped until you run `make` in the corresponding copy. Skipped checks are reported by test file rather than counted as passed; `--strict` makes any skipped check fail the run.

### Testing your own changes

You can also run the tests against your own checkouts:

```bash
pret-test --worktree    # the whole suite, against your own checkouts and edits
```

Your checkout is located through its corresponding environment variables (e.g. `$POKECRYSTAL_TREE`) or conventional locations such as `~/code/pokecrystal`.

If a test fails because of an intentional change in your tree, you can record it in `.known-red.json`. This file is git-ignored, and its entries only apply to `--worktree` runs.

## Disclaimer

This project is not affiliated with or endorsed by Nintendo, Game Freak, Creatures, or The Pokémon Company. Pokémon is a trademark of Nintendo.

## License

MIT. See [LICENSE](LICENSE).
