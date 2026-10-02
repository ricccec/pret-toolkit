# pret-toolkit

Python tools to read, edit, build and run a [pret](https://github.com/pret)
Game Boy Gen-2 disassembly — pokecrystal, Polished Crystal, Prism, or your own
hack of one.

It knows about *pret*, not about any one hack. A repo root is recognised by its
signature rather than its name (a `Makefile` and a `main.asm` in the same
folder), the ROMs a tree can build are read out of its own `Makefile`, and
nothing here branches on which hack you are pointing it at.

## Install

```bash
pip install pret-toolkit
```

Requires Python 3.10 or newer. No dependencies outside the standard library.

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
overworld engine, `bank-usage-plan.md` and `blockdata-plan.md` for the design
arguments behind two of the harder pieces.

## Tests

```bash
python scripts/run-tests.py
```

Plain scripts, not pytest: each prints `ok`/`FAIL` lines and exits non-zero.

Several read a **real disassembly** rather than a fixture, because the thing
being checked is whether the reader agrees with an actual tree. Point the suite
at yours with `POKECRYSTAL_TREE`, `POLISHEDCRYSTAL_TREE` and `POKEPRISM_TREE`,
or check them out somewhere conventional (`~/code/<name>`, `~/src/<name>`, or one
grouping directory below either). Without a tree those checks are reported as
skipped rather than passed, and the runner counts them so a green run cannot
hide an empty one.

## Licence

MIT. See `LICENSE`.
