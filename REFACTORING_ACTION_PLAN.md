# Refactoring Action Plan - Quick Start

**Status:** READY TO EXECUTE
**Time Required:** 1.5 days
**Review:** Architectural feedback incorporated

---

## 🚦 Pre-Flight Checklist

Before starting:
- [ ] Read [REFACTORING_PLAN_V2.md](REFACTORING_PLAN_V2.md) (comprehensive plan)
- [ ] Commit all current changes
- [ ] Create feature branch: `git checkout -b refactor/modular-structure`
- [ ] Record baseline metrics (see Phase 0)

---

## 📋 Phase 0: Safety Net (4 hours) - START HERE

### Step 1: Record Baselines (30 min)

```bash
# Import time
python -X importtime -c "import main" 2>&1 | tail -1 > baselines/import_time.txt

# Test coverage
pytest --cov=. --cov-report=term | tee baselines/coverage.txt

# Module complexity
radon cc *.py -a > baselines/complexity.txt

# Current module sizes
wc -l *.py > baselines/module_sizes.txt
```

### Step 2: Create Golden Files (2 hours)

```bash
# Create test data directory
mkdir -p tests/golden

# Generate golden outputs
python main.py --batch --format txt --output tests/golden/batch_output.txt
python main.py --batch --format json --output tests/golden/batch_output.json
python main.py --batch --format csv --output tests/golden/batch_output.csv
python main.py --help > tests/golden/cli_help.txt
```

### Step 3: Write Characterization Tests (1.5 hours)

Create `tests/test_golden_outputs.py`:

```python
"""Golden file tests - DO NOT MODIFY during refactoring."""

import json
import subprocess
from pathlib import Path
import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"

def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for comparison."""
    return "\n".join(line.rstrip() for line in text.splitlines())

def test_batch_txt_output_unchanged(tmp_path):
    """TXT output must not change."""
    result_file = tmp_path / "output.txt"
    subprocess.run([
        "python", "main.py", "--batch",
        "--format", "txt",
        "--output", str(result_file)
    ], check=True)

    golden = (GOLDEN_DIR / "batch_output.txt").read_text()
    result = result_file.read_text()

    # Ignore timestamps in comparison
    golden_normalized = normalize_whitespace(golden).replace("Generated: ", "")
    result_normalized = normalize_whitespace(result).replace("Generated: ", "")

    assert golden_normalized == result_normalized

def test_batch_json_output_unchanged(tmp_path):
    """JSON structure must not change."""
    result_file = tmp_path / "output.json"
    subprocess.run([
        "python", "main.py", "--batch",
        "--format", "json",
        "--output", str(result_file)
    ], check=True)

    golden_data = json.loads((GOLDEN_DIR / "batch_output.json").read_text())
    result_data = json.loads(result_file.read_text())

    # Compare structure (ignore timestamps)
    assert len(result_data["results"]) == len(golden_data["results"])
    assert result_data["metadata"]["targets_count"] == golden_data["metadata"]["targets_count"]

def test_cli_help_unchanged():
    """CLI interface must not change."""
    result = subprocess.check_output(["python", "main.py", "--help"], text=True)
    golden = (GOLDEN_DIR / "cli_help.txt").read_text()

    assert "--batch" in result
    assert "--format" in result
    assert result.count("--") == golden.count("--")  # Same number of flags

def test_alternation_analysis_unchanged():
    """Alternation analysis behavior must not change."""
    from data import TargetsProcessor, AlternationPair
    from analyze import PhoneticAnalyzer

    analyzer = PhoneticAnalyzer()
    processor = TargetsProcessor("data/dataset.txt", analyzer)

    pair = AlternationPair("p", "b")
    result = processor.analyze_alternation(pair)

    # Verify key properties
    assert result.pair.segment1 == "p"
    assert result.pair.segment2 == "b"
    assert result.pattern in ["complementary", "contrastive", "free_variation", "neutralization", "partial_overlap", "inconclusive"]
    assert result.segment1_total >= 0
    assert result.segment2_total >= 0
```

