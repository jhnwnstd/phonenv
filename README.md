# Phonenv

A robust Python library for **phonetic environment analysis**. It examines where specific IPA symbols occur in word lists and summarizes their **INITIAL, FINAL, and MEDIAL** contexts (V_V, V_C, C_V, C_C). Phonenv is **language-agnostic** and focuses on **Unicode-correct IPA text processing** with comprehensive validation and multiple output formats.

## Features

* **Environment Analysis** — INITIAL / FINAL / MEDIAL (V_V, V_C, C_V, C_C) classification
* **Robust Target Validation** — Segmentation-based validation ensures only valid IPA segments are analyzed
* **Dataset Format** — Language-aware section headers, inline `#` comments, and `[tags]` (parsed, ignored by analysis); fully backwards compatible with simple "one IPA per line"
* **Interactive CLI** — Browse IPA categories and analyze targets from the terminal
* **Transcription Modes** — **Narrow** (phonetic: diacritics contrastive) and **Broad** (phonemic: diacritics folded)
* **IPA Processing** — Unicode-compliant NFC/NFD normalization, tie-bar normalization, robust segmentation
* **Atomic Units** — Diphthongs/triphthongs and **tie-bar affricates** treated as single segments
* **Multiple Output Formats** — TXT, CSV, JSON, JSONL with proper deduplication and formatting
* **Efficient Caching** — SHA256-based result caching with configuration awareness
* **Comprehensive Testing** — 100% test coverage with validation for both transcription modes

## Installation

```bash
# Core dependency
pip install regex

# Optional enhancements
pip install panphon         # feature vectors & helpers (optional)
pip install rich            # prettier terminal output (optional)

# Install Phonenv (editable for development)
pip install -e .
```

## Quick Start

### Interactive Mode

Launch the interactive CLI to select targets and run analyses:

```bash
python3 cli.py
```

Or use the console script after installation:

```bash
phonenv
```

**Interactive Features:**
- Guided IPA character selection through consonant/vowel categories
- Diacritic panel for building complex segments
- Transcription mode selection (narrow/broad)
- Integrated dictionary management
- Real-time validation of target segments

### Batch Processing

Process multiple targets from a file:

```bash
python3 -c "
from data import TargetsProcessor
from phonenv_io import AutoOutputWriter

processor = TargetsProcessor('data/dataset.txt', 'data/targets.txt')
results = list(processor.process_targets())

writer = AutoOutputWriter('data/output')
writer.write_batch_results(results, 'txt')
"
```

## Interactive Features

### Character Selection
- Browse consonants by place/manner of articulation
- Browse vowels by height/backness/rounding
- Select from common diphthongs and triphthongs
- Build complex segments with diacritic panel

### Analysis Options
- Choose narrow (phonetic) or broad (phonemic) transcription mode
- Analyze selected character across all environment types
- View results in organized tables with examples

### Dictionary Management

Access via 'd' during analysis:

- **View Dictionary**: Display all words in current dataset
- **Add Words**: Add new IPA transcriptions to dataset
- **Remove Words**: Delete words containing specific substrings
- **Statistics**: View word count, length statistics, character usage
- **Clear Dataset**: Remove all words (with confirmation)

## Python API

```python
from analysis import PhoneticAnalyzer, IPAProcessorV2, get_config_for_transcription_mode
from data import TargetsProcessor, DictionaryProcessor, load_words_list, iter_word_entries, WordEntry
from phonenv_io import AutoOutputWriter

# Basic phonetic environment analysis
analyzer = PhoneticAnalyzer(use_ipa_processing=True)
results = analyzer.analyze_character('ɪ', 'data/dataset.txt')

# Transcription mode configuration
config = get_config_for_transcription_mode('narrow')  # or 'broad'
analyzer = PhoneticAnalyzer(use_ipa_processing=True)
analyzer.ipa_processor_v2 = IPAProcessorV2(config)
analyzer.transcription_mode = 'narrow'
results = analyzer.analyze_character('ɪ', 'data/dataset.txt')

# Batch processing with validation
processor = TargetsProcessor('data/dataset.txt', 'data/targets.txt')
targets = processor.load_targets()  # Segmentation-based validation
for target in targets[:5]:  # Process first 5 targets
    result = processor.analyze_target(target)
    print(f"{target}: {result.total_occurrences} occurrences")

# Enhanced dataset parsing with metadata
for entry in iter_word_entries('data/dataset.txt'):
    print(f"IPA: {entry.ipa}")
    print(f"Language: {entry.section.get('lang', 'unknown')}")
    print(f"Mode: {entry.section.get('mode', 'narrow')}")
    print(f"Tags: {entry.tags}")

# Multiple output formats
writer = AutoOutputWriter('data/output')
results = [result]  # Your analysis results
paths = writer.write_batch_results(results, 'csv')  # or 'txt', 'json', 'jsonl'

# Direct IPA text processing
processor = IPAProcessorV2()
normalized_text = processor.normalize_nfc('tʰãsə')
segments = processor.ipa_segments(normalized_text)
```

