"""I/O operations for phonetic environment analysis.

This module consolidates all input/output functionality including:
- Result caching with SHA256 fingerprinting
- Output file writing in multiple formats (JSONL, JSON, CSV, TXT)
- Automatic output file management
"""

from __future__ import annotations

import csv
import enum
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from config import (
    CACHE_MAX_ENTRIES,
    CACHE_MAX_SIZE_MB,
    CACHE_FILENAME,
    DEFAULT_CACHE_DIR,
    DEFAULT_OUTPUT_DIR,
    REPORT_SEPARATOR_WIDTH,
    NARROW_SEPARATOR_WIDTH,
)
from logger import get_logger

# Additional constants not in config
DEFAULT_CACHE_MAX_AGE_DAYS = 30.0
MAX_SLUG_LENGTH = 80

# Initialize logger
logger = get_logger()

# ========================= RESULT CACHING =========================


@dataclass
class CacheEntry:
    """Represents a cached analysis result."""

    key: str
    target: str
    dataset_hash: str
    result: Dict[str, Any]
    timestamp: float
    dataset_path: str
    analysis_config: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        return cls(**data)

    def is_valid(
        self, current_dataset_hash: str, current_config: Dict[str, Any]
    ) -> bool:
        return (
            self.dataset_hash == current_dataset_hash
            and self.analysis_config == current_config
        )


