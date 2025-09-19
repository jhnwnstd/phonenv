"""Shared utility functions for Phonenv.

This module contains common functionality used across multiple modules
to eliminate code duplication and improve maintainability.
"""

from __future__ import annotations

import regex as re
import unicodedata as ud
from typing import Set

# Unicode constants
TIE_ABOVE = "\u0361"  # ͡
TIE_BELOW = "\u035C"  # ͜

# IPA Unicode blocks for validation
_IPA_BLOCKS = {
    (0x0250, 0x02AF),  # IPA Extensions
    (0x1D00, 0x1D7F),  # Phonetic Extensions
    (0x1D80, 0x1DBF),  # Phonetic Extensions Supplement
    (0x0300, 0x036F),  # Combining Diacritical Marks
    (0x1AB0, 0x1AFF),  # Combining Diacritical Marks Extended
    (0x02B0, 0x02FF),  # Spacing Modifier Letters
    (0xA700, 0xA71F),  # Modifier Tone Letters
}


def normalize_tiebar(s: str) -> str:
    """Normalize all tie-bar variants to U+0361 for consistency.

    Unifies tie-bar variants and strips accidental spaces around them.
    This is the consolidated version from analysis.py and data.py.

    Args:
        s: Input string that may contain tie-bar variants

    Returns:
        String with normalized tie-bars
    """
    # Replace tie-bar below with tie-bar above
    s = s.replace(TIE_BELOW, TIE_ABOVE)
    # Collapse any spaces around the tie bar (from analysis.py version)
    return re.sub(rf"\s*{re.escape(TIE_ABOVE)}\s*", TIE_ABOVE, s)


def in_ipa_blocks(ch: str) -> bool:
    """Check if a character belongs to IPA Unicode blocks.

    This is the consolidated version from analysis.py and validate.py.

    Args:
        ch: Single Unicode character to check

    Returns:
        True if character is in IPA Unicode blocks
    """
    if not ch:
        return False
    code = ord(ch)
    return any(start <= code <= end for start, end in _IPA_BLOCKS)


def is_combining(ch: str) -> bool:
    """Check if character is a combining mark."""
    return ud.category(ch) == "Mn"


def is_spacing_modifier(ch: str) -> bool:
    """Check if character is a spacing modifier letter (excluding suprasegmentals)."""
    _SUPRA: Set[str] = {"ˈ", "ˌ", "|", "‖"}
    return ud.category(ch) in ("Sk", "Lm") and ch not in _SUPRA