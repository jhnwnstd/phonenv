"""CSV output formatter.

IMPORT RULES:
- Can import: models, config, output.formats.base
- Cannot import: processors, alternations, parsers
"""

from __future__ import annotations

import csv
import json
import unicodedata as ud
from io import StringIO
from typing import Any, Dict, List

from output.formats.base import OutputFormatter


class CsvFormatter(OutputFormatter):
    """Formats analysis results as CSV (comma-separated values)."""

    def __init__(self, flatten_environments: bool = True):
        """Initialize CSV formatter.

        Args:
            flatten_environments: If True, create one row per environment.
                                 If False, keep environments as JSON string.
        """
        self.flatten_environments = flatten_environments

    def get_file_extension(self) -> str:
        return "csv"

    def format_target_result(self, result: Any, **kwargs) -> str:
        """Format a single target result as CSV."""
        return self.format_batch_results([result], [], **kwargs)

    def format_alternation_result(self, result: Any, **kwargs) -> str:
        """Format a single alternation result as CSV."""
        return self.format_batch_results([], [result], **kwargs)

    def format_batch_results(
        self, target_results: List[Any], alternation_results: List[Any], **kwargs
    ) -> str:
        """Format batch results as CSV string."""
        all_results = list(target_results) + list(alternation_results)
        payload = [_to_plain(r) for r in all_results]

        # Use StringIO to capture CSV output
        output = StringIO()

        if self.flatten_environments:
            fieldnames = [
                "target",
                "group",
                "environment",
                "left_context",
                "right_context",
                "count",
                "examples",
                "source_file",
                "total_occurrences",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for res in payload:
                target = res.get("target", _get_target_name(res))
                source_file = res.get("source_file", "")
                total_occ = res.get("total_occurrences", 0)

                for group_name, envs in self._get_envs(res).items():
                    if not isinstance(envs, dict):
                        continue
                    for env, examples in envs.items():
                        if not isinstance(examples, (list, tuple)):
                            examples = []

                        # Deduplicate and normalize
                        deduped_examples = list(
                            dict.fromkeys(ud.normalize("NFC", ex) for ex in examples)
                        )

                        # Parse environment key
                        left, right = (
                            (env.split("__", 1) + [""])[:2]
                            if "__" in env
                            else (env, "")
                        )

                        writer.writerow(
                            {
                                "target": target,
                                "group": group_name,
                                "environment": env,
                                "left_context": left,
                                "right_context": right,
                                "count": len(deduped_examples),
                                "examples": "; ".join(deduped_examples[:5]),
                                "source_file": source_file,
                                "total_occurrences": total_occ,
                            }
                        )
        else:
            fieldnames = [
                "target",
                "total_occurrences",
                "environments_json",
                "source_file",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for res in payload:
                writer.writerow(
                    {
                        "target": res.get("target", _get_target_name(res)),
                        "total_occurrences": res.get("total_occurrences", 0),
                        "environments_json": json.dumps(
                            res.get("environments", {}), ensure_ascii=False
                        ),
                        "source_file": res.get("source_file", ""),
                    }
                )

        return output.getvalue()

    def _get_envs(self, res: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
        """Extract environments dict from result."""
        envs = res.get("environments", {})
        # ensure dict-of-dicts
        return envs if isinstance(envs, dict) else {}


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


__all__ = ["CsvFormatter"]
