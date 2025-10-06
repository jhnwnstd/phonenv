# Phonenv

A Python library and CLI for phonetic environment analysis. Phonenv analyzes IPA transcriptions to identify where target segments occur—word-initially, word-finally, or in various medial contexts—using Unicode-correct IPA processing.

---

## Features

* **Environment Classification**: Analyzes INITIAL (`# _ X`), FINAL (`X _ #`), and MEDIAL contexts with sub-classification by neighbor types (`V_V`, `V_C`, `C_V`, `C_C`)
* **Transcription Modes**: Narrow (phonetic) mode treats diacritics as contrastive; broad (phonemic) mode folds them for pattern analysis
* **Automatic Normalization**: Applies unambiguous mappings (e.g., ASCII `g`→`ɡ`, `:`→`ː`) during analysis
* **Data Validation**: Detects 36+ character confusables (ASCII/IPA, Greek, Cyrillic homoglyphs) with interactive auto-fix
* **Unicode-Correct Processing**: Performs NFC/NFD normalization, tie-bar unification, and proper handling of combining marks
* **Intelligent Segmentation**: Treats affricates with tie-bars (`t͡ʃ`) and diphthongs as atomic units
* **Multiple Output Formats**: Writes TXT, CSV, JSON, and JSONL with canonical deduplication
* **Efficient Caching**: Uses SHA256-based result caching with configurable size limits (10,000 entries / 100MB)
* **Interactive CLI**: Lets you browse phonemes by place/manner, apply diacritics, and manage datasets
* **Batch Processing**: Processes multiple targets from files with comprehensive validation
* **Alternation Analysis**: Analyzes phonological alternations between segment pairs to determine distributional relationships (complementary, contrastive, free variation, neutralization, etc.)
* **Security Features**: Enforces path validation to restrict file access to the project directory; applies cache size limits to prevent resource exhaustion

---

## Installation

```bash
# Core dependency
pip install regex

# Optional enhancements
pip install panphon     # IPA feature analysis
pip install rich        # Enhanced terminal output

# Install Phonenv
pip install -e .
```

---

## Quick Start

### Interactive Mode

```bash
python3 main.py
# or if installed as a console script:
phonenv
```

Use the menus to select consonants/vowels by place and manner, apply diacritics, toggle transcription modes, and analyze environments.

### Batch Processing

```bash
# Process targets from file
phonenv --batch --format txt

# Custom paths and formats
phonenv --targets my_targets.txt --dataset my_data.txt --format json

# Utility commands
phonenv --cache-stats      # View cache statistics
phonenv --clear-cache      # Clear cached results
phonenv --create-targets   # Generate sample targets file
```

### Python API

```python
from analyze import PhoneticAnalyzer
from data import TargetsProcessor, AlternationPair
from phonenv_io import AutoOutputWriter
from normalize import UNAMBIGUOUS_MAPPINGS, CONFUSABLE_HINTS

# Analyze a single phoneme
analyzer = PhoneticAnalyzer(
    use_ipa_processing=True,
    transcription_mode='narrow'  # or 'broad'
)
results = analyzer.analyze_character('ɪ', 'data/dataset.txt')
analyzer.print_analysis('ɪ', 'data/dataset.txt')

# Batch processing
processor = TargetsProcessor('data/dataset.txt', 'data/targets.txt')
results = processor.process_targets_to_list()

# Alternation analysis
targets, alternations = processor.load_targets()
pair = AlternationPair('p', 'b', 'voicing alternation')
result = processor.analyze_alternation(pair)
print(f"Pattern: {result.pattern}")
print(f"Analysis: {result.analysis}")

# Export to multiple formats
writer = AutoOutputWriter('data/output')
writer.write_batch_results(results, format_preference='csv')

# Validation
from validate import validate
exit_code = validate('data/dataset.txt', 'data/targets.txt', interactive_autofix=True)
```

---

## How It Works

### Automatic Normalization

Phonenv automatically normalizes input to ensure consistency, operating only on the transcription field (not on `#` comments or bracketed `[tags]`):

**Unambiguous Transformations** (applied automatically):

* ASCII `g` (U+0067) → IPA `ɡ` (U+0261, script g)
* ASCII `:` (U+003A) → IPA `ː` (U+02D0, triangular colon / length mark)
* Colon variants (modifier, ratio, fullwidth) → IPA length mark
* Tie-bar canonicalization (normalizes U+035C/0361 to a consistent form)
* Fullwidth characters → standard IPA equivalents

**Unicode Normalization**:

* **Storage/Output**: NFC (composed form)
* **Analysis**: NFD (decomposed form) for explicit diacritic handling
* **Canonical equivalence**: `ã` and `a + ̃` behave identically

