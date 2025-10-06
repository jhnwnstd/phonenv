"""Tests for regular target loading and processing."""

from pathlib import Path
from typing import Callable

import pytest

from data import TargetsProcessor


@pytest.mark.targets
class TestTargetLoading:
    """Test suite for loading regular targets from files."""

    def test_load_regular_targets(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test loading regular targets without alternations."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            kʰæt
            bæt
            sɪt
            zɪp
            pʰɪn
            spɪn
            æsk
            bæks
        """,
        )

        targets = targets_factory(
            "targets.txt",
            """
            s
            z
            p
            k
        """,
        )

        processor = TargetsProcessor(str(dataset), str(targets))
        target_list, alternation_list = processor.load_targets()

        assert (
            len(target_list) == 4
        ), f"Expected 4 targets, got {len(target_list)}"
        assert (
            len(alternation_list) == 0
        ), f"Expected 0 alternations, got {len(alternation_list)}"
        assert set(target_list) == {
            "s",
            "z",
            "p",
            "k",
        }, f"Target set mismatch: expected {{'s', 'z', 'p', 'k'}}, got {set(target_list)}"

    def test_load_targets_preserves_order(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test that target loading preserves file order."""
        dataset = dataset_factory("data.txt", "pɪn\nsɪt\n")
        targets = targets_factory("targets.txt", "p\ns\nk\nz\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        target_list, _ = processor.load_targets()

        assert target_list == [
            "p",
            "s",
            "k",
            "z",
        ], f"Target order not preserved: got {target_list}"


@pytest.mark.targets
class TestTargetProcessing:
    """Test suite for processing targets and analyzing environments."""

    def test_process_regular_targets(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test processing regular targets and environment detection."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            kʰæt
            bæt
            sɪt
            zɪp
            pʰɪn
            spɪn
            æsk
            bæks
        """,
        )

        targets = targets_factory("targets.txt", "s\nz\np\nk\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        assert len(results) == 4, f"Expected 4 results, got {len(results)}"

        # Verify result structure
        for result in results:
            assert hasattr(
                result, "target"
            ), "Result missing 'target' attribute"
            assert hasattr(
                result, "environments"
            ), "Result missing 'environments' attribute"
            assert hasattr(
                result, "total_occurrences"
            ), "Result missing 'total_occurrences' attribute"

    @pytest.mark.parametrize(
        "target,expected_envs",
        [
            ("s", {"INITIAL", "FINAL"}),
            ("p", {"INITIAL"}),
            ("k", {"FINAL"}),  # k appears in final position in æsk and bæks
        ],
    )
    def test_environment_detection(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        target: str,
        expected_envs: set,
    ):
        """Test that specific targets appear in expected environments."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            pɪn
            sɪt
            æsk
            bæks
            spɪn
        """,
        )

        targets = targets_factory("targets.txt", "s\np\nk\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        target_result = next((r for r in results if r.target == target), None)
        assert (
            target_result is not None
        ), f"No result found for target '{target}'"

        actual_envs = set(target_result.environments.keys())
        assert expected_envs.issubset(
            actual_envs
        ), f"Target '{target}': expected environments {expected_envs}, got {actual_envs}"

    def test_medial_environment_classification(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
    ):
        """Test medial environment classification (V_V, V_C, C_V, C_C)."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            asa
            ask
            ksa
            ksk
        """,
        )

        targets = targets_factory("targets.txt", "s\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        s_result = next((r for r in results if r.target == "s"), None)
        assert s_result is not None, "No result for 's'"

        # Should have medial environments
        medial_envs = {
            k for k in s_result.environments.keys() if "MEDIAL" in k
        }
        assert (
            len(medial_envs) > 0
        ), f"No medial environments found for 's': {s_result.environments.keys()}"
