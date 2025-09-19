"""Data management for phonetic environment analysis.

This module consolidates all data-related functionality including:
- Dictionary/dataset parsing and management
- Targets file processing for batch analysis
- Word entry parsing with enhanced format support
"""

from __future__ import annotations

import regex as re
import unicodedata as ud
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, Optional, Set, Any, Mapping
from utils import normalize_tiebar


# ========================= WORD ENTRY PARSING =========================

_COMMENT = re.compile(r"#.*$")
_SECTION = re.compile(r"^\[(?P<body>.+)\]\s*$")
_KV = re.compile(r"\s*([a-zA-Z_][\w-]*)\s*=\s*([^;]+)\s*")
_BRACKETS = re.compile(r"\[(?P<tag>[^\[\]]+)\]")

# ---- Target processing helpers ----
# Tie-bar constants now imported from utils module




def _split_targets_line(line: str) -> List[str]:
    """Split line by comma or whitespace; supports mixed styles."""
    if "," in line:
        parts = [t for t in (p.strip() for p in line.split(",")) if t]
    else:
        parts = [t for t in line.split() if t]
    return parts


# Deprecated: _clean_token removed - now using segmentation-based validation


@dataclass(frozen=True)
class WordEntry:
    """Rich data structure for parsed word entries with metadata."""
    ipa: str
    section: Dict[str, str] = field(default_factory=dict)
    tags: Tuple[str, ...] = field(default_factory=tuple)
    source_path: Optional[str] = None
    line_no: Optional[int] = None


_DEFAULT_SECTION: Dict[str, str] = {
    "lang": "und",
    "mode": "narrow",
    "profile": "default",
}


def _parse_section(line: str) -> Optional[Dict[str, str]]:
    """Parse section header like [lang=en-GB; mode=narrow; profile=english]."""
    m = _SECTION.match(line)
    if not m:
        return None
    body = m.group("body")
    out: Dict[str, str] = {}

    # Must contain only valid key=value pairs and/or bare flags
    valid_section = True
    for part in body.split(";"):
        part = part.strip()
        if not part:
            continue
        kv = _KV.match(part)
        if kv:
            k, v = kv.group(1), kv.group(2).strip()
            out[k] = v
        else:
            # Check if it's a valid bare flag
            if isinstance(part, str) and re.match(r'^[a-zA-Z_][\w-]*$', part):
                out[part] = "true"
            else:
                valid_section = False
                break

    return out if valid_section and out else None


def _strip_comment(s: str) -> str:
    """Remove everything after # symbol."""
    return _COMMENT.sub("", s).strip()


def _extract_tags(s: str) -> Tuple[str, Tuple[str, ...]]:
    """Extract bracket tags and return cleaned string and tags."""
    tags = tuple(t.strip() for t in _BRACKETS.findall(s))
    s = _BRACKETS.sub("", s)
    return s.strip(), tags


def iter_word_entries(path: str | Path) -> Iterator[WordEntry]:
    """Parse enhanced dataset format with sections, comments, and tags.

    Yields WordEntry objects with rich metadata while maintaining
    backwards compatibility with simple "one IPA per line" format.
    """
    p = Path(path)
    section = dict(_DEFAULT_SECTION)

    if not p.exists():
        return

    with p.open("r", encoding="utf-8") as fh:
        for i, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")

            # 1) section headers (strip comments first)
            clean_line = _strip_comment(line)
            sh = _parse_section(clean_line)
            if sh is not None:
                section = {**section, **{k: v for k, v in sh.items() if v}}
                continue

            # 2) comments / blanks
            s = _strip_comment(line)
            if not s:
                continue

            # 3) bracket tags
            s, tags = _extract_tags(s)
            if not s:
                continue

            # 4) normalize form + tie-bars for stability
            s = ud.normalize("NFC", s)
            s = normalize_tiebar(s)

            yield WordEntry(
                ipa=s,
                section=section.copy(),
                tags=tags,
                source_path=str(p),
                line_no=i,
            )


def load_words_set(path: str = "data/dataset.txt") -> Set[str]:
    """Load words as set (backwards-compatible)."""
    return {e.ipa for e in iter_word_entries(path)}


