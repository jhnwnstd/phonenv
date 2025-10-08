"""Data processors - orchestration layer.

IMPORT RULES:
- Can import: models, parsers, analyze, alternations
- Cannot import: output (to avoid cycles), cli, data
- Can do I/O (file reads, dataset loading)
"""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Tuple, Optional, Dict, Any

from pathlib import Path
from models import WordEntry, AlternationPair, TargetResult
from parsers import load_words_list, iter_word_entries, load_targets_file
from alternations import AlternationAnalyzer

if TYPE_CHECKING:
    from analyze import PhoneticAnalyzer


class DictionaryProcessor:
    """Manages phonetic dictionary operations."""

    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self._words_cache: Optional[List[str]] = None

    def get_words(self) -> List[str]:
        """Get words with caching."""
        if self._words_cache is None:
            self._words_cache = load_words_list(str(self.dataset_path))
        return self._words_cache

    def add_word(self, word: str) -> bool:
        """Add word to dataset."""
        words = self.get_words()
        if word in words:
            return False

        with self.dataset_path.open("a", encoding="utf-8") as f:
            f.write(f"\n{word}")

        self._words_cache = None  # Invalidate cache
        return True

    def remove_words_containing(self, substring: str) -> int:
        """Remove words containing substring."""
        words = self.get_words()
        filtered = [w for w in words if substring not in w]
        removed_count = len(words) - len(filtered)

        if removed_count > 0:
            with self.dataset_path.open("w", encoding="utf-8") as f:
                for word in filtered:
                    f.write(f"{word}\n")
            self._words_cache = None

        return removed_count

    def clear_all(self) -> int:
        """Clear entire dataset."""
        count = len(self.get_words())
        self.dataset_path.write_text("")
        self._words_cache = None
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        words = self.get_words()
        return {
            "word_count": len(words),
            "avg_length": sum(len(w) for w in words) / len(words) if words else 0,
            "unique_chars": len(set("".join(words))),
        }


class TargetsProcessor:
    """Processes targets and coordinates analysis."""

    def __init__(self, targets_path: str, dataset_path: str, analyzer: PhoneticAnalyzer):
        self.targets_path = Path(targets_path)
        self.dataset_path = Path(dataset_path)
        self.analyzer = analyzer
        self.alternation_analyzer = AlternationAnalyzer(analyzer)

    def load_targets(
        self, allow_null_segments: bool = True
    ) -> Tuple[List[str], List[AlternationPair]]:
        """Load targets and alternations from file."""
        return load_targets_file(str(self.targets_path), allow_null_segments)

    def analyze_target(self, target: str, word_list: Optional[List[str]] = None) -> TargetResult:
        """Analyze single target."""
        envs = self.analyzer.analyze_character(target, str(self.dataset_path), word_list=word_list)
        total = sum(len(w) for group in envs.values() for w in group.values())

        return TargetResult(
            target=target,
            environments=envs,
            total_occurrences=total,
            source_file=str(self.dataset_path),
            analysis_mode=getattr(self.analyzer, "mode", "narrow"),
        )

    def analyze_alternation(
        self,
        pair: AlternationPair,
        auto_window: bool = True,
        max_window: int = 2,
        threshold: float = 0.6,
    ):
        """Analyze alternation (delegates to alternation analyzer)."""
        # Get filtered words if pair has a filter
        words1, words2 = self._get_filtered_words(pair)

        return self.alternation_analyzer.analyze(
            pair,
            words1=words1,
            words2=words2,
            dataset_path=str(self.dataset_path),
            auto_window=auto_window,
            max_window=max_window,
            threshold=threshold,
        )

    def _get_filtered_words(self, pair: AlternationPair) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        """Get filtered word lists based on pair filter."""
        if not pair.pair_filter:
            return None, None

        # Parse pair filter like "sg:pl" or "1:2"
        parts = pair.pair_filter.split(":")
        if len(parts) != 2:
            return None, None

        tag1, tag2 = parts[0].strip(), parts[1].strip()

        # Load dataset with tags
        from parsers import load_words_with_tags

        tagged_words = load_words_with_tags(str(self.dataset_path))

        # Filter by tags
        words1 = [e.ipa for e in tagged_words if tag1 in e.tags]
        words2 = [e.ipa for e in tagged_words if tag2 in e.tags]

        return words1 if words1 else None, words2 if words2 else None

    def filter_by_tag(self, tagged_words: List[WordEntry], tag: str) -> List[str]:
        """Filter words by tag."""
        return [e.ipa for e in tagged_words if tag in e.tags]

    def load_dataset_with_tags(self) -> List[WordEntry]:
        """Load dataset with full metadata."""
        return list(iter_word_entries(str(self.dataset_path)))

    def process_targets_to_list(
        self,
        targets: List[str],
        alternations: List[AlternationPair],
        min_evidence: int = 3,
    ) -> Tuple[List[TargetResult], List[Any]]:
        """Process all targets and alternations to lists."""
        target_results = []
        for target in targets:
            result = self.analyze_target(target)
            if result.total_occurrences >= min_evidence or target in [t for t in targets]:
                target_results.append(result)

        alternation_results = []
        for pair in alternations:
            result = self.analyze_alternation(pair)
            alternation_results.append(result)

        return target_results, alternation_results


# Utility functions (kept for backward compatibility)

def create_sample_targets_file(targets_path: str = "data/targets.txt") -> None:
    """Create sample targets file with common IPA targets."""
    content = """# Common IPA targets for phonetic environment analysis
# Vowels
i, ɪ, e, ɛ, æ, a, ɑ, ɒ, ɔ, o, ʊ, u, ʌ, ə, ɚ, ɜ, ɞ, y, ʉ

# Consonants
p, t, k, b, d, ɡ
f, v, θ, ð, s, z, ʃ, ʒ, ç, ʝ, x, ɣ, χ, ʁ, ħ, ʕ, h, ɦ
m, n, ŋ, ɲ, ɳ, ɴ
l, ɫ, r, ɾ, ɹ, ɻ, ʀ
j, w, ɥ, ʋ

# Affricates (tie bar normalized to U+0361)
t͡s, d͡z, t͡ʃ, d͡ʒ, t͡ɕ, d͡ʑ, ʈ͡ʂ, ɖ͡ʐ

# Diacritic-bearing bases (broad mode may merge)
pʰ, tʰ, kʰ, s̪, n̪, l̩, n̩

# Common alternations (optional - use these for alternation analysis)
# p ~ b
# t ~ d
# k ~ ɡ
# s ~ z
"""
    Path(targets_path).write_text(content, encoding="utf-8")


def targets_exist(targets_path: str = "data/targets.txt") -> bool:
    """Check if targets file exists."""
    return Path(targets_path).exists()


__all__ = [
    "DictionaryProcessor",
    "TargetsProcessor",
    "create_sample_targets_file",
    "targets_exist",
]