class ResultCache:
    """Manages caching of phonetic analysis results with SHA256-based keys.

    Args:
        cache_dir: Directory for cache files (default from config.DEFAULT_CACHE_DIR)
        max_entries: Maximum cache entries before LRU eviction (default from config.CACHE_MAX_ENTRIES)
        max_size_mb: Maximum cache size in MB before LRU eviction (default from config.CACHE_MAX_SIZE_MB)
    """

    def __init__(
        self,
        cache_dir: str = DEFAULT_CACHE_DIR,
        max_entries: int = CACHE_MAX_ENTRIES,
        max_size_mb: int = CACHE_MAX_SIZE_MB,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / CACHE_FILENAME
        self.max_entries = max_entries
        self.max_size_mb = max_size_mb

        # In-memory cache for faster access during session
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            with self.cache_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = CacheEntry.from_dict(data)
                        self._memory_cache[entry.key] = entry
                    except (json.JSONDecodeError, TypeError, KeyError) as e:
                        # Skip malformed cache entry (corrupted or incompatible version)
                        logger.warning(
                            f"Skipping corrupted cache entry",
                            cache_file=str(self.cache_file),
                            error=str(e),
                        )
                        continue
        except (IOError, OSError) as e:
            logger.cache_error(
                "load", e, cache_file=str(self.cache_file)
            )

    def _save_cache(self) -> None:
        try:
            temp_file = self.cache_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                for entry in self._memory_cache.values():
                    f.write(
                        json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"
                    )
            temp_file.replace(self.cache_file)
        except (IOError, OSError) as e:
            logger.cache_error(
                "save",
                e,
                cache_file=str(self.cache_file),
                note="Cache will not persist between sessions",
            )

    def _compute_dataset_hash(self, dataset_path: str) -> str:
        """Compute SHA256 hash of dataset file for cache validation.

        Returns empty string if file doesn't exist or cannot be read.
        """
        path = Path(dataset_path)
        if not path.exists():
            return ""
        hasher = hashlib.sha256()
        try:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (IOError, OSError) as e:
            logger.warning(
                f"Could not compute hash for dataset",
                dataset=dataset_path,
                error=str(e),
                note="Caching will be disabled for this file",
            )
            return ""

    def _compute_cache_key(
        self, target: str, dataset_path: str, config: Dict[str, Any]
    ) -> str:
        key_data = {
            "target": target,
            "dataset_path": str(Path(dataset_path).resolve()),
            "config": config,
        }
        key_string = json.dumps(
            key_data, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    def get_analysis_config(self, analyzer) -> Dict[str, Any]:
        """Extract relevant configuration from analyzer for cache key."""
        config = {
            "use_ipa_processing": getattr(
                analyzer, "use_ipa_processing", False
            ),
            "transcription_mode": getattr(
                analyzer, "transcription_mode", "narrow"
            ),
            "no_color": getattr(analyzer, "no_color", False),
        }

        if hasattr(analyzer, "ipa_processor_v2") and getattr(
            analyzer, "ipa_processor_v2"
        ):
            processor = analyzer.ipa_processor_v2
            # include match_mode to distinguish broad vs narrow semantic matching
            match_mode = getattr(processor.config, "match_mode", None)
            config["ipa_processor"] = {
                "use_panphon": getattr(processor.config, "use_panphon", False),
                "tie_bar_clusters": getattr(
                    processor.config, "tie_bar_clusters", []
                ),
                "diphthong_patterns": getattr(
                    processor.config, "diphthong_patterns", []
                ),
                "normalization_mode": getattr(
                    processor.config, "normalization_mode", "NFC"
                ),
                "match_mode": (
                    match_mode if match_mode is not None else "broad"
                ),
            }

        return config

    def get(self, target: str, dataset_path: str, analyzer) -> Optional[Any]:
        config = self.get_analysis_config(analyzer)
        cache_key = self._compute_cache_key(target, dataset_path, config)

        entry = self._memory_cache.get(cache_key)
        if not entry:
            return None

        current_dataset_hash = self._compute_dataset_hash(dataset_path)
        if not entry.is_valid(current_dataset_hash, config):
            # stale cache; purge it
            self._memory_cache.pop(cache_key, None)
            return None

        # Convert cached result back to TargetResult (or dict if class unavailable)
        try:
            from data import TargetResult  # type: ignore

            return TargetResult(
                target=entry.result["target"],
                environments=entry.result["environments"],
                total_occurrences=entry.result["total_occurrences"],
                source_file=entry.result["source_file"],
            )
        except Exception:
            # fall back to dict
            return entry.result

    def put(self, target: str, dataset_path: str, analyzer, result) -> None:
        config = self.get_analysis_config(analyzer)
        cache_key = self._compute_cache_key(target, dataset_path, config)
        dataset_hash = self._compute_dataset_hash(dataset_path)

        # best-effort to_dict
        result_payload = _to_plain(result)
        if not isinstance(result_payload, dict):
            # keep minimal fields at least
            result_payload = {
                "target": _get_target_name(result),
                "payload": result_payload,
                "source_file": getattr(
                    result, "source_file", str(Path(dataset_path).resolve())
                ),
                "total_occurrences": getattr(result, "total_occurrences", 0),
                "environments": getattr(result, "environments", {}),
            }

        entry = CacheEntry(
            key=cache_key,
            target=target,
            dataset_hash=dataset_hash,
            result=result_payload,
            timestamp=time.time(),
            dataset_path=str(Path(dataset_path).resolve()),
            analysis_config=config,
        )
        self._memory_cache[cache_key] = entry

    def clear(self) -> None:
        self._memory_cache.clear()
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
        except Exception:
            pass

    def clear_target(self, target: str) -> int:
        to_remove = [
            k for k, e in self._memory_cache.items() if e.target == target
        ]
        for k in to_remove:
            self._memory_cache.pop(k, None)
        return len(to_remove)

    def clear_dataset(self, dataset_path: str) -> int:
        resolved = str(Path(dataset_path).resolve())
        to_remove = [
            k
            for k, e in self._memory_cache.items()
            if e.dataset_path == resolved
        ]
        for k in to_remove:
            self._memory_cache.pop(k, None)
        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        if not self._memory_cache:
            return {
                "total_entries": 0,
                "cache_file_exists": self.cache_file.exists(),
                "cache_dir": str(self.cache_dir),
                "memory_cache_size": 0,
            }

        targets = {e.target for e in self._memory_cache.values()}
        datasets = {e.dataset_path for e in self._memory_cache.values()}
        oldest_ts = min(e.timestamp for e in self._memory_cache.values())
        newest_ts = max(e.timestamp for e in self._memory_cache.values())

        return {
            "total_entries": len(self._memory_cache),
            "unique_targets": len(targets),
            "unique_datasets": len(datasets),
            "targets": sorted(targets),
            "datasets": sorted(datasets),
            "oldest_entry": time.ctime(oldest_ts),
            "newest_entry": time.ctime(newest_ts),
            "cache_file_exists": self.cache_file.exists(),
            "cache_dir": str(self.cache_dir),
            "memory_cache_size": len(self._memory_cache),
        }

    def cleanup_old_entries(
        self, max_age_days: float = DEFAULT_CACHE_MAX_AGE_DAYS
    ) -> int:
        cutoff = time.time() - (max_age_days * 24 * 60 * 60)
        to_remove = [
            k for k, e in self._memory_cache.items() if e.timestamp < cutoff
        ]
        for k in to_remove:
            self._memory_cache.pop(k, None)
        return len(to_remove)

    def save(self) -> None:
        self._save_cache()

    def __del__(self):
        try:
            self._save_cache()
        except Exception:
            pass


# ========================= CONVERSION & NAMING HELPERS =========================


def _get_target_name(result: Any) -> str:
    # Check for alternation results first
    if isinstance(result, dict) and "alternation" in result:
        return str(result["alternation"])
    if hasattr(result, "pair"):
        return str(getattr(result, "pair"))
    # Regular target results
    if isinstance(result, dict) and "target" in result:
        return str(result["target"])
    if hasattr(result, "target"):
        return str(getattr(result, "target"))
    if hasattr(result, "query"):
        return str(getattr(result, "query"))
    return str(result)


def _slug(s: str, max_len: int = MAX_SLUG_LENGTH) -> str:
    # keep IPA/Unicode letters and digits; strip path separators and whitespace
    s = s.replace("/", "_").replace("\\", "_").replace(" ", "")
    s = "".join(ch for ch in s if ch.isalnum() or ch in "._-")
    return s[:max_len] if len(s) > max_len else s


def _to_plain(obj: Any) -> Any:
    """
    Recursively convert to JSON-serializable structures:
    - dataclasses -> dict
    - has .to_dict() -> use it
    - dict/list/tuple/set -> recurse
    - Path -> str; Enum -> value; bytes -> utf-8 string (best effort)
    - objects -> vars() if available; else str()
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")

    if is_dataclass(obj):
        if not isinstance(obj, type) and is_dataclass(obj):
            obj = asdict(obj)
    elif hasattr(obj, "to_dict") and callable(getattr(obj, "to_dict")):
        try:
            obj = obj.to_dict()
        except Exception:
            # fall through
            obj = getattr(obj, "__dict__", obj)

    if isinstance(obj, dict):
        return {
            str(k): _to_plain(v)
            for k, v in obj.items()
            if not str(k).startswith("_")
        }
    if isinstance(obj, (list, tuple, set)):
        return [_to_plain(v) for v in obj]

    if hasattr(obj, "__dict__"):
        return {
            k: _to_plain(v)
            for k, v in vars(obj).items()
            if not k.startswith("_")
        }

    return str(obj)


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


# ========================= OUTPUT FILE WRITING =========================


class OutputWriter:
    """Handles writing analysis results to various output formats."""

    def __init__(self, output_dir: str = "data/output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # -------- JSONL --------
    def write_jsonl(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        include_metadata: bool = True,
    ) -> str:
        payload = [_to_plain(r) for r in results]
        targets = [_get_target_name(r) for r in results]

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = (
                self.output_dir / f"analysis_results_{timestamp}.jsonl"
            )
        else:
            output_file = Path(output_path)
            _ensure_parent(output_file)

        with output_file.open("w", encoding="utf-8") as f:
            if include_metadata:
                metadata = {
                    "_metadata": {
                        "format": "phonenv-jsonl",
                        "version": "1.0",
                        "timestamp": datetime.now().isoformat(),
                        "total_results": len(payload),
                        "targets": targets,
                    }
                }
                f.write(json.dumps(metadata, ensure_ascii=False) + "\n")

            for row in payload:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return str(output_file)

    # -------- JSON --------
    def write_json(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        pretty: bool = True,
    ) -> str:
        payload = [_to_plain(r) for r in results]

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = (
                self.output_dir / f"analysis_results_{timestamp}.json"
            )
        else:
            output_file = Path(output_path)
            _ensure_parent(output_file)

        data = {
            "metadata": {
                "format": "phonenv-json",
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "total_results": len(payload),
            },
            "results": payload,
        }

        with output_file.open("w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(data, f, separators=(",", ":"), ensure_ascii=False)

        return str(output_file)

    # -------- CSV --------
    def write_csv(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        flatten_environments: bool = True,
    ) -> str:
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"analysis_results_{timestamp}.csv"
        else:
            output_file = Path(output_path)
            _ensure_parent(output_file)

        # normalize to dict-y structures
        payload = [_to_plain(r) for r in results]

        def _get_envs(res: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
            envs = res.get("environments", {})
            # ensure dict-of-dicts
            return envs if isinstance(envs, dict) else {}

        with output_file.open("w", newline="", encoding="utf-8") as f:
            if flatten_environments:
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
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for res in payload:
                    target = res.get("target", _get_target_name(res))
                    source_file = res.get("source_file", "")
                    total_occ = res.get("total_occurrences", 0)

                    for group_name, envs in _get_envs(res).items():
                        if not isinstance(envs, dict):
                            continue
                        for env, examples in envs.items():
                            if not isinstance(examples, (list, tuple)):
                                examples = []

                            # Deduplicate examples and normalize to NFC to handle canonical equivalents
                            import unicodedata as ud

                            deduped_examples = list(
                                dict.fromkeys(
                                    ud.normalize("NFC", ex) for ex in examples
                                )
                            )

                            # Parse environment key - use full tokens, don't truncate affricates
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
                                    "examples": "; ".join(
                                        deduped_examples[:5]
                                    ),
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
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for res in payload:
                    writer.writerow(
                        {
                            "target": res.get("target", _get_target_name(res)),
                            "total_occurrences": res.get(
                                "total_occurrences", 0
                            ),
                            "environments_json": json.dumps(
                                res.get("environments", {}), ensure_ascii=False
                            ),
                            "source_file": res.get("source_file", ""),
                        }
                    )

        return str(output_file)

    # -------- TXT --------
    def write_text_report(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        include_examples: bool = True,
        max_examples: int = 5,
        transcription_mode: str = "narrow",
    ) -> str:
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"analysis_report_{timestamp}.txt"
        else:
            output_file = Path(output_path)
            _ensure_parent(output_file)

        payload = [_to_plain(r) for r in results]

        with output_file.open("w", encoding="utf-8") as f:
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
            structural_count = sum(
                1 for res in payload if "process_type" in res
            )
            phonemic_count = num_alternations - structural_count

            # Header
            f.write("PHONETIC ENVIRONMENT ANALYSIS REPORT\n")
            f.write("=" * REPORT_SEPARATOR_WIDTH + "\n")
            f.write(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"Transcription mode: {transcription_mode}\n")
            f.write(f"Targets: {num_targets}\n")
            f.write(
                f"Alternations: {num_alternations} (phonemic: {phonemic_count}, structural: {structural_count})\n"
            )
            f.write(f"Total lexical items: {len(payload)}\n")

            # Add source file information to header
            if payload:
                source_file = payload[0].get("source_file", "")
                if source_file:
                    f.write(f"Source dataset: {source_file}\n")
            f.write("\n")

            # Summary
            f.write("SUMMARY\n")
            f.write("-" * NARROW_SEPARATOR_WIDTH + "\n")
            f.write(f"{'Target':<10} {'Count':<12} Envs\n")
            f.write("-" * NARROW_SEPARATOR_WIDTH + "\n")

            def _env_count(res: Dict[str, Any]) -> int:
                envs = res.get("environments", {})
                if isinstance(envs, dict):
                    return sum(
                        len(v) for v in envs.values() if isinstance(v, dict)
                    )
                return 0

            for res in payload:
                # Skip alternations in summary (they'll be in details)
                if "pair" in res or "alternation" in res:
                    continue
                target = res.get("target", _get_target_name(res))
                env_count = _env_count(res)
                f.write(
                    f"{target:<10} {res.get('total_occurrences', 0):<12} {env_count}\n"
                )

            f.write("\n" + "=" * REPORT_SEPARATOR_WIDTH + "\n\n")

            # Details
            for i, res in enumerate(payload, 1):
                # Check if this is an alternation result
                if "pair" in res or "alternation" in res:
                    self._write_alternation_detail(
                        f, i, res, include_examples, max_examples
                    )
                else:
                    # Regular target result
                    target = res.get("target", _get_target_name(res))
                    total = res.get("total_occurrences", 0)
                    envs = (
                        res.get("environments", {})
                        if isinstance(res.get("environments", {}), dict)
                        else {}
                    )
                    f.write(f"TARGET {i}: '{target}' ({total})\n")
                    f.write("-" * NARROW_SEPARATOR_WIDTH + "\n")

                    if not envs:
                        f.write("No environments found.\n\n")
                    else:
                        for group_name, environments in envs.items():
                            if not environments:
                                continue
                            f.write(f"  {group_name}:\n")
                            for env, examples in environments.items():
                                if not isinstance(examples, (list, tuple)):
                                    examples = []

                                # Deduplicate examples and normalize to NFC to handle canonical equivalents
                                import unicodedata as ud

                                deduped_examples = list(
                                    dict.fromkeys(
                                        ud.normalize("NFC", ex)
                                        for ex in examples
                                    )
                                )

                                # Parse environment key - use full tokens, don't truncate affricates
                                left, right = (
                                    (env.split("__", 1) + [""])[:2]
                                    if "__" in env
                                    else (env, "")
                                )

                                # Compact format: context ×count : examples
                                count = len(deduped_examples)
                                f.write(f"    {left} _ {right} ×{count}")

                                if include_examples and deduped_examples:
                                    shown = deduped_examples[:max_examples]
                                    f.write(f" : {', '.join(shown)}")
                                    extra = max(
                                        0, len(deduped_examples) - max_examples
                                    )
                                    if extra:
                                        f.write(f" (+{extra} more)")
                                f.write("\n")
                            f.write("\n")

                if i < len(payload):
                    f.write("—\n\n")

        return str(output_file)

    def _write_alternation_detail(
        self,
        f,
        index: int,
        res: Dict[str, Any],
        include_examples: bool,
        max_examples: int,
    ) -> None:
        """Write alternation result details to report file."""
        import unicodedata as ud

        # Check if this is a structural alternation (X ~ Ø)
        if "process_type" in res:
            self._write_structural_alternation_detail(
                f, index, res, include_examples, max_examples
            )
            return

        # Handle phonemic alternation (standard case)
        # Handle both _to_plain format (pair key) and to_dict format (alternation key)
        if "pair" in res:
            pair = res["pair"]
            alternation = (
                f"{pair.get('segment1', '')} ~ {pair.get('segment2', '')}"
            )
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

        f.write(f"ALTERNATION {index}: '{alternation}' ({total_count})\n")
        f.write("-" * NARROW_SEPARATOR_WIDTH + "\n")

        # Format pattern type with descriptive label
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

        f.write(f"Pattern: {pattern_display}\n")
        f.write(
            "Method: Auto-window = L2-left; Abstraction = {L2/L1: class+features, R1/R2: segment}; Min-evidence = 3\n"
        )
        if analysis:
            f.write(f"Analysis: {analysis}\n")
        f.write("-" * 60 + "\n\n")

        # Helper to convert extended context to simple _ notation
        def simplify_context(env: str) -> tuple:
            """Convert L2=X|L1=Y|R1=Z format to Y _ Z for display."""
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

        # VARIANT 1
        env1 = res.get("segment1_envs", res.get("segment1_environments", {}))
        if env1:
            f.write(f"  VARIANT 1: '{seg1}' ({total1})\n")
            f.write("  " + "-" * 40 + "\n")
            for group_name, environments in env1.items():
                if not environments:
                    continue
                f.write(f"    {group_name}:\n")
                for env, examples in environments.items():
                    if not isinstance(examples, (list, tuple)):
                        examples = []
                    deduped = list(
                        dict.fromkeys(
                            ud.normalize("NFC", ex) for ex in examples
                        )
                    )
                    left, right = simplify_context(env)
                    count = len(deduped)
                    f.write(f"      {left} _ {right} ×{count}")
                    if include_examples and deduped:
                        shown = deduped[:max_examples]
                        f.write(f" : {', '.join(shown)}")
                        extra = max(0, len(deduped) - max_examples)
                        if extra:
                            f.write(f" (+{extra} more)")
                    f.write("\n")
            f.write("\n")

        # VARIANT 2
        env2 = res.get("segment2_envs", res.get("segment2_environments", {}))
        if env2:
            f.write(f"  VARIANT 2: '{seg2}' ({total2})\n")
            f.write("  " + "-" * 40 + "\n")
            for group_name, environments in env2.items():
                if not environments:
                    continue
                f.write(f"    {group_name}:\n")
                for env, examples in environments.items():
                    if not isinstance(examples, (list, tuple)):
                        examples = []
                    deduped = list(
                        dict.fromkeys(
                            ud.normalize("NFC", ex) for ex in examples
                        )
                    )
                    left, right = simplify_context(env)
                    count = len(deduped)
                    f.write(f"      {left} _ {right} ×{count}")
                    if include_examples and deduped:
                        shown = deduped[:max_examples]
                        f.write(f" : {', '.join(shown)}")
                        extra = max(0, len(deduped) - max_examples)
                        if extra:
                            f.write(f" (+{extra} more)")
                    f.write("\n")
            f.write("\n")

    def _write_structural_alternation_detail(
        self,
        f,
        index: int,
        res: Dict[str, Any],
        include_examples: bool,
        max_examples: int,
    ) -> None:
        """Write structural alternation (X ~ Ø) result details to report file."""
        import unicodedata as ud

        # Extract structural alternation fields
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

        # Write header
        f.write(f"STRUCTURAL ALTERNATION {index}: '{alternation}' ({total})\n")
        f.write("-" * NARROW_SEPARATOR_WIDTH + "\n")

        # Format process type with descriptive label
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
        process_display = process_labels.get(
            process_type, process_type.upper()
        )

        f.write(f"Process: {process_display}\n")
        f.write(f"Rule: {rule}\n")
        f.write(
            "Method: Auto-window = L2-left; Abstraction = {L2/L1: class+features, R1/R2: segment}; Min-evidence = 3\n"
        )
        if analysis:
            f.write(f"Analysis: {analysis}\n")
        f.write("-" * 60 + "\n\n")

        # Show same-frame contrasts if available
        frame_contrasts = res.get("frame_contrasts", {})
        if frame_contrasts:
            f.write("  Same-frame contrasts (with-X vs with-\u00d8):\n")
            # Show top 3 by with_X count
            sorted_frames = sorted(
                frame_contrasts.items(),
                key=lambda kv: kv[1]["with_X"],
                reverse=True,
            )[:3]
            for ctx, counts in sorted_frames:
                with_x = counts["with_X"]
                with_null = counts["with_\u00d8"]
                skew = counts["skew"]
                f.write(
                    f"    {ctx}: with-{segment} = {with_x}, with-\u00d8 = {with_null} \u2192 skew = {skew:.2f}\n"
                )
            f.write("\n")

        # Show dominant contexts
        if dominant_contexts:
            f.write("  Dominant contexts:\n")
            for ctx in dominant_contexts:
                f.write(f"    {ctx}\n")
            f.write("\n")

        # Show detailed environments for the real segment
        envs = res.get("segment_envs", res.get("segment_environments", {}))
        if envs and include_examples:
            f.write(f"  {segment} distribution:\n")
            for group_name, environments in envs.items():
                if not environments:
                    continue
                f.write(f"    {group_name}:\n")
                for env, examples in environments.items():
                    if not isinstance(examples, (list, tuple)):
                        examples = []
                    deduped = list(
                        dict.fromkeys(
                            ud.normalize("NFC", ex) for ex in examples
                        )
                    )
                    left, right = (
                        (env.split("__", 1) + [""])[:2]
                        if "__" in env
                        else (env, "")
                    )
                    count = len(deduped)
                    f.write(f"      {left} _ {right} ×{count}")
                    if deduped:
                        shown = deduped[:max_examples]
                        f.write(f" : {', '.join(shown)}")
                        extra = max(0, len(deduped) - max_examples)
                        if extra:
                            f.write(f" (+{extra} more)")
                    f.write("\n")
            f.write("\n")


class AutoOutputWriter:
    """Automatically determines output format and writes results."""

    def __init__(self, output_dir: str = "data/output"):
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
            _ensure_parent(path)
            output_paths["jsonl"] = self.writer.write_jsonl(results, str(path))
        elif fmt == "json":
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.json")
            )
            _ensure_parent(path)
            output_paths["json"] = self.writer.write_json(results, str(path))
        elif fmt == "csv":
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.csv")
            )
            _ensure_parent(path)
            output_paths["csv"] = self.writer.write_csv(results, str(path))
        elif fmt == "txt":
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.txt")
            )
            _ensure_parent(path)
            output_paths["txt"] = self.writer.write_text_report(
                results, str(path), transcription_mode=transcription_mode
            )
        else:
            # Default to txt for unknown formats
            path = (
                Path(custom_path)
                if custom_path
                else (self.output_dir / f"{base_name}.txt")
            )
            _ensure_parent(path)
            output_paths["txt"] = self.writer.write_text_report(
                results, str(path), transcription_mode=transcription_mode
            )

        return output_paths

    def write_single_target(
        self, result: Any, format_preference: str = "txt"
    ) -> str:
        outputs = self.write_batch_results([result], format_preference)
        return list(outputs.values())[0] if outputs else ""


# ========================= GLOBAL CACHE MANAGEMENT =========================

_global_cache: Optional[ResultCache] = None


def get_cache(cache_dir: str = "data/.cache") -> ResultCache:
    """Get global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ResultCache(cache_dir)
    return _global_cache


def clear_cache() -> None:
    cache = get_cache()
    cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    cache = get_cache()
    return cache.get_stats()


# ========================= CONVENIENCE FUNCTIONS =========================


def write_results(
    results: List[Any],
    output_format: str = "jsonl",
    output_path: Optional[str] = None,
    output_dir: str = "data/output",
) -> str:
    """Convenience function to write results in specified format."""
    writer = OutputWriter(output_dir)

    fmt = (output_format or "jsonl").lower()
    if fmt == "jsonl":
        return writer.write_jsonl(results, output_path)
    if fmt == "json":
        return writer.write_json(results, output_path)
    if fmt == "csv":
        return writer.write_csv(results, output_path)
    if fmt == "txt":
        return writer.write_text_report(results, output_path)
    raise ValueError(f"Unsupported output format: {output_format}")


def get_default_output_path(
    format_type: str,
    targets: Optional[List[str]] = None,
    output_dir: str = "data/output",
) -> str:
    """Generate default output path for given format and targets."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if targets:
        target_str = "_".join(_slug(t) for t in targets[:3])
        if len(targets) > 3:
            target_str += f"_plus{len(targets) - 3}"
        filename = f"analysis_{target_str}_{timestamp}.{format_type}"
    else:
        filename = f"analysis_results_{timestamp}.{format_type}"

    return str(Path(output_dir) / filename)
