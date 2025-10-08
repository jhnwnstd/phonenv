"""Phonological alternation analysis.

IMPORT RULES:
- Can import: models, analyze
- Cannot import: processors, output, cli, data, parsers
- Keep stateless: analyzer is injected, no file I/O
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Mapping, Set, Tuple, List, Optional, Dict, Any

from models import AlternationPair, AlternationResult, StructuralAlternationResult

if TYPE_CHECKING:
    from analyze import PhoneticAnalyzer


class AlternationAnalyzer:
    """Analyzes phonological alternations (stateless/functional).

    Design: This class contains ONLY analysis logic.
    - NO file I/O (delegate to processors)
    - NO caching (delegate to output layer)
    - Pure functions where possible
    """

    def __init__(self, phonetic_analyzer: PhoneticAnalyzer):
        """Initialize with injected analyzer dependency."""
        self.analyzer = phonetic_analyzer

    def analyze(
        self,
        pair: AlternationPair,
        words1: Optional[List[str]] = None,
        words2: Optional[List[str]] = None,
        dataset_path: str = "",
        auto_window: bool = True,
        max_window: int = 2,
        threshold: float = 0.6,
    ) -> AlternationResult | StructuralAlternationResult:
        """Main entry point for alternation analysis.

        Args:
            pair: Alternation pair to analyze
            words1: Optional filtered word list for segment1
            words2: Optional filtered word list for segment2
            dataset_path: Path to dataset (for result metadata)
            auto_window: If True, use progressive window widening
            max_window: Maximum window size (1-3)
            threshold: Decision score threshold

        Returns:
            AlternationResult or StructuralAlternationResult
        """
        # Route to structural analysis for Ø alternations
        if pair.segment1 == "" or pair.segment2 == "":
            return self.analyze_structural(pair, words1, words2, dataset_path)

        # Standard phonemic analysis
        if auto_window:
            return self._analyze_with_progressive_window(
                pair, max_window, threshold, words1, words2, dataset_path
            )
        else:
            return self._analyze_phonemic(pair, words1, words2, dataset_path)

    def analyze_structural(
        self,
        pair: AlternationPair,
        words1: Optional[List[str]],
        words2: Optional[List[str]],
        dataset_path: str,
    ) -> StructuralAlternationResult:
        """Analyze structural alternations (X ~ Ø)."""
        # Determine which is present/absent
        if pair.segment1 == "":
            present_seg, absent_seg = pair.segment2, pair.segment1
            present_words = words2
        else:
            present_seg, absent_seg = pair.segment1, pair.segment2
            present_words = words1

        # Analyze the present segment
        envs = self.analyzer.analyze_character(present_seg, dataset_path, word_list=present_words)
        total = sum(len(w) for group in envs.values() for w in group.values())

        # Classify structural process
        process, process_type, analysis = self._classify_structural_process(
            present_seg, envs
        )

        return StructuralAlternationResult(
            pair=pair,
            present_segment=present_seg,
            absent_segment=absent_seg,
            present_envs=envs,
            present_total=total,
            process=process,
            process_type=process_type,
            analysis=analysis,
            source_file=dataset_path,
        )

    def _analyze_phonemic(
        self,
        pair: AlternationPair,
        words1: Optional[List[str]],
        words2: Optional[List[str]],
        dataset_path: str,
    ) -> AlternationResult:
        """Analyze phonemic alternation at current window."""
        env1 = self.analyzer.analyze_character(pair.segment1, dataset_path, word_list=words1)
        env2 = self.analyzer.analyze_character(pair.segment2, dataset_path, word_list=words2)

        total1 = sum(len(words) for env_group in env1.values() for words in env_group.values())
        total2 = sum(len(words) for env_group in env2.values() for words in env_group.values())

        pattern, analysis = self._analyze_distribution_pattern(pair, env1, env2)

        return AlternationResult(
            pair=pair,
            segment1_envs=env1,
            segment2_envs=env2,
            segment1_total=total1,
            segment2_total=total2,
            source_file=dataset_path,
            pattern=pattern,
            analysis=analysis,
        )

    def _analyze_with_progressive_window(
        self,
        pair: AlternationPair,
        max_window: int,
        threshold: float,
        words1: Optional[List[str]],
        words2: Optional[List[str]],
        dataset_path: str,
    ) -> AlternationResult:
        """Analyze with progressive window widening (auto-window algorithm)."""
        from analyze import IPAConfig, IPAProcessorV2

        windows_to_try = [(1, "L1/R1")]
        if max_window >= 2:
            windows_to_try.append((2, "L2-left"))
        if max_window >= 3:
            windows_to_try.append((3, "L2/L1/R1"))

        best_result = None
        best_score = 0

        for window_size, window_label in windows_to_try:
            config = IPAConfig(match_mode="narrow", context_window=window_size)
            self.analyzer.ipa_processor_v2 = IPAProcessorV2(config)

            env1 = self.analyzer.analyze_character(pair.segment1, dataset_path, word_list=words1)
            env2 = self.analyzer.analyze_character(pair.segment2, dataset_path, word_list=words2)

            contexts1 = self._build_context_set(env1)
            contexts2 = self._build_context_set(env2)

            sigma, S, Ex, Ey = self.compute_separability_score(contexts1, contexts2, env1, env2)
            pi = self.compute_complexity_penalty(window_size)
            D = sigma * pi

            if D > best_score:
                total1 = sum(len(words) for env_group in env1.values() for words in env_group.values())
                total2 = sum(len(words) for env_group in env2.values() for words in env_group.values())

                pattern, analysis = self._analyze_distribution_pattern(pair, env1, env2, auto_window=False)

                best_result = AlternationResult(
                    pair=pair,
                    segment1_envs=env1,
                    segment2_envs=env2,
                    segment1_total=total1,
                    segment2_total=total2,
                    source_file=dataset_path,
                    pattern=pattern,
                    analysis=f"[Window: {window_label}, D={D:.2f}] {analysis}",
                    window_size=window_size,
                    decision_score=D,
                )
                best_score = D

            if D >= threshold:
                break

        return best_result or self._analyze_phonemic(pair, words1, words2, dataset_path)

    @staticmethod
    def _build_context_set(envs: Mapping[str, Mapping[str, List[str]]]) -> Set[str]:
        """Build unified context set from environments."""
        contexts = set()
        for env_type, contexts_map in envs.items():
            for context in contexts_map.keys():
                contexts.add(f"{env_type}:{context}")
        return contexts

    @staticmethod
    def compute_separability_score(
        contexts1: Set[str],
        contexts2: Set[str],
        env1: Mapping[str, Mapping[str, List[str]]],
        env2: Mapping[str, Mapping[str, List[str]]],
    ) -> Tuple[float, int, int, int]:
        """Compute separability score for alternation pair."""
        shared = contexts1 & contexts2
        exclusive1 = contexts1 - contexts2
        exclusive2 = contexts2 - contexts1

        S = len(shared)
        Ex = len(exclusive1)
        Ey = len(exclusive2)

        total1 = sum(len(words) for env_group in env1.values() for words in env_group.values())
        total2 = sum(len(words) for env_group in env2.values() for words in env_group.values())

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

        if S > 0:
            sigma = ((Ex + Ey) / (S + Ex + Ey + 1)) * ((Cx + Cy) / 2)
        else:
            sigma = 1.0 if (Ex > 0 or Ey > 0) else 0.0

        return sigma, S, Ex, Ey

    @staticmethod
    def compute_complexity_penalty(window: int, alpha: float = 0.5) -> float:
        """Compute complexity penalty for window size."""
        return 1.0 / (1.0 + alpha * (window - 1))

    def _analyze_distribution_pattern(
        self,
        pair: AlternationPair,
        env1: Mapping[str, Mapping[str, List[str]]],
        env2: Mapping[str, Mapping[str, List[str]]],
        auto_window: bool = True,
    ) -> Tuple[str, str]:
        """Analyze distribution pattern between two segments."""
        contexts1 = self._build_context_set(env1)
        contexts2 = self._build_context_set(env2)

        shared = contexts1 & contexts2
        exclusive1 = contexts1 - contexts2
        exclusive2 = contexts2 - contexts1

        total1 = sum(len(words) for env_group in env1.values() for words in env_group.values())
        total2 = sum(len(words) for env_group in env2.values() for words in env_group.values())

        if total1 == 0 or total2 == 0:
            return "inconclusive", f"Insufficient data: {pair.segment1}={total1}, {pair.segment2}={total2}"

        if not shared:
            return "complementary", f"Perfect complementary distribution (allophones): {pair.segment1} and {pair.segment2} never occur in the same environments"

        overlap_ratio = len(shared) / (len(contexts1 | contexts2))

        if overlap_ratio > 0.7:
            return "contrastive", f"High context overlap ({overlap_ratio:.1%}): {pair.segment1} and {pair.segment2} are likely distinct phonemes"

        if overlap_ratio < 0.3:
            return "partial_overlap", f"Mostly separate ({overlap_ratio:.1%} overlap): partial complementary distribution with some free variation"

        return "neutralization", f"Moderate overlap ({overlap_ratio:.1%}): possible neutralization or conditional alternation"

    def _classify_structural_process(
        self,
        segment: str,
        envs: Mapping[str, Mapping[str, List[str]]],
    ) -> Tuple[str, str, str]:
        """Classify structural process (prothesis, epenthesis, etc.)."""
        initial = "INITIAL" in envs and len(envs.get("INITIAL", {})) > 0
        final = "FINAL" in envs and len(envs.get("FINAL", {})) > 0
        medial = any(k.startswith("MEDIAL") for k in envs.keys())

        if initial and not final and not medial:
            return "prothesis", "insertion", f"Prothesis: {segment} appears only word-initially"
        elif final and not initial and not medial:
            return "paragoge", "insertion", f"Paragoge: {segment} appears only word-finally"
        elif medial and not initial and not final:
            return "epenthesis", "insertion", f"Epenthesis: {segment} appears only word-medially"
        elif initial and medial and final:
            return "deletion", "deletion", f"Deletion: {segment} can be deleted in various positions"
        else:
            return "structural", "alternation", f"Structural alternation: {segment} ~ Ø in multiple environments"


__all__ = ["AlternationAnalyzer"]