**Run:**
```bash
pytest tests/test_golden_outputs.py -v
# All should PASS before proceeding
```

---

## 📦 Phase 1: Foundation Layer (4 hours)

### Step 1: Create `models.py` (1 hour)

```bash
# Copy template from REFACTORING_PLAN_V2.md Phase 1.1
# Key points:
# - NO internal imports (stdlib only)
# - from __future__ import annotations
# - frozen=True for cache keys
```

**Test:**
```bash
python -c "from models import WordEntry, AlternationPair; print('✓ Models import')"
pytest tests/ -k "not golden" -v  # Existing tests should still pass
```

### Step 2: Create `parsers.py` (2 hours)

Move from `data.py`:
- `iter_word_entries()`
- `load_words_set()`
- `load_words_list()`
- `_parse_section()`
- `_strip_comment()`
- `_extract_tags()`
- `_split_targets_line()`

**Update imports in parsers.py:**
```python
from models import WordEntry, AlternationPair  # Not from data
```

**Test:**
```bash
python -c "from parsers import load_words_set; print(len(load_words_set('data/dataset.txt')))"
pytest tests/test_data_structures.py -v
```

### Step 3: Update `utils.py` (30 min)

Add TYPE_CHECKING imports:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models import WordEntry
```

**Test:**
```bash
python -c "from utils import normalize_tiebar; print('✓')"
```

---

## 🔬 Phase 2: Core Analysis (4 hours)

### Step 1: Create `alternations.py` (2.5 hours)

Extract from `data.py` TargetsProcessor:
- All alternation methods → AlternationAnalyzer class
- Make methods stateless where possible
- Use staticmethod for pure functions

**Key changes:**
```python
class AlternationAnalyzer:
    def __init__(self, phonetic_analyzer):
        self.analyzer = phonetic_analyzer  # Injected dependency

    @staticmethod
    def compute_separability_score(...):
        """Pure function - no self needed."""
```

**Test:**
```bash
pytest tests/test_alternations.py -v
pytest tests/test_golden_outputs.py::test_alternation_analysis_unchanged -v
```

### Step 2: Create `processors.py` (1.5 hours)

Move from `data.py`:
- `DictionaryProcessor` class
- `TargetsProcessor` class (minus alternation methods)
- Update TargetsProcessor to use AlternationAnalyzer

```python
class TargetsProcessor:
    def __init__(self, dataset_path, analyzer):
        self.analyzer = analyzer
        self.alternation_analyzer = AlternationAnalyzer(analyzer)

    def analyze_alternation(self, pair):
        words1, words2 = self._get_filtered_words(pair)
        return self.alternation_analyzer.analyze(pair, words1, words2)
```

**Test:**
```bash
pytest tests/test_targets.py -v
pytest tests/test_golden_outputs.py -v
```

---

## 📤 Phase 3: Output Layer (3 hours)

### Step 1: Create Package Structure (30 min)

```bash
mkdir -p output/formats
touch output/__init__.py
touch output/cache.py
touch output/writers.py
touch output/registry.py
touch output/formats/__init__.py
touch output/formats/base.py
touch output/formats/txt.py
touch output/formats/csv.py
touch output/formats/json.py
```

### Step 2: Move Cache Logic (1 hour)

Move `ResultCache` from `phonenv_io.py` → `output/cache.py`

**Update imports:**
```python
from models import CacheEntry, CacheKey  # Not from phonenv_io
```

### Step 3: Create Format Registry (1 hour)

Implement `output/registry.py` to avoid import cycles.

### Step 4: Move Formatters (30 min)

Split `phonenv_io.py` OutputWriter methods into separate format files.

**Test:**
```bash
pytest tests/test_output_formats.py -v
pytest tests/test_golden_outputs.py -v
```

---

## 💻 Phase 4: CLI Layer (3 hours)

### Step 1: Create Package (30 min)

```bash
mkdir -p cli
touch cli/__init__.py
touch cli/interactive.py
touch cli/batch.py
touch cli/menus.py
touch cli/constants.py
touch cli/utils.py
```

### Step 2: Move Interactive UI (1.5 hours)

Move `InteractivePhonenvCLI` class from `main.py` → `cli/interactive.py`

### Step 3: Move Menus & Constants (30 min)

Move to `cli/constants.py`:
- CONSONANT_CATEGORIES
- VOWEL_CATEGORIES
- COMMON_DIACRITICS

### Step 4: Move Batch Processing (30 min)

Move batch functions → `cli/batch.py`

**Test:**
```bash
python main.py --help  # Should work
echo "" | timeout 3 python main.py  # Should exit gracefully
pytest tests/test_golden_outputs.py::test_cli_help_unchanged -v
```

---

## 🔄 Phase 5: Backward Compatibility (2 hours)

### Step 1: Update `data.py` (1 hour)

Replace content with re-exports + deprecation warnings:

```python
import warnings

