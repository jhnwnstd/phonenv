"""Output file writers using format registry.

IMPORT RULES:
- Can import: models, config, logger, output.formats, output.cache
- Cannot import: processors, alternations, parsers
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import DEFAULT_OUTPUT_DIR
from logger import get_logger
from output.formats import (
    TxtFormatter,
    CsvFormatter,
    JsonFormatter,
    JsonlFormatter,
)

logger = get_logger()

# Constants
MAX_SLUG_LENGTH = 80


class OutputWriter:
    """Handles writing analysis results to various output formats."""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_jsonl(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        include_metadata: bool = True,
    ) -> str:
        """Write results in JSONL format."""
        formatter = JsonlFormatter(include_metadata=include_metadata)

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"analysis_results_{timestamp}.jsonl"
        else:
            output_file = Path(output_path)

        content = formatter.format_batch_results(results, [])
        self._write_file(output_file, content)
        return str(output_file)

    def write_json(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        pretty: bool = True,
    ) -> str:
        """Write results in JSON format."""
        formatter = JsonFormatter(pretty=pretty)

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"analysis_results_{timestamp}.json"
        else:
            output_file = Path(output_path)

        content = formatter.format_batch_results(results, [])
        self._write_file(output_file, content)
        return str(output_file)

    def write_csv(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        flatten_environments: bool = True,
    ) -> str:
        """Write results in CSV format."""
        formatter = CsvFormatter(flatten_environments=flatten_environments)

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"analysis_results_{timestamp}.csv"
        else:
            output_file = Path(output_path)

        content = formatter.format_batch_results(results, [])
        self._write_file(output_file, content)
        return str(output_file)

    def write_text_report(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        include_examples: bool = True,
        max_examples: int = 5,
        transcription_mode: str = "narrow",
    ) -> str:
        """Write results in TXT format."""
        formatter = TxtFormatter(
            include_examples=include_examples,
            max_examples=max_examples,
            transcription_mode=transcription_mode,
        )

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"analysis_report_{timestamp}.txt"
        else:
            output_file = Path(output_path)

        content = formatter.format_batch_results(results, [])
        self._write_file(output_file, content)
        return str(output_file)

    def _write_file(self, path: Path, content: str) -> None:
        """Write content to file, creating parent directories if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class AutoOutputWriter:
    """Automatically determines output format and writes results."""

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.writer = OutputWriter(output_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_batch_results(
        self,
        results: List[Any],
        format_preference: str = "txt",
        custom_path: Optional[str] = None,
        transcription_mode: str = "narrow",
    ) -> Dict[str, str]:
        """Write batch results in the specified format.

        Args:
            results: List of analysis results
            format_preference: Desired format ('txt', 'json', 'jsonl', 'csv')
            custom_path: Optional custom output path
            transcription_mode: Transcription mode for report header

        Returns:
            Dict mapping format name to output file path
        """
        if not results:
            return {}

        # Build a compact, safe base name from first few target names
        first_three = [_slug(_get_target_name(r)) for r in results[:3]]
        target_names = "_".join(t for t in first_three if t) or "targets"
        if len(results) > 3:
            target_names += f"_plus{len(results) - 3}"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"batch_{target_names}_{timestamp}"

        fmt = (format_preference or "txt").lower()
        output_paths: Dict[str, str] = {}

        if fmt == "jsonl":
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.jsonl")
            )
            output_paths["jsonl"] = self.writer.write_jsonl(results, str(path))
        elif fmt == "json":
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.json")
            )
            output_paths["json"] = self.writer.write_json(results, str(path))
        elif fmt == "csv":
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.csv")
            )
            output_paths["csv"] = self.writer.write_csv(results, str(path))
        else:  # Default to txt
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.txt")
            )
            output_paths["txt"] = self.writer.write_text_report(
                results, str(path), transcription_mode=transcription_mode
            )

        return output_paths


# ========================= HELPER FUNCTIONS =========================


def _slug(text: str) -> str:
    """Convert text to safe filename slug."""
    # Remove or replace unsafe characters
    safe = re.sub(r"[^\w\-]", "_", text)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Trim and limit length
    safe = safe.strip("_")[:MAX_SLUG_LENGTH]
    return safe


def _get_target_name(result: Any) -> str:
    """Extract target name from result object."""
    if isinstance(result, dict) and "alternation" in result:
        return str(result["alternation"])
    if hasattr(result, "target"):
        return result.target
    if isinstance(result, dict) and "target" in result:
        return result["target"]
    return "unknown"


__all__ = [
    "OutputWriter",
    "AutoOutputWriter",
]
