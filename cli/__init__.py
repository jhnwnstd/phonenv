"""CLI package - command-line interface utilities.

IMPORT RULES:
- Can import: stdlib, config, cli.*
- Cannot import: processors, alternations, parsers, analyze
"""

from cli.utils import (
    safe_input,
    normalize_user_input,
    calculate_total_occurrences,
)

__all__ = [
    "safe_input",
    "normalize_user_input",
    "calculate_total_occurrences",
]
