"""Tests for core data structures and dataclasses."""

from pathlib import Path
from typing import Callable

import pytest

from data import AlternationPair, TargetsProcessor


@pytest.mark.targets
class TestAlternationPairDataclass:
    """Test suite for AlternationPair dataclass."""

    def test_alternation_pair_creation(self):
        """Test creating an AlternationPair."""
        pair = AlternationPair("p", "b", "voicing")

        assert pair is not None, "AlternationPair creation failed"
        assert (
            pair.segment1 == "p"
        ), f"Expected segment1='p', got '{pair.segment1}'"
        assert (
            pair.segment2 == "b"
        ), f"Expected segment2='b', got '{pair.segment2}'"
        assert (
            pair.description == "voicing"
        ), f"Expected description='voicing', got '{pair.description}'"

    def test_alternation_pair_without_description(self):
        """Test creating AlternationPair without description (optional)."""
        pair = AlternationPair("s", "z")

        assert pair.segment1 == "s", "segment1 should be 's'"
        assert pair.segment2 == "z", "segment2 should be 'z'"
        assert (
            pair.description is None
        ), "description should be None when not provided"

    def test_alternation_pair_immutable(self):
        """Test that AlternationPair is frozen (immutable)."""
        pair = AlternationPair("p", "b")

        with pytest.raises(AttributeError):
            pair.segment1 = "t"  # Should raise because frozen=True

    def test_alternation_pair_hashable(self):
        """Test that AlternationPair is hashable (can be used in sets/dicts)."""
        pair1 = AlternationPair("p", "b")
        pair2 = AlternationPair("p", "b")
        pair3 = AlternationPair("t", "d")

        # Should be hashable
        assert isinstance(
            hash(pair1), int
        ), "AlternationPair should be hashable"

        # Can be used in sets
        pair_set = {pair1, pair2, pair3}
        assert len(pair_set) == 2, "Identical pairs should deduplicate in sets"

    def test_alternation_pair_equality(self):
        """Test equality comparison for AlternationPair."""
        pair1 = AlternationPair("p", "b", "voicing")
        pair2 = AlternationPair("p", "b", "voicing")
        pair3 = AlternationPair("p", "b", "different description")
        pair4 = AlternationPair("t", "d")

        assert pair1 == pair2, "Identical pairs should be equal"
        assert (
            pair1 != pair3
        ), "Pairs with different descriptions should not be equal"
        assert pair1 != pair4, "Different pairs should not be equal"


@pytest.mark.alternations
class TestAlternationResultStructure:
    """Test suite for AlternationResult structure and fields."""

    def test_alternation_result_required_fields(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that AlternationResult has all required fields."""
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

        # Verify all required attributes exist
        required_attrs = {
            "pair": AlternationPair,
            "segment1_envs": dict,
            "segment2_envs": dict,
            "pattern": str,
            "analysis": str,
            "segment1_total": int,
            "segment2_total": int,
            "source_file": str,
        }

        for attr, expected_type in required_attrs.items():
            assert hasattr(result, attr), f"Missing required attribute: {attr}"

            value = getattr(result, attr)
            if expected_type == dict:
                # segment_envs can be dict or Mapping
                assert hasattr(
                    value, "keys"
                ), f"{attr} should be dict-like, got {type(value)}"
            else:
                assert isinstance(
                    value, expected_type
                ), f"{attr} should be {expected_type.__name__}, got {type(value).__name__}"

    def test_alternation_result_pattern_values(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that pattern field contains valid pattern types."""
        dataset = dataset_factory("dataset.txt", "pɪn\nbɪn\n")
        targets = targets_factory("targets.txt", "p ~ b\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternations = processor.load_targets()

        result = processor.analyze_alternation(alternations[0])

        valid_patterns = {
            "complementary",
            "contrastive",
            "free_variation",
            "neutralization",
            "partial_overlap",
            "unknown",
            "overlapping",  # legacy
            "identical",  # legacy
        }

        assert (
            result.pattern in valid_patterns
        ), f"Invalid pattern '{result.pattern}'. Expected one of: {valid_patterns}"

    def test_alternation_result_analysis_non_empty(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that analysis field is populated with meaningful text."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            siːl
            ziːl
            suːm
            zuːm
        """,
        )

        targets = targets_factory("targets.txt", "s ~ z\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternations = processor.load_targets()

        result = processor.analyze_alternation(alternations[0])

        assert len(result.analysis) > 0, "Analysis text should not be empty"
        assert (
            len(result.analysis) > 10
        ), f"Analysis should be meaningful (got {len(result.analysis)} chars): {result.analysis}"

        # Should contain at least one of the segment names
        assert (
            result.pair.segment1 in result.analysis
            or result.pair.segment2 in result.analysis
        ), "Analysis should mention the segments being analyzed"


@pytest.mark.targets
class TestResultDataStructure:
    """Test suite for regular target result structure."""

    def test_target_result_structure(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that target results have proper structure."""
        dataset = dataset_factory("dataset.txt", "pɪn\npæt\næp\n")
        targets = targets_factory("targets.txt", "p\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        assert len(results) > 0, "Should have at least one result"

        result = results[0]

        # Verify required attributes
        assert hasattr(
            result, "target"
        ), "Result should have 'target' attribute"
        assert hasattr(
            result, "environments"
        ), "Result should have 'environments' attribute"
        assert hasattr(
            result, "total_occurrences"
        ), "Result should have 'total_occurrences' attribute"

        # Verify types
        assert isinstance(result.target, str), "target should be a string"
        assert hasattr(
            result.environments, "keys"
        ), "environments should be dict-like"
        assert isinstance(
            result.total_occurrences, int
        ), "total_occurrences should be an integer"

    def test_environment_structure(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that environment dictionaries have proper structure."""
        dataset = dataset_factory("dataset.txt", "pɪn\næp\n")
        targets = targets_factory("targets.txt", "p\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        result = results[0]

        # Environments should be a nested dictionary
        for env_name, env_data in result.environments.items():
            assert isinstance(
                env_name, str
            ), f"Environment name should be string, got {type(env_name)}"

            assert hasattr(
                env_data, "keys"
            ), f"Environment data for '{env_name}' should be dict-like"

            # Each environment contains contexts
            for context, examples in env_data.items():
                assert isinstance(
                    context, str
                ), f"Context should be string, got {type(context)}"
                assert isinstance(
                    examples, list
                ), f"Examples should be list, got {type(examples)}"
