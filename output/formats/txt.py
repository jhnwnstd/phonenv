"""TXT (text report) output formatter.

IMPORT RULES:
- Can import: models, config, output.formats.base
- Cannot import: processors, alternations, parsers
"""

from __future__ import annotations

import unicodedata as ud
from datetime import datetime
from typing import Any, Dict, List

from config import REPORT_SEPARATOR_WIDTH, NARROW_SEPARATOR_WIDTH
from output.formats.base import OutputFormatter


class TxtFormatter(OutputFormatter):
    """Formats analysis results as human-readable text reports."""

    def __init__(
        self,
        include_examples: bool = True,
        max_examples: int = 5,
        transcription_mode: str = "narrow",
    ):
        self.include_examples = include_examples
        self.max_examples = max_examples
        self.transcription_mode = transcription_mode

    def get_file_extension(self) -> str:
        return "txt"

    def format_target_result(self, result: Any, **kwargs) -> str:
        """Format a single target analysis result."""
        res = _to_plain(result)
        target = res.get("target", _get_target_name(result))
        total = res.get("total_occurrences", 0)
        envs = res.get("environments", {}) if isinstance(res.get("environments", {}), dict) else {}

        lines = []
        lines.append(f"TARGET: '{target}' ({total})")
        lines.append("-" * NARROW_SEPARATOR_WIDTH)

        if not envs:
            lines.append("No environments found.")
        else:
            for group_name, environments in envs.items():
                if not environments:
                    continue
                lines.append(f"  {group_name}:")
                for env, examples in environments.items():
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

                    # Format: context ×count : examples
                    count = len(deduped_examples)
                    line = f"    {left} _ {right} ×{count}"

                    if self.include_examples and deduped_examples:
                        shown = deduped_examples[: self.max_examples]
                        line += f" : {', '.join(shown)}"
                        extra = max(0, len(deduped_examples) - self.max_examples)
                        if extra:
                            line += f" (+{extra} more)"
                    lines.append(line)
                lines.append("")

        return "\n".join(lines)

    def format_alternation_result(self, result: Any, **kwargs) -> str:
        """Format a single alternation analysis result."""
        res = _to_plain(result)

        # Check if structural alternation (X ~ Ø)
        if "process_type" in res:
            return self._format_structural_alternation(res)
        else:
            return self._format_phonemic_alternation(res)

    def _format_phonemic_alternation(self, res: Dict[str, Any]) -> str:
        """Format phonemic alternation (standard case)."""
        return self._format_phonemic_alternation_indexed(res, None)

    def _format_phonemic_alternation_indexed(self, res: Dict[str, Any], index: int = None) -> str:
        """Format phonemic alternation with optional index number."""
        # Handle both _to_plain format (pair key) and to_dict format (alternation key)
        if "pair" in res:
            pair = res["pair"]
            alternation = f"{pair.get('segment1', '')} ~ {pair.get('segment2', '')}"
            seg1 = pair.get("segment1", "")
            seg2 = pair.get("segment2", "")
        else:
            alternation = res.get("alternation", "")
            seg1 = res.get("segment1", "")
            seg2 = res.get("segment2", "")

        pattern = res.get("pattern", "unknown")
        analysis = res.get("analysis", "")
        total1 = res.get("segment1_total", 0)
        total2 = res.get("segment2_total", 0)
        total_count = total1 + total2

        lines = []
        if index is not None:
            lines.append(f"ALTERNATION {index}: '{alternation}' ({total_count})")
        else:
            lines.append(f"ALTERNATION: '{alternation}' ({total_count})")
        lines.append("-" * NARROW_SEPARATOR_WIDTH)

        # Format pattern type
        pattern_labels = {
            "complementary": "COMPLEMENTARY DISTRIBUTION (likely allophones)",
            "free_variation": "FREE VARIATION (interchangeable)",
            "neutralization": "NEUTRALIZATION (contrast lost in context)",
            "partial_overlap": "PARTIAL OVERLAP (gradience/variation)",
            "contrastive": "CONTRASTIVE (distinct phonemes)",
            "overlapping": "OVERLAPPING (partial contrast)",
            "identical": "IDENTICAL DISTRIBUTION",
            "unknown": "UNKNOWN PATTERN",
        }
        pattern_display = pattern_labels.get(pattern, pattern.upper())

        lines.append(f"Pattern: {pattern_display}")
        lines.append(
            "Method: Auto-window = L2-left; Abstraction = {L2/L1: class+features, R1/R2: segment}; Min-evidence = 3"
        )
        if analysis:
            lines.append(f"Analysis: {analysis}")
        lines.append("-" * 60)
        lines.append("")

        # VARIANT 1
        env1 = res.get("segment1_envs", res.get("segment1_environments", {}))
        if env1:
            lines.append(f"  VARIANT 1: '{seg1}' ({total1})")
            lines.append("  " + "-" * 40)
            self._append_env_details(lines, env1)
            lines.append("")

        # VARIANT 2
        env2 = res.get("segment2_envs", res.get("segment2_environments", {}))
        if env2:
            lines.append(f"  VARIANT 2: '{seg2}' ({total2})")
            lines.append("  " + "-" * 40)
            self._append_env_details(lines, env2)
            lines.append("")

        return "\n".join(lines)

    def _format_structural_alternation(self, res: Dict[str, Any]) -> str:
        """Format structural alternation (X ~ Ø)."""
        return self._format_structural_alternation_indexed(res, None)

    def _format_structural_alternation_indexed(self, res: Dict[str, Any], index: int = None) -> str:
        """Format structural alternation with optional index number."""
        # Extract fields
        if "pair" in res:
            pair = res["pair"]
            alternation = f"{pair.get('segment1', 'Ø') or 'Ø'} ~ {pair.get('segment2', 'Ø') or 'Ø'}"
        else:
            alternation = res.get("alternation", "")

        segment = res.get("segment", "")
        process_type = res.get("process_type", "unknown")
        rule = res.get("rule", "")
        analysis = res.get("analysis", "")
        total = res.get("segment_total", 0)
        dominant_contexts = res.get("dominant_contexts", [])

        lines = []
        if index is not None:
            lines.append(f"STRUCTURAL ALTERNATION {index}: '{alternation}' ({total})")
        else:
            lines.append(f"STRUCTURAL ALTERNATION: '{alternation}' ({total})")
        lines.append("-" * NARROW_SEPARATOR_WIDTH)

        # Format process type
        process_labels = {
            "prothesis": "PROTHESIS (word-initial insertion)",
            "epenthesis": "EPENTHESIS (insertion)",
            "syncope": "SYNCOPE (vowel deletion)",
            "apocope": "APOCOPE (word-final deletion)",
            "aphaeresis": "APHAERESIS (word-initial deletion)",
            "deletion": "DELETION",
            "inconclusive": "INCONCLUSIVE",
            "unknown": "UNKNOWN PROCESS",
        }
        process_display = process_labels.get(process_type, process_type.upper())

        lines.append(f"Process: {process_display}")
        lines.append(f"Rule: {rule}")
        lines.append(
            "Method: Auto-window = L2-left; Abstraction = {L2/L1: class+features, R1/R2: segment}; Min-evidence = 3"
        )
        if analysis:
            lines.append(f"Analysis: {analysis}")
        lines.append("-" * 60)
        lines.append("")

        # Same-frame contrasts
        frame_contrasts = res.get("frame_contrasts", {})
        if frame_contrasts:
            lines.append("  Same-frame contrasts (with-X vs with-Ø):")
            sorted_frames = sorted(
                frame_contrasts.items(), key=lambda kv: kv[1]["with_X"], reverse=True
            )[:3]
            for ctx, counts in sorted_frames:
                with_x = counts["with_X"]
                with_null = counts["with_Ø"]
                skew = counts["skew"]
                lines.append(
                    f"    {ctx}: with-{segment} = {with_x}, with-Ø = {with_null} → skew = {skew:.2f}"
                )
            lines.append("")

        # Dominant contexts
        if dominant_contexts:
            lines.append("  Dominant contexts:")
            for ctx in dominant_contexts:
                lines.append(f"    {ctx}")
            lines.append("")

        # Detailed environments
        envs = res.get("segment_envs", res.get("segment_environments", {}))
        if envs and self.include_examples:
            lines.append(f"  {segment} distribution:")
            self._append_env_details(lines, envs, is_structural=True)
            lines.append("")

        return "\n".join(lines)

    def _append_env_details(
        self, lines: List[str], envs: Dict[str, Any], is_structural: bool = False
    ) -> None:
        """Append environment details to lines list."""
        for group_name, environments in envs.items():
            if not environments:
                continue
            lines.append(f"    {group_name}:")
            for env, examples in environments.items():
                if not isinstance(examples, (list, tuple)):
                    examples = []

                deduped = list(
                    dict.fromkeys(ud.normalize("NFC", ex) for ex in examples)
                )

                # Simplify context for display
                left, right = self._simplify_context(env)
                count = len(deduped)
                line = f"      {left} _ {right} ×{count}"

                if self.include_examples and deduped:
                    shown = deduped[: self.max_examples]
                    line += f" : {', '.join(shown)}"
                    extra = max(0, len(deduped) - self.max_examples)
                    if extra:
                        line += f" (+{extra} more)"
                lines.append(line)

    def _simplify_context(self, env: str) -> tuple:
        """Convert extended context to simple _ notation for display."""
        if "|" in env:
            # Extended format: extract L1 and R1
            parts = dict(p.split("=") for p in env.split("|") if "=" in p)
            left = parts.get("L1", "#")
            right = parts.get("R1", "#")
            return left, right
        elif "__" in env:
            # Simple format
            return tuple((env.split("__", 1) + [""])[:2])
        else:
            return env, ""

    def format_batch_results(
        self, target_results: List[Any], alternation_results: List[Any], **kwargs
    ) -> str:
        """Format batch analysis results as complete report."""
        all_results = list(target_results) + list(alternation_results)
        payload = [_to_plain(r) for r in all_results]

        lines = []

        # Count targets vs alternations
        num_targets = sum(
            1
            for res in payload
            if "pair" not in res
            and "alternation" not in res
            and "process_type" not in res
        )
        num_alternations = len(payload) - num_targets

        # Count structural vs phonemic alternations
        structural_count = sum(1 for res in payload if "process_type" in res)
        phonemic_count = num_alternations - structural_count

        # Header
        lines.append("PHONETIC ENVIRONMENT ANALYSIS REPORT")
        lines.append("=" * REPORT_SEPARATOR_WIDTH)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Transcription mode: {self.transcription_mode}")
        lines.append(f"Targets: {num_targets}")
        lines.append(
            f"Alternations: {num_alternations} (phonemic: {phonemic_count}, structural: {structural_count})"
        )
        lines.append(f"Total lexical items: {len(payload)}")

        # Add source file if available
        if payload:
            source_file = payload[0].get("source_file", "")
            if source_file:
                lines.append(f"Source dataset: {source_file}")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * NARROW_SEPARATOR_WIDTH)
        lines.append(f"{'Target':<10} {'Count':<12} Envs")
        lines.append("-" * NARROW_SEPARATOR_WIDTH)

        def _env_count(res: Dict[str, Any]) -> int:
            envs = res.get("environments", {})
            if isinstance(envs, dict):
                return sum(len(v) for v in envs.values() if isinstance(v, dict))
            return 0

        for res in payload:
            # Skip alternations in summary
            if "pair" in res or "alternation" in res:
                continue
            target = res.get("target", _get_target_name(res))
            env_count = _env_count(res)
            lines.append(
                f"{target:<10} {res.get('total_occurrences', 0):<12} {env_count}"
            )

        lines.append("")
        lines.append("=" * REPORT_SEPARATOR_WIDTH)
        lines.append("")

        # Details
        for i, res in enumerate(payload, 1):
            if "pair" in res or "alternation" in res:
                # Alternation result - format with index number
                if "process_type" in res:
                    formatted = self._format_structural_alternation_indexed(res, i)
                else:
                    formatted = self._format_phonemic_alternation_indexed(res, i)
            else:
                # Regular target result
                target = res.get("target", _get_target_name(res))
                total = res.get("total_occurrences", 0)
                envs = (
                    res.get("environments", {})
                    if isinstance(res.get("environments", {}), dict)
                    else {}
                )

                formatted_lines = []
                formatted_lines.append(f"TARGET {i}: '{target}' ({total})")
                formatted_lines.append("-" * NARROW_SEPARATOR_WIDTH)

                if not envs:
                    formatted_lines.append("No environments found.")
                    formatted_lines.append("")
                else:
                    for group_name, environments in envs.items():
                        if not environments:
                            continue
                        formatted_lines.append(f"  {group_name}:")
                        for env, examples in environments.items():
                            if not isinstance(examples, (list, tuple)):
                                examples = []

                            deduped_examples = list(
                                dict.fromkeys(
                                    ud.normalize("NFC", ex) for ex in examples
                                )
                            )

                            left, right = (
                                (env.split("__", 1) + [""])[:2]
                                if "__" in env
                                else (env, "")
                            )

                            count = len(deduped_examples)
                            line = f"    {left} _ {right} ×{count}"

                            if self.include_examples and deduped_examples:
                                shown = deduped_examples[: self.max_examples]
                                line += f" : {', '.join(shown)}"
                                extra = max(0, len(deduped_examples) - self.max_examples)
                                if extra:
                                    line += f" (+{extra} more)"
                            formatted_lines.append(line)
                        formatted_lines.append("")

                formatted = "\n".join(formatted_lines)

            lines.append(formatted)

            if i < len(payload):
                lines.append("—")
                lines.append("")

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


__all__ = ["TxtFormatter"]
