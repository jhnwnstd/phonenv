"""File parsing and data loading for Phonenv.

IMPORT RULES:
- Can import: models, utils, normalize
- Cannot import: processors, alternations, output, cli, data
"""

from __future__ import annotations

import regex as re
import unicodedata as ud
from pathlib import Path
from typing import Dict, Iterator, List, Tuple, Optional, Set

from models import WordEntry, AlternationPair
from utils import normalize_tiebar, is_safe_path

# ========================= CONSTANTS =========================

_COMMENT = re.compile(r"#.*$")
_SECTION = re.compile(r"^\[(?P<body>.+)\]\s*$")
_KV = re.compile(r"\s*([a-zA-Z_][\w-]*)\s*=\s*([^;]+)\s*")
_BRACKETS = re.compile(r"\[(?P<tag>[^\[\]]+)\]")

_DEFAULT_SECTION: Dict[str, str] = {
    "lang": "und",
    "mode": "narrow",
    "profile": "default",
}

# ========================= HELPER FUNCTIONS =========================


def strip_comment(text: str) -> str:
    """Remove everything after # symbol."""
    return _COMMENT.sub("", text).strip()


def parse_section_header(line: str) -> Optional[Dict[str, str]]:
    """Parse section header like [lang=en-GB; mode=narrow; profile=english]."""
    m = _SECTION.match(line)
    if not m:
        return None
    body = m.group("body")
    out: Dict[str, str] = {}

    # Must contain only valid key=value pairs and/or bare flags
    valid_section = True
    for part in body.split(";"):
        part = part.strip()
        if not part:
            continue
        kv = _KV.match(part)
        if kv:
            k, v = kv.group(1), kv.group(2).strip()
            out[k] = v
        else:
            # Check if it's a valid bare flag
            if isinstance(part, str) and re.match(r"^[a-zA-Z_][\w-]*$", part):
                out[part] = "true"
            else:
                valid_section = False
                break

    return out if valid_section and out else None


def extract_tags(text: str) -> Tuple[str, Tuple[str, ...]]:
    """Extract bracket tags and return cleaned string and tags."""
    tags = tuple(t.strip() for t in _BRACKETS.findall(text))
    text = _BRACKETS.sub("", text)
    return text.strip(), tags


def split_targets_line(line: str) -> List[str]:
    """Split line by comma or whitespace; supports mixed styles."""
    if "," in line:
        parts = [t for t in (p.strip() for p in line.split(",")) if t]
    else:
        parts = [t for t in line.split() if t]
    return parts


# ========================= WORD ENTRY PARSING =========================


def iter_word_entries(path: str | Path) -> Iterator[WordEntry]:
    """Parse enhanced dataset format with sections, comments, and tags.

    Yields WordEntry objects with rich metadata while maintaining
    backwards compatibility with simple "one IPA per line" format.

    Args:
        path: Path to dataset file

    Yields:
        WordEntry objects with IPA string and metadata

    Raises:
        ValueError: If path is outside allowed directory
    """
    p = Path(path)

    # Security: Validate path is within project directory
    if not is_safe_path(p):
        raise ValueError(
            f"Access denied: path '{p}' is outside allowed directory"
        )

    section = dict(_DEFAULT_SECTION)

    if not p.exists():
        return

    with p.open("r", encoding="utf-8") as fh:
        for i, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")

            # 1) section headers (strip comments first)
            clean_line = strip_comment(line)
            sh = parse_section_header(clean_line)
            if sh is not None:
                section = {**section, **{k: v for k, v in sh.items() if v}}
                continue

            # 2) comments / blanks
            s = strip_comment(line)
            if not s:
                continue

            # 3) bracket tags
            s, tags = extract_tags(s)
            if not s:
                continue

            # 4) normalize form + tie-bars for stability
            s = ud.normalize("NFC", s)
            s = normalize_tiebar(s)

            yield WordEntry(
                ipa=s,
                section=section.copy(),
                tags=tags,
                source_path=str(p),
                line_no=i,
            )


def load_words_set(path: str = "data/dataset.txt") -> Set[str]:
    """Load words as set (backwards-compatible)."""
    return {e.ipa for e in iter_word_entries(path)}


def load_words_list(path: str = "data/dataset.txt") -> List[str]:
    """Load words as list (backwards-compatible)."""
    return [e.ipa for e in iter_word_entries(path)]


def load_words_with_tags(path: str = "data/dataset.txt") -> List[WordEntry]:
    """Load words with full metadata including tags."""
    return list(iter_word_entries(path))


# ========================= TARGET PARSING =========================


def parse_alternation_line(line: str) -> Optional[AlternationPair]:
    """Parse alternation from line like 'p ~ b' or 'p ~ b [voicing]'.

    Args:
        line: Line containing alternation pattern

    Returns:
        AlternationPair if valid alternation, None otherwise
    """
    if "~" not in line:
        return None

    # Extract description if present
    description = None
    if "[" in line and "]" in line:
        match = re.search(r"\[([^\]]+)\]", line)
        if match:
            description = match.group(1).strip()
            line = line[: match.start()] + line[match.end() :]

    # Parse segments
    parts = [p.strip() for p in line.split("~") if p.strip()]
    if len(parts) != 2:
        return None

    seg1, seg2 = parts[0], parts[1]

    # Check for pair filter (e.g., "p:sg ~ b:pl")
    pair_filter = None
    if ":" in seg1 and ":" in seg2:
        seg1_parts = seg1.split(":")
        seg2_parts = seg2.split(":")
        if len(seg1_parts) == 2 and len(seg2_parts) == 2:
            pair_filter = f"{seg1_parts[1]}:{seg2_parts[1]}"
            seg1 = seg1_parts[0]
            seg2 = seg2_parts[0]

    # Normalize to empty string for null segment
    seg1 = "" if seg1.lower() in ("ø", "null", "zero") else seg1
    seg2 = "" if seg2.lower() in ("ø", "null", "zero") else seg2

    return AlternationPair(
        segment1=seg1,
        segment2=seg2,
        description=description,
        pair_filter=pair_filter,
    )


def load_targets_file(
    path: str = "data/targets.txt",
    allow_null_segments: bool = True,
) -> Tuple[List[str], List[AlternationPair]]:
    """Load targets file and separate regular targets from alternations.

    Args:
        path: Path to targets file
        allow_null_segments: If True, parse Ø alternations

    Returns:
        Tuple of (regular_targets, alternation_pairs)
    """
    p = Path(path)
    if not p.exists():
        return [], []

    targets: List[str] = []
    alternations: List[AlternationPair] = []

    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = strip_comment(line)
            if not line:
                continue

            # Check if it's an alternation
            pair = parse_alternation_line(line)
            if pair is not None:
                # Skip Ø alternations if not allowed
                if not allow_null_segments and (
                    pair.segment1 == "" or pair.segment2 == ""
                ):
                    continue
                alternations.append(pair)
            else:
                # Regular target(s) - may be comma or space separated
                for target in split_targets_line(line):
                    target = normalize_tiebar(target)
                    targets.append(target)

    return targets, alternations


# ========================= FILE UTILITIES =========================


def read_file_lines(path: Path) -> List[str]:
    """Read all lines from file (used by validation)."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]


__all__ = [
    # Helper functions
    "strip_comment",
    "parse_section_header",
    "extract_tags",
    "split_targets_line",
    # Word entry parsing
    "iter_word_entries",
    "load_words_set",
    "load_words_list",
    "load_words_with_tags",
    # Target parsing
    "parse_alternation_line",
    "load_targets_file",
    # Utilities
    "read_file_lines",
]
