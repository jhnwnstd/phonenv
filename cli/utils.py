"""CLI utility functions.

IMPORT RULES:
- Can import: stdlib only
- Cannot import: any phonenv modules (except config for constants)
"""

from __future__ import annotations

import sys
from typing import Any


def safe_input(prompt: str) -> str:
    """Get user input with EOF/KeyboardInterrupt handling.

    Args:
        prompt: Input prompt to display

    Returns:
        User input as string

    Raises:
        SystemExit: On EOF or KeyboardInterrupt (exits gracefully)
    """
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print("\n\nGoodbye!")
        sys.exit(0)


def normalize_user_input(text: str) -> str:
    """Normalize user input: strip whitespace and convert to lowercase."""
    return text.strip().lower()


def calculate_total_occurrences(results: list) -> int:
    """Safely calculate total occurrences across results."""
    return sum(getattr(r, "total_occurrences", 0) for r in results)


__all__ = [
    "safe_input",
    "normalize_user_input",
    "calculate_total_occurrences",
]
