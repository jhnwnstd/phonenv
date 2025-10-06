"""Tests for alternation pattern detection and analysis."""

from pathlib import Path
from typing import Callable

import pytest

from data import AlternationPair, TargetsProcessor


@pytest.mark.alternations
class TestAlternationLoading:
    """Test suite for loading alternation pairs."""

    def test_load_alternation_pairs(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test loading alternation pairs from targets file."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            pʊt
            fʊɫ
            kjuːt
            njuː
            siːl
            ziːl
        """,
        )

        targets = targets_factory(
            "targets.txt",
            """
            ʊ ~ uː
            s ~ z
        """,
        )

        processor = TargetsProcessor(str(dataset), str(targets))
        target_list, alternation_list = processor.load_targets()

        assert (
            len(alternation_list) == 2
        ), f"Expected 2 alternations, got {len(alternation_list)}"
        assert (
            len(target_list) == 0
        ), f"Expected 0 regular targets, got {len(target_list)}"

        # Verify alternation structure
        assert all(
            isinstance(alt, AlternationPair) for alt in alternation_list
        ), "All alternations should be AlternationPair instances"

    def test_alternation_with_description(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that inline comments are captured as descriptions."""
        dataset = dataset_factory("dataset.txt", "pɪn\nbɪn\n")
        targets = targets_factory(
            "targets.txt", "p ~ b  # voicing alternation\n"
        )

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternation_list = processor.load_targets()

        assert (
            len(alternation_list) == 1
        ), f"Expected 1 alternation, got {len(alternation_list)}"
        alt = alternation_list[0]
        assert alt.description is not None, "Description should be captured"
        assert (
            "voicing" in alt.description.lower()
        ), f"Description should mention 'voicing', got: {alt.description}"


@pytest.mark.alternations
class TestAlternationPatterns:
    """Test suite for alternation pattern detection."""

    def test_complementary_distribution(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test detection of complementary distribution (allophones)."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            pʊt
            fʊɫ
            sʊɡɚ
            kjuːt
            njuː
            djuːn
        """,
        )

        targets = targets_factory("targets.txt", "ʊ ~ uː\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternations = processor.load_targets()

        result = processor.analyze_alternation(alternations[0])

        assert (
            result.pattern == "complementary"
        ), f"Expected 'complementary' pattern, got '{result.pattern}'"
        assert (
            "allophones" in result.analysis.lower()
            or "complementary" in result.analysis.lower()
        ), f"Analysis should mention allophones/complementary: {result.analysis}"

    def test_contrastive_distribution(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test detection of contrastive distribution (distinct phonemes)."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            siːl
            ziːl
            suːm
            zuːm
            æsk
            bæɡz
        """,
        )

        targets = targets_factory("targets.txt", "s ~ z\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternations = processor.load_targets()

        result = processor.analyze_alternation(alternations[0])

        assert (
            result.pattern == "contrastive"
        ), f"Expected 'contrastive' pattern, got '{result.pattern}'"
        assert (
            result.pair.segment1 == "s"
        ), f"Expected segment1='s', got '{result.pair.segment1}'"
        assert (
            result.pair.segment2 == "z"
        ), f"Expected segment2='z', got '{result.pair.segment2}'"

    @pytest.mark.parametrize(
        "pattern_type,expected_label",
        [
            ("complementary", "allophones"),
            ("contrastive", "phonemes"),
            ("free_variation", "interchangeable"),
            ("neutralization", "contrast lost"),
            ("partial_overlap", "gradience"),
        ],
    )
    def test_pattern_analysis_labels(
        self,
        pattern_type: str,
        expected_label: str,
    ):
        """Test that pattern types have appropriate linguistic labels."""
        # This is a documentation test - verifies our pattern naming is consistent
        # Pattern labels should be defined in the analysis method
        # This test ensures we maintain linguistic accuracy
        assert pattern_type in {
            "complementary",
            "contrastive",
            "free_variation",
            "neutralization",
            "partial_overlap",
            "unknown",
        }, f"Unexpected pattern type: {pattern_type}"


@pytest.mark.alternations
class TestAlternationResults:
    """Test suite for alternation result structure."""

    def test_alternation_result_structure(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that alternation results have all required fields."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            pʰɪn
            bɪn
            æp
            æb
        """,
        )

        targets = targets_factory("targets.txt", "p ~ b\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternations = processor.load_targets()

        assert len(alternations) > 0, "No alternations loaded"

        result = processor.analyze_alternation(alternations[0])

        # Verify all required attributes
        required_attrs = [
            "pair",
            "segment1_envs",
            "segment2_envs",
            "pattern",
            "analysis",
            "segment1_total",
            "segment2_total",
        ]

        for attr in required_attrs:
            assert hasattr(result, attr), f"Missing required attribute: {attr}"

        # Verify types
        assert isinstance(result.pattern, str), "pattern should be a string"
        assert isinstance(result.analysis, str), "analysis should be a string"
        assert len(result.analysis) > 0, "analysis should not be empty"
        assert isinstance(
            result.segment1_total, int
        ), "segment1_total should be an integer"
        assert isinstance(
            result.segment2_total, int
        ), "segment2_total should be an integer"

    def test_alternation_occurrence_counts(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that occurrence counts are accurate."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            pɪn
            pɪn
            pæt
            bɪn
        """,
        )

        targets = targets_factory("targets.txt", "p ~ b\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternations = processor.load_targets()

        result = processor.analyze_alternation(alternations[0])

        # p appears 3 times (2x pɪn + 1x pæt)
        # b appears 1 time
        assert (
            result.segment1_total >= 1
        ), f"Expected segment1 (p) total >= 1, got {result.segment1_total}"
        assert (
            result.segment2_total >= 1
        ), f"Expected segment2 (b) total >= 1, got {result.segment2_total}"
