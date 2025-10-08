"""Base formatter interface for output formats.

IMPORT RULES:
- Can import: models, config
- Cannot import: processors, alternations, parsers, analyze
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from pathlib import Path


class OutputFormatter(ABC):
    """Abstract base class for output formatters."""

    @abstractmethod
    def format_target_result(self, result: Any, **kwargs) -> str:
        """Format a single target analysis result.

        Args:
            result: TargetResult object or dict
            **kwargs: Additional formatting options

        Returns:
            Formatted string representation
        """
        pass

    @abstractmethod
    def format_alternation_result(self, result: Any, **kwargs) -> str:
        """Format a single alternation analysis result.

        Args:
            result: AlternationResult object or dict
            **kwargs: Additional formatting options

        Returns:
            Formatted string representation
        """
        pass

    @abstractmethod
    def format_batch_results(
        self,
        target_results: List[Any],
        alternation_results: List[Any],
        **kwargs,
    ) -> str:
        """Format batch analysis results.

        Args:
            target_results: List of TargetResult objects
            alternation_results: List of AlternationResult objects
            **kwargs: Additional formatting options

        Returns:
            Formatted string representation of all results
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """Get default file extension for this format (e.g., 'txt', 'json')."""
        pass

    def write_to_file(
        self,
        content: str,
        output_path: str | Path,
        **kwargs,
    ) -> None:
        """Write formatted content to file.

        Args:
            content: Formatted string to write
            output_path: Path to output file
            **kwargs: Additional options (e.g., encoding)
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        encoding = kwargs.get("encoding", "utf-8")
        path.write_text(content, encoding=encoding)


class StreamingFormatter(ABC):
    """Base class for formatters that support streaming output (e.g., JSONL)."""

    @abstractmethod
    def format_header(self, **kwargs) -> str:
        """Format header/preamble if needed (e.g., JSON array opening bracket).

        Returns:
            Header string (may be empty)
        """
        pass

    @abstractmethod
    def format_item(self, item: Any, is_last: bool = False, **kwargs) -> str:
        """Format a single item for streaming output.

        Args:
            item: Item to format (TargetResult, AlternationResult, etc.)
            is_last: Whether this is the last item (for separator logic)
            **kwargs: Additional formatting options

        Returns:
            Formatted string for this item
        """
        pass

    @abstractmethod
    def format_footer(self, **kwargs) -> str:
        """Format footer/epilogue if needed (e.g., JSON array closing bracket).

        Returns:
            Footer string (may be empty)
        """
        pass


__all__ = [
    "OutputFormatter",
    "StreamingFormatter",
]