warnings.warn(
    "Importing from data.py is deprecated. See MIGRATION.md for new import paths. "
    "This module will be removed in v3.0.0.",
    DeprecationWarning,
    stacklevel=2
)

from models import WordEntry, AlternationPair, TargetResult
from parsers import load_words_set, load_words_list
from processors import DictionaryProcessor, TargetsProcessor

# Keep these functions (not worth moving)
def create_sample_targets_file(path="data/targets.txt"):
    ...

def targets_exist(path="data/targets.txt"):
    ...
```

### Step 2: Update `phonenv_io.py` (30 min)

```python
import warnings

warnings.warn(
    "phonenv_io is deprecated. Use 'from output import ...' instead.",
    DeprecationWarning,
    stacklevel=2
)

from output import ResultCache, AutoOutputWriter, get_cache, write_results
```

### Step 3: Update `main.py` (30 min)

Slim down to ~200 lines:
- Import from cli/ package
- Keep only argument parsing and delegation

**Test:**
```bash
# Old imports should still work (with warnings)
python -c "from data import WordEntry; print('✓')" 2>&1 | grep "DeprecationWarning"
python -c "from phonenv_io import get_cache; print('✓')" 2>&1 | grep "DeprecationWarning"

# New imports should work silently
python -c "from models import WordEntry; print('✓')"
python -c "from output import get_cache; print('✓')"

pytest tests/ -v  # ALL tests must pass
```

---

## 🔍 Phase 6: Import Hygiene (2 hours)

### Step 1: Create `.importlinter` (30 min)

Copy config from REFACTORING_PLAN_V2.md Phase 6.1

### Step 2: Install & Run (30 min)

```bash
pip install import-linter
lint-imports
# Fix any violations
```

### Step 3: Add Pre-commit Hook (optional, 1 hour)

```bash
pip install pre-commit
# Create .pre-commit-config.yaml
pre-commit install
```

---

## ✅ Phase 7: Final Validation (3 hours)

### Step 1: Run Full Test Suite (1 hour)

```bash
pytest tests/ -v --cov=. --cov-report=html
# Target: 49/52 tests passing (same as before)
```

### Step 2: Check Golden Files (30 min)

```bash
pytest tests/test_golden_outputs.py -v
# ALL must PASS
```

### Step 3: Performance Check (30 min)

```bash
# Import time
python -X importtime -c "import main" 2>&1 | tail -1
# Compare with baseline (must be < 2×)

# Batch processing
time python main.py --batch
# Compare with baseline (±10%)
```

### Step 4: Manual Smoke Tests (1 hour)

```bash
# CLI help
python main.py --help

# Create targets
python main.py --create-targets

# Cache stats
python main.py --cache-stats

# Batch TXT
python main.py --batch --format txt

# Batch JSON
python main.py --batch --format json --output /tmp/test.json

# Interactive (test EOF handling)
echo "" | python main.py
```

---

## 📦 Phase 8: Packaging (1 hour)

### Step 1: Create `pyproject.toml` (30 min)

Copy from REFACTORING_PLAN_V2.md Appendix

### Step 2: Test Installation (30 min)

```bash
# Editable install
pip install -e .

# Test entry point
phonenv --help
phonenv --batch

