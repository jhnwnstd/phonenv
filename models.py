"""Data models for Phonenv.

IMPORT RULES:
- This module MUST NOT import from any other phonenv modules
- Keep it pure: stdlib types + dataclasses only
- Use forward references for type hints

This ensures no circular import issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional, Set, Mapping, Any

# ========================= ENUMS =========================


class LogLevel(Enum):
    """Logging levels."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class DistributionPattern(Enum):
    """Phonological distribution patterns."""

    COMPLEMENTARY = "complementary"
    CONTRASTIVE = "contrastive"
    FREE_VARIATION = "free_variation"
    NEUTRALIZATION = "neutralization"
    PARTIAL_OVERLAP = "partial_overlap"
    INCONCLUSIVE = "inconclusive"


# ========================= DATA ENTRY MODELS =========================


@dataclass(frozen=True)
class WordEntry:
    """Rich data structure for parsed word entries with metadata."""

    ipa: str
    section: Dict[str, str] = field(default_factory=dict)
    tags: Tuple[str, ...] = field(default_factory=tuple)
    source_path: Optional[str] = None
    line_no: Optional[int] = None


@dataclass(frozen=True)
class AlternationPair:
    """Represents a phonological alternation between two segments."""

    segment1: str
    segment2: str
    description: Optional[str] = None
    pair_filter: Optional[str] = None  # e.g., "1:2" to match word pairs by position

    def __str__(self) -> str:
        return f"{self.segment1} ~ {self.segment2}"

    def __repr__(self) -> str:
        return f"AlternationPair({self.segment1!r}, {self.segment2!r})"


# ========================= RESULT MODELS =========================


@dataclass
class TargetResult:
    """Result of analyzing a single target phoneme."""

    target: str
    environments: Dict[str, Dict[str, List[str]]]
    total_occurrences: int
    source_file: str
    analysis_mode: str = "narrow"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "target": self.target,
            "environments": self.environments,
            "total_occurrences": self.total_occurrences,
            "source_file": self.source_file,
            "analysis_mode": self.analysis_mode,
        }


@dataclass
class AlternationResult:
    """Result of analyzing a phonological alternation."""

    pair: AlternationPair
    segment1_envs: Mapping[str, Mapping[str, List[str]]]
    segment2_envs: Mapping[str, Mapping[str, List[str]]]
    segment1_total: int
    segment2_total: int
    source_file: str
    pattern: str
    analysis: str
    window_size: int = 1
    decision_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pair": str(self.pair),
            "segment1": self.pair.segment1,
            "segment2": self.pair.segment2,
            "segment1_envs": dict(self.segment1_envs),
            "segment2_envs": dict(self.segment2_envs),
            "segment1_total": self.segment1_total,
            "segment2_total": self.segment2_total,
            "source_file": self.source_file,
            "pattern": self.pattern,
            "analysis": self.analysis,
            "window_size": self.window_size,
            "decision_score": self.decision_score,
        }


@dataclass
class StructuralAlternationResult:
    """Result of analyzing structural alternations (X ~ Ø)."""

    pair: AlternationPair
    present_segment: str
    absent_segment: str
    present_envs: Mapping[str, Mapping[str, List[str]]]
    present_total: int
    process: str
    process_type: str
    analysis: str
    source_file: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pair": str(self.pair),
            "present_segment": self.present_segment,
            "absent_segment": self.absent_segment,
            "present_envs": dict(self.present_envs),
            "present_total": self.present_total,
            "process": self.process,
            "process_type": self.process_type,
            "analysis": self.analysis,
            "source_file": self.source_file,
        }


# ========================= CACHE MODELS =========================


@dataclass(frozen=True)
class CacheKey:
    """Immutable cache key for analysis results."""

    target: str
    dataset_hash: str
    config_hash: str

    def __str__(self) -> str:
        return f"{self.target}:{self.dataset_hash[:8]}:{self.config_hash[:8]}"


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""

    key: str
    result: Dict[str, Any]
    timestamp: float
    dataset_hash: str
    analysis_config: Dict[str, Any]
    result_type: str = "target"  # "target" | "alternation"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "key": self.key,
            "result": self.result,
            "timestamp": self.timestamp,
            "dataset_hash": self.dataset_hash,
            "analysis_config": self.analysis_config,
            "result_type": self.result_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheEntry:
        """Create from dictionary."""
        return cls(
            key=data["key"],
            result=data["result"],
            timestamp=data["timestamp"],
            dataset_hash=data["dataset_hash"],
            analysis_config=data["analysis_config"],
            result_type=data.get("result_type", "target"),
        )

    def is_valid(
        self, current_dataset_hash: str, current_config: Dict[str, Any]
    ) -> bool:
        """Check if cache entry is still valid."""
        return (
            self.dataset_hash == current_dataset_hash
            and self.analysis_config == current_config
        )


# ========================= EXPORTS =========================

__all__ = [
    # Enums
    "LogLevel",
    "DistributionPattern",
    # Data entries
    "WordEntry",
    "AlternationPair",
    # Results
    "TargetResult",
    "AlternationResult",
    "StructuralAlternationResult",
    # Cache
    "CacheKey",
    "CacheEntry",
]