### Data Validation

Phonenv validates transcriptions before analysis. Validation runs only on IPA transcriptions (not on `#` glosses or bracketed `[tags]`).

**Usage**:

```bash
# Validate dataset and targets
python3 -m validate

# Use in Python
from validate import validate
exit_code = validate('data/dataset.txt', 'data/targets.txt')
```

**Three-Tier Detection System**:

1. **Unambiguous Mappings** (applied during analysis):

   * ASCII `g`→`ɡ`, ASCII `:`→`ː`
   * Colon variants, tie-bars, fullwidth characters
2. **Confusable Hints** (warns with suggestions):

   * **Greek homoglyphs**: φ→ɸ, γ→ɣ, α→ɑ, λ→ʎ, ρ→p, ν→v, χ→x
   * **Cyrillic homoglyphs**: а→a, е→e, о→o, р→p, с→c, у→y, х→x, і→i, ј→j, к→k, т→t
   * **ASCII capitals**: N→ɴ, R→ʀ, G→ɢ, L→ʟ, Y→ʏ
   * **Punctuation-as-IPA**: '→ˈ, ,→ˌ, ?→ʔ, ;→ˑ
3. **Orthography Detection** (heuristics):

   * ng→ŋ, th→θ/ð, sh→ʃ, ch→t͡ʃ/ç, zh→ʒ
   * Invisible characters (zero-width spaces, BOM, soft hyphens)
   * Morpheme boundary hyphens

**Interactive Auto-fix**:
The validator shows diffs and applies safe fixes with your confirmation, creating `.bak` backups.

### Segmentation Model

Each segment functions as an atomic unit consisting of:

* **Base**: Single codepoint (e.g., `t`, `a`, `ɪ`, `ʃ`)
* **Diacritics**: Combining marks and spacing modifiers attached to the base
* **Length markers**: `ˑ` (half-long), `ː` (long)
* **Suprasegmentals**: Stress (`ˈ`, `ˌ`), boundaries, tone (tracked separately)

**Atomic units**:

* Affricates with tie-bars: `t͡ʃ`, `d͡ʒ`
* Diphthongs/triphthongs: `aɪ`, `aʊ`

**Clusters without tie-bars**:

* `tʃ` (two segments: `t` + `ʃ`)
* `dʒ` (two segments: `d` + `ʒ`)

### Transcription Modes

**Default: Narrow mode** (use `--mode broad` or toggle in CLI to change)

**Narrow (Phonetic)** — Default

* Diacritics and length are contrastive
* `p ≠ pʰ ≠ p̚`
* `a ≠ ã ≠ aː`
* Use for phonetic detail and allophonic analysis

**Broad (Phonemic)**

* Diacritics and length fold
* `p = pʰ = p̚`
* `a = ã = aː`
* Use for phonological patterns and general distribution

### Environment Classification

**INITIAL**: `# _ X`
The first segment after a word boundary (ignores suprasegmentals)

**FINAL**: `X _ #`
The last segment before a word boundary

**MEDIAL**: Classified by neighbor types

* `V_V`: Intervocalic (between vowels)
* `V_C`: Pre-consonantal (vowel followed by consonant)
* `C_V`: Post-consonantal (consonant followed by vowel)
* `C_C`: Cluster (between consonants)

**Context rules**:

* Ignores suprasegmentals (`ˈ`, `ˌ`, `|`, `‖`) when selecting neighbors
* Treats syllabic consonants (`n̩`, `l̩`) as vowels for classification

---

## Alternation Analysis

Phonenv supports **phonological alternation analysis** to determine distributional relationships between segment pairs (e.g., `p ~ b`, `s ~ z`).

### Quick Start

Add alternation pairs to `targets.txt` using the tilde (`~`) separator:

```
# Regular single-segment analysis
s
z

# Alternation analysis (segments separated by ~)
s ~ z  # voicing alternation
θ ~ ð  # dental fricative voicing
p ~ b  # stop voicing

# You can mix both formats in the same file!
```

Run analysis as usual:

```bash
phonenv --batch --format txt
```

### Distribution Patterns

Phonenv automatically detects **six distribution patterns**:

#### 1. Complementary Distribution (Allophones)
**Linguistic Meaning**: Sounds are **allophones** of the same phoneme
**Detection**: Segments **never** share contexts
**Example**: ʊ ~ uː in English (complementary by position)

#### 2. Contrastive (Distinct Phonemes)
**Linguistic Meaning**: Sounds are **separate phonemes**
**Detection**: Appear in shared contexts (creates minimal pairs)
**Example**: s ~ z, p ~ b (*seal* vs *zeal*)