## Transcription Modes

### Narrow (phonetic; default in interactive UI)

* **Diacritics contrastive**: `[p] ≠ [pʰ]`, `[a] ≠ [ã]`, `[i] ≠ [iː]`
* Exact segment equality (base + diacritics + length)

### Broad (phonemic)

* **Diacritics not contrastive**: `[p] = [pʰ]`, `[a] = [ã]`, `[i] = [iː]`
* Collapses to base symbol (language-agnostic folding)

## Special Handling Rules

### Diacritics

* Never standalone; always attach to a base (e.g., `[pʰ]`, not `[ʰ]`)

### Diphthongs & Triphthongs

* Treated as **single nuclei** (atomic)
* Searching for `[a]` **does not** match `[aɪ]`/`[aʊ]`

### Affricates

* **Tie-bar** forms (e.g., `t͡ʃ`, `d͜ʒ`) are **single segments**
* Without a tie-bar (e.g., `dʒ`) → treated as **cluster**

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

## Input Format (v1.1+)

The format uses optional language-aware sections, comments, and inline tags:

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

**Format Features:**

- **Section Headers**: `[lang=…; mode=…; profile=…]` set language, transcription mode, and analysis profile
- **Comments**: Everything after `#` is ignored - perfect for glosses and notes
- **Inline Tags**: `[tag]` tokens are parsed but ignored by analysis (useful for metadata)
- **Flexible Spacing**: Headers and tags tolerate extra whitespace
- **Backwards Compatible**: Simple format files work without modification

**Section Parameters:**

- `lang`: Language code (e.g., `en`, `en-GB`, `es-MX`)
- `mode`: `narrow` (phonetic) or `broad` (phonemic)
- `profile`: Analysis profile name (e.g., `english`, `spanish`, `custom`)
- `tag`: Optional section label for organization

The default dataset (`data/dataset.txt`) contains 100 phonetically transcribed English words using the simple format.

## Project Structure

```
phonenv/
├── analysis.py               # Core phonetic analysis and IPA processing
├── cli.py                    # Interactive CLI with character selection
├── data.py                   # Dataset parsing, target validation, and batch processing
├── phonenv_io.py             # Output formatting, caching, and file I/O
├── validate.py               # Unicode validation and IPA compliance
├── setup.py                  # Package configuration and dependencies
└── data/
    ├── dataset.txt           # Enhanced IPA word list with metadata
    ├── targets.txt           # Comprehensive target list with affricates
    └── output/               # Generated analysis reports
```

## Environment Categories

