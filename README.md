# Phonenv

**Phonenv** is a Python library and CLI for **phonetic environment analysis**. It scans IPA word lists and reports where a target segment occurs—**INITIAL** (`# _ X`), **FINAL** (`X _ #`), and **MEDIAL** with context classes `V_V`, `V_C`, `C_V`, `C_C`—using **Unicode-correct** IPA processing. It’s **language-agnostic**, fast, and offers multiple output formats with caching.

---

## Table of Contents

1. [Features](#features)
2. [Installation](#installation)
3. [Quick Start](#quick-start)

   * [Interactive Mode](#interactive-mode)
   * [Batch Processing](#batch-processing)
4. [Interactive Capabilities](#interactive-capabilities)
5. [Python API](#python-api)
6. [How Phonenv Works](#how-phonenv-works)

   * [Normalization & Text Hygiene](#normalization--text-hygiene)
   * [Segmentation Model](#segmentation-model)
   * [Narrow vs Broad Matching](#narrow-vs-broad-matching)
   * [Environment Classification](#environment-classification)
   * [Special Handling Rules](#special-handling-rules)
7. [Dataset Format (v1.1+)](#dataset-format-v11)

   * [Migration Guide](#migration-guide)
   * [Format Specification](#format-specification)
   * [Example Enhanced Dataset](#example-enhanced-dataset)
8. [Example Output](#example-output)
9. [Project Structure](#project-structure)
10. [Dependencies](#dependencies)
11. [Technical Details](#technical-details)

    * [Performance](#performance)
    * [Output Formats](#output-formats)
    * [Validation & Error Handling](#validation--error-handling)
    * [Testing](#testing)
12. [Known Issues](#known-issues)
13. [Recent Improvements](#recent-improvements)
14. [Contributing](#contributing)
15. [License](#license)

---

## Features

* **Environment Analysis**
  INITIAL / FINAL / MEDIAL classification; MEDIAL split by `V_V`, `V_C`, `C_V`, `C_C`.
* **Robust Target Validation**
  **Segmentation-based** validation ensures only valid IPA segments are analyzed.
* **Dataset Format**
  Language-aware **section headers**, inline `#` comments, and `[tags]`; fully backwards-compatible with simple “one IPA per line”.
* **Interactive CLI**
  Browse IPA categories, apply diacritics, set modes, manage datasets, and analyze from the terminal.
* **Transcription Modes**
  **Narrow** (phonetic; diacritics contrastive) and **Broad** (phonemic; diacritics folded).
* **IPA Processing**
  Unicode-compliant **NFC/NFD** normalization, tie-bar unification, and robust segmentation.
* **Atomic Units**
  Diphthongs/triphthongs and **tie-bar affricates** treated as single segments.
* **Multiple Output Formats**
  TXT, CSV, JSON, JSONL with canonical deduplication and correct grammar.
* **Efficient Caching**
  SHA256-based result caching that respects configuration (mode, etc.).
* **Comprehensive Testing**
  Designed for full coverage; validates both transcription modes.

---

## Installation

```bash
# Core dependency
pip install regex

# Optional enhancements
pip install panphon     # feature vectors & helpers (optional)
pip install rich        # prettier terminal output (optional)

# Install Phonenv (editable for development)
pip install -e .
```

### Installation Options

```bash
# Minimal installation (regex only)
pip install .

# With enhanced IPA processing
pip install .[enhanced]

# Full development setup
pip install .[enhanced,dev]
```

---

## Quick Start

### Interactive Mode

Launch the interactive CLI:

```bash
python3 cli.py
```

If installed as a console script:

```bash
phonenv
```

**What you can do interactively:**

* Pick targets from consonant/vowel menus
* Apply diacritics via a quick panel
* Choose **narrow** or **broad** mode
* Manage the dataset (view/add/remove/clear/stats)
* Run batch processing on `data/targets.txt`

### Batch Processing

Process multiple targets from a file:

```bash
python3 -c "
from data import TargetsProcessor
from phonenv_io import AutoOutputWriter

processor = TargetsProcessor('data/dataset.txt', 'data/targets.txt')
results = []
for t in processor.load_targets():         # segmentation-based validation
    results.append(processor.analyze_target(t))

writer = AutoOutputWriter('data/output')
writer.write_batch_results(results, 'txt')
"
```

---

## Interactive Capabilities

### Character Selection

* Consonants by **place/manner**
* Vowels by **height/backness/rounding**
* Common **diphthongs** and **triphthongs**
* **Diacritic panel** to build complex segments

### Analysis Options

* Toggle **narrow** (phonetic) vs **broad** (phonemic)
* Analyze a character across **INITIAL/FINAL/MEDIAL** contexts
* View results in organized tables with examples

### Dictionary Management

Access from the interactive UI:

* **View Dictionary**: list all words
* **Add Words**: append new IPA forms
* **Remove Words**: delete forms containing a substring
* **Statistics**: counts, lengths, character usage
* **Clear Dataset** (with confirmation)

---

## Python API

```python
from analysis import PhoneticAnalyzer, IPAProcessorV2, get_config_for_transcription_mode
from data import TargetsProcessor, DictionaryProcessor, load_words_list, iter_word_entries, WordEntry
from phonenv_io import AutoOutputWriter

# Basic phonetic environment analysis
analyzer = PhoneticAnalyzer(use_ipa_processing=True)
envs = analyzer.analyze_character('ɪ', 'data/dataset.txt')  # dict grouped by environments

# Transcription mode configuration
config = get_config_for_transcription_mode('narrow')  # or 'broad'
analyzer = PhoneticAnalyzer(use_ipa_processing=True)
analyzer.ipa_processor_v2 = IPAProcessorV2(config)
analyzer.transcription_mode = 'narrow'
envs = analyzer.analyze_character('ɪ', 'data/dataset.txt')

# Batch processing with validation
processor = TargetsProcessor('data/dataset.txt', 'data/targets.txt')
targets = processor.load_targets()  # segmentation-based validation
results = []
for target in targets[:5]:
    r = processor.analyze_target(target)
    results.append(r)
    print(f"{target}: {r.total_occurrences} occurrences")

# Multiple output formats
writer = AutoOutputWriter('data/output')
paths = writer.write_batch_results(results, 'csv')  # or 'txt', 'json', 'jsonl'

# Direct IPA text processing
processor = IPAProcessorV2()
normalized_text = processor.normalize_nfc('tʰãsə')
segments = processor.ipa_segments(normalized_text)
```

---

## How Phonenv Works

### Normalization & Text Hygiene

* **Store/emit** in **NFC**; **analyze** in **NFD**
* Tie-bar variants unified (`͡` and `͜`) so equivalents compare the same
* Canonical equivalence guaranteed: e.g., `ã` ≡ `a` + ̃

**Why:** NFC ensures stable on-disk representation; NFD makes diacritics explicit for correct attachment during segmentation.

### Segmentation Model

Each **segment** is treated as an atomic unit with attached marks and modifiers.

```python
Segment {
  base: codepoint              # e.g., t, a, ɪ, ʃ, ɚ …
  diacritics: list             # combining marks & spacing modifiers bound to base
  length: {none, half, long}   # ˑ, ː
  suprasegmentals: dict        # stress, tone sequence, boundaries (stored separately)
}
```

**Attach to the base**

* Combining marks (U+0300–036F): ̃, ̥, ̬, ̟, ̠, ̝, ̞, ̩, etc.
* Spacing modifier letters (U+02B0–02FF): ʰ, ʱ, ʷ, ʲ, ˠ, ˤ, ⁿ, ˡ, etc.
* Length (ː long, ˑ half-long) stored as `length`

**Do not attach**

* Stress markers `ˈ`, `ˌ`
* Tone letters/diacritics
* Word/foot boundaries, pauses, intonation

### Narrow vs Broad Matching

* **Narrow (phonetic; default in the interactive UI)**
  Diacritics/length are **contrastive**
  Examples: `[p] ≠ [pʰ]`, `[a] ≠ [ã]`, `[i] ≠ [iː]`

* **Broad (phonemic)**
  Diacritics/length **folded away** (language-agnostic folding)
  Examples: `[p] = [pʰ]`, `[a] = [ã]`, `[i] = [iː]`
  (Profiles could refine this per language if desired.)

### Environment Classification

* **INITIAL**: `# _ X` — first segment after stripping suprasegmentals
* **FINAL**: `X _ #` — last segment
* **MEDIAL**: classified by neighbor types: `V_V`, `V_C`, `C_V`, `C_C`

**Rules & examples:**

* Suprasegmentals (`ˈ`, `ˌ`, `|`, `‖`) are ignored when choosing neighbors.
* **Syllabic consonants** (`̩`) are treated as **V** for context classification.
  E.g., `n̩` behaves as a vowel nucleus.

### Special Handling Rules

* **Diacritics**
  Never standalone. Always attached to a base (e.g., `[pʰ]`, not `[ʰ]`).
* **Diphthongs/Triphthongs**
  Treated as **single nuclei** (atomic).
  Searching for `a` **does not** match `aɪ` / `aʊ`.
* **Affricates**
  **Tie-bar forms** (`t͡ʃ`, `d͜ʒ`, etc.) are **single segments**.
  Without a tie-bar (`ts`, `dʒ`) they are **clusters** (two segments).

---

## Dataset Format (v1.1+)

The format is permissive and **backward compatible** with “one IPA per line.”

```
# English (RP)
[lang=en-GB; mode=narrow; profile=english; tag=RP]
kʰæt                     # cat
θɪŋk [dental]           # think - dental fricative
t͡ʃɪp                    # chip

# English (GA)
[lang=en-US; mode=broad; profile=english; tag=GA]
spɹɪŋ [GA]              # spring - General American
kæt                      # cat (broad transcription)

# Spanish (MX)
[lang=es-MX; mode=broad; profile=spanish]
t͡ʃiko                   # chico
mweɣo [dialect]         # fuego (diphthong nucleus)
```

### Migration Guide

* **Existing users**: Your current `data/dataset.txt` works unchanged.
* **Immediate benefits**: Add `#` comments today without affecting analysis.
* **Advanced**: Add headers like `[lang=…; mode=…; profile=…; tag=…]` to annotate sections.

### Format Specification

**File structure rules**

1. Lines beginning with `[...]` are **section headers** (stateful until next header).
2. Everything after a `#` is a **comment** (ignored by analysis).
3. Inline `[tag]` tokens are **metadata** (parsed, ignored by analysis).
4. Blank lines and whitespace are ignored.
5. One IPA transcription per line (post comment/tag stripping).

**Valid section keys**

* `lang`: Language/locale (e.g., `en`, `en-US`, `es-MX`)
* `mode`: `narrow` or `broad`
* `profile`: Arbitrary analyzer profile name
* `tag`: Optional label for organization

**Parsing behavior**

* Invalid headers revert to plain lines
* Malformed tags don’t break parsing
* Extra whitespace tolerated everywhere
* Unicode normalization preserves data integrity

### Example Enhanced Dataset

```
# Multi-language phonetic dataset
# Demonstrates section headers, comments, and tags

[lang=en-GB; mode=narrow; profile=rp; tag=received_pronunciation]
kʰæt [basic]                    # cat - basic vocabulary
θɪŋk [fricative] [dental]      # think - dental fricative
t͡ʃɪp                          # chip - affricate

[lang=en-US; mode=broad; profile=ga]
kæt [basic]                     # cat - General American (broad)
θɪŋk                           # think - simplified transcription

# Spanish Mexican variety
[lang=es-MX; mode=broad; profile=mexican]
gato [cognate]                  # cat - Spanish cognate
t͡ʃiko [native]                 # chico - native vocabulary

# Loan words section
[tag=loanwords]
kʰaɾe [loan] [japanese]        # karate - from Japanese
```

---

## Example Output

```
──────────────────────── Phonetic environments for 'ɪ' ─────────────────────────

 Group               Left    Target     Right       Count   Examples
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 INITIAL                #      [ɪ]      n               1   [ɪ]nɪʃəl

 FINAL                  f      [ɪ]      #               1   kʰɔːf[ɪ]

 MEDIAL C_C             ɹ      [ɪ]      ŋ               2   stɹ[ɪ]ŋ, spɹ[ɪ]ŋ
                        θ      [ɪ]      ŋ               2   θ[ɪ]ŋk, sʌmθ[ɪ]ŋ
                       tʰ      [ɪ]      p               1   tʰ[ɪ]p
```

---

## Project Structure

```
phonenv/
├── analysis.py               # Core phonetic analysis & IPA processing
├── cli.py                    # Interactive CLI with character selection & batch
├── data.py                   # Dataset parsing, target validation, batch helpers
├── phonenv_io.py             # Output formatting, caching, file I/O
├── validate.py               # Unicode/IPA validation helpers
├── setup.py                  # Packaging
└── data/
    ├── dataset.txt           # Example IPA word list with metadata
    ├── targets.txt           # Comprehensive target list (incl. affricates)
    └── output/               # Generated analysis reports
```

---

## Dependencies

**Required**

* `regex` (≥ 2021.0)

**Optional**

* `panphon` (≥ 0.20) — feature vectors and helpers
* `rich` (≥ 10.0) — improved terminal rendering

**Development**

* `pytest` (≥ 6.0)
* `black` (≥ 21.0)
* `flake8` (≥ 3.9)
* `mypy` (≥ 0.910)

---

## Technical Details

### Performance

* Memory-efficient; supports multiple concurrent analyses.
* Optimized Unicode processing; **SHA256-based caching** keyed by dataset + configuration.
* Streamed parsing of datasets; minimal memory footprint.
* Segmentation-based validation avoids processing invalid targets.

### Output Formats

* **TXT, CSV, JSON, JSONL** writers
* Canonical deduplication (NFC) prevents “look-alike” duplicates
* Target highlighting with brackets: `[ɪ]`
* Correct singular/plural grammar in counts

### Validation & Error Handling

* **Segmentation-based** target validation (rejects malformed tokens)
* Graceful handling of missing files and malformed input
* Unicode normalization throughout, with tie-bar unification
* Helpful, concise error messages

### Testing

* Designed for comprehensive test coverage
* Validates **narrow** and **broad** modes
* Affricate processing and end-to-end pipeline tests

---

## Contributing

Contributions are welcome! Please ensure:

* All tests pass
* Code follows project style (Black, Flake8, type hints)
* Open an issue to discuss major changes prior to PRs

---

## License

**MIT License** — see `LICENSE` for details.

---

### Unicode Block Validation (Reference)

Validated against:

* IPA Extensions (U+0250–02AF)
* Spacing Modifier Letters (U+02B0–02FF)
* Combining Diacritical Marks (U+0300–036F)
* Phonetic Extensions (U+1D00–1D7F)
* Phonetic Extensions Supplement (U+1D80–1DBF)
* Modifier Tone Letters (U+A700–A71F)

---

### Implementation Notes for Developers

**Test invariants to keep in mind**

* Normalization: `segment("ã")` equals `segment("a\u0303")`
* Affricates: `len(segment("t͡ʃ")) == 1`; `len(segment("tʃ")) == 2`
* Length: `iː` (narrow) ≠ `i`; in broad mode they compare equal
* Stress removal (`ˈ` `ˌ`) must not change C/V neighbor selection

**Vowel vs. consonant classification**

* **Vowels** include canonical vowel bases and **syllabic consonants (`̩`)**, which count as **V** for context.
* **Consonants** include pulmonic/non-pulmonic consonants and approximants (`j, ɹ, ɻ, ɰ, ʋ`) unless syllabic.

**Affricates**

* **Tie-bar required** to be atomic: `t͡ʃ`, `d͡ʒ`, etc.
  Without tie-bar (`dʒ`, `ts`) → treat as clusters.

**Diphthongs/Triphthongs**

* Treated as **single vocalic nuclei**; searching `a` does **not** match `aɪ`/`aʊ`.