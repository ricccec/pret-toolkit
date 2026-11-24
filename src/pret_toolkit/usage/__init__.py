#!/usr/bin/env python3
"""CLI for RGBDS link-map analysis.

Usage:
    pret-usage                              # summary (default)
    pret-usage banks [N ...] [--region R]   # ANSI bar chart
    pret-usage bank N [N ...]               # section breakdown of one or more banks
    pret-usage largest [-n N]               # top-N sections by size
    pret-usage free [--region R]            # banks sorted by free space
    pret-usage section NAME [NAME ...]      # find section(s) by name
    pret-usage check [--max-bank-usage P]   # exit 1 if any bank exceeds P%
    pret-usage diff OLD.map NEW.map         # per-bank/section deltas

    N accepts decimal (23), hex ($17 / 0x17 / 17), or a range (10-20).
"""

from .bankselector import parse_bank_selectors
from .cli import main

__all__ = ["main", "parse_bank_selectors"]
