"""JSON and JSONL output formatters.

IMPORT RULES:
- Can import: models, config, output.formats.base
- Cannot import: processors, alternations, parsers
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from output.formats.base import OutputFormatter, StreamingFormatter


class JsonFormatter(OutputFormatter):
    """Formats analysis results as JSON."""

    def __init__(self, pretty: bool = True):
        """Initialize JSON formatter.

        Args:
            pretty: If True, format with indentation. If False, compact output.
        """
        self.pretty = pretty

    def get_file_extension(self) -> str:
        return "json"

    def format_target_result(self, result: Any, **kwargs) -> str:
        """Format a single target result as JSON."""
        return self.format_batch_results([result], [], **kwargs)

    def format_alternation_result(self, result: Any, **kwargs) -> str:
        """Format a single alternation result as JSON."""
        return self.format_batch_results([], [result], **kwargs)

    def format_batch_results(
        self, target_results: List[Any], alternation_results: List[Any], **kwargs
    ) -> str:
        """Format batch results as JSON string."""
        all_results = list(target_results) + list(alternation_results)
        payload = [_to_plain(r) for r in all_results]

        data = {
            "metadata": {
                "format": "phonenv-json",
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "total_results": len(payload),
            },
            "results": payload,
        }

        if self.pretty:
            return json.dumps(data, indent=2, ensure_ascii=False)
        else:
            return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


class JsonlFormatter(StreamingFormatter, OutputFormatter):
    """Formats analysis results as JSONL (JSON Lines)."""

    def __init__(self, include_metadata: bool = True):
        """Initialize JSONL formatter.

        Args:
            include_metadata: If True, include metadata as first line.
        """
        self.include_metadata = include_metadata

    def get_file_extension(self) -> str:
        return "jsonl"

    def format_header(self, **kwargs) -> str:
        """Format JSONL header (metadata line)."""
        if not self.include_metadata:
            return ""

        total_results = kwargs.get("total_results", 0)
        targets = kwargs.get("targets", [])

        metadata = {
            "_metadata": {
                "format": "phonenv-jsonl",
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "total_results": total_results,
                "targets": targets,
            }
        }
        return json.dumps(metadata, ensure_ascii=False) + "\n"

    def format_item(self, item: Any, is_last: bool = False, **kwargs) -> str:
        """Format a single item as JSONL line."""
        payload = _to_plain(item)
        return json.dumps(payload, ensure_ascii=False) + "\n"

    def format_footer(self, **kwargs) -> str:
        """Format JSONL footer (empty for JSONL)."""
        return ""

    def format_target_result(self, result: Any, **kwargs) -> str:
        """Format a single target result as JSONL."""
        return self.format_batch_results([result], [], **kwargs)

    def format_alternation_result(self, result: Any, **kwargs) -> str:
        """Format a single alternation result as JSONL."""
        return self.format_batch_results([], [result], **kwargs)

    def format_batch_results(
        self, target_results: List[Any], alternation_results: List[Any], **kwargs
    ) -> str:
        """Format batch results as JSONL string."""
        all_results = list(target_results) + list(alternation_results)
        payload = [_to_plain(r) for r in all_results]
        targets = [_get_target_name(r) for r in all_results]

        lines = []

        # Header with metadata
        if self.include_metadata:
            lines.append(
                self.format_header(total_results=len(payload), targets=targets).rstrip("\n")
            )

        # Data lines
        for item in payload:
            lines.append(json.dumps(item, ensure_ascii=False))

        return "\n".join(lines)


# ========================= HELPER FUNCTIONS =========================


def _to_plain(obj: Any) -> Any:
    """Convert dataclass/complex objects to plain dicts recursively."""
    from dataclasses import is_dataclass, asdict

    if is_dataclass(obj):
        return asdict(obj)
    elif isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items() if not str(k).startswith("_")}
    elif isinstance(obj, (list, tuple, set)):
        return [_to_plain(v) for v in obj]
    elif hasattr(obj, "__dict__"):
        return {
            k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")
        }
    return str(obj)


def _get_target_name(result: Any) -> str:
    """Extract target name from result object."""
    if isinstance(result, dict) and "alternation" in result:
        return str(result["alternation"])
    if hasattr(result, "target"):
        return result.target
    if isinstance(result, dict) and "target" in result:
        return result["target"]
    return "unknown"


__all__ = ["JsonFormatter", "JsonlFormatter"]
