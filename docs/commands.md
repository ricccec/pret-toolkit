# `pret-sym` and `pret-usage`

`pret-sym` reads a built `.sym`; `pret-usage` reads an RGBDS link map. Both are
**hack-neutral by construction**: they locate a tree by walking up for a
`Makefile` beside a `main.asm`, and know no hack's name, so they work the same on
pokecrystal, Polished Crystal, Prism or your own hack.

They arrive with anything that depends on this distribution, so both commands are
on `$PATH` after installing the IDE or a hack's tools. This is their reference
wherever they came from.

## Setup

Python 3.11+, and no third-party dependency at all — this distribution is
stdlib-only. `pipx install -e /path/to/pret-toolkit` puts both commands on
`$PATH`; `pip install -e .` into a virtualenv does the same for that
environment.

Both need a built ROM, or rather the artifact emitted beside it: `pret-sym`
needs the `.sym`, `pret-usage` the `.map`. Run `make` once in the tree first.
The candidates are read out of the tree's own `Makefile`, so a tree whose ROM is
named something this code has never heard of still works.

**Which build.** A tree that builds several ROMs (pokecrystal builds five) is read
through the first one its `Makefile` lists that is on disk. `--rom NAME` picks
another, by the ROM's filename: `--rom pokecrystal11_debug.gbc`. There is no
`--debug`, because no rule finds "the debug build" in every tree — some name
it `_debug`, and some name the *plain* build `_nodebug`.

The examples below are from pokecrystal at `31880ea`; another tree prints its
own labels and addresses.

---

## pret-sym

Query the RGBDS symbol table that the build emits next to the ROM
(`pokecrystal.sym` beside `pokecrystal.gbc`). Useful any time you're looking
for a function, RAM variable, or save data field by name — or you have an
address from a debugger and want to know what it points at.

### Synopsis

```bash
pret-sym LABEL                  # exact match; falls back to substring search
pret-sym --addr BB:AAAA         # reverse: address → label(s) at or before
pret-sym --prefix STR           # list labels starting with STR
pret-sym --search STR           # case-insensitive substring search
pret-sym --region SRAM ...      # filter results by memory region
pret-sym --rom NAME ...         # read another ROM's .sym, e.g. pokecrystal11_debug.gbc
pret-sym -n N                   # cap results at N (default 50; 0 = unlimited)
```

Address format is RGBDS-standard: `BB:AAAA` where `BB` is the bank in hex
and `AAAA` is the GB address in hex (e.g. `05:4f9b`, `01:a009`).

Memory regions: `ROM0`, `ROMX`, `VRAM`, `SRAM`, `WRAM0`, `WRAMX`, `OAM`,
`IO`, `HRAM`, `ECHO`, `UNUSED`.

### Examples

**Find a function:**

```text
$ pret-sym TryLoadSaveFile
05:4ea5 TryLoadSaveFile
```

The output is the raw `BB:AAAA Label` line from the `.sym`. For scripts and
debugger hookup, that's the canonical format.

**Reverse lookup (debugger PC → source):**

```text
$ pret-sym --addr 01:a020
01:a009 sGameData  (+0x17)  [SRAM]
01:a009 sPlayerData  (+0x17)  [SRAM]
```

Multiple labels share `01:a009` because `sPlayerData` and `sGameData` are
defined at the same address in `ram/sram.asm`. `+0x17` is the offset
from the matched label to the address you asked about — handy when you're
poking inside a struct.

**Find all related labels:**

```text
$ pret-sym --prefix sCheckValue
01:a008 sCheckValue1  [SRAM]
01:ad0f sCheckValue2  [SRAM]

$ pret-sym --prefix wPartyMon1 -n 5
01:dcdf wPartyMon1  [WRAMX]
01:dcdf wPartyMon1Species  [WRAMX]
01:dce0 wPartyMon1Item  [WRAMX]
01:dce1 wPartyMon1Moves  [WRAMX]
01:dce5 wPartyMon1ID  [WRAMX]
... (truncated to 5; pass --limit 0 for all)
```