#### 3. Free Variation (Interchangeable)
**Linguistic Meaning**: **Interchangeable allophones**
**Detection**: Appear in **identical** contexts
**Example**: English final /t/ → [t] or [ʔ] in *cat*

#### 4. Neutralization (Context-Dependent Merger)
**Linguistic Meaning**: **Contrast lost** in specific positions
**Detection**: Asymmetric distribution (one broad, one restricted)
**Example**: German /t/ ~ /d/ (final devoicing)

#### 5. Partial Overlap (Gradience/Variation)
**Linguistic Meaning**: **Transitional** or **dialectal variation**
**Detection**: Substantial overlap (>40%) + unique contexts
**Example**: /r/ realizations across dialects

#### 6. Unknown
Insufficient data or segments not found in dataset.

### Detection Algorithm

**Analysis metrics**:
- **Shared contexts**: Where both segments appear
- **Exclusive contexts**: Unique to each segment
- **Overlap ratio**: `shared_contexts / total_contexts`
- **Distribution asymmetry**: Restricted vs. broad

**Decision rules**:
```
if no_shared_contexts:
    → COMPLEMENTARY

elif all_contexts_identical:
    → FREE_VARIATION

elif one_segment <30% coverage AND other >70%:
    → NEUTRALIZATION

elif overlap_ratio > 40%:
    → PARTIAL_OVERLAP

else:
    → CONTRASTIVE
```

### Output Format

Alternation results appear in the report with pattern classification:

```
ALTERNATION 3: 's ~ z'
----------------------------------------
Pattern: CONTRASTIVE (distinct phonemes)
s: 53 occurrences | z: 15 occurrences
Analysis: s and z are contrastive (distinct phonemes). They contrast in 1 shared contexts, with 26 contexts exclusive to s and 11 exclusive to z

  s appears in:
    INITIAL:
      # _ k ×10 : [s]kaɪ, [s]kuːl...

  z appears in:
    FINAL:
      ɡ _ # ×3 : bæɡ[z], dɔɡ[z]...
```

### Use Cases

**Phonological Analysis**:
```
# Voicing alternations
p ~ b
t ~ d
s ~ z

# Place assimilation
n ~ m
n ~ ŋ
```

**Historical Linguistics**:
```
# Sound changes
θ ~ t  # theta > t merger
x ~ h  # velar > glottal fricative
```

**Language Learning**:
```
# Difficult contrasts
l ~ r
b ~ v
θ ~ s
```

---

## Dataset Format

The enhanced format supports metadata while maintaining backward compatibility. Normalization and validation run only on the transcription; they ignore `#` comments and bracketed `[tags]`.

### Simple Format

```
kʰæt
θɪŋk
t͡ʃɪp
```

### Enhanced Format (v1.1+)

```
# English RP
[lang=en-GB; mode=narrow; profile=english]
kʰæt                     # cat
θɪŋk [dental]           # think
t͡ʃɪp                    # chip

# Spanish
[lang=es-MX; mode=broad]
gato [cognate]          # cat
t͡ʃiko                   # chico
```

**Format features**:

* `#` comments (ignored by analysis/validation)
* `[key=value; ...]` section headers (metadata)
* `[tag]` inline tags (metadata)
* One IPA transcription per line
* Blank lines and whitespace ignored

---

## Output Formats

### TXT (Human-Readable)

```
PHONETIC ENVIRONMENT ANALYSIS REPORT
============================================================
TARGET 1: 'p'
----------------------------------------
Total occurrences: 6

  INITIAL:
    # _ a (1 occurrence): [p]aɴɢɔɔ

  MEDIAL V_C:
    u _ t͡ʃ (2 occurrences): ku[p]t͡ʃɨ, ku[p]t͡ʃaa
```

### CSV (Spreadsheet)

```csv
target,group,environment,left_context,right_context,count,examples
p,INITIAL,#__a,#,a,1,[p]aɴɢɔɔ
p,MEDIAL V_C,u__t͡ʃ,u,t͡ʃ,2,ku[p]t͡ʃɨ; ku[p]t͡ʃaa
```

### JSON (Structured)

```json
{
  "metadata": {
    "format": "phonenv-json",
    "version": "1.0",
    "timestamp": "2025-10-01T11:23:35"
  },
  "results": [
    {
      "target": "p",
      "environments": {...},
      "total_occurrences": 6
    }
  ]
}
```

### JSONL (Streaming)

```jsonl
{"_metadata": {"format": "phonenv-jsonl", "version": "1.0"}}
{"target": "p", "environments": {...}, "total_occurrences": 6}
{"target": "t", "environments": {...}, "total_occurrences": 6}
```

