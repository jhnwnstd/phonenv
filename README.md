# Phonenv

A Python library for phonetic environment analysis that examines the phonetic contexts where specific sounds occur in word lists. Provides professional-grade International Phonetic Alphabet (IPA) text processing with Unicode compliance and rich terminal output.

## Features

- **Phonetic Environment Analysis**: Categorizes contexts as INITIAL, FINAL, and MEDIAL (V_V, V_C, C_V, C_C) based on surrounding phonetic environments  
- **Interactive IPA Interface**: Navigate through organized consonant and vowel categories with intuitive command-line menus  
- **Transcription Mode Support**: Choose between narrow (phonetic) and broad (phonemic) analysis approaches  
- **Professional IPA Processing**: Unicode-compliant text processing with proper NFC/NFD normalization and segmentation  
- **Advanced Segmentation**: Treats diphthongs, triphthongs, and tie-bar affricates as atomic phonological units  
- **Rich Terminal Output**: Beautiful tables with Unicode box-drawing characters and highlighted target segments  
- **Comprehensive CLI**: Full command-line interface for analysis and dictionary management  

## Installation

Install the required dependency:

```bash
pip install regex
````

For enhanced IPA processing capabilities:

```bash
pip install panphon
```

Install the package:

```bash
pip install -e .
```

## Quick Start

### Interactive Mode

The interactive mode provides guided navigation through IPA character categories:

```bash
python3 phonenv_cl.py interactive
```

Or analyze a specific character with mode selection:

```bash
python3 phonenv_cl.py interactive 'ɪ' --mode narrow --file data/input.txt
```

**Note**: The fully interactive menu system (with character selection) is designed for terminal use with keyboard input.

### Direct Analysis Commands

For scripted or automated analysis:

```bash
# Basic environment analysis
python3 phonenv_cl.py analyze 'ɪ' --file data/input.txt

# Advanced IPA-aware analysis with Unicode information
python3 phonenv_cl.py ipa_analyze 'ɪ' --file data/input.txt --unicode-info
```

## Command Reference

### Interactive Analysis

* `interactive` - Launch interactive mode with transcription mode selection
* `interactive <character>` - Analyze specific character with interactive setup
* `interactive <character> --mode <narrow|broad>` - Set transcription mode directly
* `interactive <character> --file <path>` - Use custom word list

### Environment Analysis

* `analyze <character>` - Basic phonetic environment analysis
* `ipa_analyze <character>` - Advanced IPA-aware analysis with Unicode support
* `ipa_analyze <character> --unicode-info` - Include detailed Unicode character information

### Dictionary Management

* `dict --print` - Display current word list
* `dict --append <word>` - Add word to dictionary
* `dict --delete <substring>` - Remove words containing substring
* `dict --stats` - Show dictionary statistics (total words, unique letters, etc.)
* `dict --clear` - Clear entire dictionary

### Special Characters

* `add_special <character>` - Add custom phonetic character
* `add_special <character> --erase` - Remove special character

## Python API

```python
from environment_analyzer import PhoneticAnalyzer
from ipa_processor_v2 import IPAProcessorV2, get_config_for_transcription_mode

# Basic phonetic environment analysis
analyzer = PhoneticAnalyzer()
results = analyzer.analyze_character('ɪ', 'data/input.txt')

# Advanced IPA analysis with transcription modes
config = get_config_for_transcription_mode('narrow')  # or 'broad'
analyzer = PhoneticAnalyzer(use_ipa_processing=True)
analyzer.ipa_processor_v2 = IPAProcessorV2(config)
results = analyzer.analyze_character('ɪ', 'data/input.txt')

# Direct IPA text processing
processor = IPAProcessorV2()
normalized_text = processor.normalize_nfc('tʰãsə')
segments = processor.ipa_segments(normalized_text)
```

## Transcription Modes

### Narrow Transcription (Phonetic)

* **Default mode in interactive interface**
* **Diacritics are contrastive**: \[p] ≠ \[pʰ], \[a] ≠ \[ã], \[i] ≠ \[iː]
* Focuses on surface phonetic detail and allophonic variation
* Uses exact string matching for precise phonetic analysis
* Best for detailed phonetic environment studies

### Broad Transcription (Phonemic)

* **Diacritics are not contrastive**: \[p] = \[pʰ], \[a] = \[ã], \[i] = \[iː]
* Focuses on underlying phonological patterns rather than phonetic variation
* Uses base symbol equivalence for matching
* Best for phonological analysis and pattern discovery

## Special Handling Rules

### Diacritics

* Diacritics are **never treated as standalone characters**.
* They must always be attached to a base character (e.g., \[pʰ], not \[ʰ]).

### Diphthongs and Triphthongs

* Treated as **atomic vocalic nuclei**.
* Searching for \[a] will **not** match \[aɪ] or \[aʊ].

### Affricates

* Only **tie-bar affricates** (e.g., \[t͡ʃ], \[d͜ʒ]) are treated as single phonological units.
* If no tie bar is present (e.g., \[dʒ]), the sequence is analyzed as a **stop + fricative cluster**.

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

## Input Format

Word lists should contain one IPA transcription per line in UTF-8 encoding:

```
kʰæt
tʰɪp
sɑːm
ʃiːp
θɪŋk
```

The default dataset (`data/input.txt`) contains 96 phonetically transcribed English words.

## Project Structure

```
phonenv/
├── phonenv_cl.py              # Main command-line interface
├── interactive_cli.py         # Interactive IPA character selection
├── environment_analyzer.py    # Core phonetic analysis engine
├── ipa_processor_v2.py        # Professional IPA text processing
├── dict_parse.py              # Dictionary management utilities
├── setup.py                   # Package configuration and dependencies
└── data/
    └── input.txt              # Default IPA word list (96 words)
```

## Environment Categories

**INITIAL**: Word-initial position (#\_X)

* Example: \[ɪ]nɪʃəl for target 'ɪ'

**FINAL**: Word-final position (X\_#)

* Example: kʰɔːf\[ɪ] for target 'ɪ'

**MEDIAL**: Word-medial positions, classified by phonetic context:

* **V\_V**: Between vowels (vowel-vowel environment)
* **V\_C**: After vowel, before consonant
* **C\_V**: After consonant, before vowel
* **C\_C**: Between consonants (consonant cluster environment)

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
* `rich` (≥10.0) - Enhanced terminal output formatting

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
* Optimized Unicode text processing with caching

### Output Format

* Unicode box-drawing characters for clear tables
* Bracketed highlighting of targets: \[ɪ]
* Grouped by environment category with counts and examples

### Error Handling

* Graceful handling of missing files and invalid characters
* EOF detection for non-interactive environments
* Unicode validation with helpful error messages

## Known Issues

* Interactive menu navigation requires terminal keyboard input (not suitable for piped input)
* Unicode info display may show "N/A" depending on system Unicode data

## Contributing

Contributions are welcome. Please ensure all tests pass and follow the established code style. For major changes, open an issue first to discuss proposed modifications.

## License

MIT License - see LICENSE file for details.