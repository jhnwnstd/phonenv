"""Data management for phonetic environment analysis (backward compatibility module).

DEPRECATED: This module is maintained for backward compatibility only.
New code should import from the refactored packages:
- models.* for data structures (WordEntry, AlternationPair, TargetResult, etc.)
- parsers.* for parsing functions (iter_word_entries, load_words_list, load_targets_file, etc.)
- processors.* for processing classes (DictionaryProcessor, TargetsProcessor)
- alternations.* for alternation analysis (AlternationAnalyzer)

This module will be removed in version 3.0.
"""

from __future__ import annotations

import warnings
from typing import List

# Re-export data structures from models
from models import (
    WordEntry,
    AlternationPair,
    TargetResult,
    AlternationResult,
    StructuralAlternationResult,
)

# Re-export parsing functions from parsers
from parsers import (
    iter_word_entries,
    load_words_set,
    load_words_list,
    load_words_with_tags,
    load_targets_file,
    strip_comment,
    parse_section_header,
    extract_tags,
    split_targets_line,
    parse_alternation_line,
)

# Re-export processors
from processors import (
    DictionaryProcessor,
    TargetsProcessor,
    create_sample_targets_file,
    targets_exist,
)

# Backward compatibility functions


def load_targets(
    targets_path: str = "data/targets.txt", allow_null_segments: bool = True
):
    """Load targets file (backward compatible wrapper)."""
    return load_targets_file(targets_path, allow_null_segments)


def process_all_targets(
    dataset_path: str = "data/dataset.txt",
    targets_path: str = "data/targets.txt",
) -> List[TargetResult]:
    """Process all targets (backwards compatible function).

    Args:
        dataset_path: Path to dataset file
        targets_path: Path to targets file

    Returns:
        List of TargetResult objects
    """
    from analyze import PhoneticAnalyzer

    analyzer = PhoneticAnalyzer(use_ipa_processing=True)
    processor = TargetsProcessor(
        targets_path=targets_path, dataset_path=dataset_path, analyzer=analyzer
    )
    results, _ = processor.process_targets_to_list(
        *load_targets_file(targets_path)
    )
    return [result for result in results if isinstance(result, TargetResult)]


# Show deprecation warning when module is imported
warnings.warn(
    "data module is deprecated and will be removed in version 3.0. "
    "Please import from refactored packages: "
    "from models import WordEntry; from parsers import load_words_list; "
    "from processors import DictionaryProcessor, TargetsProcessor",
    DeprecationWarning,
    stacklevel=2,
)