**Filter by region:**

```text
$ pret-sym --search map --region SRAM -n 5
00:ba33 sBackupCurMapData  [SRAM]
01:a833 sCurMapData  [SRAM]
```

**No exact match → falls back to substring search:**

```text
$ pret-sym partymon1 -n 3
00:a600 sPartyMon1Mail  [SRAM]
00:a600 sPartyMon1MailMessage  [SRAM]
00:a620 sPartyMon1MailMessageEnd  [SRAM]
... (truncated to 3; pass --limit 0 for all)
```

### Exit codes

- `0`: at least one result printed
- `1`: no match found (also when reverse-lookup finds nothing in that bank)
- `2`: usage error (bad address format, no query, missing `.sym`)

Useful in shell scripts:

```bash
if addr=$(pret-sym SomeLabel 2>/dev/null); then
    echo "found at $addr"
fi
```

### When to use it

- **Debugging in an emulator**: SameBoy / mGBA shows you `PC = 05:4ea5`. Run
  `pret-sym --addr 05:4ea5` to know what function (or nearest one) that is.
- **Locating save fields**: `pret-sym --region SRAM --prefix sPokemonData`
  gives the bank and address of the party and Pokédex block of the save
  (`01:a865`); `sPlayerData` and `sCurMapData` are its neighbours.
- **Exploring related symbols**: `pret-sym --prefix sBox` lists every save
  field related to boxes.

---
## pret-usage

Parses the RGBDS link map (`pokecrystal.map` beside `pokecrystal.gbc`) and
exposes bank usage through focused subcommands. Auto-locates the `.map` next to
the built ROM; `--rom NAME` reads another ROM's, `--map PATH` any file.

**Synopsis**

```
pret-usage [--rom NAME] [--map PATH] [SUBCOMMAND [ARGS]]
```

**Subcommands**

| Subcommand | Purpose |
|---|---|
| `summary` (default) | Headline ROM/RAM stats, top-5 most-full and most-free ROM banks. |
| `banks [N ...] [--region R]` | ANSI bar chart of every ROM bank's occupancy (or a RAM region with `--region SRAM\|WRAMX\|…`). Pass one or more bank numbers/ranges to show only those banks. |
| `bank N [N ...]` | Section-by-section breakdown of one or more banks. N accepts decimal (`60`), `$3c`, `0x3c`, or a range (`10-20`). |
| `largest [-n N]` | Top-N sections globally by size (default 20; `-n 0` for all). |
| `free [--region R]` | Banks sorted by free space — answers "where do I put new data?". |
| `section NAME [NAME ...]` | All banks containing a section. Exact match first, then substring. Repeat to search several names at once. |
| `check [--max-bank-usage P]` | Exit 1 if any ROM bank exceeds P% (default 95). Pre-commit–friendly. |
| `diff OLD.map NEW.map [--max-bank-usage P]` | Per-bank and per-section deltas between two map files. |

**Exit codes** — matches `pret-sym`:
- `0` — success / all checks pass
- `1` — no results / threshold exceeded
- `2` — usage error or file not found

**Examples**

```bash
pret-usage                                   # quick overview
pret-usage banks                             # visual utilization chart
pret-usage banks 5 12 $1a                    # just these banks
pret-usage bank 5                            # what's in ROM bank 5?
pret-usage bank '$3c'                        # a bank by hex
pret-usage bank 5 12 10-14                   # detail for several banks
pret-usage largest -n 10                     # 10 biggest sections
pret-usage free                              # where to put new data
pret-usage section "Map Scripts"            # find all map-script sections
pret-usage section "Map Scripts" "battle"   # search multiple names
pret-usage check --max-bank-usage 98        # exit 1 if any bank > 98%
pret-usage diff prev.map pokecrystal.map     # what did my edit cost?
```

**Pre-commit hook**

```bash
# .git/hooks/pre-commit
pret-usage check --max-bank-usage 98 || exit 1
```

---