def load_words_list(path: str = "data/dataset.txt") -> List[str]:
    """Load words as list (backwards-compatible)."""
    return [e.ipa for e in iter_word_entries(path)]


# ========================= DICTIONARY PROCESSOR =========================

class DictionaryProcessor:
    """Processes and manages word dictionaries."""

    def __init__(self, input_file: str = "data/dataset.txt", encoding: str = "utf-8"):
        """Initialize the dictionary processor.

        Args:
            input_file: Path to the input dictionary file
            encoding: File encoding (default: utf-8)
        """
        self.input_file = Path(input_file)
        self.encoding = encoding

    def load_words(self) -> Set[str]:
        """Load words from the input file.

        Returns:
            Set of words from the file

        Raises:
            FileNotFoundError: If input file doesn't exist
            IOError: If file cannot be read
        """
        if not self.input_file.exists():
            return set()

        try:
            return load_words_set(str(self.input_file))
        except (IOError, OSError) as e:
            raise IOError(f"Cannot read file {self.input_file}: {e}") from e

    def save_words(self, words: Set[str]) -> None:
        """Save words to the input file.

        Args:
            words: Set of words to save

        Raises:
            IOError: If file cannot be written
        """
        try:
            # Ensure directory exists
            self.input_file.parent.mkdir(parents=True, exist_ok=True)

            with self.input_file.open('w', encoding='utf-8') as f:
                for word in sorted(words):
                    f.write(f"{word}\n")
        except (IOError, OSError) as e:
            raise IOError(f"Cannot write to file {self.input_file}: {e}") from e

    def add_word(self, word: str) -> bool:
        """Add a word to the dictionary.

        Args:
            word: Word to add

        Returns:
            True if word was added, False if it already existed
        """
        word = normalize_tiebar(ud.normalize("NFC", word))

        words = self.load_words()
        if word in words:
            return False

        words.add(word)
        self.save_words(words)
        return True

    def remove_words_containing(self, substring: str) -> int:
        """Remove words containing a specific substring.

        Args:
            substring: Substring to filter out

        Returns:
            Number of words removed
        """
        words = self.load_words()
        original_count = len(words)

        filtered_words = {word for word in words if substring not in word}

        self.save_words(filtered_words)
        return original_count - len(filtered_words)

    def clear_dictionary(self) -> None:
        """Clear all words from the dictionary."""
        self.save_words(set())

    def print_dictionary(self) -> None:
        """Print all words in the dictionary to console."""
        words = self.load_words()
        if not words:
            print("Dictionary is empty")
            return

        print(f"Dictionary contains {len(words)} words:")
        for word in sorted(words):
            print(word)

    def get_stats(self) -> dict:
        """Get statistics about the dictionary.

        Returns:
            Dictionary with statistics
        """
        words = self.load_words()
        return {
            'total_words': len(words),
            'unique_letters': len(set(''.join(words).lower())),
            'avg_word_length': sum(len(word) for word in words) / len(words) if words else 0,
            'longest_word': max(words, key=len) if words else None,
            'shortest_word': min(words, key=len) if words else None
        }

    def process_dictionary(
        self,
        append: Optional[str] = None,
        print_dict: bool = False,
        delete_substring: Optional[str] = None,
        clear_file: bool = False
    ) -> None:
        """Process dictionary with various operations.

        Args:
            append: Word to append to dictionary
            print_dict: Whether to print dictionary to console
            delete_substring: Substring to delete words containing it
            clear_file: Whether to clear the file first
        """
        print(f"Processing dictionary from '{self.input_file}'")

        try:
            # Clear file if requested
            if clear_file:
                self.clear_dictionary()
                words = set()
            else:
                words = self.load_words()

            # Add word if provided (normalize)
            if append:
                append_norm = normalize_tiebar(ud.normalize("NFC", append))
                if append_norm in words:
                    print(f"Word '{append_norm}' already exists in dictionary")
                else:
                    words.add(append_norm)
                    print(f"Added '{append_norm}' to dictionary")

            # Remove words containing substring
            if delete_substring:
                original_count = len(words)
                words = {word for word in words if delete_substring not in word}
                removed_count = original_count - len(words)
                print(f"Removed {removed_count} words containing '{delete_substring}'")

            # Save changes
            self.save_words(words)

            # Print dictionary if requested
            if print_dict:
                self.print_dictionary()
            else:
                stats = self.get_stats()
                print(f"Dictionary now contains {stats['total_words']} words")

        except IOError as e:
            print(f"Error processing dictionary: {e}")


