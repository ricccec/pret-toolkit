# Using `pret_toolkit` as a library

What is in the package, how an edit works, and what you have to tell it about
your tree. For the commands, see `commands.md`; for the save patcher in
`shared.overworld`, see `save-patch.md`.

## Before you build on it

**The API is not stable yet.** The library was extracted from two tools
(`crystal-studio` and `pokeprism-devtools`) as the ground they share, and at
0.x it changes when they need it to. Pin a commit:

```bash
pip install git+https://github.com/ricccec/pret-toolkit@<commit>
```

**Requirements.** Python 3.11 or newer, and nothing outside the standard
library. Anything that reads build output (`.gbc`, `.sym`, `.map`) needs a tree
built with `make`; the library runs `make` for you but brings no toolchain, so
install the RGBDS version your tree's `INSTALL.md` asks for. `shared.emulator`
needs SameBoy: it looks at `$SAMEBOY_BIN`, then `$PATH`, then (on macOS) for
`SameBoy.app`.

**Imports are by module.** The package and its subpackages export nothing at
the top level, so import the module you need:
`from pret_toolkit.shared import symfile`.

## What is where

### `shared`: reading a tree and its build

| module | what it gives you |
|---|---|
| `paths` | The tree's root (`find_repo_root`), the ROMs its `Makefile` builds (`read_built_roms`), and the `.gbc`, `.sym` and `.map` beside a built one (`find_built_rom`, `find_built_sym`, `find_built_map`). Also finds a named checkout on the machine (`find_checkout`). |
| `symfile` | A parsed `.sym`: label → `Symbol` (bank, address), and the reverse. |
| `mapfile` | A parsed RGBDS `.map`: banks, their sections, used and free space. |
| `constants` | The `const NAME` enums in `constants/*.asm`, with their values. |
| `mapindex` | The tree's map listing, in the order the tree gives it. |
| `lz` | `decompress`: the Gen-2 LZ format used for graphics. |
| `coords` | The units a map is measured in (blocks, tiles, the `+4` object coordinates) and conversions between them. |
| `edits` | `Edit` and `apply_edits`: how every editor below describes a change. See [How an edit works](#how-an-edit-works). |
| `make` | `run_make`: run a `make` target and stream its output. |
| `emulator`, `launcher` | Start SameBoy on a ROM, and replace the instance you started last time. |
| `world` | A snapshot of every hand-authored source file, for telling whether the tree changed since you last looked. |
| `devtools` | `make_devtools_dir`: a `.devtools/` folder for your tool's own files, which hides itself from `git status`. |
| `caches` | `clear`: empty every cache in this library and in every installed package built on it, after the tree changes underneath them. |
| `textfit`, `swatches`, `viewer` | Small helpers for linters and renderers: whether a line of text fits its box, a tile's display colour, image-viewer plumbing. |

### `shared.overworld`: standing a save on a map

| module | what it gives you |
|---|---|
| `rebuild` | `rebuild_map`: rewrite a `.sav` so the game boots on a chosen map and position, with the right tiles and people around the player. |
| `blockdata` | A map's block grid, header and connections, read from the ROM; the 30-byte `wScreenSave` window for a position. |
| `people` | Reset the player and load the destination map's NPCs into the save's object structs. |
| `spritevram` | The sprite tables the overworld reads, and the VRAM tile each on-screen sprite gets. |

`save-patch.md` explains what a patch has to change and why.

### `asmedit`: editing the asm source

Each module is one kind of change that has to keep several files consistent.
None of them writes anything: each returns `Edit`s for you to show or apply.

| module | the change |
|---|---|
| `mapnew` | `add_map`: wire a new map into the tree, which touches six files in a fixed order. |
| `mapresize` | `resize`: grow or shrink a map from one edge, refusing if anything stands in a strip being removed. |
| `warpdel` | `delete_warp`: renumber every reference to the warps after a deleted one, across the whole tree. |
| `flagalloc` | `load`, then `EventFlags.allocate`: add an event flag in a free slot of `constants/event_flags.asm`. |
| `fruittrees` | Add a fruit tree: its id constant and the item it drops, which live in two files and are matched by position. |
| `macroline` | `find_macro_args`, `splice_macro_args`: read and rewrite the arguments of one `macro Label, …` line, leaving the arguments you did not change exactly as written. |
| `blocks` | The asm block and the names (label, object constant, event flag) a new item ball, trainer, hidden item or fruit tree needs. |
| `regions`, `placement` | Where a new block of asm goes inside a map file, and where a new map's script and blocks go in the ROM. |
| `trainerroster` | The trainer classes a tree defines, and the parties each already has. |
| `editvocab` | The shared vocabulary of editing an existing entry: `Change`, `EditError`, and `same`, which keeps an unchanged argument byte-for-byte. |

## How an edit works

Adding an event flag to pokecrystal, from inside the tree:

```python
import difflib
from pathlib import Path

from pret_toolkit.asmedit import flagalloc
from pret_toolkit.shared.edits import Edit, apply_edits

root = Path(".")
flags: flagalloc.EventFlags = flagalloc.load(root)
landed: flagalloc.Bucket = flags.allocate("EVENT_MY_NEW_FLAG", prefer="Kanto people")
print(f"landed in {landed.label!r}, value {landed.next_value - 1}")

edit: Edit = flags.to_edit("add EVENT_MY_NEW_FLAG")
before: list[str] = (root / edit.path).read_text().splitlines(keepends=True)
after: list[str] = edit.new_text.splitlines(keepends=True)
print("".join(difflib.unified_diff(before, after, edit.path, edit.path, n=1)))

apply_edits(root, [edit], dry_run=False)
```

On pokecrystal at `31880ea` it prints:

```text
landed in 'Kanto people', value 2000
--- constants/event_flags.asm
+++ constants/event_flags.asm
@@ -1461,3 +1461,4 @@
 	const EVENT_BATTLE_TOWER_OPEN_CIVILIANS
-; Unused: next 48 events
+	const EVENT_MY_NEW_FLAG
+; Unused: next 47 events
```

Every editor works this way: it reads the tree, refuses (by raising) if the
change cannot be made safely, and otherwise returns an `Edit` holding the
file's whole new text. Nothing is on disk until `apply_edits`.

**Build an edit, apply it, then build the next.** An `Edit` carries the whole
file, so two built from the same starting text would overwrite each other.
Each one records the text it was computed from, and `apply_edits` raises
`StaleEdit` instead of writing over a file that has changed since.

## Where trees differ

Nothing in the library checks which hack it is running on. Where pokecrystal,
Polished Crystal and Prism really differ, the function takes the difference as
an argument, and stock pokecrystal is the default wherever one makes sense.
Pointing the library at a new hack means supplying these:

| what differs | what you pass | defaults to |
|---|---|---|
| Which built ROM you mean, when a tree builds several | `prefer=` (ROM filenames) to `paths.find_built_rom`/`_sym`/`_map` | the first one the `Makefile` lists that is on disk |
| How map data is laid out in the ROM: compressed blocks, event record sizes, label names | `blockdata.MapFormat` | stock pokecrystal's |
| Where the rebuilt fields sit in the `.sav` | `rebuild.SaveOffsets` | none: read them from your tree's `.sym` |
| How a new map is spelled: header macros, file names, `INCBIN`s | an object implementing `mapnew.Dialect` | none |
| How a map's size is declared and its blocks are stored | an object implementing `mapresize.Dialect` | none |
| Which macros name a warp, and how a dead door is written | `warpdel.WarpGrammar` | none |
| The order of the parts of a map file | `regions.Layout` | none |
| Which file, macro and argument index a header field is | the arguments to `macroline.splice_macro_args` | none |

`crystal-studio` has working versions of all of these for pokecrystal and
Polished Crystal, in `crystal_studio/hacks/vanilla/`: `shapes.py` (layouts),
`write.py` (warp grammars), `newmap.py`, `resize.py` and `savefile.py`.
`pokeprism-devtools` declares Prism's map format in
`pokeprism_devtools/prism/maps/mapformat.py`. Starting from the nearest of
those is quicker than starting from the protocols.
