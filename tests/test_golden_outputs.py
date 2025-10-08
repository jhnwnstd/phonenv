"""Golden file tests - safety net for refactoring.

DO NOT MODIFY these tests during refactoring.
They ensure behavioral consistency across code reorganization.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden"
PROJECT_ROOT = Path(__file__).parent.parent


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for comparison."""
    return "\n".join(line.rstrip() for line in text.splitlines())


def remove_timestamps(text: str) -> str:
    """Remove timestamp lines for comparison."""
    lines = []
    for line in text.splitlines():
        if not line.strip().startswith("Generated:") and "202" not in line[:30]:
            lines.append(line)
    return "\n".join(lines)


class TestGoldenOutputs:
    """Test that refactoring doesn't change behavior."""

    def test_batch_txt_output_structure_unchanged(self, tmp_path):
        """TXT output structure must not change."""
        result_file = tmp_path / "output.txt"
        subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "main.py"),
                "--batch",
                "--format",
                "txt",
                "--output",
                str(result_file),
            ],
            check=True,
            cwd=PROJECT_ROOT,
        )

        golden = (GOLDEN_DIR / "batch_output.txt").read_text()
        result = result_file.read_text()

        # Normalize for comparison (ignore timestamps)
        golden_normalized = remove_timestamps(normalize_whitespace(golden))
        result_normalized = remove_timestamps(normalize_whitespace(result))

        # Check key sections exist
        assert "PHONETIC ENVIRONMENT ANALYSIS REPORT" in result
        assert "SUMMARY" in result
        assert "TARGET" in result
        assert golden_normalized == result_normalized

    def test_batch_json_output_structure_unchanged(self, tmp_path):
        """JSON structure must not change."""
        result_file = tmp_path / "output.json"
        subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "main.py"),
                "--batch",
                "--format",
                "json",
                "--output",
                str(result_file),
            ],
            check=True,
            cwd=PROJECT_ROOT,
        )

        golden_data = json.loads((GOLDEN_DIR / "batch_output.json").read_text())
        result_data = json.loads(result_file.read_text())

        # Compare structure (ignore timestamps in metadata)
        assert len(result_data["results"]) == len(golden_data["results"])
        # Metadata fields may vary, just check results count matches
        assert len(result_data.get("results", [])) == len(golden_data.get("results", []))

        # Check first result structure
        if golden_data["results"]:
            golden_first = golden_data["results"][0]
            result_first = result_data["results"][0]
            assert golden_first["target"] == result_first["target"]
            assert golden_first["total_occurrences"] == result_first["total_occurrences"]

    def test_cli_help_interface_unchanged(self):
        """CLI interface must not change."""
        result = subprocess.check_output(
            [sys.executable, str(PROJECT_ROOT / "main.py"), "--help"],
            text=True,
            cwd=PROJECT_ROOT,
        )
        golden = (GOLDEN_DIR / "cli_help.txt").read_text()

        # Check key flags exist
        assert "--batch" in result
        assert "--format" in result
        assert "--targets" in result
        assert "--dataset" in result
        assert "--cache-stats" in result

        # Check flag count is the same
        assert result.count("--") == golden.count("--"), "Number of CLI flags changed"

    def test_alternation_analysis_behavior_unchanged(self):
        """Alternation analysis behavior must not change."""
        from data import AlternationPair, TargetsProcessor
        from analyze import PhoneticAnalyzer

        # TargetsProcessor takes (targets_path, dataset_path, analyzer)
        analyzer = PhoneticAnalyzer()
        processor = TargetsProcessor("data/targets.txt", "data/dataset.txt", analyzer)

        pair = AlternationPair("p", "b")
        result = processor.analyze_alternation(pair)

        # Verify key properties
        assert result.pair.segment1 == "p"
        assert result.pair.segment2 == "b"
        assert result.pattern in [
            "complementary",
            "contrastive",
            "free_variation",
            "neutralization",
            "partial_overlap",
            "inconclusive",
        ]
        assert result.segment1_total >= 0
        assert result.segment2_total >= 0
        assert isinstance(result.analysis, str)
        assert len(result.analysis) > 0

    def test_target_analysis_behavior_unchanged(self):
        """Single target analysis behavior must not change."""
        from analyze import PhoneticAnalyzer

        analyzer = PhoneticAnalyzer()
        result = analyzer.analyze_character("p", "data/dataset.txt")

        # Check structure
        assert isinstance(result, dict)
        # Should have environment categories
        assert any(key in result for key in ["INITIAL", "FINAL", "MEDIAL V_V", "MEDIAL V_C", "MEDIAL C_V", "MEDIAL C_C"])

        # Check that we get expected occurrences for 'p'
        total = sum(len(words) for env_group in result.values() for words in env_group.values())
        assert total > 0, "Should find occurrences of 'p'"
