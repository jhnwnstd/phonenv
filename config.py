"""Centralized configuration for Phonenv.

This module contains all configurable constants and default values
used throughout the application. Modify these values to customize
behavior without changing source code.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any

# ========================= File Paths =========================

DEFAULT_DATASET_PATH = "data/dataset.txt"
DEFAULT_TARGETS_PATH = "data/targets.txt"
DEFAULT_OUTPUT_DIR = "data/output"
DEFAULT_CACHE_DIR = "data/.cache"

# ========================= Cache Settings =========================

# Maximum number of cache entries before LRU eviction
CACHE_MAX_ENTRIES = 10_000

# Maximum cache size in megabytes before LRU eviction
CACHE_MAX_SIZE_MB = 100

# Cache file name
CACHE_FILENAME = "phonenv_cache.jsonl"

# ========================= Output Formatting =========================

# Terminal display widths
DEFAULT_TERMINAL_WIDTH = 100
DEFAULT_TERMINAL_HEIGHT = 20

# Preview text truncation length
PREVIEW_TRUNCATE_LENGTH = 25

# Report separator widths
REPORT_SEPARATOR_WIDTH = 60
NARROW_SEPARATOR_WIDTH = 40

# ========================= Analysis Settings =========================

# Default transcription mode: "narrow" or "broad"
DEFAULT_TRANSCRIPTION_MODE = "narrow"

# Default context window: 1 = neighbor class only (V/C), 2 = include segment identity
DEFAULT_CONTEXT_WINDOW = 1

# Include vowel features (front/back, high/low) in contexts
DEFAULT_INCLUDE_VOWEL_FEATURES = False

# Minimum occurrences per segment for alternation analysis
DEFAULT_MIN_EVIDENCE = 3

# ========================= Alternation Analysis =========================

# Auto-window decision threshold (separability × complexity penalty)
ALTERNATION_DECISION_THRESHOLD = 0.6

# Overlap ratio threshold for partial overlap classification
PARTIAL_OVERLAP_THRESHOLD = 0.4

# Coverage thresholds for neutralization detection
NEUTRALIZATION_RESTRICTED_MAX = 0.3
NEUTRALIZATION_BROAD_MIN = 0.7

# ========================= Validation Settings =========================

# Maximum number of validation errors to display per category
MAX_VALIDATION_ERRORS_DISPLAY = 50

# Create backups when auto-fixing files
VALIDATION_CREATE_BACKUPS = True

# Backup file extension
VALIDATION_BACKUP_EXTENSION = ".bak"

# ========================= IPA Processing =========================

# Unicode normalization mode: "NFC" or "NFD"
DEFAULT_NORMALIZATION_MODE = "NFC"

# Common tie-bar clusters (affricates)
DEFAULT_TIE_BAR_CLUSTERS = [
    "t͡s", "d͡z", "t͡ʃ", "d͡ʒ", "t͡ɕ", "d͡ʑ",
    "ʈ͡ʂ", "ɖ͡ʐ", "t͡θ", "d͡ð", "p͡f", "b͡v",
    "c͡ç", "ɟ͡ʝ", "k͡x", "ɡ͡ɣ", "q͡χ", "ɢ͡ʁ",
    "t͡ɬ", "d͡ɮ", "p͡ɸ", "b͡β",
]

# Common diphthong patterns
DEFAULT_DIPHTHONG_PATTERNS = [
    "aɪ", "eɪ", "ɔɪ", "aʊ", "oʊ", "ou",
    "ɪə", "eə", "ʊə", "ai", "au", "ei",
    "eu", "oi", "ou", "iu", "ui", "ie", "uo",
]

# ========================= Helper Functions =========================


def get_config() -> Dict[str, Any]:
    """Get all configuration values as a dictionary.

    Returns:
        Dictionary containing all configuration constants
    """
    return {
        # File paths
        "default_dataset_path": DEFAULT_DATASET_PATH,
        "default_targets_path": DEFAULT_TARGETS_PATH,
        "default_output_dir": DEFAULT_OUTPUT_DIR,
        "default_cache_dir": DEFAULT_CACHE_DIR,
        # Cache settings
        "cache_max_entries": CACHE_MAX_ENTRIES,
        "cache_max_size_mb": CACHE_MAX_SIZE_MB,
        "cache_filename": CACHE_FILENAME,
        # Output formatting
        "default_terminal_width": DEFAULT_TERMINAL_WIDTH,
        "default_terminal_height": DEFAULT_TERMINAL_HEIGHT,
        "preview_truncate_length": PREVIEW_TRUNCATE_LENGTH,
        "report_separator_width": REPORT_SEPARATOR_WIDTH,
        "narrow_separator_width": NARROW_SEPARATOR_WIDTH,
        # Analysis settings
        "default_transcription_mode": DEFAULT_TRANSCRIPTION_MODE,
        "default_context_window": DEFAULT_CONTEXT_WINDOW,
        "default_include_vowel_features": DEFAULT_INCLUDE_VOWEL_FEATURES,
        "default_min_evidence": DEFAULT_MIN_EVIDENCE,
        # Alternation analysis
        "alternation_decision_threshold": ALTERNATION_DECISION_THRESHOLD,
        "partial_overlap_threshold": PARTIAL_OVERLAP_THRESHOLD,
        "neutralization_restricted_max": NEUTRALIZATION_RESTRICTED_MAX,
        "neutralization_broad_min": NEUTRALIZATION_BROAD_MIN,
        # Validation
        "max_validation_errors_display": MAX_VALIDATION_ERRORS_DISPLAY,
        "validation_create_backups": VALIDATION_CREATE_BACKUPS,
        "validation_backup_extension": VALIDATION_BACKUP_EXTENSION,
        # IPA processing
        "default_normalization_mode": DEFAULT_NORMALIZATION_MODE,
        "default_tie_bar_clusters": DEFAULT_TIE_BAR_CLUSTERS,
        "default_diphthong_patterns": DEFAULT_DIPHTHONG_PATTERNS,
    }


def load_config_from_file(config_path: str | Path) -> Dict[str, Any]:
    """Load configuration from a JSON file.

    Args:
        config_path: Path to JSON configuration file

    Returns:
        Dictionary of configuration values merged with defaults

    Example config.json:
        {
            "cache_max_entries": 5000,
            "default_transcription_mode": "broad",
            "default_min_evidence": 5
        }
    """
    import json

    config = get_config()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            config.update(user_config)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load config from {config_path}: {e}")
    return config


__all__ = [
    # File paths
    "DEFAULT_DATASET_PATH",
    "DEFAULT_TARGETS_PATH",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_CACHE_DIR",
    # Cache settings
    "CACHE_MAX_ENTRIES",
    "CACHE_MAX_SIZE_MB",
    "CACHE_FILENAME",
    # Output formatting
    "DEFAULT_TERMINAL_WIDTH",
    "DEFAULT_TERMINAL_HEIGHT",
    "PREVIEW_TRUNCATE_LENGTH",
    "REPORT_SEPARATOR_WIDTH",
    "NARROW_SEPARATOR_WIDTH",
    # Analysis settings
    "DEFAULT_TRANSCRIPTION_MODE",
    "DEFAULT_CONTEXT_WINDOW",
    "DEFAULT_INCLUDE_VOWEL_FEATURES",
    "DEFAULT_MIN_EVIDENCE",
    # Alternation analysis
    "ALTERNATION_DECISION_THRESHOLD",
    "PARTIAL_OVERLAP_THRESHOLD",
    "NEUTRALIZATION_RESTRICTED_MAX",
    "NEUTRALIZATION_BROAD_MIN",
    # Validation
    "MAX_VALIDATION_ERRORS_DISPLAY",
    "VALIDATION_CREATE_BACKUPS",
    "VALIDATION_BACKUP_EXTENSION",
    # IPA processing
    "DEFAULT_NORMALIZATION_MODE",
    "DEFAULT_TIE_BAR_CLUSTERS",
    "DEFAULT_DIPHTHONG_PATTERNS",
    # Helper functions
    "get_config",
    "load_config_from_file",
]
