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
import time
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

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

    def is_valid(self, current_dataset_hash: str, current_config: Dict[str, Any]) -> bool:
        return (self.dataset_hash == current_dataset_hash
                and self.analysis_config == current_config)


class ResultCache:
    """Manages caching of phonetic analysis results with SHA256-based keys."""

    def __init__(self, cache_dir: str = "data/.cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "analysis_cache.jsonl"

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
                    except (json.JSONDecodeError, TypeError, KeyError):
                        # skip malformed lines
                        continue
        except (IOError, OSError) as e:
            print(f"Warning: Could not load cache: {e}")

    def _save_cache(self) -> None:
        try:
            temp_file = self.cache_file.with_suffix(".tmp")
            with temp_file.open("w", encoding="utf-8") as f:
                for entry in self._memory_cache.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            temp_file.replace(self.cache_file)
        except (IOError, OSError) as e:
            print(f"Warning: Could not save cache: {e}")

    def _compute_dataset_hash(self, dataset_path: str) -> str:
        path = Path(dataset_path)
        if not path.exists():
            return ""
        hasher = hashlib.sha256()
        try:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (IOError, OSError):
            return ""

    def _compute_cache_key(self, target: str, dataset_path: str, config: Dict[str, Any]) -> str:
        key_data = {
            "target": target,
            "dataset_path": str(Path(dataset_path).resolve()),
            "config": config,
        }
        key_string = json.dumps(key_data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    def get_analysis_config(self, analyzer) -> Dict[str, Any]:
        """Extract relevant configuration from analyzer for cache key."""
        config = {
            "use_ipa_processing": getattr(analyzer, "use_ipa_processing", False),
            "transcription_mode": getattr(analyzer, "transcription_mode", "narrow"),
            "no_color": getattr(analyzer, "no_color", False),
        }

        if hasattr(analyzer, "ipa_processor_v2") and getattr(analyzer, "ipa_processor_v2"):
            processor = analyzer.ipa_processor_v2
            # include match_mode to distinguish broad vs narrow semantic matching
            match_mode = getattr(processor.config, "match_mode", None)
            config["ipa_processor"] = {
                "use_panphon": getattr(processor.config, "use_panphon", False),
                "tie_bar_clusters": getattr(processor.config, "tie_bar_clusters", []),
                "diphthong_patterns": getattr(processor.config, "diphthong_patterns", []),
                "normalization_mode": getattr(processor.config, "normalization_mode", "NFC"),
                "match_mode": match_mode if match_mode is not None else "broad",
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
            from .data import TargetResult  # type: ignore
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
                "source_file": getattr(result, "source_file", str(Path(dataset_path).resolve())),
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
        to_remove = [k for k, e in self._memory_cache.items() if e.target == target]
        for k in to_remove:
            self._memory_cache.pop(k, None)
        return len(to_remove)

    def clear_dataset(self, dataset_path: str) -> int:
        resolved = str(Path(dataset_path).resolve())
        to_remove = [k for k, e in self._memory_cache.items() if e.dataset_path == resolved]
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

    def cleanup_old_entries(self, max_age_days: float = 30.0) -> int:
        cutoff = time.time() - (max_age_days * 24 * 60 * 60)
        to_remove = [k for k, e in self._memory_cache.items() if e.timestamp < cutoff]
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
    if isinstance(result, dict) and "target" in result:
        return str(result["target"])
    if hasattr(result, "target"):
        return str(getattr(result, "target"))
    if hasattr(result, "query"):
        return str(getattr(result, "query"))
    return str(result)


def _slug(s: str, max_len: int = 80) -> str:
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
        return {str(k): _to_plain(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple, set)):
        return [_to_plain(v) for v in obj]

    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}

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
            output_file = self.output_dir / f"analysis_results_{timestamp}.jsonl"
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
            output_file = self.output_dir / f"analysis_results_{timestamp}.json"
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
                    "target", "group", "environment", "left_context", "right_context",
                    "count", "examples", "source_file", "total_occurrences",
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
                            left, right = (env.split("__", 1) + [""])[:2] if "__" in env else (env, "")
                            writer.writerow({
                                "target": target,
                                "group": group_name,
                                "environment": env,
                                "left_context": left,
                                "right_context": right,
                                "count": len(examples),
                                "examples": "; ".join(list(examples)[:5]),
                                "source_file": source_file,
                                "total_occurrences": total_occ,
                            })
            else:
                fieldnames = ["target", "total_occurrences", "environments_json", "source_file"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for res in payload:
                    writer.writerow({
                        "target": res.get("target", _get_target_name(res)),
                        "total_occurrences": res.get("total_occurrences", 0),
                        "environments_json": json.dumps(res.get("environments", {}), ensure_ascii=False),
                        "source_file": res.get("source_file", ""),
                    })

        return str(output_file)

    # -------- TXT --------
    def write_text_report(
        self,
        results: List[Any],
        output_path: Optional[str] = None,
        include_examples: bool = True,
        max_examples: int = 5,
    ) -> str:
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"analysis_report_{timestamp}.txt"
        else:
            output_file = Path(output_path)
            _ensure_parent(output_file)

        payload = [_to_plain(r) for r in results]

        with output_file.open("w", encoding="utf-8") as f:
            # Header
            f.write("PHONETIC ENVIRONMENT ANALYSIS REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total targets analyzed: {len(payload)}\n\n")

            # Summary
            f.write("SUMMARY\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'Target':<10} {'Occurrences':<12} {'Environments':<15} {'Source'}\n")
            f.write("-" * 60 + "\n")

            def _env_count(res: Dict[str, Any]) -> int:
                envs = res.get("environments", {})
                if isinstance(envs, dict):
                    return sum(len(v) for v in envs.values() if isinstance(v, dict))
                return 0

            for res in payload:
                target = res.get("target", _get_target_name(res))
                env_count = _env_count(res)
                source_name = Path(res.get("source_file", "")).name
                f.write(f"{target:<10} {res.get('total_occurrences', 0):<12} {env_count:<15} {source_name}\n")

            f.write("\n" + "=" * 60 + "\n\n")

            # Details
            for i, res in enumerate(payload, 1):
                target = res.get("target", _get_target_name(res))
                envs = res.get("environments", {}) if isinstance(res.get("environments", {}), dict) else {}
                f.write(f"TARGET {i}: '{target}'\n")
                f.write("-" * 40 + "\n")
                f.write(f"Total occurrences: {res.get('total_occurrences', 0)}\n")
                f.write(f"Source file: {res.get('source_file', '')}\n\n")

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
                            left, right = (env.split('__', 1) + [''])[:2] if '__' in env else (env, "")
                            f.write(f"    {left} _ {right} ({len(examples)} occurrences)")
                            if include_examples and examples:
                                shown = list(examples)[:max_examples]
                                f.write(f": {', '.join(shown)}")
                                extra = max(0, len(examples) - max_examples)
                                if extra:
                                    f.write(f" (+{extra} more)")
                            f.write("\n")
                        f.write("\n")

                if i < len(payload):
                    f.write("-" * 60 + "\n\n")

        return str(output_file)


class AutoOutputWriter:
    """Automatically determines output format and writes results."""

    def __init__(self, output_dir: str = "data/output"):
        self.writer = OutputWriter(output_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_batch_results(
        self,
        results: List[Any],
        format_preference: str = "jsonl",
        custom_path: Optional[str] = None,
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

        fmt = (format_preference or "jsonl").lower()
        output_paths: Dict[str, str] = {}

        if fmt == "jsonl":
            path = Path(custom_path) if custom_path else (self.output_dir / f"{base_name}.jsonl")
            _ensure_parent(path)
            output_paths["jsonl"] = self.writer.write_jsonl(results, str(path))
        elif fmt == "json":
            path = Path(custom_path) if custom_path else (self.output_dir / f"{base_name}.json")
            _ensure_parent(path)
            output_paths["json"] = self.writer.write_json(results, str(path))
        elif fmt == "csv":
            path = Path(custom_path) if custom_path else (self.output_dir / f"{base_name}.csv")
            _ensure_parent(path)
            output_paths["csv"] = self.writer.write_csv(results, str(path))
        elif fmt == "txt":
            path = Path(custom_path) if custom_path else (self.output_dir / f"{base_name}.txt")
            _ensure_parent(path)
            output_paths["txt"] = self.writer.write_text_report(results, str(path))
        else:
            path = Path(custom_path) if custom_path else (self.output_dir / f"{base_name}.jsonl")
            _ensure_parent(path)
            output_paths["jsonl"] = self.writer.write_jsonl(results, str(path))

        return output_paths

    def write_single_target(self, result: Any, format_preference: str = "txt") -> str:
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