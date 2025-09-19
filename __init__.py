"""Phonenv - Phonetic Environment Analysis Library.

A Python library for analyzing phonetic environments in word lists and datasets.
Supports IPA text processing, batch analysis, and multiple output formats.
"""

from .analysis import PhoneticAnalyzer, analyze_character, analyze_character_print
from .data import DictionaryProcessor, TargetsProcessor, load_words_list, load_words_set

__version__ = "0.1.0"
__author__ = "shameedjob"

__all__ = [
    # Core analysis
    "PhoneticAnalyzer",
    "analyze_character",
    "analyze_character_print",

    # Data management
    "DictionaryProcessor",
    "TargetsProcessor",
    "load_words_list",
    "load_words_set",
]