# ========================= TARGETS PROCESSOR =========================

@dataclass
class TargetResult:
    """Result of analyzing a single target character."""
    target: str
    environments: Mapping[str, Mapping[str, List[str]]]
    total_occurrences: int
    source_file: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'target': self.target,
            'environments': self.environments,
            'total_occurrences': self.total_occurrences,
            'source_file': self.source_file
        }


class TargetsProcessor:
    """Processes targets from targets.txt file and runs batch analysis."""

    def __init__(
        self,
        dataset_path: str = "data/dataset.txt",
        targets_path: str = "data/targets.txt",
        analyzer=None  # PhoneticAnalyzer instance
    ):
        """Initialize the targets processor.

        Args:
            dataset_path: Path to the dataset file
            targets_path: Path to the targets file
            analyzer: Pre-configured PhoneticAnalyzer instance
        """
        self.dataset_path = Path(dataset_path)
        self.targets_path = Path(targets_path)
        self.analyzer = analyzer

    def load_targets(self) -> List[str]:
        """Load targets from targets.txt file (sanitized, deduped, order-preserving).

        Uses segmentation-based validation to ensure only valid single IPA segments
        are accepted as targets.
        """
        if not self.targets_path.exists():
            raise FileNotFoundError(f"Targets file not found: {self.targets_path}")

        try:
            # Lazy import to avoid circular dependency
            from analysis import IPAProcessorV2, get_config_for_transcription_mode

            proc = IPAProcessorV2(get_config_for_transcription_mode("broad"))

            def _is_single_segment(tok: str) -> bool:
                """Validate that token is exactly one IPA segment."""
                s = normalize_tiebar(ud.normalize("NFC", tok))
                segs = proc.ipa_segments(s)
                return len(segs) == 1

            seen: set[str] = set()
            out: list[str] = []

            with self.targets_path.open('r', encoding='utf-8') as f:
                for line_num, raw in enumerate(f, 1):
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue

                    # Allow inline comments: keep content before '#'
                    if '#' in line:
                        line = line.split('#', 1)[0].strip()
                        if not line:
                            continue

                    for tok in _split_targets_line(line):
                        tok = tok.strip().strip("[]")  # Remove brackets and whitespace
                        if not tok:
                            continue

                        # Normalize and validate as single segment
                        norm = normalize_tiebar(ud.normalize("NFC", tok))
                        if _is_single_segment(norm):
                            if norm not in seen:
                                seen.add(norm)
                                out.append(norm)
                        # Silently drop multi-segment tokens (e.g., English words)

            return out

        except (IOError, OSError) as e:
            raise IOError(f"Cannot read targets file {self.targets_path}: {e}") from e

    def save_targets(self, targets: List[str]) -> None:
        """Save targets to targets.txt file.

        Args:
            targets: List of target characters to save

        Raises:
            IOError: If file cannot be written
        """
        try:
            # Ensure directory exists
            self.targets_path.parent.mkdir(parents=True, exist_ok=True)

            with self.targets_path.open('w', encoding='utf-8') as f:
                f.write("# Phonetic targets for batch analysis\n")
                f.write("# One target per line, or comma/space separated\n")
                f.write("# Lines starting with # are comments\n\n")

                for target in targets:
                    f.write(f"{normalize_tiebar(ud.normalize('NFC', target))}\n")

        except (IOError, OSError) as e:
            raise IOError(f"Cannot write to targets file {self.targets_path}: {e}") from e

    def analyze_target(self, target: str) -> TargetResult:
        """Analyze a single target character.

        Args:
            target: Character/phoneme to analyze

        Returns:
            TargetResult with analysis data
        """
        if not self.analyzer:
            from analysis import PhoneticAnalyzer  # avoid package-relative import issues
            self.analyzer = PhoneticAnalyzer(use_ipa_processing=True)

        environments = self.analyzer.analyze_character(target, str(self.dataset_path))

        # Count total occurrences
        total_occurrences = 0
        for env_group in environments.values():
            for word_list in env_group.values():
                total_occurrences += len(word_list)

        return TargetResult(
            target=target,
            environments=environments,
            total_occurrences=total_occurrences,
            source_file=str(self.dataset_path)
        )

    def process_targets(self) -> Iterator[TargetResult]:
        """Process all targets from targets.txt file.

        Yields:
            TargetResult for each target

        Raises:
            FileNotFoundError: If targets.txt or dataset doesn't exist
        """
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.dataset_path}")

        targets = self.load_targets()

        for target in targets:
            yield self.analyze_target(target)

    def process_targets_to_list(self) -> List[TargetResult]:
        """Process all targets and return as list.

        Returns:
            List of TargetResult objects
        """
        return list(self.process_targets())

    def get_targets_summary(self) -> Dict[str, Any]:
        """Get summary information about targets file.

        Returns:
            Dictionary with summary statistics
        """
        try:
            targets = self.load_targets()
            unique_targets = list(dict.fromkeys(targets))  # Preserve order, remove duplicates

            return {
                'targets_file': str(self.targets_path),
                'dataset_file': str(self.dataset_path),
                'total_targets': len(targets),
                'unique_targets': len(unique_targets),
                'targets': unique_targets,
                'targets_exist': self.targets_path.exists(),
                'dataset_exists': self.dataset_path.exists()
            }
        except Exception as e:
            return {
                'targets_file': str(self.targets_path),
                'dataset_file': str(self.dataset_path),
                'error': str(e),
                'targets_exist': self.targets_path.exists(),
                'dataset_exists': self.dataset_path.exists()
            }