**INITIAL**: Word-initial position (#_X)

* Example: `[ɪ]`nɪʃəl for target 'ɪ'

**FINAL**: Word-final position (X_#)

* Example: kʰɔːf`[ɪ]` for target 'ɪ'

**MEDIAL**: Word-medial positions, classified by phonetic context:

* **V_V**: Between vowels (vowel-vowel environment)
* **V_C**: After vowel, before consonant
* **C_V**: After consonant, before vowel
* **C_C**: Between consonants (consonant cluster environment)

## Dataset Format (v1.1)

### Migration Guide

**Existing users**: Your current `data/dataset.txt` files work without any changes. The format is fully backwards compatible.

**Immediate benefits**: Start adding comments to your existing files today:

```
kʰæt    # cat - aspirated voiceless stop
tʰɪp    # tip - aspirated
```

**Advanced usage**: Add language sections for multi-language datasets:

```
[lang=en; mode=narrow]
kʰæt    # English: cat
tʰɪp    # English: tip

[lang=es; mode=broad]
gato    # Spanish: cat
```

### Format Specification

**File Structure:**
1. Lines starting with `[...]` are section headers
2. Everything after `#` is a comment (ignored by analysis)
3. `[tag]` tokens within lines are metadata tags (parsed but ignored by analysis)
4. Blank lines and whitespace are ignored
5. One IPA transcription per line (after processing comments/tags)

**Section Headers:**
- Update settings for all following entries
- Format: `[key=value; key2=value2]`
- Settings persist until the next header
- Comments allowed: `[lang=en] # English section`

**Valid Section Keys:**
- `lang`: Language/locale code (ISO 639, e.g., `en`, `en-US`, `es-MX`)
- `mode`: `narrow` (phonetic) or `broad` (phonemic)
- `profile`: Custom analysis profile name
- `tag`: Section label for organization

**Example Enhanced Dataset:**

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

### Parsing Behavior

**Robust Processing:**
- Invalid section headers are treated as regular lines
- Malformed tags don't break parsing
- Extra whitespace is tolerated everywhere
- Unicode normalization maintains data integrity

**Backwards Compatibility:**
- Files without headers use default settings: `lang=und; mode=narrow; profile=default`
- All existing CLI commands work unchanged
- Legacy API functions (`load_words_list`, `load_words_set`) return plain IPA strings

## IPA Processing Features

### Unicode Normalization

* **NFC (Normalized Form Composed)**: Used for storage and display
* **NFD (Normalized Form Decomposed)**: Used internally for diacritic analysis
* Correctly handles canonical equivalence (ã vs a + combining tilde)

### Advanced Segmentation

* **Atomic diphthongs/triphthongs**: grouped as single nuclei
* **Affricates with tie bars** recognized as atomic; untied stop+fricatives remain separate
* **Feature-based classification**: panphon provides articulatory feature vectors
* **Diacritic preservation**: combining marks and spacing modifiers stay bound to bases

### Unicode Block Validation

Validates against official IPA Unicode ranges:

* IPA Extensions (U+0250–02AF)
* Spacing Modifier Letters (U+02B0–02FF)
* Combining Diacritical Marks (U+0300–036F)
* Phonetic Extensions (U+1D00–1D7F)
* Phonetic Extensions Supplement (U+1D80–1DBF)
* Modifier Tone Letters (U+A700–A71F)

## Dependencies

**Required**:

* `regex` (≥2021.0) - Unicode-aware regex and grapheme clustering

**Optional**:

* `panphon` (≥0.20) - IPA segmentation and phonetic feature analysis
* `rich` (≥10.0) - Terminal output formatting

**Development**:

* `pytest` (≥6.0) - Testing framework
* `black` (≥21.0) - Code formatting
* `flake8` (≥3.9) - Linting
* `mypy` (≥0.910) - Type checking

## Installation Options

```bash
# Minimal installation (regex only)
pip install .

# With enhanced IPA processing
pip install .[enhanced]

# Full development setup
pip install .[enhanced,dev]
```

## Technical Details

### Performance

* Memory-efficient with support for multiple concurrent analyses
* Optimized Unicode text processing with SHA256-based caching
* Stream-based parsing for dataset format (minimal memory footprint)
* Segmentation-based validation eliminates invalid target processing

### Output Format

* Multiple formats: TXT (human-readable), CSV (data analysis), JSON/JSONL (programmatic)
* Proper deduplication with Unicode canonical equivalence handling
* Bracketed highlighting of targets: `[ɪ]`
* Correct singular/plural grammar in occurrence counts

### Validation and Error Handling

* Segmentation-based target validation ensures only valid IPA segments
* Graceful handling of missing files and malformed input
* Comprehensive Unicode validation with helpful error messages
* Robust tie-bar normalization (above/below variants)

### Testing

* 100% test coverage with comprehensive validation
* Both narrow and broad transcription mode testing
* Affricate processing validation
* End-to-end pipeline testing

## Known Issues

* Interactive menu navigation requires terminal keyboard input (not suitable for piped input)
* Unicode info display may show "N/A" depending on system Unicode data availability

## Recent Improvements

### Version 2.0 Features

* **Segmentation-based validation**: Replaced regex-based validation with robust IPA segmentation
* **Enhanced affricate support**: Complete support for tie-bar affricates (t͡ʃ, d͡ʒ, etc.)
* **Improved output formatting**: No truncation, proper deduplication, correct grammar
* **Transcription mode support**: Full narrow/broad mode implementation with diacritic folding
* **Comprehensive testing**: 100% test coverage with extensive validation
* **Performance optimization**: SHA256-based caching with configuration awareness

## IPA Segmentation and Character Handling

This section provides implementation guidance for how Phonenv treats IPA characters and diacritics in analysis, aligned with standard phonetic practice.

### Normalization & Text Hygiene

**Policy:**
* **Store/emit in NFC; analyze in NFD**
  * On input: normalize to **NFC** for file integrity, display, and reproducible storage
  * For segmentation/matching: convert to **NFD** so all combining diacritics are explicit and attachable to a base
* **Canonical equivalence must not change analysis** - e.g., `ã` ≡ `a + ̃` must segment to the same object

**Why:** NFC prevents "look-the-same but compare-different" bugs in files; NFD makes diacritic attachment explicit for the analyzer.

### Segment Model

Each segment is represented as an object with these components:

```python
Segment {
  base: codepoint          # e.g., t, a, ɪ, ʃ, ɚ …
  diacritics: list         # combining marks and spacing modifiers bound to base
  length: {none, half, long}  # ˑ, ː (also handle geminates)
  suprasegmentals: dict    # stress, tone_seq, boundary_flags stored separately
}
```

**Attach to the Base:**
* **Combining marks** from U+0300–036F: nasalization ̃, voiceless ̥, voiced ̬, advanced ̟, retracted ̠, raised ̝, lowered ̞, syllabicity ̩, etc.
* **Spacing modifier letters** (U+02B0–02FF): aspiration `ʰ`, breathy `ʱ`, labialization `ʷ`, palatalization `ʲ`, velarization `ˠ`, pharyngealization `ˤ`, nasal release `ⁿ`, lateral release `ˡ`, etc.
* **Length marks** `ː` long, `ˑ` half-long → store in `length`, not as separate segments

**Do Not Attach:**
* **Stress markers** `ˈ`, `ˌ` → suprasegmental, not part of the segment
* **Tone letters/diacritics** → suprasegmental; ignore for left/right segmental context
* **Word/foot boundaries**, pauses, intonation—ignore for C/V context

### Vowel vs. Consonant Classification

**Vowels include:**
* Vowel bases: i, e, a, ɑ, u, ʊ, ɪ, y, ʏ, ø, œ, ɘ, ɤ, ə, ɜ, ɞ, ɨ, ʉ, ɯ, …
* **Syllabic consonants** (diacritic **̩**): treat as **vocalic nuclei** for environment classification (e.g., `n̩` behaves as **V**)

**Consonants include:**
* Pulmonic/non-pulmonic consonant bases and their diacritics
* Approximants `j, ɹ, ɻ, ɰ, ʋ` are consonants unless syllabic `̩`

### Complex Segments (Atomic Units)

**Affricates with Tie-Bar Only:**
* `t͡ʃ`, `d͡ʒ`, `ts͡`, etc. (tie bars `͡` or `͜`) → **single segment**
* **Without tie-bar** (`dʒ`, `ts`) → treat as **clusters** (two segments)

**Diphthongs/Triphthongs:**
* Language/profile-driven lists (English: `{aɪ, aʊ, eɪ, oʊ, ɔɪ}`, Spanish: `{ai, ei, oi, au, eu, ia, ie, io, ua, ue, uo}`)
* Treat each as **one vocalic nucleus** for environment classification

### Narrow vs. Broad Matching

**Narrow Mode (Phonetic):**
* **Exact segment equality**: base + diacritics + length must match
* `p ≠ pʰ`, `a ≠ ã`, `i ≠ iː`

**Broad Mode (Phonemic):**
* **Collapse to base**: strip diacritics and map allophones to phoneme classes
* Example folds: `pʰ → p`, `ã → a`, `iː → i`, `ɚ → ə`, `t̪ → t`
* Language/profile-specific (e.g., don't fold aspiration in Hindi)

### Environment Classification

* **INITIAL** `# _ X`: first segment after stripping suprasegmentals
* **FINAL** `X _ #`: last segment
* **MEDIAL**: V_V, C_V, V_C, C_C based on neighbor classification

**Examples:**
* `ˈspɹɪŋ` → segments: `s p ɹ ɪ ŋ` (stress stripped)
* For target `ɪ`: left `ɹ` (C), right `ŋ` (C) ⇒ **C_C**
* `n̩` counts as **V** (syllabic) for environment classification

### Implementation Guidelines

**Tokenization Steps:**
1. **NFC in → NFD for analysis**
2. **Scan by base**: detect tie-bar affricates, diphthongs, or simple bases
3. **Consume trailing diacritics**: attach combining marks, spacing modifiers, length marks
4. **Record suprasegmentals** separately (stress, tone)
5. Build segment list

**Test Invariants:**
* Normalization: `segment("ã")` equals `segment("a\u0303")`
* Affricates: `len(segment("t͡ʃ")) == 1`; `len(segment("tʃ")) == 2`
* Length: `iː` narrow ≠ `i`; broad equal if non-contrastive
* Stress: removing `ˈ`/`ˌ` doesn't change segment neighbors for C/V logic

### Unicode Block Validation

Validates against official IPA Unicode ranges:
* IPA Extensions (U+0250–02AF)
* Spacing Modifier Letters (U+02B0–02FF)
* Combining Diacritical Marks (U+0300–036F)
* Phonetic Extensions (U+1D00–1D7F)
* Phonetic Extensions Supplement (U+1D80–1DBF)
* Modifier Tone Letters (U+A700–A71F)

## Contributing

Contributions are welcome. Please ensure all tests pass and follow the established code style. For major changes, open an issue first to discuss proposed modifications.

## License

MIT License - see LICENSE file for details.