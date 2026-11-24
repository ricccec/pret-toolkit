# pret-toolkit

Python tools to read, edit, build and run a [pret](https://github.com/pret)
Game Boy Gen-2 disassembly — Pokémon G/S/C, Polished Crystal, Prism, or your own
hack of one.

It knows about *pret*, not about any one hack. A repo root is recognised by its
signature rather than its name (a `Makefile` and a `main.asm` in the same
folder), the ROMs a tree can build are read out of its own `Makefile`, and
nothing here branches on which hack you are pointing it at.

## Install

```bash
pip install git+https://github.com/ricccec/pret-toolkit
```

Not on PyPI yet. Requires Python 3.11 or newer. No dependencies outside the
standard library.

## The two commands

```bash
pret-sym   <symbol>     # where a label lives: bank, address, source file
pret-usage              # what each ROM bank holds, and what is free
```

`docs/commands.md` is the reference for both.

## The library

```python
from pretkit.shared import paths

root = paths.find_repo_root()           # walk up for the pret signature
rom  = paths.find_built_rom(root)       # the ROM its Makefile says it builds
sym  = paths.find_built_sym(root)       # the .sym beside it
```

The import name is `pretkit`, and it is a [PEP 420][pep420] namespace package.
That matters because three other distributions extend the same namespace —
`crystal-studio-plugin-api`, `crystal-studio` and `pokeprism-devtools` — so
installing any combination of them gives you one package spanning several source
trees. Imports point downward only: this package imports nothing from the other
three.

[pep420]: https://peps.python.org/pep-0420/

Reference material lives in `docs/`: `save-patch.md` for the save-file and
overworld engine, and `blockdata-plan.md` for the asm cross-references behind
the map rebuild.

## Tests

```bash
pret-test               # the whole suite, against the pinned game trees
pret-test --worktree    # the same, against your own checkouts, edits and all
```

Plain scripts, not pytest: each prints `ok`/`FAIL` lines and exits non-zero.
`pret-test` ships with `pret-toolkit`, so it is on `$PATH` once this repo is
installed; run it from anywhere inside the repo.

Several read a **real disassembly** rather than a fixture, because what is being checked
is whether the reader agrees with an actual tree.
Each tree is pinned to the one commit the tests were written against, in
`pyproject.toml` under `[tool.pret-test.upstreams]`:

- `pokecrystal` — [pret/pokecrystal](https://github.com/pret/pokecrystal) at `31880ea`
- `polishedcrystal` — [Rangi42/polishedcrystal](https://github.com/Rangi42/polishedcrystal) at `a79dd2a`

`pret-test` checks out a clean copy of each pinned commit into
`~/.cache/pretkit/` — taken from your own checkout when it has the commit, from
the URL otherwise — so neither your edits nor your branch change the result.
Your checkout is found the way every command here finds one: `$<NAME>_TREE`
(`$POKECRYSTAL_TREE`, say), or a conventional place such as `~/code/<name>`.
`pret-test --fetch` fetches them and prints where they are. The copies hold no
build output, so checks that need a ROM skip until you run `make` in one. A
skipped check is counted and reported rather than passed, and `--strict` fails
the run on one.

`--worktree` is for seeing what your own edits do. A test that fails there
because of an edit in *your* tree is a fact about your checkout: record it in
`.known-red.json`, which is git-ignored and counts only in `--worktree` runs.

## Disclaimer

Not affiliated with or endorsed by Nintendo, Game Freak, Creatures or The
Pokémon Company. Pokémon is a trademark of Nintendo.

## Licence

MIT. See `LICENSE`.
