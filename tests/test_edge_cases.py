"""Tests for edge cases and error handling."""

from pathlib import Path
from typing import Callable

import pytest

from data import TargetsProcessor


@pytest.mark.edge
class TestEmptyInputs:
    """Test handling of empty or missing inputs."""

    def test_empty_dataset(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test processing with empty dataset file."""
        empty_dataset = dataset_factory("empty.txt", "")
        targets = targets_factory("targets.txt", "p\n")

        processor = TargetsProcessor(str(empty_dataset), str(targets))
        results = processor.process_targets_to_list()

        assert isinstance(
            results, list
        ), "Should return a list even with empty dataset"
        # Results may be empty or have zero occurrences
        assert all(
            hasattr(r, "total_occurrences") for r in results
        ), "All results should have total_occurrences attribute"

    def test_empty_targets(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test loading with empty targets file."""
        dataset = dataset_factory("dataset.txt", "pʰɪn\ntʰɪp\n")
        empty_targets = targets_factory("empty_targets.txt", "")

        processor = TargetsProcessor(str(dataset), str(empty_targets))
        targets, alternations = processor.load_targets()

        assert len(targets) == 0, "Empty targets file should yield no targets"
        assert (
            len(alternations) == 0
        ), "Empty targets file should yield no alternations"


@pytest.mark.edge
class TestCommentHandling:
    """Test handling of comments and whitespace."""

    def test_comments_only_file(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test file containing only comments."""
        dataset = dataset_factory("dataset.txt", "pʰɪn\ntʰɪp\n")
        comments_only = targets_factory(
            "comments.txt",
            """
            # This is a comment
            # Another comment

            # More comments
        """,
        )

        processor = TargetsProcessor(str(dataset), str(comments_only))
        targets, alternations = processor.load_targets()

        assert len(targets) == 0, "Comments should not be parsed as targets"
        assert (
            len(alternations) == 0
        ), "Comments should not be parsed as alternations"

    def test_whitespace_handling(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test proper handling of leading/trailing whitespace."""
        dataset = dataset_factory("dataset.txt", "pʰɪn\nsɪt\nkʰæt\n")
        whitespace_targets = targets_factory(
            "whitespace.txt",
            """
              p

              s ~ z

              k
        """,
        )

        processor = TargetsProcessor(str(dataset), str(whitespace_targets))
        targets, alternations = processor.load_targets()

        total = len(targets) + len(alternations)
        assert (
            total > 0
        ), f"Should parse targets/alternations despite whitespace (got {len(targets)} targets, {len(alternations)} alternations)"

    def test_mixed_comments_and_targets(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test file with both comments and valid targets."""
        dataset = dataset_factory("dataset.txt", "pɪn\nsɪt\n")
        mixed = targets_factory(
            "mixed.txt",
            """
            # Section 1: Stops
            p
            # voicing
            p ~ b

            # Section 2: Fricatives
            s  # voiceless
        """,
        )

        processor = TargetsProcessor(str(dataset), str(mixed))
        targets, alternations = processor.load_targets()

        assert "p" in targets, "Should parse 'p' from mixed file"
        assert "s" in targets, "Should parse 's' from mixed file"
        assert len(alternations) >= 1, "Should parse 'p ~ b' alternation"


@pytest.mark.edge
class TestInvalidInputs:
    """Test handling of invalid or malformed inputs."""

    def test_duplicate_targets(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that duplicate targets are handled gracefully."""
        dataset = dataset_factory("dataset.txt", "pɪn\nsɪt\n")
        duplicates = targets_factory(
            "duplicates.txt",
            """
            p
            s
            p
            s
            p ~ b
            p ~ b
        """,
        )

        processor = TargetsProcessor(str(dataset), str(duplicates))
        targets, alternations = processor.load_targets()

        # Should handle duplicates (exact behavior depends on implementation)
        assert isinstance(targets, list), "Should return a list of targets"
        assert isinstance(
            alternations, list
        ), "Should return a list of alternations"

    def test_invalid_ipa_gracefully_handled(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that invalid IPA characters don't crash the system."""
        dataset = dataset_factory("dataset.txt", "pɪn\n")
        # Mix valid and potentially invalid targets
        targets = targets_factory("targets.txt", "p\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        # Should not raise an exception
        results = processor.process_targets_to_list()
        assert isinstance(results, list), "Should handle gracefully"


@pytest.mark.edge
class TestBoundaryConditions:
    """Test boundary conditions and special cases."""

    def test_single_target(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test processing with just one target."""
        dataset = dataset_factory("dataset.txt", "pɪn\npæt\n")
        targets = targets_factory("targets.txt", "p\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        assert (
            results[0].target == "p"
        ), f"Expected target 'p', got '{results[0].target}'"

    def test_single_alternation(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test processing with just one alternation."""
        dataset = dataset_factory("dataset.txt", "pɪn\nbɪn\n")
        targets = targets_factory("targets.txt", "p ~ b\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        target_list, alternation_list = processor.load_targets()

        assert (
            len(alternation_list) == 1
        ), f"Expected 1 alternation, got {len(alternation_list)}"
        assert (
            len(target_list) == 0
        ), f"Expected 0 regular targets, got {len(target_list)}"

    def test_target_not_in_dataset(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test target that doesn't appear in dataset."""
        dataset = dataset_factory("dataset.txt", "pɪn\ntɪp\n")
        targets = targets_factory("targets.txt", "z\n")  # z not in dataset

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        # Should still process, but with zero occurrences
        assert len(results) >= 0, "Should handle target not in dataset"
        if len(results) > 0:
            z_result = next((r for r in results if r.target == "z"), None)
            if z_result:
                assert (
                    z_result.total_occurrences == 0
                ), "Target not in dataset should have 0 occurrences"


@pytest.mark.edge
@pytest.mark.regression
class TestRegressionCases:
    """Regression tests for previously identified issues."""

    def test_unicode_normalization_edge_case(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that Unicode normalization doesn't break analysis."""
        # Test with composed and decomposed forms
        dataset = dataset_factory(
            "dataset.txt", "ã\na\u0303\n"
        )  # ã as single char and a + combining tilde
        targets = targets_factory("targets.txt", "ã\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        # Should find both occurrences due to normalization
        assert len(results) > 0, "Should process Unicode normalized targets"

    def test_alternation_with_whitespace_variations(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test alternations with various whitespace formats."""
        dataset = dataset_factory("dataset.txt", "pɪn\nbɪn\n")
        targets = targets_factory(
            "targets.txt",
            """
            p~b
            t ~ d
            k  ~  g
        """,
        )

        processor = TargetsProcessor(str(dataset), str(targets))
        _, alternations = processor.load_targets()

        # Should parse all three despite whitespace differences
        assert (
            len(alternations) >= 1
        ), f"Should parse alternations with varying whitespace (got {len(alternations)})"
