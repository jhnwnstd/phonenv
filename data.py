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
from utils import normalize_tiebar, is_safe_path

# ========================= WORD ENTRY PARSING =========================

_COMMENT = re.compile(r"#.*$")
_SECTION = re.compile(r"^\[(?P<body>.+)\]\s*$")
_KV = re.compile(r"\s*([a-zA-Z_][\w-]*)\s*=\s*([^;]+)\s*")
_BRACKETS = re.compile(r"\[(?P<tag>[^\[\]]+)\]")

# ---- Target processing helpers ----


def _split_targets_line(line: str) -> List[str]:
    """Split line by comma or whitespace; supports mixed styles."""
    if "," in line:
        parts = [t for t in (p.strip() for p in line.split(",")) if t]
    else:
        parts = [t for t in line.split() if t]
    return parts


@dataclass(frozen=True)
class WordEntry:
    """Rich data structure for parsed word entries with metadata."""

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

    def __str__(self) -> str:
        return f"{self.segment1} ~ {self.segment2}"

    def __repr__(self) -> str:
        return f"AlternationPair({self.segment1!r}, {self.segment2!r})"


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
            if isinstance(part, str) and re.match(r"^[a-zA-Z_][\w-]*$", part):
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

    # Security: Validate path is within project directory
    if not is_safe_path(p):
        raise ValueError(
            f"Access denied: path '{p}' is outside allowed directory"
        )

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

    def __init__(
        self, input_file: str = "data/dataset.txt", encoding: str = "utf-8"
    ):
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

            with self.input_file.open("w", encoding="utf-8") as f:
                for word in sorted(words):
                    f.write(f"{word}\n")
        except (IOError, OSError) as e:
            raise IOError(
                f"Cannot write to file {self.input_file}: {e}"
            ) from e

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
            "total_words": len(words),
            "unique_letters": len(set("".join(words).lower())),
            "avg_word_length": (
                sum(len(word) for word in words) / len(words) if words else 0
            ),
            "longest_word": max(words, key=len) if words else None,
            "shortest_word": min(words, key=len) if words else None,
        }

    def process_dictionary(
        self,
        append: Optional[str] = None,
        print_dict: bool = False,
        delete_substring: Optional[str] = None,
        clear_file: bool = False,
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
                words = {
                    word for word in words if delete_substring not in word
                }
                removed_count = original_count - len(words)
                print(
                    f"Removed {removed_count} words containing '{delete_substring}'"
                )

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
            "target": self.target,
            "environments": self.environments,
            "total_occurrences": self.total_occurrences,
            "source_file": self.source_file,
        }


@dataclass
class AlternationResult:
    """Result of analyzing a phonological alternation."""

    pair: AlternationPair
    segment1_envs: Mapping[str, Mapping[str, List[str]]]
    segment2_envs: Mapping[str, Mapping[str, List[str]]]
    segment1_total: int
    segment2_total: int
    source_file: str
    pattern: str = "unknown"  # complementary, overlapping, asymmetric
    analysis: str = ""  # Human-readable interpretation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "alternation": str(self.pair),
            "segment1": self.pair.segment1,
            "segment2": self.pair.segment2,
            "segment1_environments": self.segment1_envs,
            "segment2_environments": self.segment2_envs,
            "segment1_total": self.segment1_total,
            "segment2_total": self.segment2_total,
            "pattern": self.pattern,
            "analysis": self.analysis,
            "source_file": self.source_file,
        }


