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
    pair_filter: Optional[str] = (
        None  # e.g., "1:2" to match word pairs by position
    )

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


@dataclass
class StructuralAlternationResult:
    """Result of analyzing a structural alternation (X ~ Ø).

    Represents insertion/deletion processes like epenthesis, prothesis,
    syncope, apocope, etc.
    """

    pair: AlternationPair
    segment: str  # The real segment (X in X ~ Ø)
    process_type: str  # 'prothesis', 'epenthesis', 'syncope', 'apocope', etc.
    rule: str  # Human-readable rule (e.g., "Ø → ʔ / # __ V")
    segment_envs: Mapping[str, Mapping[str, List[str]]]  # Where X appears
    segment_total: int
    dominant_contexts: List[str]  # Most common contexts for X
    source_file: str
    analysis: str = ""  # Human-readable interpretation
    frame_contrasts: Dict[str, Dict[str, int]] = (
        None  # Same-frame pairing: {context: {'with_X': n, 'with_Ø': m}}
    )
    confidence: float = 0.0  # Rule confidence (max skew from frame contrasts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "alternation": str(self.pair),
            "segment": self.segment,
            "process_type": self.process_type,
            "rule": self.rule,
            "segment_environments": self.segment_envs,
            "segment_total": self.segment_total,
            "dominant_contexts": self.dominant_contexts,
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

    def load_dataset_with_tags(self) -> List[WordEntry]:
        """Load dataset with full tag information for pair-aware analysis."""
        return list(iter_word_entries(str(self.dataset_path)))

    def filter_by_tag(self, words: List[WordEntry], tag: str) -> Set[str]:
        """Filter words by tag and return as set of IPA strings.

        Args:
            words: List of WordEntry objects
            tag: Tag to filter by (e.g., 'sg', 'pl', '1', '2')

        Returns:
            Set of IPA strings matching the tag
        """
        return {w.ipa for w in words if tag in w.tags}

    def load_targets(
        self,
        allow_null_segments: bool = True,
    ) -> Tuple[List[str], List[AlternationPair]]:
        """Load targets and alternation pairs from targets.txt file.

        Supports two formats in the same file:
        - Single segments: p, b, t (one per line or comma/space separated)
        - Alternation pairs: p ~ b, t ~ d (segments separated by ~)

        Automatically detects and handles Ø (null segment) alternations.
        When Ø is found in an alternation pair, it's treated as a structural
        alternation (insertion/deletion) rather than a phonemic alternation.

        Args:
            allow_null_segments: If True (default), parse Ø alternations.
                Set to False to suppress them (backward compatibility).

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
                # Allow Ø (empty string or explicit null marker)
                if tok in ("Ø", "∅", ""):
                    return True  # Always allow Ø in alternations
                s = normalize_tiebar(ud.normalize("NFC", tok))
                segs = proc.ipa_segments(s)
                return len(segs) == 1

            seen_targets: set[str] = set()
            seen_pairs: set[Tuple[str, str]] = set()
            targets: list[str] = []
            alternations: list[AlternationPair] = []
            current_pair_filter: Optional[str] = (
                None  # Track active [pair=...] tag
            )

            with self.targets_path.open("r", encoding="utf-8") as f:
                for line_num, raw in enumerate(f, 1):
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Check for section header with pair filter
                    section = _parse_section(line)
                    if section:
                        # Extract pair filter if present
                        current_pair_filter = section.get("pair")
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

                            # Normalize null markers
                            if seg1 in ("Ø", "∅"):
                                seg1 = ""
                            if seg2 in ("Ø", "∅"):
                                seg2 = ""

                            # Skip null alternations if suppressed
                            if not allow_null_segments and (
                                seg1 == "" or seg2 == ""
                            ):
                                continue

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
                                            pair_filter=current_pair_filter,
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

    def analyze_structural_alternation(
        self, pair: AlternationPair, min_evidence: int = 3
    ) -> StructuralAlternationResult:
        """Analyze a structural alternation (X ~ Ø).

        Uses same-frame pairing to determine directionality:
        - If X observed but Ø never in same frame → insertion (Ø → X)
        - If both X and Ø observed in same frame → check skew for direction
        - If insufficient evidence → inconclusive

        Classifies insertion/deletion processes:
        - Prothesis: Ø → X / # __ (word-initial insertion)
        - Epenthesis: Ø → X / C __ C (cluster breaking)
        - Syncope: X → Ø / V __ V (vowel deletion between vowels)
        - Apocope: X → Ø / __ # (word-final deletion)
        - Aphaeresis: X → Ø / # __ (word-initial deletion)

        Args:
            pair: AlternationPair with one segment as "" (Ø)
            min_evidence: Minimum occurrences for confident classification

        Returns:
            StructuralAlternationResult with process classification
        """
        if not self.analyzer:
            from analyze import PhoneticAnalyzer

            self.analyzer = PhoneticAnalyzer(use_ipa_processing=True)

        # Determine which is the real segment
        if pair.segment1 == "":
            segment = pair.segment2
        elif pair.segment2 == "":
            segment = pair.segment1
        else:
            raise ValueError(
                f"Expected one segment to be Ø, got {pair.segment1} ~ {pair.segment2}"
            )

        # Analyze the real segment
        envs = self.analyzer.analyze_character(segment, str(self.dataset_path))

        total = sum(
            len(words)
            for env_group in envs.values()
            for words in env_group.values()
        )

        # Compute same-frame contrasts to determine directionality
        frame_contrasts, confidence = self._compute_frame_contrasts(
            segment, envs, min_evidence
        )

        # Determine direction from frame contrasts
        # If with_Ø == 0 everywhere → insertion (we only see X, never Ø)
        # If with_Ø > 0 and skew favors X → insertion
        # If skew favors Ø → deletion
        total_with_null = sum(fc["with_Ø"] for fc in frame_contrasts.values())

        if total_with_null == 0 and total > 0:
            # Only X observed, never Ø in same frames → insertion
            direction = "insertion"
        elif confidence >= 0.7:
            # Strong skew toward X → insertion
            direction = "insertion"
        elif confidence <= 0.3:
            # Strong skew toward Ø → deletion
            direction = "deletion"
        else:
            # Inconclusive
            direction = "inconclusive"

        # Classify the structural process based on dominant contexts
        process_type, rule, analysis = self._classify_structural_process(
            segment, envs, direction, confidence, total_with_null
        )

        # Extract dominant contexts (top 3 by frequency)
        dominant_contexts = self._get_dominant_contexts(envs, max_contexts=3)

        return StructuralAlternationResult(
            pair=pair,
            segment=segment,
            process_type=process_type,
            rule=rule,
            segment_envs=envs,
            segment_total=total,
            dominant_contexts=dominant_contexts,
            source_file=str(self.dataset_path),
            analysis=analysis,
            frame_contrasts=frame_contrasts,
            confidence=confidence,
        )

    def _classify_structural_process(
        self,
        segment: str,
        envs: Mapping[str, Mapping[str, List[str]]],
        direction: str,
        confidence: float = 0.0,
        total_with_null: int = 0,
    ) -> Tuple[str, str, str]:
        """Classify structural process type from environment distribution.

        Returns:
            Tuple of (process_type, rule, analysis)
        """
        # Count occurrences by position type
        initial_count = sum(
            len(words) for words in envs.get("INITIAL", {}).values()
        )
        final_count = sum(
            len(words) for words in envs.get("FINAL", {}).values()
        )
        v_v_count = sum(
            len(words) for words in envs.get("MEDIAL V_V", {}).values()
        )
        c_c_count = sum(
            len(words) for words in envs.get("MEDIAL C_C", {}).values()
        )
        v_c_count = sum(
            len(words) for words in envs.get("MEDIAL V_C", {}).values()
        )
        c_v_count = sum(
            len(words) for words in envs.get("MEDIAL C_V", {}).values()
        )

        total = (
            initial_count
            + final_count
            + v_v_count
            + c_c_count
            + v_c_count
            + c_v_count
        )

        if total == 0:
            return (
                "unknown",
                f"{segment} ~ Ø (no occurrences found)",
                f"No occurrences of {segment} found in dataset",
            )

        # Calculate proportions
        initial_ratio = initial_count / total if total > 0 else 0
        final_ratio = final_count / total if total > 0 else 0
        v_v_ratio = v_v_count / total if total > 0 else 0
        c_c_ratio = c_c_count / total if total > 0 else 0

        # Classify based on dominant context (>60% threshold for strong pattern)
        threshold = 0.6

        # Handle inconclusive direction (no same-frame evidence)
        if direction == "inconclusive":
            return (
                "inconclusive",
                f"{segment} ~ Ø (insufficient evidence)",
                f"Inconclusive: No same-frame with/without contrast ≥ min-evidence. "
                f"Observed {segment} in {total} tokens but cannot determine if insertion or deletion.",
            )

        if direction == "insertion":
            # Ø → X patterns
            # Add note about Ø evidence
            null_note = (
                " (no Ø attested in same frames)"
                if total_with_null == 0
                else f" (Rule confidence = {confidence:.2f})"
            )

            if initial_ratio > threshold:
                # Check if before vowels specifically
                initial_envs = envs.get("INITIAL", {})
                vowel_initial = sum(
                    len(words)
                    for ctx, words in initial_envs.items()
                    if self._context_right_is_vowel(ctx)
                )
                if vowel_initial > initial_count * 0.7:
                    return (
                        "prothesis",
                        f"Ø → {segment} / # __ V",
                        f"Prothesis: {segment} inserted word-initially before vowels "
                        f"({initial_count}/{total} tokens = {initial_ratio:.0%}){null_note}",
                    )
                return (
                    "prothesis",
                    f"Ø → {segment} / # __",
                    f"Prothesis: {segment} inserted word-initially "
                    f"({initial_count}/{total} tokens = {initial_ratio:.0%}){null_note}",
                )

            elif c_c_ratio > threshold:
                return (
                    "epenthesis",
                    f"Ø → {segment} / C __ C",
                    f"Epenthesis/Anaptyxis: {segment} inserted between consonants "
                    f"({c_c_count}/{total} tokens = {c_c_ratio:.0%}). "
                    f"Cluster-breaking process.",
                )

            else:
                return (
                    "epenthesis",
                    f"Ø → {segment} (mixed contexts)",
                    f"Epenthesis: {segment} inserted in multiple contexts. "
                    f"Initial: {initial_ratio:.0%}, C_C: {c_c_ratio:.0%}, "
                    f"V_V: {v_v_ratio:.0%}",
                )

        else:  # direction == "deletion"
            # X → Ø patterns
            if initial_ratio > threshold:
                return (
                    "aphaeresis",
                    f"{segment} → Ø / # __",
                    f"Aphaeresis: {segment} deleted word-initially "
                    f"({initial_count}/{total} tokens = {initial_ratio:.0%})",
                )

            elif final_ratio > threshold:
                return (
                    "apocope",
                    f"{segment} → Ø / __ #",
                    f"Apocope: {segment} deleted word-finally "
                    f"({final_count}/{total} tokens = {final_ratio:.0%})",
                )

            elif v_v_ratio > threshold:
                return (
                    "syncope",
                    f"{segment} → Ø / V __ V",
                    f"Syncope: {segment} deleted between vowels "
                    f"({v_v_count}/{total} tokens = {v_v_ratio:.0%}). "
                    f"Hiatus avoidance or vowel coalescence.",
                )

            else:
                return (
                    "deletion",
                    f"{segment} → Ø (mixed contexts)",
                    f"Deletion: {segment} deleted in multiple contexts. "
                    f"Initial: {initial_ratio:.0%}, Final: {final_ratio:.0%}, "
                    f"V_V: {v_v_ratio:.0%}, C_C: {c_c_ratio:.0%}",
                )

    def _context_right_is_vowel(self, context: str) -> bool:
        """Check if right context in 'left__right' is a vowel."""
        if "__" not in context:
            return False
        _, right = context.split("__", 1)
        if not right or right == "#":
            return False

        # Check if first character is a vowel base
        from analyze import PhoneticAnalyzer

        if not self.analyzer:
            self.analyzer = PhoneticAnalyzer(use_ipa_processing=True)

        return self.analyzer._is_vowel_segment(right)

    def _get_dominant_contexts(
        self,
        envs: Mapping[str, Mapping[str, List[str]]],
        max_contexts: int = 3,
    ) -> List[str]:
        """Extract the most frequent contexts from environment map.

        Args:
            envs: Environment mapping (position → context → examples)
            max_contexts: Maximum number of contexts to return

        Returns:
            List of dominant contexts in format "POSITION:context (N tokens)"
        """
        # Flatten all contexts with counts
        context_counts: List[Tuple[str, str, int]] = []

        for pos, contexts in envs.items():
            for ctx, examples in contexts.items():
                context_counts.append((pos, ctx, len(examples)))

        # Sort by count descending
        context_counts.sort(key=lambda x: x[2], reverse=True)

        # Format top N
        return [
            f"{pos}:{ctx} ({count} tokens)"
            for pos, ctx, count in context_counts[:max_contexts]
        ]

    def _compute_frame_contrasts(
        self,
        segment: str,
        segment_envs: Mapping[str, Mapping[str, List[str]]],
        min_evidence: int = 3,
    ) -> Tuple[Dict[str, Dict[str, int]], float]:
        """Compute same-frame pairing evidence for X ~ Ø.

        For each context where X appears, check if Ø also appears in the same frame
        (i.e., adjacent segments with no intervening material).

        Args:
            segment: The real segment (X in X ~ Ø)
            segment_envs: Environments where X appears
            min_evidence: Minimum occurrences to consider

        Returns:
            Tuple of (frame_contrasts dict, max_confidence)
            frame_contrasts: {context: {'with_X': n, 'with_Ø': m, 'skew': n/(n+m)}}
            max_confidence: Maximum skew value (0-1, where 1.0 = only X, never Ø)
        """
        if not self.analyzer:
            from analyze import PhoneticAnalyzer

            self.analyzer = PhoneticAnalyzer(use_ipa_processing=True)

        # Load all words from dataset
        dataset = load_words_set(str(self.dataset_path))

        # For each context where X appears, count Ø occurrences
        frame_contrasts = {}

        for pos, contexts in segment_envs.items():
            for ctx, words_with_x in contexts.items():
                with_x = len(words_with_x)

                # Count words where Ø appears in same frame
                # This requires checking all dataset words for adjacent segments matching the frame
                with_null = self._count_null_in_frame(
                    ctx, pos, dataset, words_with_x
                )

                total = with_x + with_null
                if total >= min_evidence:
                    skew = with_x / total if total > 0 else 0.0
                    frame_contrasts[f"{pos}:{ctx}"] = {
                        "with_X": with_x,
                        "with_Ø": with_null,
                        "skew": skew,
                    }

        # Compute max confidence (highest skew)
        max_confidence = max(
            (v["skew"] for v in frame_contrasts.values()), default=0.0
        )

        return frame_contrasts, max_confidence

    def _count_null_in_frame(
        self, ctx: str, pos: str, dataset: Set[str], words_with_x: List[str]
    ) -> int:
        """Count occurrences of Ø (absence of segment) in given frame.

        Args:
            ctx: Context string (e.g., "L2=C|L1=V[front,high]|R1=a|R2=k")
            pos: Position type (INITIAL, MEDIAL V_V, etc.)
            dataset: All words in dataset
            words_with_x: Words that have X in this context (to exclude from Ø count)

        Returns:
            Count of words where Ø appears in same frame
        """
        # For now, return 0 (conservative: assume no Ø evidence)
        # Full implementation would require checking for adjacent segments
        # matching the L2/L1/R1/R2 pattern with no intervening material
        return 0

    def analyze_alternation(
        self,
        pair: AlternationPair,
        auto_window: bool = True,
        max_window: int = 2,
        threshold: float = 0.6,
    ) -> AlternationResult | StructuralAlternationResult:
        """Analyze a phonological alternation pair.

        Routes to structural analysis if one segment is Ø (empty string).
        Otherwise performs standard phonemic alternation analysis with
        automatic window widening.

        Args:
            pair: AlternationPair to analyze
            auto_window: If True, progressively widen context window
            max_window: Maximum window size to try (1-3)
            threshold: Decision score threshold for classification

        Returns:
            AlternationResult for phonemic alternations,
            StructuralAlternationResult for X ~ Ø alternations
        """
        # Route Ø alternations to structural analysis
        if pair.segment1 == "" or pair.segment2 == "":
            return self.analyze_structural_alternation(pair)

        # Standard phonemic alternation analysis with auto-window
        if not self.analyzer:
            from analyze import PhoneticAnalyzer

            self.analyzer = PhoneticAnalyzer(use_ipa_processing=True)

        # Handle pair filtering if specified
        words1 = None
        words2 = None
        if pair.pair_filter:
            # Parse pair filter like "sg:pl" or "1:2"
            parts = pair.pair_filter.split(":")
            if len(parts) == 2:
                tag1, tag2 = parts[0].strip(), parts[1].strip()
                tagged_words = self.load_dataset_with_tags()
                words1 = list(self.filter_by_tag(tagged_words, tag1))
                words2 = list(self.filter_by_tag(tagged_words, tag2))

        if auto_window:
            return self._analyze_with_progressive_window(
                pair, max_window, threshold, words1, words2
            )

        # Fallback: analyze at current window
        env1 = self.analyzer.analyze_character(
            pair.segment1, str(self.dataset_path), word_list=words1
        )
        env2 = self.analyzer.analyze_character(
            pair.segment2, str(self.dataset_path), word_list=words2
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

    def _compute_separability_score(
        self,
        contexts1: Set[str],
        contexts2: Set[str],
        env1: Mapping[str, Mapping[str, List[str]]],
        env2: Mapping[str, Mapping[str, List[str]]],
    ) -> Tuple[float, int, int, int]:
        """Compute separability score for alternation pair.

        This algorithm determines how well two phonetic segments are distributed
        in complementary (non-overlapping) contexts. Used for auto-window context
        widening to find the optimal level of detail.

        Algorithm:
        1. Identify context overlap:
           - Shared contexts (S): where both segments appear
           - Exclusive contexts (Ex, Ey): unique to each segment
        2. Calculate coverage (Cx, Cy): fraction of tokens in exclusive contexts
        3. Compute separability score (σ):
           - If overlapping: σ = (context_separation × token_coverage)
           - If complementary: σ = 1.0 (perfect separation)

        High σ (near 1.0) indicates complementary distribution (likely allophones).
        Low σ (near 0.0) indicates overlapping distribution (likely contrastive).

        Returns:
            Tuple of (score, shared_count, exclusive1_count, exclusive2_count)
        """
        # Step 1: Partition contexts into shared vs. exclusive sets
        shared = contexts1 & contexts2  # Contexts where both segments appear
        exclusive1 = contexts1 - contexts2  # Contexts unique to segment1
        exclusive2 = contexts2 - contexts1  # Contexts unique to segment2

        S = len(shared)  # Number of overlapping contexts
        Ex = len(exclusive1)  # Number of exclusive contexts for segment1
        Ey = len(exclusive2)  # Number of exclusive contexts for segment2

        # Step 2: Calculate total token counts for each segment
        # (tokens = actual word occurrences, not just unique contexts)
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

        # Step 3: Calculate exclusive coverage (Cx, Cy)
        # Coverage = fraction of tokens appearing in exclusive contexts
        # High coverage means most occurrences are in non-overlapping environments
        exclusive1_tokens = sum(
            len(words)
            for env_type, contexts_map in env1.items()
            for ctx, words in contexts_map.items()
            if f"{env_type}:{ctx}" in exclusive1
        )
        exclusive2_tokens = sum(
            len(words)
            for env_type, contexts_map in env2.items()
            for ctx, words in contexts_map.items()
            if f"{env_type}:{ctx}" in exclusive2
        )

        Cx = exclusive1_tokens / total1 if total1 > 0 else 0
        Cy = exclusive2_tokens / total2 if total2 > 0 else 0

        # Step 4: Compute separability score (σ)
        # σ balances two factors:
        #   - Context separation: (Ex + Ey) / (S + Ex + Ey + 1)
        #     Higher when more contexts are exclusive vs. shared
        #   - Token coverage: (Cx + Cy) / 2
        #     Higher when most tokens appear in exclusive contexts
        if S > 0:
            # If there are shared contexts, penalize by weighting exclusive coverage
            # Example: If S=10, Ex=5, Ey=5, Cx=0.8, Cy=0.7
            #   → σ = (10/21) × (0.75) ≈ 0.36 (moderate overlap)
            sigma = ((Ex + Ey) / (S + Ex + Ey + 1)) * ((Cx + Cy) / 2)
        else:
            # No shared contexts = perfect complementary distribution
            # Example: Ex=15, Ey=12, S=0 → σ = 1.0 (allophones)
            sigma = 1.0 if (Ex > 0 or Ey > 0) else 0.0

        return sigma, S, Ex, Ey

    def _compute_complexity_penalty(
        self, window: int, alpha: float = 0.5
    ) -> float:
        """Compute complexity penalty for window size.

        Wider context windows (L2/L1/R1/R2) capture more detail but risk
        overfitting to incidental differences. This penalty discourages
        unnecessarily wide windows unless they provide significantly better
        separability.

        Formula: π = 1 / (1 + α × (window - 1))

        Examples (α=0.5):
        - window=1 (L1/R1): π = 1.0 (no penalty, simplest)
        - window=2 (L2/L1/R1/R2): π = 0.67 (moderate penalty)
        - window=3 (L3/.../R3): π = 0.5 (strong penalty, rarely worth it)

        Args:
            window: Window size (1, 2, or 3)
            alpha: Penalty weight (0.5 = moderate, higher = stronger penalty)

        Returns:
            Penalty multiplier in [0, 1], lower for wider windows
        """
        return 1.0 / (1.0 + alpha * (window - 1))

    def _analyze_with_progressive_window(
        self,
        pair: AlternationPair,
        max_window: int = 2,
        threshold: float = 0.6,
        words1: Optional[List[str]] = None,
        words2: Optional[List[str]] = None,
    ) -> AlternationResult:
        """Analyze alternation with progressive window widening.

        AUTO-WINDOW ALGORITHM:
        ----------------------
        This algorithm automatically finds the optimal context window size
        for alternation analysis, balancing detail vs. overfitting.

        Process:
        1. Start with simplest window (W=1: L1/R1 only)
        2. Compute separability score σ (how well segments separate)
        3. Apply complexity penalty π (discourages wider windows)
        4. Calculate decision score: D = σ × π
        5. If D ≥ threshold (0.6), accept this window and stop
        6. Otherwise, try wider window (W=2: L2/L1/R1/R2)
        7. Return window with best D score

        Decision Examples:
        - D=0.75: Strong complementary distribution at this window → ACCEPT
        - D=0.45: Weak separation, try wider window → CONTINUE
        - D=0.30: Overlapping distribution even with detail → CONTRASTIVE

        Args:
            pair: Alternation pair to analyze
            max_window: Maximum window size (1-3)
            threshold: Decision score threshold (default 0.6)
            words1: Optional word list for segment1 (for pair filtering)
            words2: Optional word list for segment2 (for pair filtering)

        Returns:
            AlternationResult with best window and decision metadata
        """
        from analyze import IPAConfig, IPAProcessorV2

        # Define window progression: start simple, gradually add detail
        # W=1: L1/R1 (immediate neighbors only)
        # W=2: L2/L1/R1/R2 (extends to second neighbor on left)
        # W=3: L3/.../R3 (full context, rarely needed)
        windows_to_try = [(1, "L1/R1")]
        if max_window >= 2:
            windows_to_try.append((2, "L2-left"))
        if max_window >= 3:
            windows_to_try.append((3, "L2/L1/R1"))

        best_result = None
        best_score = 0  # Track highest D score across all windows

        # Progressive window widening: try each window in sequence
        for window_size, window_label in windows_to_try:
            # Step 1: Configure analyzer for this context window
            config = IPAConfig(
                match_mode="narrow",
                context_window=window_size,
            )
            self.analyzer.ipa_processor_v2 = IPAProcessorV2(config)

            # Step 2: Analyze both segments at this window level
            # (with optional word filtering for morphological alternations)
            env1 = self.analyzer.analyze_character(
                pair.segment1, str(self.dataset_path), word_list=words1
            )
            env2 = self.analyzer.analyze_character(
                pair.segment2, str(self.dataset_path), word_list=words2
            )

            # Step 3: Build unified context sets for comparison
            # Format: "env_type:context" (e.g., "MEDIAL V_V:V_V", "INITIAL:#_V")
            contexts1 = set()
            contexts2 = set()

            for env_type, contexts in env1.items():
                for context in contexts.keys():
                    contexts1.add(f"{env_type}:{context}")

            for env_type, contexts in env2.items():
                for context in contexts.keys():
                    contexts2.add(f"{env_type}:{context}")

            # Step 4: Compute separability score (σ)
            # How well do the segments separate into exclusive contexts?
            sigma, S, Ex, Ey = self._compute_separability_score(
                contexts1, contexts2, env1, env2
            )

            # Step 5: Apply complexity penalty (π)
            # Penalize wider windows to avoid overfitting
            pi = self._compute_complexity_penalty(window_size)

            # Step 6: Calculate decision score (D = σ × π)
            # High D = good separation with reasonable complexity
            D = sigma * pi

            # Step 7: Track best result (highest D score)
            # Even if D < threshold, keep best window as fallback
            if D > best_score:
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

                pattern, analysis = self._analyze_distribution_pattern(
                    pair, env1, env2, auto_window=False
                )

                best_result = AlternationResult(
                    pair=pair,
                    segment1_envs=env1,
                    segment2_envs=env2,
                    segment1_total=total1,
                    segment2_total=total2,
                    source_file=str(self.dataset_path),
                    pattern=pattern,
                    analysis=f"[Window: {window_label}, D={D:.2f}] {analysis}",
                )
                best_score = D

            # Check if threshold met
            if D >= threshold:
                # Add window metadata to analysis
                best_result.analysis = (
                    f"[Auto-window: {window_label}, D={D:.2f}≥{threshold}] "
                    + best_result.analysis.split("] ", 1)[-1]
                    if "] " in best_result.analysis
                    else best_result.analysis
                )
                return best_result

        # No window met threshold - return best attempt with INCONCLUSIVE
        if best_result:
            best_result.pattern = "inconclusive"
            best_result.analysis = (
                f"[Auto-window: tried up to W={max_window}, best D={best_score:.2f}<{threshold}] "
                f"No window separated distributions with sufficient confidence."
            )

        return best_result

    def _analyze_distribution_pattern(
        self,
        pair: AlternationPair,
        env1: Mapping[str, Mapping[str, List[str]]],
        env2: Mapping[str, Mapping[str, List[str]]],
        min_occurrences: int = 3,
        min_contexts: int = 2,
        auto_window: bool = True,
        threshold: float = 0.6,
    ) -> Tuple[str, str]:
        """Analyze the distribution pattern of an alternation.

        Detects:
        - Complementary distribution (allophones)
        - Contrastive/overlapping (separate phonemes)
        - Free variation (interchangeable in same contexts)
        - Neutralization (contrast lost in specific positions)
        - Partial overlap (gradience)
        - Inconclusive (insufficient evidence)

        Args:
            pair: The alternation pair to analyze
            env1: Environments for segment 1
            env2: Environments for segment 2
            min_occurrences: Minimum total occurrences required for confident analysis
            min_contexts: Minimum number of contexts required per segment

        Returns:
            Tuple of (pattern_type, human_readable_analysis)
        """
        # Count total occurrences
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

        # Check for insufficient evidence
        if (
            total1 < min_occurrences
            or total2 < min_occurrences
            or len(contexts1) < min_contexts
            or len(contexts2) < min_contexts
        ):
            return (
                "inconclusive",
                f"Insufficient evidence for {pair.segment1} ~ {pair.segment2}. "
                f"{pair.segment1}: {total1} occurrences in {len(contexts1)} contexts; "
                f"{pair.segment2}: {total2} occurrences in {len(contexts2)} contexts. "
                f"Need at least {min_occurrences} occurrences and {min_contexts} contexts per segment.",
            )

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
