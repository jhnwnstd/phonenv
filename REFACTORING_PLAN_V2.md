# Phonenv Refactoring Plan v2 (Production-Ready)

**Date:** 2025-10-07
**Status:** REVISED based on architectural review
**Goal:** Decompose by responsibility (SRP) while maintaining 100% backward compatibility

---

## Review Feedback Integration

### ✅ Strengths Confirmed
- Clear separation of concerns (models/parsing/processing/alternations/output/CLI)
- Backward compatibility via re-exports (SemVer-compliant)
- Feature-oriented packaging (aligns with Parnas's information hiding)

### 🔧 Critical Fixes Applied
1. **Circular import prevention** - Strict dependency rules + TYPE_CHECKING
2. **Business logic ownership** - Clear boundaries between analysis/orchestration
3. **Deprecation path** - Explicit warnings + SemVer migration
4. **Characterization tests** - Golden file tests before refactoring
5. **Realistic timeline** - 1-1.5 days (not 6-8 hours)

---

## Architecture: Dependency Rules

### One-Way Dependency Flow
```
┌─────────────────────────────────────────────┐
│  CLI Layer (cli/)                           │
│  - Can import: models, parsers, processors, │
│    alternations, output, analyze            │
└─────────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Output Layer (output/)                     │
│  - Can import: models only                  │
│  - NO imports from: cli, processors         │
└─────────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Processing Layer (processors, alternations)│
│  - Can import: models, parsers, analyze     │
│  - NO imports from: cli, output             │
└─────────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Core Layer (analyze, parsers)              │
│  - Can import: models, utils, normalize     │
│  - NO imports from: processors, output, cli │
└─────────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Foundation Layer (models, utils, config)   │
│  - stdlib + third-party only                │
│  - NO internal imports (except normalize)   │
└─────────────────────────────────────────────┘
```

**Enforcement:** Use import-linter or custom pre-commit hook

---

## Phase 0: Pre-Refactoring (4 hours) 🆕

### 0.1 Create Characterization Tests
**Why:** Safety net to detect behavioral changes

```python
# tests/test_golden_outputs.py
"""Golden file tests for refactoring safety."""

def test_batch_txt_output_unchanged(tmp_path):
    """Ensure TXT format doesn't change during refactoring."""
    # Run batch processing
    result = run_batch(dataset="data/dataset.txt", format="txt")

    # Compare with golden file
    golden = Path("tests/golden/batch_output.txt").read_text()
    assert normalize_whitespace(result) == normalize_whitespace(golden)

def test_alternation_analysis_unchanged():
    """Ensure alternation patterns stay consistent."""
    processor = TargetsProcessor(...)
    result = processor.analyze_alternation(AlternationPair("p", "b"))

    # Check key attributes
    assert result.pattern in ["complementary", "contrastive", ...]
    assert result.segment1_total > 0
    # ... more assertions

def test_cli_help_unchanged():
    """CLI interface shouldn't change."""
    output = subprocess.check_output(["python", "main.py", "--help"])
    assert b"--batch" in output
    assert b"--format" in output
```

**Golden Files to Create:**
- `tests/golden/batch_output.txt` - Full batch TXT output
- `tests/golden/alternation_p_b.json` - Alternation result JSON
- `tests/golden/cli_help.txt` - Help text

### 0.2 Measure Baseline Metrics
```bash
# Import time
python -X importtime -c "import main" 2>&1 | grep "import time:"

# Test coverage
pytest --cov=. --cov-report=term

# Module complexity
radon cc *.py -a
```

**Record baselines:**
- Import time: ___ ms
- Test coverage: ___%
- Cyclomatic complexity: ___

---

## Phase 1: Foundation Layer (4 hours)

### 1.1 Create `models.py` - Pure Data Structures

**Rules:**
- ✅ stdlib + `@dataclass` only (no internal imports except `typing`)
- ✅ `frozen=True` for cache keys
- ✅ `from __future__ import annotations` at top

```python
"""Data models for Phonenv.

IMPORT RULES:
- This module MUST NOT import from any other phonenv modules
- Keep it pure: stdlib types + dataclasses only
- Use forward references for type hints
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional, Set, Mapping

# Enums
class LogLevel(Enum):
    """Logging levels."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class DistributionPattern(Enum):
    """Phonological distribution patterns."""
    COMPLEMENTARY = "complementary"
    CONTRASTIVE = "contrastive"
    FREE_VARIATION = "free_variation"
    NEUTRALIZATION = "neutralization"
    PARTIAL_OVERLAP = "partial_overlap"
    INCONCLUSIVE = "inconclusive"

# Data Entry Models
@dataclass(frozen=True)  # Immutable for hashing
class WordEntry:
    """Rich data structure for parsed word entries."""
    ipa: str
    section: Dict[str, str] = field(default_factory=dict)
    tags: Tuple[str, ...] = field(default_factory=tuple)
    source_path: Optional[str] = None
    line_no: Optional[int] = None

@dataclass(frozen=True)
class AlternationPair:
    """Represents a phonological alternation between two segments."""
    segment1: str
    segment2: str
    description: Optional[str] = None
    pair_filter: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.segment1} ~ {self.segment2}"

# Result Models
@dataclass
class TargetResult:
    """Result of analyzing a single target phoneme."""
    target: str
    environments: Dict[str, Dict[str, List[str]]]
    total_occurrences: int
    source_file: str
    analysis_mode: str = "narrow"

@dataclass
class AlternationResult:
    """Result of analyzing a phonological alternation."""
    pair: AlternationPair
    segment1_envs: Mapping[str, Mapping[str, List[str]]]
    segment2_envs: Mapping[str, Mapping[str, List[str]]]
    segment1_total: int
    segment2_total: int
    source_file: str
    pattern: str
    analysis: str
    window_size: int = 1
    decision_score: float = 0.0

@dataclass
class StructuralAlternationResult:
    """Result of analyzing structural alternations (X ~ Ø)."""
    pair: AlternationPair
    present_segment: str
    absent_segment: str
    present_envs: Mapping[str, Mapping[str, List[str]]]
    present_total: int
    process: str
    process_type: str
    analysis: str
    source_file: str

# Cache Models
@dataclass(frozen=True)  # Immutable for dict keys
class CacheKey:
    """Cache key for analysis results."""
    target: str
    dataset_hash: str
    config_hash: str

@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    key: str
    result: Dict
    timestamp: float
    dataset_hash: str
    analysis_config: Dict
    result_type: str = "target"  # "target" | "alternation"

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "result": self.result,
            "timestamp": self.timestamp,
            "dataset_hash": self.dataset_hash,
            "analysis_config": self.analysis_config,
            "result_type": self.result_type,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> CacheEntry:
        return cls(
            key=data["key"],
            result=data["result"],
            timestamp=data["timestamp"],
            dataset_hash=data["dataset_hash"],
            analysis_config=data["analysis_config"],
            result_type=data.get("result_type", "target"),
        )

__all__ = [
    # Enums
    "LogLevel", "DistributionPattern",
    # Data entries
    "WordEntry", "AlternationPair",
    # Results
    "TargetResult", "AlternationResult", "StructuralAlternationResult",
    # Cache
    "CacheKey", "CacheEntry",
]
```

**Migration:**
- Move from `data.py`: WordEntry, AlternationPair, TargetResult, AlternationResult, StructuralAlternationResult
- Move from `phonenv_io.py`: CacheEntry
- Move from `logger.py`: LogLevel
- Add: DistributionPattern, CacheKey (new)

### 1.2 Create `parsers.py` - File Parsing

**Dependency:** `models.py` only (for WordEntry, AlternationPair)

```python
"""File parsing and data loading.

IMPORT RULES:
- Can import: models, utils, normalize
- Cannot import: processors, alternations, output, cli
"""

from __future__ import annotations
from typing import TYPE_CHECKING

import regex as re
import unicodedata as ud
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, Optional, Set

from models import WordEntry, AlternationPair
from utils import normalize_tiebar, is_safe_path

if TYPE_CHECKING:
    # Type-only imports to avoid cycles
    from typing import Any

# Constants
_COMMENT = re.compile(r"#.*$")
_SECTION = re.compile(r"^\[(?P<body>.+)\]\s*$")
_KV = re.compile(r"\s*([a-zA-Z_][\w-]*)\s*=\s*([^;]+)\s*")

# ... rest of parsing functions
```

### 1.3 Update `utils.py` - Import from models

```python
# utils.py - add at top
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models import WordEntry  # Type hint only
```

**Test Phase 1:**
```bash
python -c "from models import WordEntry; print(WordEntry.__name__)"
python -c "from parsers import load_words_set; print(len(load_words_set('data/dataset.txt')))"
pytest tests/test_models.py  # New: test all dataclasses
```

---

## Phase 2: Core Analysis Layer (4 hours)

### 2.1 Create `alternations.py` - Pure Analysis Logic

**Role:** Stateless alternation analysis (no I/O, no caching)

```python
"""Phonological alternation analysis.

IMPORT RULES:
- Can import: models, analyze (PhoneticAnalyzer)
- Cannot import: processors, output, cli, parsers
- Keep stateless: analyzer is injected, no file I/O
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Mapping, Set, Tuple, List, Optional

from models import AlternationPair, AlternationResult, StructuralAlternationResult

if TYPE_CHECKING:
    from analyze import PhoneticAnalyzer

class AlternationAnalyzer:
    """Analyzes phonological alternations (stateless/functional).

    Design: This class contains ONLY analysis logic.
    - NO file I/O (delegate to processors)
    - NO caching (delegate to output layer)
    - Pure functions where possible
    """

    def __init__(self, phonetic_analyzer: PhoneticAnalyzer):
        """Initialize with injected analyzer dependency."""
        self.analyzer = phonetic_analyzer

    def analyze(
        self,
        pair: AlternationPair,
        words1: Optional[List[str]] = None,
        words2: Optional[List[str]] = None,
    ) -> AlternationResult | StructuralAlternationResult:
        """Main entry point for alternation analysis.

        Args:
            pair: Alternation pair to analyze
            words1: Optional filtered word list for segment1
            words2: Optional filtered word list for segment2

        Returns:
            AlternationResult or StructuralAlternationResult
        """
        # Route to structural analysis for Ø alternations
        if pair.segment1 == "" or pair.segment2 == "":
            return self.analyze_structural(pair, words1, words2)

        # Standard phonemic analysis
        return self.analyze_phonemic(pair, words1, words2)

    def analyze_phonemic(self, ...) -> AlternationResult:
        """Analyze phonemic alternations (p ~ b)."""
        ...

    def analyze_structural(self, ...) -> StructuralAlternationResult:
        """Analyze structural alternations (X ~ Ø)."""
        ...

    # Pure functions (staticmethod where possible)
    @staticmethod
    def compute_separability_score(...) -> Tuple[float, int, int, int]:
        """Compute separability score (pure function)."""
        ...

    @staticmethod
    def compute_complexity_penalty(window: int, alpha: float = 0.5) -> float:
        """Compute complexity penalty (pure function)."""
        return 1.0 / (1.0 + alpha * (window - 1))
```

### 2.2 Create `processors.py` - Orchestration Logic

**Role:** Coordinate analysis, handle I/O, manage state

```python
"""Data processors - orchestration layer.

IMPORT RULES:
- Can import: models, parsers, analyze, alternations
- Cannot import: output (to avoid cycles), cli
- Can do I/O (file reads, dataset loading)
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from pathlib import Path
from models import WordEntry, AlternationPair, TargetResult
from parsers import load_words_list, iter_word_entries
from alternations import AlternationAnalyzer

if TYPE_CHECKING:
    from analyze import PhoneticAnalyzer

class DictionaryProcessor:
    """Manages phonetic dictionary operations."""

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        # Stateful: caches word list
        self._words_cache: Optional[List[str]] = None

    def get_words(self) -> List[str]:
        """Get words with caching."""
        if self._words_cache is None:
            self._words_cache = load_words_list(str(self.dataset_path))
        return self._words_cache

    # ... other methods

class TargetsProcessor:
    """Processes targets and coordinates analysis."""

    def __init__(self, dataset_path: str, analyzer: PhoneticAnalyzer):
        self.dataset_path = dataset_path
        self.analyzer = analyzer
        # Composition: alternation analyzer
        self.alternation_analyzer = AlternationAnalyzer(analyzer)

    def analyze_target(self, target: str) -> TargetResult:
        """Analyze single target (delegates to analyzer)."""
        envs = self.analyzer.analyze_character(target, self.dataset_path)
        total = sum(len(w) for group in envs.values() for w in group.values())
        return TargetResult(
            target=target,
            environments=envs,
            total_occurrences=total,
            source_file=self.dataset_path,
        )

    def analyze_alternation(self, pair: AlternationPair):
        """Analyze alternation (delegates to alternation analyzer)."""
        # Orchestration: load words, filter, delegate
        words1, words2 = self._get_filtered_words(pair)
        return self.alternation_analyzer.analyze(pair, words1, words2)

    def _get_filtered_words(self, pair):
        """Orchestration helper: load and filter words."""
        # Handle pair_filter logic here (orchestration, not analysis)
        ...
```

**Test Phase 2:**
```bash
pytest tests/test_alternations.py  # Should still pass
pytest tests/test_processors.py    # Test orchestration
pytest tests/test_golden_outputs.py  # Golden files match
```

---

## Phase 3: Output Layer (3 hours)

### 3.1 Create `output/` Package Structure

```
output/
├── __init__.py          # Public API exports
├── cache.py             # ResultCache (storage only)
├── writers.py           # OutputWriter base + AutoOutputWriter
├── registry.py          # Format registry (avoid import cycles) 🆕
└── formats/
    ├── __init__.py
    ├── base.py          # BaseFormatter ABC 🆕
    ├── txt.py           # TXT formatter
    ├── csv.py           # CSV formatter
    └── json.py          # JSON/JSONL formatters
```

### 3.2 Create `output/__init__.py` - Thin Public API

```python
"""Output package - caching and formatting.

Public API:
    from output import ResultCache, AutoOutputWriter
    from output import get_cache, write_results
"""

from output.cache import ResultCache, get_cache, clear_cache, get_cache_stats
from output.writers import AutoOutputWriter
from output.registry import write_results, get_default_output_path

__all__ = [
    "ResultCache", "AutoOutputWriter",
    "get_cache", "clear_cache", "get_cache_stats",
    "write_results", "get_default_output_path",
]
```

### 3.3 Create `output/registry.py` - Format Discovery

**Why:** Avoid circular imports between writers and formats

```python
"""Format registry for output writers.

This module discovers available formats dynamically to avoid
import cycles between writers.py and formats/*.
"""

from typing import Dict, Type
from output.formats.base import BaseFormatter

# Lazy-loaded registry
_FORMAT_REGISTRY: Dict[str, Type[BaseFormatter]] = {}

def register_format(name: str):
    """Decorator to register a format."""
    def wrapper(cls: Type[BaseFormatter]):
        _FORMAT_REGISTRY[name] = cls
        return cls
    return wrapper

def get_formatter(name: str) -> Type[BaseFormatter]:
    """Get formatter class by name (lazy import)."""
    if not _FORMAT_REGISTRY:
        # Lazy load all formats
        from output.formats import txt, csv, json as json_fmt
        # Formats register themselves via @register_format

    return _FORMAT_REGISTRY[name]

def write_results(results, output_path, format_name):
    """High-level write function using registry."""
    formatter_cls = get_formatter(format_name)
    formatter = formatter_cls(output_path)
    formatter.write(results)
```

### 3.4 Create `output/formats/base.py` - ABC

```python
"""Base formatter abstract class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, List

class BaseFormatter(ABC):
    """Abstract base for output formatters."""

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

    @abstractmethod
    def write(self, results: List[Any]) -> None:
        """Write results to file."""
        pass

    @abstractmethod
    def format_name(self) -> str:
        """Return format name (txt, csv, json, jsonl)."""
        pass
```

### 3.5 Create `output/formats/txt.py` - TXT Formatter

```python
"""TXT output formatter."""

from output.formats.base import BaseFormatter
from output.registry import register_format

@register_format("txt")
class TxtFormatter(BaseFormatter):
    """Formats results as human-readable text."""

    def format_name(self) -> str:
        return "txt"

    def write(self, results):
        """Write TXT output."""
        # Move TXT formatting logic here from phonenv_io.py
        ...
```

**Similar for:** `csv.py`, `json.py`

### 3.6 Create `output/cache.py` - Storage Only

```python
"""Result caching with SHA256 fingerprinting.

IMPORT RULES:
- Can import: models (CacheEntry, CacheKey)
- Cannot import: processors, cli
- Keep storage-only: no business logic
"""

from __future__ import annotations
from typing import TYPE_CHECKING

import hashlib
import json
from pathlib import Path

from models import CacheEntry, CacheKey
from config import CACHE_MAX_ENTRIES, CACHE_MAX_SIZE_MB
from logger import get_logger

if TYPE_CHECKING:
    from typing import Dict, Any

logger = get_logger()

class ResultCache:
    """Manages result caching (storage layer only)."""

    def __init__(self, cache_dir: str = "data/.cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "analysis_cache.jsonl"
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._load_cache()

    def get(self, key: CacheKey) -> Optional[Any]:
        """Retrieve from cache."""
        ...

    def put(self, key: CacheKey, result: Any) -> None:
        """Store in cache."""
        ...

    # Pure storage methods (no analysis logic)
```

---

## Phase 4: CLI Layer (3 hours)

### 4.1 Create `cli/` Package

```
cli/
├── __init__.py          # Export main() only
├── interactive.py       # InteractivePhonenvCLI
├── batch.py             # Batch processing
├── menus.py             # IPA character menus
├── constants.py         # Shared CLI constants 🆕
└── utils.py             # safe_input, format_error
```

### 4.2 Create `cli/constants.py` - Constants

```python
"""Shared CLI constants (menus, categories, diacritics).

Moved here to avoid circular imports and keep cli/ cohesive.
"""

from typing import Dict

# IPA character categories
CONSONANT_CATEGORIES: Dict[str, Dict[str, str]] = {
    "Plosives": {
        "Voiceless": ["p", "t", "ʈ", "c", "k", "q", "ʔ"],
        "Voiced": ["b", "d", "ɖ", "ɟ", "ɡ", "ɢ"],
    },
    # ...
}

VOWEL_CATEGORIES: Dict[str, Dict[str, Dict[str, str]]] = {
    "Front": {
        "Unrounded": {"Close": "i", "Near-close": "ɪ", ...},
        # ...
    },
    # ...
}

COMMON_DIACRITICS: Dict[str, Dict[str, str | bool | None]] = {
    # ...
}
```

### 4.3 Create `cli/__init__.py` - Minimal Surface

```python
"""CLI package for Phonenv.

Public API:
    from cli import main
"""

from cli.interactive import InteractivePhonenvCLI
from cli.batch import run_batch_cli

def main():
    """Main CLI entry point (delegates to main.py)."""
    # This is just a re-export; actual main() stays in main.py
    from main import main as _main
    return _main()

__all__ = ["main", "InteractivePhonenvCLI", "run_batch_cli"]
```

### 4.4 Update `main.py` - Thin Orchestrator

**New size:** ~200 lines

```python
#!/usr/bin/env python3
"""Command-line interface entry point.

This is the thin orchestrator. Heavy lifting delegated to:
- cli/ for UI
- processors/ for analysis coordination
- output/ for results
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli.interactive import InteractivePhonenvCLI
from cli.batch import run_batch_cli
from cli.utils import format_error
from processors import create_sample_targets_file, targets_exist
from output import clear_cache, get_cache_stats
from config import DEFAULT_DATASET_PATH

def create_argument_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Phonenv - Phonetic Environment Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # ... add arguments
    return parser

def main():
    """Main entry point."""
    parser = create_argument_parser()
    args = parser.parse_args()

    try:
        # Utility commands
        if args.create_targets:
            create_sample_targets_file(args.targets)
            print(f"Created sample targets file: {args.targets}")
            return 0

        if args.clear_cache:
            clear_cache()
            print("Cache cleared successfully.")
            return 0

        if args.cache_stats:
            stats = get_cache_stats()
            print("Cache Statistics:")
            for key, value in stats.items():
                print(f"   {key}: {value}")
            return 0

        # Batch or interactive mode
        if args.batch:
            run_batch_cli(args)
        else:
            cli = InteractivePhonenvCLI(args.dataset)
            cli.run()

        return 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return 130
    except Exception as e:
        print(format_error("during execution", e), file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

---

## Phase 5: Backward Compatibility (2 hours)

### 5.1 Update `data.py` - Compatibility Layer

```python
"""Data management for phonetic environment analysis.

DEPRECATED: This module is kept for backward compatibility.

New code should use:
- models.py for data structures
- parsers.py for file parsing
- processors.py for data processing
- alternations.py for alternation analysis

This module will be removed in version 3.0.0.
"""

import warnings
from typing import Set, List

# Re-export from new modules (with deprecation warnings)
from models import WordEntry, AlternationPair, TargetResult, AlternationResult
from parsers import load_words_set, load_words_list
from processors import DictionaryProcessor, TargetsProcessor

# Add deprecation warnings
def _deprecated_import(name: str, new_module: str):
    """Helper to emit deprecation warning."""
    warnings.warn(
        f"Importing {name} from data.py is deprecated. "
        f"Use 'from {new_module} import {name}' instead. "
        f"data.py will be removed in version 3.0.0.",
        DeprecationWarning,
        stacklevel=3,
    )

# Wrap exports to trigger warnings on first import
class _DeprecatedModule:
    """Proxy to emit warnings on attribute access."""

    def __getattr__(self, name):
        if name == "WordEntry":
            _deprecated_import("WordEntry", "models")
            return WordEntry
        elif name == "load_words_set":
            _deprecated_import("load_words_set", "parsers")
            return load_words_set
        # ... handle all exports
        raise AttributeError(f"module 'data' has no attribute '{name}'")

# Keep utility functions (not moving)
def create_sample_targets_file(path: str = "data/targets.txt") -> None:
    """Create sample targets file."""
    # Keep implementation here (not worth moving)
    ...

def targets_exist(path: str = "data/targets.txt") -> bool:
    """Check if targets file exists."""
    from pathlib import Path
    return Path(path).exists()

__all__ = [
    # Re-exports (with deprecation)
    "WordEntry", "AlternationPair", "TargetResult",
    "load_words_set", "load_words_list",
    "DictionaryProcessor", "TargetsProcessor",
    # Kept here
    "create_sample_targets_file", "targets_exist",
]
```

### 5.2 Update `phonenv_io.py` - Compatibility Layer

```python
"""I/O operations for phonetic environment analysis.

DEPRECATED: This module is kept for backward compatibility.

New code should use:
- output.cache for caching (ResultCache)
- output.writers for output formatting (AutoOutputWriter)
- output.write_results for high-level API

This module will be removed in version 3.0.0.
"""

import warnings

# Re-export from output package
from output import (
    ResultCache,
    AutoOutputWriter,
    get_cache,
    clear_cache,
    get_cache_stats,
    write_results,
    get_default_output_path,
)

# Emit deprecation warning on module import
warnings.warn(
    "phonenv_io is deprecated. Use 'from output import ...' instead. "
    "phonenv_io will be removed in version 3.0.0.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "ResultCache", "AutoOutputWriter",
    "get_cache", "clear_cache", "get_cache_stats",
    "write_results", "get_default_output_path",
]
```

### 5.3 SemVer Migration Plan

**Current:** v1.2.0 (implicit)

**Release Plan:**
1. **v2.0.0** - Refactored modules (this release)
   - New: models, parsers, alternations, processors, cli/, output/
   - Deprecated: data.py, phonenv_io.py (with warnings)
   - Backward compatible: all old imports work

2. **v2.1.0** - Deprecation period (6 months)
   - Emit louder warnings
   - Update docs with migration guide

3. **v3.0.0** - Break compatibility (future)
   - Remove data.py, phonenv_io.py
   - Clean up deprecated code paths

**Migration Guide (add to README):**
```markdown
## Migration from v1.x to v2.0

### Old (deprecated):
```python
from data import WordEntry, load_words_set
from phonenv_io import get_cache, write_results
```

### New (recommended):
```python
from models import WordEntry
from parsers import load_words_set
from output import get_cache, write_results
```

See [MIGRATION.md](MIGRATION.md) for full details.
```

---

## Phase 6: Import Hygiene (2 hours)

### 6.1 Create Import Linter Config

**File:** `.importlinter`

```ini
[importlinter]
root_package = phonenv

[importlinter:contract:1]
name = "Foundation layer doesn't import application code"
type = forbidden
source_modules =
    models
    utils
    normalize
    config
forbidden_modules =
    parsers
    analyze
    processors
    alternations
    output
    cli

[importlinter:contract:2]
name = "Core layer doesn't import higher layers"
type = forbidden
source_modules =
    parsers
    analyze
forbidden_modules =
    processors
    alternations
    output
    cli

[importlinter:contract:3]
name = "Processing layer doesn't import output or CLI"
type = forbidden
source_modules =
    processors
    alternations
forbidden_modules =
    output
    cli

[importlinter:contract:4]
name = "Output layer doesn't import processors or CLI"
type = forbidden
source_modules =
    output
forbidden_modules =
    processors
    alternations
    cli
```

**Run:**
```bash
pip install import-linter
lint-imports
```

### 6.2 Pre-commit Hook

**File:** `.pre-commit-config.yaml` (optional)

```yaml
repos:
  - repo: local
    hooks:
      - id: import-linter
        name: Check import boundaries
        entry: lint-imports
        language: system
        pass_filenames: false
```

---

## Phase 7: Testing & Validation (3 hours)

### 7.1 Update Existing Tests

```bash
# Run tests after each phase
pytest tests/

# Check coverage
pytest --cov=. --cov-report=html

# Validate golden files
pytest tests/test_golden_outputs.py -v
```

### 7.2 New Tests to Add

```python
# tests/test_import_boundaries.py
"""Test that modules respect dependency boundaries."""

def test_models_has_no_internal_imports():
    """models.py must not import from other phonenv modules."""
    import ast
    source = Path("models.py").read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not node.module or not node.module.startswith("phonenv")

def test_output_doesnt_import_processors():
    """output/ must not import from processors."""
    # Similar AST check
    ...
```

### 7.3 Performance Regression Tests

```python
# tests/test_performance.py
"""Ensure refactoring doesn't slow things down."""

def test_import_time_acceptable():
    """Import time should be < 2x baseline."""
    import subprocess
    import time

    start = time.time()
    subprocess.run([sys.executable, "-c", "import main"], check=True)
    elapsed = time.time() - start

    # Baseline: 500ms, allow up to 1000ms
    assert elapsed < 1.0, f"Import took {elapsed:.2f}s (baseline: 0.5s)"

def test_batch_processing_speed():
    """Batch processing shouldn't slow down."""
    # Compare against baseline timing
    ...
```

---

## Definition of Done

### ✅ Functional Requirements
- [ ] All 49 unit tests pass (minimum)
- [ ] CLI smoke tests pass (interactive + batch modes)
- [ ] Golden file tests pass (outputs unchanged)
- [ ] Backward compatibility verified (old imports work)

### ✅ Architectural Requirements
- [ ] No circular imports (lint-imports passes)
- [ ] Dependency rules enforced (.importlinter config)
- [ ] No module > 700 lines
- [ ] models.py has zero internal imports

### ✅ Performance Requirements
- [ ] Import time increase < 2× baseline (< 1 second)
- [ ] Batch processing time unchanged (±10%)
- [ ] Memory usage unchanged (±10%)

### ✅ Documentation Requirements
- [ ] README updated with new structure
- [ ] MIGRATION.md created
- [ ] Deprecation warnings in old modules
- [ ] Docstrings updated with new import paths

### ✅ Packaging Requirements
- [ ] `pyproject.toml` created (modern packaging)
- [ ] Console entry point works: `phonenv --help`
- [ ] `pip install -e .` succeeds
- [ ] `pip install .` creates working package

---

## Timeline (Revised)

**Total: 1.5 days focused work**

| Phase | Hours | Day |
|-------|-------|-----|
| Phase 0: Pre-refactoring (characterization tests) | 4h | Day 1 AM |
| Phase 1: Foundation layer (models, parsers) | 4h | Day 1 PM |
| Phase 2: Core layer (alternations, processors) | 4h | Day 2 AM |
| Phase 3: Output layer (output/ package) | 3h | Day 2 PM (1/2) |
| Phase 4: CLI layer (cli/ package) | 3h | Day 2 PM (2/2) |
| Phase 5: Backward compatibility | 2h | Day 2 PM (overlap) |
| Phase 6: Import hygiene (linting) | 2h | Day 2 End |
| Phase 7: Testing & validation | 3h | Buffer/Final |

**Note:** Phases can overlap; some parallelization possible

---

## Risk Mitigation

### Risk 1: Circular Imports
**Mitigation:**
- ✅ Strict dependency rules enforced
- ✅ TYPE_CHECKING for type-only imports
- ✅ models.py import-free
- ✅ Import linter in CI

### Risk 2: Breaking Changes
**Mitigation:**
- ✅ Backward compat layer (data.py, phonenv_io.py)
- ✅ Deprecation warnings
- ✅ Golden file tests
- ✅ SemVer migration plan

### Risk 3: Performance Regression
**Mitigation:**
- ✅ Baseline metrics recorded
- ✅ Performance tests added
- ✅ Import time monitored
- ✅ Lazy loading where needed

### Risk 4: Test Breakage
**Mitigation:**
- ✅ Characterization tests BEFORE refactoring
- ✅ Test after each phase
- ✅ Maintain test coverage (> 80%)
- ✅ Old imports still work

---

## Success Metrics

**After refactoring:**

| Metric | Before | Target | Result |
|--------|--------|--------|--------|
| Largest module | 1,781 LOC | < 700 LOC | ___ |
| Test pass rate | 94% (49/52) | ≥ 94% | ___ |
| Import time | ___ ms | < 2× | ___ ms |
| Circular imports | ? | 0 | ___ |
| Test coverage | ___% | > 80% | ___% |

---

## Appendix: pyproject.toml (Modern Packaging)

**File:** `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "phonenv"
version = "2.0.0"
description = "Phonetic environment analysis toolkit"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Science/Research",
    "Topic :: Text Processing :: Linguistic",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "regex>=2021.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=6.0",
    "pytest-cov",
    "black>=21.0",
    "flake8>=3.9",
    "import-linter>=1.2",
]
full = [
    "panphon>=0.20",
    "rich>=10.0",
]

[project.scripts]
phonenv = "main:main"

[tool.setuptools.packages.find]
where = ["."]
include = ["phonenv*", "cli*", "output*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

[tool.black]
line-length = 88
target-version = ['py39']

[tool.coverage.run]
source = ["."]
omit = ["tests/*", "setup.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

---

## Conclusion

This revised plan addresses all identified risks:

✅ **Circular imports** - Prevented via strict rules + linting
✅ **Business logic boundaries** - Clear: alternations.py (analysis) vs processors.py (orchestration)
✅ **Deprecation path** - SemVer-compliant with warnings
✅ **Characterization tests** - Safety net before changes
✅ **Realistic timeline** - 1.5 days instead of 6-8 hours
✅ **Import hygiene** - Enforced via import-linter
✅ **Modern packaging** - pyproject.toml + console entry point

**Recommendation:** Proceed with Phase 0 (characterization tests) immediately to establish safety net.
