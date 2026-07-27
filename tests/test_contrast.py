"""WCAG 2.1 AA contrast regression test for the console theme.

Every color pair the UI actually renders (see web/theme.py) is checked here.
If a future palette edit drops a pair below its required ratio, this test
fails instead of the regression shipping silently.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web.theme import PALETTE, CONTRAST_PAIRS, contrast_ratio


@pytest.mark.parametrize("fg,bg,minimum,label", CONTRAST_PAIRS)
def test_pair_meets_wcag_aa(fg, bg, minimum, label):
    ratio = contrast_ratio(PALETTE[fg], PALETTE[bg])
    assert ratio >= minimum, (
        f"{label}: {fg} ({PALETTE[fg]}) on {bg} ({PALETTE[bg]}) is {ratio:.2f}:1, "
        f"below the required {minimum}:1"
    )
