"""Result caching with SHA256-based fingerprinting.

IMPORT RULES:
- Can import: models, config, logger
- Cannot import: processors, alternations, parsers, output.formats
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Optional

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from config import (
    CACHE_MAX_ENTRIES,
    CACHE_MAX_SIZE_MB,
    CACHE_FILENAME,
    DEFAULT_CACHE_DIR,
)
from logger import get_logger

if TYPE_CHECKING:
    from analyze import PhoneticAnalyzer

logger = get_logger()

# Additional constants not in config
DEFAULT_CACHE_MAX_AGE_DAYS = 30.0


# ========================= CACHE ENTRY =========================


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


# ========================= RESULT CACHE =========================


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
        """Load cache from disk into memory."""
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
            logger.cache_error("load", e, cache_file=str(self.cache_file))

    def _save_cache(self) -> None:
        """Save in-memory cache to disk."""
        try:
            temp_file = self.cache_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                for entry in self._memory_cache.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
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
        """Generate unique cache key from target, dataset path, and config."""
        key_data = {
            "target": target,
            "dataset_path": str(Path(dataset_path).resolve()),
            "config": config,
        }
        key_string = json.dumps(key_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    def get_analysis_config(self, analyzer: "PhoneticAnalyzer") -> Dict[str, Any]:
        """Extract relevant configuration from analyzer for cache key."""
        config = {
            "use_ipa_processing": getattr(analyzer, "use_ipa_processing", False),
            "transcription_mode": getattr(analyzer, "transcription_mode", "narrow"),
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
                "tie_bar_clusters": getattr(processor.config, "tie_bar_clusters", []),
                "diphthong_patterns": getattr(
                    processor.config, "diphthong_patterns", []
                ),
                "normalization_mode": getattr(
                    processor.config, "normalization_mode", "NFC"
                ),
                "match_mode": match_mode if match_mode is not None else "broad",
            }

        return config

    def get(
        self, target: str, dataset_path: str, analyzer: "PhoneticAnalyzer"
    ) -> Optional[Any]:
        """Retrieve cached result for target, or None if not found/stale."""
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
            from models import TargetResult

            return TargetResult(
                target=entry.result["target"],
                environments=entry.result["environments"],
                total_occurrences=entry.result["total_occurrences"],
                source_file=entry.result["source_file"],
                analysis_mode=entry.result.get("analysis_mode", "narrow"),
            )
        except Exception:
            # fall back to dict
            return entry.result

    def put(
        self, target: str, dataset_path: str, analyzer: "PhoneticAnalyzer", result: Any
    ) -> None:
        """Cache analysis result for target."""
        config = self.get_analysis_config(analyzer)
        cache_key = self._compute_cache_key(target, dataset_path, config)
        dataset_hash = self._compute_dataset_hash(dataset_path)

        # Convert result to plain dict
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
        """Clear entire cache (memory and disk)."""
        self._memory_cache.clear()
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
        except Exception:
            pass

    def clear_target(self, target: str) -> int:
        """Clear all cache entries for a specific target."""
        to_remove = [k for k, e in self._memory_cache.items() if e.target == target]
        for k in to_remove:
            self._memory_cache.pop(k, None)
        return len(to_remove)

    def clear_dataset(self, dataset_path: str) -> int:
        """Clear all cache entries for a specific dataset."""
        resolved = str(Path(dataset_path).resolve())
        to_remove = [
            k for k, e in self._memory_cache.items() if e.dataset_path == resolved
        ]
        for k in to_remove:
            self._memory_cache.pop(k, None)
        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
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
        """Remove cache entries older than max_age_days."""
        cutoff = time.time() - (max_age_days * 24 * 60 * 60)
        to_remove = [
            k for k, e in self._memory_cache.items() if e.timestamp < cutoff
        ]
        for k in to_remove:
            self._memory_cache.pop(k, None)
        return len(to_remove)

    def save(self) -> None:
        """Explicitly save cache to disk."""
        self._save_cache()

    def __del__(self):
        """Save cache on destruction."""
        try:
            self._save_cache()
        except Exception:
            pass


# ========================= HELPER FUNCTIONS =========================


def _to_plain(obj: Any) -> Any:
    """Convert dataclass/complex objects to plain dicts recursively."""
    from dataclasses import is_dataclass, asdict

    if is_dataclass(obj):
        return asdict(obj)
    elif isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_to_plain(item) for item in obj]
    else:
        return obj


def _get_target_name(result: Any) -> str:
    """Extract target name from result object."""
    # Check for alternation results first
    if isinstance(result, dict) and "alternation" in result:
        return str(result["alternation"])
    # Then regular target results
    if hasattr(result, "target"):
        return result.target
    if isinstance(result, dict) and "target" in result:
        return result["target"]
    return "unknown"


__all__ = [
    "CacheEntry",
    "ResultCache",
]
