#!/usr/bin/env python3
"""Print WCAG 2.1 contrast ratios for every color pair used in the console UI.

Run: python scripts/check_contrast.py

Exits non-zero if any pair fails its required ratio. This is the same check
tests/test_contrast.py enforces in the test suite; run this directly for a
human-readable before/after report.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.theme import PALETTE, CONTRAST_PAIRS, contrast_ratio


def main():
    failures = 0
    print(f"{'pair':55s} {'ratio':>8s}  {'min':>5s}  result")
    print("-" * 82)
    for fg, bg, minimum, label in CONTRAST_PAIRS:
        ratio = contrast_ratio(PALETTE[fg], PALETTE[bg])
        ok = ratio >= minimum
        failures += 0 if ok else 1
        print(f"{label:55s} {ratio:6.2f}:1  {minimum:>4.1f}:1  {'PASS' if ok else 'FAIL'}")

    print("-" * 82)
    if failures:
        print(f"{failures} pair(s) failed WCAG 2.1 AA contrast requirements")
        sys.exit(1)
    print("All pairs meet WCAG 2.1 AA contrast requirements")


if __name__ == "__main__":
    main()