class TargetsProcessor:
    """Processes targets from targets.txt file and runs batch analysis."""

    def __init__(
        self,
        dataset_path: str = "data/dataset.txt",
        targets_path: str = "data/targets.txt",
        analyzer=None,  # PhoneticAnalyzer instance
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

    def load_targets(
        self,
    ) -> Tuple[List[str], List[AlternationPair]]:
        """Load targets and alternation pairs from targets.txt file.

        Supports two formats in the same file:
        - Single segments: p, b, t (one per line or comma/space separated)
        - Alternation pairs: p ~ b, t ~ d (segments separated by ~)

        Returns:
            Tuple of (single_targets, alternation_pairs)

        Uses segmentation-based validation to ensure only valid single IPA
        segments are accepted.
        """
        if not self.targets_path.exists():
            raise FileNotFoundError(
                f"Targets file not found: {self.targets_path}"
            )

        try:
            # Lazy import to avoid circular dependency
            from analyze import (
                IPAProcessorV2,
                get_config_for_transcription_mode,
            )

            proc = IPAProcessorV2(get_config_for_transcription_mode("broad"))

            def _is_single_segment(tok: str) -> bool:
                """Validate that token is exactly one IPA segment."""
                s = normalize_tiebar(ud.normalize("NFC", tok))
                segs = proc.ipa_segments(s)
                return len(segs) == 1

            seen_targets: set[str] = set()
            seen_pairs: set[Tuple[str, str]] = set()
            targets: list[str] = []
            alternations: list[AlternationPair] = []

            with self.targets_path.open("r", encoding="utf-8") as f:
                for line_num, raw in enumerate(f, 1):
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Allow inline comments: keep content before '#'
                    comment = None
                    if "#" in line:
                        line, comment = line.split("#", 1)
                        line = line.strip()
                        comment = comment.strip()
                        if not line:
                            continue

                    # Check if line contains alternation marker (~)
                    if "~" in line:
                        # Parse alternation pair
                        parts = [
                            p.strip().strip("[]") for p in line.split("~")
                        ]
                        if len(parts) == 2:
                            seg1 = normalize_tiebar(
                                ud.normalize("NFC", parts[0])
                            )
                            seg2 = normalize_tiebar(
                                ud.normalize("NFC", parts[1])
                            )

                            # Validate both segments
                            if _is_single_segment(seg1) and _is_single_segment(
                                seg2
                            ):
                                pair_key = (seg1, seg2)
                                if pair_key not in seen_pairs:
                                    seen_pairs.add(pair_key)
                                    alternations.append(
                                        AlternationPair(
                                            segment1=seg1,
                                            segment2=seg2,
                                            description=comment,
                                        )
                                    )
                    else:
                        # Parse single targets
                        for tok in _split_targets_line(line):
                            tok = tok.strip().strip("[]")
                            if not tok:
                                continue

                            # Normalize and validate as single segment
                            norm = normalize_tiebar(ud.normalize("NFC", tok))
                            if _is_single_segment(norm):
                                if norm not in seen_targets:
                                    seen_targets.add(norm)
                                    targets.append(norm)

            return targets, alternations

        except (IOError, OSError) as e:
            raise IOError(
                f"Cannot read targets file {self.targets_path}: {e}"
            ) from e

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

            with self.targets_path.open("w", encoding="utf-8") as f:
                f.write("# Phonetic targets for batch analysis\n")
                f.write("# One target per line, or comma/space separated\n")
                f.write("# Lines starting with # are comments\n\n")

                for target in targets:
                    f.write(
                        f"{normalize_tiebar(ud.normalize('NFC', target))}\n"
                    )

        except (IOError, OSError) as e:
            raise IOError(
                f"Cannot write to targets file {self.targets_path}: {e}"
            ) from e

    def analyze_target(self, target: str) -> TargetResult:
        """Analyze a single target character.

        Args:
            target: Character/phoneme to analyze

        Returns:
            TargetResult with analysis data
        """
        if not self.analyzer:
            from analyze import (
                PhoneticAnalyzer,
            )  # avoid package-relative import issues

            self.analyzer = PhoneticAnalyzer(use_ipa_processing=True)

        environments = self.analyzer.analyze_character(
            target, str(self.dataset_path)
        )

        # Count total occurrences
        total_occurrences = 0
        for env_group in environments.values():
            for word_list in env_group.values():
                total_occurrences += len(word_list)

        return TargetResult(
            target=target,
            environments=environments,
            total_occurrences=total_occurrences,
            source_file=str(self.dataset_path),
        )

    def analyze_alternation(self, pair: AlternationPair) -> AlternationResult:
        """Analyze a phonological alternation pair.

        Args:
            pair: AlternationPair to analyze

        Returns:
            AlternationResult with comparative analysis
        """
        if not self.analyzer:
            from analyze import PhoneticAnalyzer

            self.analyzer = PhoneticAnalyzer(use_ipa_processing=True)

        # Analyze both segments independently
        env1 = self.analyzer.analyze_character(
            pair.segment1, str(self.dataset_path)
        )
        env2 = self.analyzer.analyze_character(
            pair.segment2, str(self.dataset_path)
        )

        # Count occurrences
        total1 = sum(
            len(words)
            for env_group in env1.values()
            for words in env_group.values()
        )
        total2 = sum(
            len(words)
            for env_group in env2.values()
            for words in env_group.values()
        )

        # Analyze distribution pattern
        pattern, analysis = self._analyze_distribution_pattern(
            pair, env1, env2
        )

        return AlternationResult(
            pair=pair,
            segment1_envs=env1,
            segment2_envs=env2,
            segment1_total=total1,
            segment2_total=total2,
            source_file=str(self.dataset_path),
            pattern=pattern,
            analysis=analysis,
        )

    def _analyze_distribution_pattern(
        self,
        pair: AlternationPair,
        env1: Mapping[str, Mapping[str, List[str]]],
        env2: Mapping[str, Mapping[str, List[str]]],
    ) -> Tuple[str, str]:
        """Analyze the distribution pattern of an alternation.

        Detects:
        - Complementary distribution (allophones)
        - Contrastive/overlapping (separate phonemes)
        - Free variation (interchangeable in same contexts)
        - Neutralization (contrast lost in specific positions)
        - Partial overlap (gradience)

        Returns:
            Tuple of (pattern_type, human_readable_analysis)
        """
        # Extract all environment contexts for each segment
        contexts1 = set()
        contexts2 = set()

        # Also track positional distribution
        positions1 = set()
        positions2 = set()

        for env_type, contexts in env1.items():
            positions1.add(env_type)
            for context in contexts.keys():
                contexts1.add(f"{env_type}:{context}")

        for env_type, contexts in env2.items():
            positions2.add(env_type)
            for context in contexts.keys():
                contexts2.add(f"{env_type}:{context}")

        shared = contexts1 & contexts2
        only_seg1 = contexts1 - contexts2
        only_seg2 = contexts2 - contexts1

        # Positional analysis
        _shared_positions = positions1 & positions2  # noqa: F841
        only_pos1 = positions1 - positions2
        only_pos2 = positions2 - positions1

        total_contexts = len(contexts1) + len(contexts2)
        overlap_ratio = (
            len(shared) / total_contexts if total_contexts > 0 else 0
        )

        # Determine pattern with enhanced logic

        # Case 1: No shared contexts at all → Complementary distribution
        if not shared and (only_seg1 or only_seg2):
            pattern = "complementary"

            # Check if complementary by position (e.g., one initial, one final)
            if only_pos1 and only_pos2:
                pos1_str = ", ".join(sorted(only_pos1))
                pos2_str = ", ".join(sorted(only_pos2))
                analysis = (
                    f"{pair.segment1} and {pair.segment2} are in complementary "
                    f"distribution. {pair.segment1} occurs in {pos1_str} positions; "
                    f"{pair.segment2} occurs in {pos2_str} positions (likely allophones)"
                )
            else:
                analysis = (
                    f"{pair.segment1} and {pair.segment2} are in complementary "
                    f"distribution (no shared contexts; likely allophones)"
                )

        # Case 2: Complete overlap → Free variation or contrastive
        elif shared and not (only_seg1 or only_seg2):
            pattern = "free_variation"
            analysis = (
                f"{pair.segment1} and {pair.segment2} appear in identical "
                f"contexts ({len(shared)} shared). This suggests free variation "
                f"(interchangeable allophones) or minimal pairs (contrastive phonemes)"
            )

        # Case 3: Partial overlap - need to distinguish subtypes
        elif shared and (only_seg1 or only_seg2):
            # Calculate overlap metrics
            seg1_coverage = len(shared) / len(contexts1) if contexts1 else 0
            seg2_coverage = len(shared) / len(contexts2) if contexts2 else 0

            # Neutralization: One segment has much broader distribution,
            # the other appears mainly in specific contexts
            # Heuristic: one segment appears in <30% of contexts, the other in >70%
            if (seg1_coverage < 0.3 and seg2_coverage > 0.7) or (
                seg2_coverage < 0.3 and seg1_coverage > 0.7
            ):
                pattern = "neutralization"

                # Determine which is neutralized
                if seg1_coverage < seg2_coverage:
                    restricted = pair.segment1
                    general = pair.segment2
                    restricted_envs = only_seg1
                else:
                    restricted = pair.segment2
                    general = pair.segment1
                    restricted_envs = only_seg2

                # Try to identify neutralization context
                neutral_context = self._identify_neutralization_context(
                    restricted_envs
                )

                if neutral_context:
                    analysis = (
                        f"{restricted} ~ {general} show neutralization. "
                        f"{restricted} appears primarily {neutral_context}, "
                        f"while {general} has broader distribution "
                        f"({len(shared)} shared, {len(only_seg1)} exclusive to {pair.segment1}, "
                        f"{len(only_seg2)} exclusive to {pair.segment2})"
                    )
                else:
                    analysis = (
                        f"{restricted} ~ {general} show neutralization. "
                        f"{general} has much broader distribution "
                        f"({len(shared)} shared, {len(only_seg1)} exclusive to {pair.segment1}, "
                        f"{len(only_seg2)} exclusive to {pair.segment2})"
                    )

            # Partial overlap / Gradience: Substantial overlap but also distinctions
            # High overlap ratio (>40%) suggests ongoing change or dialectal variation
            elif overlap_ratio > 0.4:
                pattern = "partial_overlap"
                analysis = (
                    f"{pair.segment1} and {pair.segment2} show partial overlap "
                    f"({len(shared)} shared contexts = {overlap_ratio:.0%} of total). "
                    f"This suggests gradience, ongoing sound change, or dialectal variation. "
                    f"{len(only_seg1)} contexts exclusive to {pair.segment1}, "
                    f"{len(only_seg2)} exclusive to {pair.segment2}"
                )

            # Contrastive/Overlapping: Standard phonemic contrast
            else:
                pattern = "contrastive"
                analysis = (
                    f"{pair.segment1} and {pair.segment2} are contrastive (distinct phonemes). "
                    f"They contrast in {len(shared)} shared contexts, with "
                    f"{len(only_seg1)} contexts exclusive to {pair.segment1} and "
                    f"{len(only_seg2)} exclusive to {pair.segment2}"
                )

        else:
            pattern = "unknown"
            analysis = (
                "Unable to determine distribution pattern (insufficient data)"
            )

        return pattern, analysis

    def _identify_neutralization_context(
        self, restricted_envs: Set[str]
    ) -> str:
        """Identify the typical neutralization context from environment strings.

        Returns a human-readable description like "word-finally" or "before voiceless consonants".
        """
        if not restricted_envs:
            return ""

        # Count position types
        final_count = sum(1 for env in restricted_envs if "FINAL" in env)
        initial_count = sum(1 for env in restricted_envs if "INITIAL" in env)
        medial_count = sum(1 for env in restricted_envs if "MEDIAL" in env)

        total = len(restricted_envs)

        # Check if predominantly one position
        if final_count / total > 0.7:
            return "word-finally"
        elif initial_count / total > 0.7:
            return "word-initially"
        elif medial_count / total > 0.7:
            # Try to identify medial context type
            v_v = sum(1 for env in restricted_envs if "V_V" in env)
            c_c = sum(1 for env in restricted_envs if "C_C" in env)

            if v_v / medial_count > 0.7:
                return "between vowels (intervocalic)"
            elif c_c / medial_count > 0.7:
                return "in consonant clusters"

        return "in restricted contexts"

    def process_targets(self) -> Iterator[TargetResult | AlternationResult]:
        """Process all targets from targets.txt file.

        Yields:
            TargetResult for each target

        Raises:
            FileNotFoundError: If targets.txt or dataset doesn't exist
        """
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset file not found: {self.dataset_path}"
            )

        targets, alternations = self.load_targets()

        # Process single targets
        for target in targets:
            yield self.analyze_target(target)

        # Process alternation pairs
        for pair in alternations:
            yield self.analyze_alternation(pair)

    def process_targets_to_list(
        self,
    ) -> List[TargetResult | AlternationResult]:
        """Process all targets and return as list.

        Returns:
            List of TargetResult and AlternationResult objects
        """
        return list(self.process_targets())

    def get_targets_summary(self) -> Dict[str, Any]:
        """Get summary information about targets file.

        Returns:
            Dictionary with summary statistics
        """
        try:
            targets, alternations = self.load_targets()
            unique_targets = list(
                dict.fromkeys(targets)
            )  # Preserve order, remove duplicates

            return {
                "targets_file": str(self.targets_path),
                "dataset_file": str(self.dataset_path),
                "total_targets": len(targets),
                "unique_targets": len(unique_targets),
                "targets": unique_targets,
                "total_alternations": len(alternations),
                "alternations": [str(pair) for pair in alternations],
                "targets_exist": self.targets_path.exists(),
                "dataset_exists": self.dataset_path.exists(),
            }
        except Exception as e:
            return {
                "targets_file": str(self.targets_path),
                "dataset_file": str(self.dataset_path),
                "error": str(e),
                "targets_exist": self.targets_path.exists(),
                "dataset_exists": self.dataset_path.exists(),
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

    with path.open("w", encoding="utf-8") as f:
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


def load_targets(
    targets_path: str = "data/targets.txt",
) -> Tuple[List[str], List[AlternationPair]]:
    """Load targets from file (backwards compatible function).

    Args:
        targets_path: Path to targets file

    Returns:
        Tuple of (single_targets, alternation_pairs)
    """
    processor = TargetsProcessor(targets_path=targets_path)
    return processor.load_targets()


def process_all_targets(
    dataset_path: str = "data/dataset.txt",
    targets_path: str = "data/targets.txt",
) -> List[TargetResult]:
    """Process all targets (backwards compatible function).

    Args:
        dataset_path: Path to dataset file
        targets_path: Path to targets file

    Returns:
        List of TargetResult objects
    """
    processor = TargetsProcessor(
        dataset_path=dataset_path, targets_path=targets_path
    )
    results = processor.process_targets_to_list()
    return [result for result in results if isinstance(result, TargetResult)]