# Clean install
pip uninstall phonenv
pip install .
phonenv --help
```

---

## 📝 Documentation Updates (1 hour)

### Step 1: Create MIGRATION.md

```markdown
# Migration Guide: v1.x → v2.0

## Quick Migration

### Old imports (deprecated):
```python
from data import WordEntry, load_words_set
from phonenv_io import get_cache
```

### New imports (recommended):
```python
from models import WordEntry
from parsers import load_words_set
from output import get_cache
```

## What Changed

- `data.py` → Split into `models`, `parsers`, `processors`, `alternations`
- `phonenv_io.py` → Moved to `output/` package
- `main.py` → UI moved to `cli/` package

## Deprecation Timeline

- v2.0.0 (now): Old imports work with warnings
- v2.1.0 (6 months): Louder warnings
- v3.0.0 (future): Old modules removed
```

### Step 2: Update README.md

Add section about new structure:
```markdown
## Project Structure

```
phonenv/
├── models.py          # Data structures
├── parsers.py         # File parsing
├── processors.py      # Data processing
├── alternations.py    # Alternation analysis
├── analyze.py         # Phonetic analysis
├── output/            # Caching & formatting
├── cli/               # User interface
└── ...
```

See [MIGRATION.md](MIGRATION.md) for upgrade guide.
```

---

## ✅ Definition of Done Checklist

### Functional
- [ ] 49/52 tests pass (minimum)
- [ ] Golden files match
- [ ] CLI modes work (interactive, batch, help, cache)
- [ ] All output formats work (TXT, CSV, JSON)

### Architectural
- [ ] No circular imports (`lint-imports` passes)
- [ ] No module > 700 lines
- [ ] models.py has zero internal imports
- [ ] Dependency rules enforced

### Performance
- [ ] Import time < 2× baseline
- [ ] Batch processing time ±10%
- [ ] Memory usage ±10%

### Documentation
- [ ] README updated
- [ ] MIGRATION.md created
- [ ] Deprecation warnings in place
- [ ] CHANGELOG.md updated

### Packaging
- [ ] `pyproject.toml` works
- [ ] `pip install -e .` succeeds
- [ ] Entry point `phonenv` works
- [ ] Version bumped to 2.0.0

---

## 🚨 If Something Goes Wrong

### Rollback Plan

```bash
# If tests fail badly:
git checkout main
git branch -D refactor/modular-structure

# Start over from Phase 0
```

### Debug Checklist

1. **Import errors?**
   - Check circular imports: `lint-imports`
   - Check missing `__init__.py` files
   - Check TYPE_CHECKING blocks

2. **Tests failing?**
   - Run golden file tests first
   - Check if old imports still work
   - Verify models.py has no internal imports

3. **Performance issues?**
   - Profile import time
   - Check for duplicate work
   - Look for missing lazy imports

---

## 📊 Progress Tracker

| Phase | Status | Time Spent | Notes |
|-------|--------|------------|-------|
| 0: Safety Net | ⬜ | ___ | |
| 1: Foundation | ⬜ | ___ | |
| 2: Core Analysis | ⬜ | ___ | |
| 3: Output Layer | ⬜ | ___ | |
| 4: CLI Layer | ⬜ | ___ | |
| 5: Backward Compat | ⬜ | ___ | |
| 6: Import Hygiene | ⬜ | ___ | |
| 7: Validation | ⬜ | ___ | |
| 8: Packaging | ⬜ | ___ | |
| 9: Documentation | ⬜ | ___ | |

**Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Complete | ❌ Blocked

---

## 🎯 Quick Win: Start with Phase 0

```bash
# 1. Create branch
git checkout -b refactor/modular-structure

# 2. Record baselines
mkdir -p baselines tests/golden

# 3. Run characterization tests
python main.py --batch --format txt --output tests/golden/batch_output.txt
python main.py --help > tests/golden/cli_help.txt

# 4. Write test_golden_outputs.py

# 5. Verify tests pass BEFORE refactoring
pytest tests/test_golden_outputs.py -v

# ✓ Safety net established - ready to refactor!
```

---

**Next:** Begin Phase 0 when ready. Good luck! 🚀
