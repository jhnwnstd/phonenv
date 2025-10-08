# Phonenv Refactoring Plan

**Date:** 2025-10-07
**Goal:** Improve modularity and code organization without removing functionality
**Approach:** Move functions to more appropriate modules, create new specialized modules

---

## Current State Analysis

### Module Sizes (LOC)
```
data.py         1,781 lines  ⚠️ TOO LARGE (data + processing + alternations)
main.py         1,472 lines  ⚠️ TOO LARGE (CLI + interactive + utilities)
phonenv_io.py   1,152 lines  ⚠️ LARGE (caching + output + utilities)
analyze.py      1,051 lines  ✅ ACCEPTABLE
validate.py       617 lines  ✅ ACCEPTABLE
config.py         211 lines  ✅ GOOD
logger.py         208 lines  ✅ GOOD
utils.py          147 lines  ✅ GOOD
normalize.py      141 lines  ✅ GOOD
setup.py           96 lines  ✅ GOOD
```

### Current Module Responsibilities

#### ❌ **Problems Identified:**

1. **data.py (1,781 lines)** - DOING TOO MUCH
   - Data parsing (WordEntry, section parsing)
   - Dictionary management (DictionaryProcessor)
   - Target processing (TargetsProcessor)
   - Alternation analysis (complex algorithms)
   - Result data classes (TargetResult, AlternationResult)
   - Utility functions (load_words_set, create_sample_targets)

2. **main.py (1,472 lines)** - DOING TOO MUCH
   - CLI argument parsing
   - Interactive UI (InteractivePhonenvCLI class - 850+ lines!)
   - Diacritic panel logic
   - Batch processing coordination
   - Helper utilities (normalize_user_input, format_error)
   - IPA character menus (CONSONANT_CATEGORIES, VOWEL_CATEGORIES)

3. **phonenv_io.py (1,152 lines)** - MIXED CONCERNS
   - Result caching (ResultCache class)
   - Output formatting (OutputWriter class)
   - Multiple output formats (TXT, CSV, JSON, JSONL)
   - Utility functions (slug, get_default_output_path)
   - Global cache management

---

## Refactoring Plan

### Phase 1: Create New Specialized Modules

#### 1.1 Create `models.py` - Data Models
**Purpose:** Centralize all data classes and enums
**Size:** ~300 lines
**Move from:**
- `data.py`: WordEntry, AlternationPair, TargetResult, AlternationResult, StructuralAlternationResult
- `phonenv_io.py`: CacheEntry
- `logger.py`: LogLevel enum

**Structure:**
```python
# models.py
"""Data models and enums for Phonenv."""

# Enums
class LogLevel(Enum): ...
class DistributionPattern(Enum): ...

# Data Entry Models
@dataclass
class WordEntry: ...
@dataclass
class AlternationPair: ...

# Result Models
@dataclass
class TargetResult: ...
@dataclass
class AlternationResult: ...
@dataclass
class StructuralAlternationResult: ...

# Cache Models
@dataclass
class CacheEntry: ...
```

**Benefits:**
- Single source of truth for data structures
- Easier to maintain and version
- Clearer dependencies
- Better for IDE autocomplete

---

#### 1.2 Create `parsers.py` - Data Parsing Logic
**Purpose:** Handle all file parsing and data loading
**Size:** ~400 lines
**Move from:**
- `data.py`: iter_word_entries, load_words_set, load_words_list, _parse_section, _strip_comment, _extract_tags, _split_targets_line
- `validate.py`: _load_words_dataset, _load_targets, _read_file_lines

**Structure:**
```python
# parsers.py
"""File parsing and data loading for Phonenv."""

def parse_section_header(line: str) -> Optional[Dict[str, str]]: ...
def strip_comment(text: str) -> str: ...
def extract_tags(text: str) -> Tuple[str, Tuple[str, ...]]: ...

# Word Entry Parsing
def iter_word_entries(path: str | Path) -> Iterator[WordEntry]: ...
def load_words_set(path: str) -> Set[str]: ...
def load_words_list(path: str) -> List[str]: ...

# Target Parsing
def split_targets_line(line: str) -> List[str]: ...
def load_targets_file(path: str) -> Tuple[List[str], List[AlternationPair]]: ...

# Validation Helpers
def read_file_lines(path: Path) -> List[str]: ...
```

