"""Shared utility functions for Phonenv.

This module contains common functionality used across multiple modules
to eliminate code duplication and improve maintainability.
"""

from __future__ import annotations

import regex as re
import unicodedata as ud
from typing import Set
from normalize import TRANSLATE_TABLE

# Unicode constants
TIE_ABOVE = "\u0361"  # ͡
TIE_BELOW = "\u035c"  # ͜

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


def normalize_ascii_to_ipa(text: str) -> str:
    """Normalize ASCII/confusable chars to IPA using TRANSLATE_TABLE.

    This applies unambiguous automatic transformations only (e.g., ':' → 'ː', 'g' → 'ɡ').

    Args:
        text: Input string with potential ASCII substitutes

    Returns:
        String with ASCII chars replaced by IPA equivalents
    """
    return text.translate(TRANSLATE_TABLE)


def is_safe_path(path) -> bool:
    """Check if a path is safe (within project directory).

    Args:
        path: Path to check (Path object or string)

    Returns:
        True if path is safe, False otherwise
    """
    from pathlib import Path

    try:
        # Convert to Path if needed
        p = Path(path) if not isinstance(path, Path) else path
        # Resolve to absolute path
        abs_path = p.resolve()
        # Get project root (current working directory)
        project_root = Path.cwd().resolve()
        # Check if path is within project root
        return abs_path.is_relative_to(project_root)
    except (ValueError, OSError):
        return False


def resolve_data_file(path: str) -> str:
    """Resolve a data file path, checking with and without .txt extension.

    For files like 'dataset' or 'targets', this will check:
    1. The exact path as given
    2. The path with .txt appended (if not already present)

    Args:
        path: File path to resolve

    Returns:
        Resolved path as string if file exists, otherwise returns original path

    Examples:
        resolve_data_file("data/dataset") -> "data/dataset.txt" (if exists)
        resolve_data_file("data/targets") -> "data/targets.txt" (if exists)
        resolve_data_file("data/dataset.txt") -> "data/dataset.txt" (unchanged)
    """
    from pathlib import Path

    p = Path(path)

    # If the exact path exists, use it
    if p.exists():
        return str(p)

    # If it doesn't have a .txt extension, try adding it
    if p.suffix != ".txt":
        p_with_txt = Path(str(p) + ".txt")
        if p_with_txt.exists():
            return str(p_with_txt)

    # Return original path if nothing found
    return path
