"""I/O operations for phonetic environment analysis (backward compatibility module).

DEPRECATED: This module is maintained for backward compatibility only.
New code should import from the output/ package directly:
- output.cache.ResultCache, CacheEntry
- output.writers.OutputWriter, AutoOutputWriter
- output.formats.*

This module will be removed in version 3.0.
"""

from __future__ import annotations

import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Re-export from new output/ package for backward compatibility
from output.cache import CacheEntry, ResultCache
from output.writers import OutputWriter, AutoOutputWriter

# Import helper functions we still need
from output.writers import _slug, _get_target_name

# Initialize global cache instance
_global_cache: Optional[ResultCache] = None


# ========================= CACHE CONVENIENCE FUNCTIONS =========================


def get_cache(cache_dir: str = "data/.cache") -> ResultCache:
    """Get or create global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ResultCache(cache_dir=cache_dir)
    return _global_cache


def clear_cache() -> None:
    """Clear global cache."""
    cache = get_cache()
    cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics."""
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


# Show deprecation warning when module is imported
warnings.warn(
    "phonenv_io module is deprecated and will be removed in version 3.0. "
    "Please import from output/ package instead: "
    "from output.cache import ResultCache; from output.writers import OutputWriter",
    DeprecationWarning,
    stacklevel=2,
)