def create_sample_targets_file(targets_path: str = "data/targets.txt") -> None:
    """Create a sample targets.txt file with common IPA targets.

    Args:
        targets_path: Path where to create the sample file
    """
    sample_targets = [
        "# Common IPA targets for phonetic environment analysis",
        "# Vowels",
        "i, ɪ, e, ɛ, æ, a, ɑ, ɒ, ɔ, o, ʊ, u, ʌ, ə, ɚ, ɜ, ɞ, y, ʉ",
        "",
        "# Consonants",
        "p, t, k, b, d, ɡ",
        "f, v, θ, ð, s, z, ʃ, ʒ, ç, ʝ, x, ɣ, χ, ʁ, ħ, ʕ, h, ɦ",
        "m, n, ŋ, ɲ, ɳ, ɴ",
        "l, ɫ, r, ɾ, ɹ, ɻ, ʀ",
        "j, w, ɥ, ʋ",
        "",
        "# Affricates (tie bar normalized to U+0361)",
        "t͡s, d͡z, t͡ʃ, d͡ʒ, t͡ɕ, d͡ʑ, ʈ͡ʂ, ɖ͡ʐ",
        "",
        "# Diacritic-bearing bases (broad mode may merge)",
        "pʰ, tʰ, kʰ, s̪, n̪, l̩, n̩",
    ]

    path = Path(targets_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open('w', encoding='utf-8') as f:
        for line in sample_targets:
            f.write(normalize_tiebar(ud.normalize("NFC", line)) + "\n")


def targets_exist(targets_path: str = "data/targets.txt") -> bool:
    """Check if targets.txt file exists.

    Args:
        targets_path: Path to targets file

    Returns:
        True if file exists, False otherwise
    """
    return Path(targets_path).exists()


# ========================= BACKWARDS COMPATIBILITY =========================

# Legacy process_dictionary function removed to eliminate code duplication.
# Use DictionaryProcessor.process_dictionary() instead.


def load_targets(targets_path: str = "data/targets.txt") -> List[str]:
    """Load targets from file (backwards compatible function).

    Args:
        targets_path: Path to targets file

    Returns:
        List of target characters
    """
    processor = TargetsProcessor(targets_path=targets_path)
    return processor.load_targets()


def process_all_targets(
    dataset_path: str = "data/dataset.txt",
    targets_path: str = "data/targets.txt"
) -> List[TargetResult]:
    """Process all targets (backwards compatible function).

    Args:
        dataset_path: Path to dataset file
        targets_path: Path to targets file

    Returns:
        List of TargetResult objects
    """
    processor = TargetsProcessor(dataset_path=dataset_path, targets_path=targets_path)
    return processor.process_targets_to_list()