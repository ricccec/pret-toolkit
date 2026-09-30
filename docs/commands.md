# The two commands `pret-toolkit` ships

`pret-sym` reads a built `.sym`; `pret-usage` reads an RGBDS link map. Both are
**hack-neutral by construction** — they locate a tree by walking up for a
`Makefile` beside a `main.asm` and know no hack's name, which is why they are
spelled `pret-*` and not `prism-*`, and why they work on a pokecrystal or
Polished Crystal checkout as readily as on Prism's.

They arrive with anything that depends on this distribution, so both commands are
on `$PATH` after installing the IDE or a hack's tools. This is their reference
wherever they came from.

## Setup

Python 3.10+, and no third-party dependency at all — this distribution is
stdlib-only. `pipx install -e /path/to/pret-toolkit` puts both commands on
`$PATH`; `pip install -e .` into a virtualenv does the same for that
environment.

Both need a built ROM, or rather the artifact emitted beside it: `pret-sym`
needs the `.sym`, `pret-usage` the `.map`. Run `make` once in the tree first.
The candidates are read out of the tree's own `Makefile`, so a tree whose ROM is
named something this code has never heard of still works.

---

## pret-sym

Query the RGBDS symbol table that the build emits next to the ROM
(`pokeprism_nodebug.sym` or `pokeprism.sym`). Useful any time you're looking
for a function, RAM variable, or save data field by name — or you have an
address from a debugger and want to know what it points at.

### Synopsis

```bash
pret-sym LABEL                  # exact match; falls back to substring search
pret-sym --addr BB:AAAA         # reverse: address → label(s) at or before
pret-sym --prefix STR           # list labels starting with STR
pret-sym --search STR           # case-insensitive substring search
pret-sym --region SRAM ...      # filter results by memory region
pret-sym --debug ...            # use the debug ROM's .sym (pokeprism.sym)
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
05:4f9b TryLoadSaveFile
```

The output is the raw `BB:AAAA Label` line from the `.sym`. For scripts and
debugger hookup, that's the canonical format.

**Reverse lookup (debugger PC → source):**

```text
$ pret-sym --addr 01:a020
01:a009 sPlayerData  (+0x17)  [SRAM]
01:a009 sGameData    (+0x17)  [SRAM]
```

Multiple labels share `01:a009` because `sPlayerData` and `sGameData` are
defined at the same SECTION boundary in `sram.asm`. `+0x17` is the offset
from the matched label to the address you asked about — handy when you're
poking inside a struct.

**Find all related labels:**

```text
$ pret-sym --prefix sValidCheck
01:a008 sValidCheck1  [SRAM]
01:ad0f sValidCheck2  [SRAM]

$ sym-lookup --prefix wPartyMon1 -n 5
00:c61f wPartyMon1Species  [WRAM0]
00:c620 wPartyMon1Item     [WRAM0]
00:c621 wPartyMon1Moves    [WRAM0]
00:c625 wPartyMon1ID       [WRAM0]
00:c627 wPartyMon1Exp      [WRAM0]
... (truncated to 5; pass --limit 0 for all)
```

**Filter by region:**

```text
$ sym-lookup --search map --region SRAM -n 5
00:ba33 sBackupMapData  [SRAM]
01:a833 sMapData        [SRAM]
```

**No exact match → falls back to substring search:**

```text
$ sym-lookup partymon1
00:c617 wPartyMon1MiscSpecies  [WRAM0]
00:c617 wPartyMon1Misc         [WRAM0]
...
```

### Exit codes

- `0`: at least one result printed
- `1`: no match found (also when reverse-lookup finds nothing in that bank)
- `2`: usage error (bad address format, no query, missing `.sym`)

Useful in shell scripts:

```bash
if addr=$(sym-lookup SomeLabel 2>/dev/null); then
    echo "found at $addr"
fi
```

### When to use it

- **Debugging in an emulator**: SameBoy / mGBA shows you `PC = 05:4f9b`. Run
  `sym-lookup --addr 05:4f9b` to know what function (or nearest one) that is.
- **Locating save fields**: trying to figure out where `wPartyMon1Species`
  lives in SRAM? `sym-lookup wPartyMon1Species` gives you the WRAM address;
  its SRAM mirror is at `bank 1 + (addr - 0xA009)` offset within
  `sPlayerData` / `sMapData` / `sPokemonData`.
- **Exploring related symbols**: `sym-lookup --prefix sBox` lists every save
  field related to boxes.

---
## pret-usage

Parses the RGBDS link-map (`pokeprism_nodebug.map`) and exposes bank usage
through focused subcommands. Auto-locates the `.map` next to the built ROM;
use `--map PATH` to override or `--debug` to use the debug build's map.

**Synopsis**

```
pret-usage [--debug] [--map PATH] [SUBCOMMAND [ARGS]]
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
pret-usage bank '$3c'                        # tightest bank by hex
pret-usage bank 5 12 10-14                   # detail for several banks
pret-usage largest -n 10                     # 10 biggest sections
pret-usage free                              # where to put new data
pret-usage section "Map Scripts"            # find all map-script sections
pret-usage section "Map Scripts" "battle"   # search multiple names
pret-usage check --max-bank-usage 98        # exit 1 if any bank > 98%
pret-usage diff prev.map pokeprism_nodebug.map   # what did my edit cost?
```

**Pre-commit hook**

```bash
# .git/hooks/pre-commit
pret-usage check --max-bank-usage 98 || exit 1
```

---