**Benefits:**
- Separates I/O from business logic
- Reusable across modules
- Easier testing
- Clear parsing responsibility

---

#### 1.3 Create `alternations.py` - Alternation Analysis
**Purpose:** Handle all alternation-related analysis
**Size:** ~600 lines
**Move from:**
- `data.py`: All alternation analysis methods from TargetsProcessor
  - `analyze_alternation()`
  - `analyze_structural_alternation()`
  - `_analyze_with_progressive_window()`
  - `_compute_separability_score()`
  - `_compute_complexity_penalty()`
  - `_analyze_distribution_pattern()`
  - `_classify_structural_process()`
  - Helper methods for alternation analysis

**Structure:**
```python
# alternations.py
"""Phonological alternation analysis."""

class AlternationAnalyzer:
    """Analyzes phonological alternations between segment pairs."""

    def __init__(self, analyzer: PhoneticAnalyzer): ...

    # Main analysis methods
    def analyze_alternation(self, pair: AlternationPair) -> AlternationResult: ...
    def analyze_structural_alternation(self, pair: AlternationPair) -> StructuralAlternationResult: ...

    # Auto-window algorithm
    def analyze_with_progressive_window(self, pair: AlternationPair) -> AlternationResult: ...
    def compute_separability_score(self, ...) -> Tuple[float, int, int, int]: ...
    def compute_complexity_penalty(self, window: int) -> float: ...

    # Pattern classification
    def analyze_distribution_pattern(self, ...) -> Tuple[str, str]: ...
    def classify_structural_process(self, ...) -> Tuple[str, str, str]: ...
```

**Benefits:**
- Complex algorithm isolation
- Easier to test alternation logic
- Clear responsibility boundary
- Can be used independently

---

#### 1.4 Create `cli/` Package - Command Line Interface
**Purpose:** Separate CLI concerns into submodules
**Size:** ~800 lines total
**Structure:**
```
cli/
├── __init__.py         # Exports main CLI class
├── interactive.py      # InteractivePhonenvCLI class (600 lines)
├── batch.py           # Batch processing logic (100 lines)
├── menus.py           # IPA menus and diacritic panel (100 lines)
└── utils.py           # CLI utilities (safe_input, format_error)
```

**Move from main.py:**
- `cli/interactive.py`: InteractivePhonenvCLI class
- `cli/batch.py`: run_batch_cli(), process_targets_with_cache()
- `cli/menus.py`: CONSONANT_CATEGORIES, VOWEL_CATEGORIES, COMMON_DIACRITICS, _compose(), _apply_mutex_list()
- `cli/utils.py`: normalize_user_input(), safe_input(), format_error()

**Benefits:**
- Logical separation of UI concerns
- main.py becomes thin orchestrator
- Easier to add new UI modes
- Better code organization

---

#### 1.5 Create `output/` Package - Output Formatting
**Purpose:** Separate output format concerns
**Size:** ~600 lines total
**Structure:**
```
output/
├── __init__.py         # Exports writers
├── writers.py         # OutputWriter, AutoOutputWriter (300 lines)
├── formats/
│   ├── __init__.py
│   ├── txt.py         # TXT formatter (150 lines)
│   ├── csv.py         # CSV formatter (50 lines)
│   ├── json.py        # JSON/JSONL formatters (100 lines)
└── cache.py           # ResultCache class (300 lines)
```

**Move from phonenv_io.py:**
- `output/cache.py`: ResultCache class and cache management
- `output/writers.py`: OutputWriter, AutoOutputWriter base classes
- `output/formats/*.py`: Format-specific logic
- Keep utility functions in phonenv_io.py for backward compatibility

**Benefits:**
- Separation of caching from formatting
- Easy to add new output formats
- Clearer responsibilities
- Better testability

---