---

## Caching System

Phonenv caches results with SHA256 fingerprints based on:

* Dataset content (file hash)
* Target phoneme
* Analysis configuration (mode, IPA processing settings)

**Cache limits** (configurable):

* Maximum entries: 10,000
* Maximum size: 100 MB
* Eviction: LRU (Least Recently Used)

**Cache commands**:

```bash
phonenv --cache-stats
phonenv --clear-cache
```

**Python API**:

```python
from phonenv_io import ResultCache

cache = ResultCache(
    cache_dir='data/.cache',
    max_entries=5000,
    max_size_mb=50
)
```

---

## Security

### Path Validation

Phonenv validates all user-provided file paths to ensure they reside within the project directory.

**Allowed**:

* `data/dataset.txt` ✓
* `./data/output/results.txt` ✓

**Blocked**:

* `../etc/passwd` ✗
* `/absolute/path` ✗
* Symlinks pointing outside the project ✗

### Cache Size Limits

LRU eviction prevents unbounded memory growth when the cache reaches configured limits.

---

## Project Structure

```
phonenv/
├── analyze.py          # Core analysis engine & IPA processing
├── normalize.py        # Character normalization mappings (ASCII→IPA, confusables)
├── validate.py         # Input validation & auto-fix with interactive mode
├── main.py             # Interactive CLI & batch processing entry point
├── data.py             # Dataset parsing & target validation
├── phonenv_io.py       # Output formatting & caching (TXT/CSV/JSON/JSONL)
├── utils.py            # Unicode utilities & path validation
├── setup.py            # Package configuration
└── data/
    ├── dataset.txt     # Example IPA word list (English RP)
    ├── targets.txt     # Target phonemes for batch analysis
    ├── output/         # Generated reports (auto-created)
    └── .cache/         # Cached analysis results (auto-created)
```

---

## Dependencies

**Required**:

* `regex` (≥ 2021.0) — Unicode-aware pattern matching

**Optional**:

* `panphon` (≥ 0.20) — IPA feature analysis
* `rich` (≥ 10.0) — Enhanced terminal output

**Development**:

* `pytest` (≥ 6.0)
* `black` (≥ 21.0)
* `flake8` (≥ 3.9)
* `mypy` (≥ 1.0)

---

## Example Use Cases

### Linguistic Research

```python
# Analyze intervocalic lenition in Lhasa Tibetan
analyzer = PhoneticAnalyzer(use_ipa_processing=True, transcription_mode='broad')
for target in ['p', 'β', 'k', 'ɣ']:
    analyzer.print_analysis(target, 'data/dataset.txt')
```

### Phonological Pattern Discovery

```bash
# Find all environments for uvular consonants
echo -e "q\nɢ\nʁ\nɴ" > uvulars.txt
phonenv --targets uvulars.txt --format csv
```

### Dataset Validation

```bash
# Validate IPA transcriptions
python3 -m validate
```

---

## Contributing

Contributions are welcome. Please ensure:

* Code passes `flake8` and `black -l79 .` checks
* All tests pass
* New features include tests
* Major changes start with an issue for discussion

---

## Contributors

**Original Author**: [shameedjob](https://github.com/shameedjob) — authors Phonenv and maintains the core architecture

**Major Enhancements**: [jhnwnstd](https://github.com/jhnwnstd) — maintains normalization, comprehensive validation (36+ character mappings), security features, caching improvements, and documentation

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Support

* **Issues**: [github.com/shameedjob/phonenv/issues](https://github.com/shameedjob/phonenv/issues)
* **Documentation**: See markdown files in the project root
* **Examples**: See the `data/` directory for sample datasets

---

## Technical Notes

### Unicode Block Coverage

* IPA Extensions (U+0250–02AF)
* Spacing Modifier Letters (U+02B0–02FF)
* Combining Diacritical Marks (U+0300–036F)
* Phonetic Extensions (U+1D00–1D7F, U+1D80–1DBF)
* Modifier Tone Letters (U+A700–A71F)

### Segmentation Invariants

* Normalization: `segment("ã") == segment("a\u0303")`
* Affricates: `len(segments("t͡ʃ")) == 1`
* Clusters: `len(segments("tʃ")) == 2`
* Broad mode: `segment("iː") == segment("i")`
* Narrow mode: `segment("iː") != segment("i")`

### Vowel/Consonant Classification

* **Vowels**: Canonical vowel bases + syllabic consonants (`n̩`, `l̩`)
* **Consonants**: All other segments unless marked syllabic
* **Approximants**: `j`, `w`, `ɹ`, `ɻ`, `ɰ`, `ʋ` count as consonants (unless syllabic)
