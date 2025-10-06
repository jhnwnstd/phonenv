"""Tests for output format generation (TXT, CSV, JSON)."""

from pathlib import Path
from typing import Callable

import pytest

from data import TargetsProcessor
from phonenv_io import AutoOutputWriter


@pytest.mark.output
class TestOutputFormats:
    """Test suite for output file generation in different formats."""

    @pytest.mark.parametrize("format_type", ["txt", "csv", "json"])
    def test_output_format_generation(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
        format_type: str,
    ):
        """Test that all output formats generate valid files."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            pʰɪn
            tʰɪp
            kʰæt
            sɪt
        """,
        )

        targets = targets_factory("targets.txt", "p\ns\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference=format_type
        )

        output_path = result_dict.get(format_type)

        assert output_path, f"No {format_type.upper()} file path returned"
        assert Path(
            output_path
        ).exists(), f"{format_type.upper()} file not created at {output_path}"

    def test_txt_format_structure(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
    ):
        """Test TXT format has proper headers and separators."""
        dataset = dataset_factory("dataset.txt", "pʰɪn\ntʰɪp\nsɪt\n")
        targets = targets_factory("targets.txt", "p\ns\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference="txt"
        )

        txt_path = Path(result_dict.get("txt", ""))
        assert txt_path.exists(), f"TXT file not found at {txt_path}"

        content = txt_path.read_text(encoding="utf-8")

        # Verify TXT format elements
        assert "TARGET" in content, "Missing TARGET header in TXT output"
        assert "---" in content, "Missing separator line (---) in TXT output"
        assert (
            "PHONETIC ENVIRONMENT ANALYSIS" in content or "TARGET" in content
        ), "Missing report header in TXT output"

    def test_csv_format_structure(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
    ):
        """Test CSV format has proper headers and data rows."""
        dataset = dataset_factory("dataset.txt", "pʰɪn\ntʰɪp\n")
        targets = targets_factory("targets.txt", "p\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference="csv"
        )

        csv_path = Path(result_dict.get("csv", ""))
        assert csv_path.exists(), f"CSV file not found at {csv_path}"

        content = csv_path.read_text(encoding="utf-8")

        # Verify CSV format
        assert (
            "target," in content.lower()
        ), "Missing CSV header row with 'target' column"
        assert (
            content.count("\n") > 1
        ), "CSV should have at least header + 1 data row"

    def test_json_format_structure(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
    ):
        """Test JSON format has metadata and valid structure."""
        dataset = dataset_factory("dataset.txt", "pʰɪn\ntʰɪp\n")
        targets = targets_factory("targets.txt", "p\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference="json"
        )

        json_path = Path(result_dict.get("json", ""))
        assert json_path.exists(), f"JSON file not found at {json_path}"

        content = json_path.read_text(encoding="utf-8")

        # Verify JSON structure
        assert '"metadata"' in content, "Missing metadata in JSON output"
        assert content.strip().startswith("{"), "JSON should start with {"
        assert content.strip().endswith("}"), "JSON should end with }"

        # Verify it's valid JSON by parsing
        import json

        try:
            data = json.loads(content)
            assert "metadata" in data, "JSON should have metadata key"
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON structure: {e}")


@pytest.mark.output
@pytest.mark.alternations
class TestOutputWithAlternations:
    """Test output format when including alternations."""

    def test_txt_with_alternations(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
    ):
        """Test TXT output includes ALTERNATION sections."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            skaɪ
            skuːl
            bæks
            ziːl
            bæɡz
        """,
        )

        targets = targets_factory(
            "targets.txt",
            """
            s
            z
            s ~ z
        """,
        )

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference="txt"
        )

        txt_path = Path(result_dict.get("txt", ""))
        content = txt_path.read_text(encoding="utf-8")

        # Should have both TARGET and ALTERNATION sections
        assert "TARGET" in content, "Missing TARGET section"

        # Check if alternations were processed
        has_alternation_result = any(hasattr(r, "pair") for r in results)
        if has_alternation_result:
            assert (
                "ALTERNATION" in content
            ), "Missing ALTERNATION section when alternations present"

    @pytest.mark.parametrize("format_type", ["txt", "csv", "json"])
    def test_mixed_output_formats(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
        format_type: str,
    ):
        """Test all formats handle mixed targets and alternations."""
        dataset = dataset_factory(
            "dataset.txt",
            """
            pʰɪn
            bɪn
            sɪt
            zɪp
        """,
        )

        targets = targets_factory(
            "targets.txt",
            """
            s
            p ~ b
        """,
        )

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference=format_type
        )

        output_path = result_dict.get(format_type)
        assert output_path, f"No {format_type} output generated"
        assert Path(output_path).exists(), f"{format_type} file not created"


@pytest.mark.output
class TestOutputFormatValidation:
    """Test output format consistency and specification compliance."""

    def test_txt_indentation_rules(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
    ):
        """Test TXT format follows 2-space/4-space indentation rules."""
        dataset = dataset_factory("dataset.txt", "skaɪ\nbæks\n")
        targets = targets_factory("targets.txt", "s\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference="txt"
        )

        content = Path(result_dict["txt"]).read_text(encoding="utf-8")
        lines = content.split("\n")

        # Check for 2-space indentation (environment groups)
        has_2_space = any(
            line.startswith("  ") and not line.startswith("    ")
            for line in lines
        )

        # Check for 4-space indentation (context lines)
        has_4_space = any(line.startswith("    ") for line in lines)

        assert (
            has_2_space
        ), "Missing 2-space indentation for environment groups"
        assert has_4_space, "Missing 4-space indentation for context lines"

    def test_txt_context_notation(
        self,
        dataset_factory: Callable[[str, str], Path],
        targets_factory: Callable[[str, str], Path],
        output_dir: Path,
    ):
        """Test TXT format uses correct context notation (×, _, brackets)."""
        dataset = dataset_factory("dataset.txt", "skaɪ\nskuːl\nbæks\n")
        targets = targets_factory("targets.txt", "s\n")

        processor = TargetsProcessor(str(dataset), str(targets))
        results = processor.process_targets_to_list()

        writer = AutoOutputWriter(str(output_dir))
        result_dict = writer.write_batch_results(
            results, format_preference="txt"
        )

        content = Path(result_dict["txt"]).read_text(encoding="utf-8")

        # Verify notation elements
        assert (
            "×" in content
        ), "Missing × (multiplication sign) for occurrence counts"
        assert " _ " in content, "Missing _ (underscore) for context notation"
        assert "[s]" in content, "Missing bracketed target notation [s]"