#### 1.6 Create `processors.py` - Data Processing
**Purpose:** High-level data processing coordination
**Size:** ~400 lines
**Move from:**
- `data.py`: DictionaryProcessor class, TargetsProcessor class (minus alternation methods)

**Structure:**
```python
# processors.py
"""High-level data processors for Phonenv."""

class DictionaryProcessor:
    """Manages phonetic dictionary operations."""
    def __init__(self, dataset_path: str): ...
    def get_words(self) -> List[str]: ...
    def add_word(self, word: str) -> bool: ...
    def remove_words_containing(self, substring: str) -> int: ...
    # ... other dictionary operations

class TargetsProcessor:
    """Processes target phonemes and coordinates analysis."""
    def __init__(self, dataset_path: str, analyzer: PhoneticAnalyzer): ...
    def load_targets(self) -> Tuple[List[str], List[AlternationPair]]: ...
    def analyze_target(self, target: str) -> TargetResult: ...
    def process_targets_to_list(self) -> List[TargetResult]: ...
    # ... (alternation methods moved to alternations.py)
```

**Benefits:**
- Clear processing logic
- Separated from parsing
- Easier testing
- Composable

---

### Phase 2: Reorganize Existing Modules

#### 2.1 Slim Down `main.py`
**New Size:** ~200 lines
**Keep:**
- `main()` function - entry point
- Argument parsing setup
- Minimal orchestration

**Move out:**
- Interactive UI → `cli/interactive.py`
- Batch processing → `cli/batch.py`
- Utilities → `cli/utils.py`

**New main.py:**
```python
#!/usr/bin/env python3
"""Command-line interface entry point for Phonenv."""

from cli import InteractivePhonenvCLI, run_batch_cli
from config import DEFAULT_DATASET_PATH
import argparse
import sys

def main():
    """Main entry point for CLI."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Handle utility flags
    if args.create_targets:
        handle_create_targets(args)
    elif args.clear_cache:
        handle_clear_cache()
    elif args.cache_stats:
        handle_cache_stats()
    elif args.batch:
        run_batch_cli(args)
    else:
        # Interactive mode
        cli = InteractivePhonenvCLI(args.dataset)
        cli.run()

if __name__ == "__main__":
    main()
```

---

#### 2.2 Slim Down `data.py`
**New Size:** ~400 lines
**Keep:**
- Legacy compatibility functions (load_words_set, load_words_list)
- Simple helpers (create_sample_targets_file, targets_exist)

**Move out:**
- Data classes → `models.py`
- Parsing logic → `parsers.py`
- Processors → `processors.py`
- Alternation analysis → `alternations.py`

**New data.py:**
```python
"""Data management for phonetic environment analysis.

NOTE: This module is kept for backward compatibility.
New code should use:
- models.py for data structures
- parsers.py for file parsing
- processors.py for data processing
- alternations.py for alternation analysis
"""

# Re-export from new modules for backward compatibility
from models import WordEntry, AlternationPair, TargetResult
from parsers import load_words_set, load_words_list
from processors import DictionaryProcessor, TargetsProcessor
from alternations import AlternationAnalyzer

# Keep utility functions here
def create_sample_targets_file(path: str = "data/targets.txt"): ...
def targets_exist(path: str = "data/targets.txt") -> bool: ...
```

---

#### 2.3 Slim Down `phonenv_io.py`
**New Size:** ~250 lines
**Keep:**
- Backward compatibility exports
- Utility functions (get_cache, clear_cache, get_cache_stats)

**Move out:**
- ResultCache → `output/cache.py`
- OutputWriter → `output/writers.py`
- Format-specific code → `output/formats/*.py`

**New phonenv_io.py:**
```python
"""I/O operations for phonetic environment analysis.

NOTE: This module is kept for backward compatibility.
New code should use:
- output.cache for caching
- output.writers for output formatting
"""

# Re-export from new modules
from output.cache import ResultCache, get_cache, clear_cache, get_cache_stats
from output.writers import OutputWriter, AutoOutputWriter
from output import write_results, get_default_output_path

# Keep backward compatibility
__all__ = [
    "ResultCache", "OutputWriter", "AutoOutputWriter",
    "get_cache", "clear_cache", "get_cache_stats",
    "write_results", "get_default_output_path"
]
```

