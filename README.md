# pret-toolkit

Two command-line tools and a Python library for working on a
[pret](https://github.com/pret)-style Game Boy disassembly: pokecrystal, and the
hacks built on it such as Polished Crystal and Prism.

- **`pret-sym`** looks a label up in a built ROM's symbol table, or tells you
  which label an address belongs to.
- **`pret-usage`** shows how full each ROM bank is, what is in it, and where
  there is room for new data.
- **The library**, `pret_toolkit`, is the groundwork for writing your own tools
  that read, edit, build and run such a tree.

None of it is tied to one hack. A tree is recognised by its shape (a `Makefile`
and a `main.asm` in the same folder), the ROMs it can build are read from its own
`Makefile`, and where trees differ, the caller says how. It is used on
pokecrystal, Polished Crystal and Prism.

## Install

```bash
pip install git+https://github.com/ricccec/pret-toolkit
```

Not on PyPI yet. Requires Python 3.11 or newer. No dependencies outside the
standard library.

## The commands

Run them from anywhere inside a tree you have built with `make`:

```bash
pret-sym TryLoadSaveFile     # 05:4ea5 TryLoadSaveFile
pret-sym --addr 05:4ea5      # which label is at this address
pret-usage                   # ROM and RAM usage at a glance
pret-usage free              # the banks with the most room
```

`docs/commands.md` is the full reference for both.

## The library

The library is for writing tools of your own: a map viewer, a linter, an
editor, a script that patches a save. It does the parts every such tool needs
and none of them should have to write again:

- **Finding things** (`shared`): a tree's root, its built ROMs and their `.sym`
  and `.map` files, parsers for those and for the asm's enums, plus running
  `make` and SameBoy.
- **Editing the asm source** (`asmedit`): changes that must keep several files
  consistent, such as adding a map or deleting a warp. Each comes back as an
  `Edit` you can show as a diff before anything is written.
- **Standing a save on a map** (`shared.overworld`): rewriting a `.sav` so the
  game boots on a chosen map, with the right tiles and people around the player.

The API is not stable before 1.0, so pin a commit. `docs/library.md` maps every
module, walks through an edit, and lists what you have to declare to point the
library at a hack of your own.

Two larger tools are built on it: `crystal-studio`, a terminal IDE for these
disassemblies, and `pokeprism-devtools`, which adds Prism support to it along with
Prism's own command-line tools.

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
`~/.cache/pret-toolkit/` — taken from your own checkout when it has the commit, from
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