---

### Phase 3: New Module Structure

```
phonenv/
├── __init__.py                 # Package exports
├── main.py                     # CLI entry point (200 lines) ⬇️
├── setup.py                    # Package setup (96 lines)
│
├── Core Analysis
├── analyze.py                  # Phonetic analysis (1,051 lines) ✅
├── alternations.py            # Alternation analysis (600 lines) 🆕
├── processors.py              # Data processors (400 lines) 🆕
│
├── Data & Models
├── models.py                  # Data structures (300 lines) 🆕
├── parsers.py                 # File parsing (400 lines) 🆕
├── data.py                    # Compatibility layer (400 lines) ⬇️
│
├── I/O & Output
├── phonenv_io.py              # Compatibility layer (250 lines) ⬇️
├── output/                    # Output package 🆕
│   ├── __init__.py
│   ├── cache.py               # Caching (300 lines)
│   ├── writers.py             # Output writers (300 lines)
│   └── formats/
│       ├── __init__.py
│       ├── txt.py             # TXT output (150 lines)
│       ├── csv.py             # CSV output (50 lines)
│       └── json.py            # JSON/JSONL output (100 lines)
│
├── CLI & UI
├── cli/                       # CLI package 🆕
│   ├── __init__.py
│   ├── interactive.py         # Interactive UI (600 lines)
│   ├── batch.py               # Batch processing (100 lines)
│   ├── menus.py               # IPA menus (100 lines)
│   └── utils.py               # CLI utilities (50 lines)
│
├── Utilities
├── utils.py                   # General utilities (147 lines) ✅
├── normalize.py               # Normalization (141 lines) ✅
├── validate.py                # Validation (617 lines) ✅
├── config.py                  # Configuration (211 lines) ✅
└── logger.py                  # Logging (208 lines) ✅
```

**Legend:**
- ✅ = No changes needed
- ⬇️ = Slimmed down (backward compatible)
- 🆕 = New module/package

---

## Benefits of This Refactoring

### 1. **Separation of Concerns**
- ✅ Data models separated from logic
- ✅ Parsing separated from processing
- ✅ CLI separated from core analysis
- ✅ Output formats isolated

### 2. **Improved Testability**
- ✅ Smaller, focused modules easier to test
- ✅ Clear interfaces between components
- ✅ Easier to mock dependencies

### 3. **Better Maintainability**
- ✅ Each module < 700 lines (manageable)
- ✅ Clear module responsibilities
- ✅ Easier to find code
- ✅ Reduced coupling

### 4. **Scalability**
- ✅ Easy to add new output formats
- ✅ Easy to add new UI modes
- ✅ Easy to extend alternation analysis
- ✅ Clear extension points

### 5. **Backward Compatibility**
- ✅ All existing imports still work
- ✅ API remains unchanged
- ✅ Tests don't need modification
- ✅ Gradual migration path

---

## Migration Strategy

### Step 1: Create New Modules (No Breaking Changes)
1. Create `models.py` with data classes
2. Create `parsers.py` with parsing logic
3. Create `alternations.py` with alternation analysis
4. Create `processors.py` with processors
5. Create `cli/` package with UI code
6. Create `output/` package with I/O code

### Step 2: Update Existing Modules (Maintain Compatibility)
1. Update `data.py` to re-export from new modules
2. Update `main.py` to use `cli/` package
3. Update `phonenv_io.py` to re-export from `output/`
4. Add deprecation warnings where appropriate

### Step 3: Update Internal Imports
1. Update cross-module imports to use new structure
2. Update tests to import from new modules (optional)
3. Update documentation

### Step 4: Testing & Validation
1. Run full test suite after each step
2. Verify backward compatibility
3. Check import times
4. Validate all CLI modes

---

## Implementation Checklist

### Phase 1: New Modules (2-3 hours)
- [ ] Create `models.py`
  - [ ] Move data classes
  - [ ] Update imports
  - [ ] Test imports work
- [ ] Create `parsers.py`
  - [ ] Move parsing functions
  - [ ] Update imports
  - [ ] Test parsing still works
- [ ] Create `alternations.py`
  - [ ] Move AlternationAnalyzer
  - [ ] Update imports
  - [ ] Test alternation analysis
- [ ] Create `processors.py`
  - [ ] Move processor classes
  - [ ] Update imports
  - [ ] Test processing works

### Phase 2: Package Structure (2-3 hours)
- [ ] Create `cli/` package
  - [ ] Create `cli/interactive.py`
  - [ ] Create `cli/batch.py`
  - [ ] Create `cli/menus.py`
  - [ ] Create `cli/utils.py`
  - [ ] Test interactive mode
  - [ ] Test batch mode
- [ ] Create `output/` package
  - [ ] Create `output/cache.py`
  - [ ] Create `output/writers.py`
  - [ ] Create `output/formats/`
  - [ ] Test all output formats

### Phase 3: Compatibility (1 hour)
- [ ] Update `data.py` with re-exports
- [ ] Update `main.py` to be thin orchestrator
- [ ] Update `phonenv_io.py` with re-exports
- [ ] Add deprecation warnings

### Phase 4: Testing (1 hour)
- [ ] Run pytest suite
- [ ] Test CLI modes
- [ ] Test interactive mode
- [ ] Verify imports
- [ ] Check backward compatibility

**Total Estimated Time:** 6-8 hours

---

## Potential Issues & Solutions

### Issue 1: Circular Imports
**Risk:** New module structure might create circular dependencies
**Solution:**
- Use type hints with `from __future__ import annotations`
- Use `TYPE_CHECKING` for type-only imports
- Keep `models.py` import-free (only stdlib)

### Issue 2: Import Performance
**Risk:** More modules might slow import time
**Solution:**
- Use lazy imports where appropriate
- Keep `__init__.py` files minimal
- Profile import time before/after

### Issue 3: Breaking Tests
**Risk:** Tests might import from old locations
**Solution:**
- Maintain re-exports in old modules
- Update test imports gradually
- Run tests after each step

### Issue 4: Documentation Updates
**Risk:** Docs reference old module structure
**Solution:**
- Update README.md with new structure
- Add migration guide
- Update docstrings with new imports

---

## Example Migration: AlternationAnalyzer

### Before (in data.py):
```python
# data.py (1,781 lines)
class TargetsProcessor:
    def analyze_alternation(self, pair): ...
    def _compute_separability_score(self, ...): ...
    def _analyze_with_progressive_window(self, ...): ...
    # ... 15+ alternation methods
```

### After (in alternations.py):
```python
# alternations.py (new file, 600 lines)
from models import AlternationPair, AlternationResult
from analyze import PhoneticAnalyzer

class AlternationAnalyzer:
    """Analyzes phonological alternations."""

    def __init__(self, analyzer: PhoneticAnalyzer):
        self.analyzer = analyzer

    def analyze(self, pair: AlternationPair) -> AlternationResult:
        """Main alternation analysis entry point."""
        ...
```

### Compatibility (in data.py):
```python
# data.py (now 400 lines)
from alternations import AlternationAnalyzer

class TargetsProcessor:
    def __init__(self, ...):
        self._alternation_analyzer = AlternationAnalyzer(self.analyzer)

    def analyze_alternation(self, pair):
        """Deprecated: Use AlternationAnalyzer directly."""
        return self._alternation_analyzer.analyze(pair)
```

---

## Success Metrics

✅ **All existing tests pass**
✅ **No module > 700 lines**
✅ **Clear module responsibilities**
✅ **Backward compatible**
✅ **Import time < 2x original**
✅ **Easy to find code**

---

## Conclusion

This refactoring will significantly improve code organization without breaking existing functionality. The modular structure will make Phonenv easier to maintain, test, and extend.

**Recommendation:** Proceed with Phase 1 (create new modules) first, test thoroughly, then continue to Phase 2 and 3.
