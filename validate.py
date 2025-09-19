# phonenv/validate.py
"""
Standalone validator for Phonenv datasets and targets (no CLI arguments).

Usage:
  python -m phonenv.validate

Behavior:
  - Validates data/dataset.txt
  - Also validates data/targets.txt if present
  - Prints a human-readable report
  - Exit codes: 0 = OK, 1 = invalid chars, 2 = I/O/unexpected error
  - If errors are found and running in a TTY, offers to auto-fix common issues
"""
from __future__ import annotations

import re
import sys
import difflib
import shutil
import unicodedata as ud
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from utils import in_ipa_blocks

# ========================= Unicode blocks & allowances =========================

# IPA blocks now available from utils.in_ipa_blocks() function

# Prosodics & structural tokens allowed by Phonenv IO/printing
_ALLOWED_MISC: Set[str] = set("[]()#_ˈˌ|‖.")
# '.' (syllable separator) is allowed; we still warn about it below.

# Greek letters used in IPA; this catches Greek/Latin lookalike mistakes (e.g., φ vs ɸ)
_ALLOWED_GREEK_FOR_IPA: Set[str] = {"β", "θ", "χ"}

# Characters that commonly appear but are wrong for IPA; value = suggested fix.
CONFUSABLE_HINTS: Dict[str, str] = {
    "φ": "ɸ",  # Greek phi -> IPA bilabial fricative
    "γ": "ɣ",  # Greek gamma -> IPA voiced velar fricative
    ":": "ː",  # ASCII colon -> length mark
    ";": "ˑ",  # ASCII semicolon -> half-long
    "'": "ˈ",  # ASCII apostrophe -> primary stress
    "’": "ˈ",  # curly apostrophe -> primary stress
    ",": "ˌ",  # comma -> secondary stress
    "?": "ʔ",  # question mark -> glottal stop
    # NOTE: '-' (hyphen) is intentionally NOT auto-converted; we flag and (optionally) remove it.
}

# Treat these as "invisible/format" gremlins to flag explicitly
INVISIBLES: Dict[int, str] = {
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0xFEFF: "BOM / ZERO WIDTH NO-BREAK SPACE",
    0x00A0: "NO-BREAK SPACE",
    0x00AD: "SOFT HYPHEN",
}

# ========================= Helpers =========================


def _is_allowed_ipa_char(c: str) -> bool:
    """Loosely validate characters acceptable in IPA datasets/targets."""
    if not c or c.isspace():
        return True
    if in_ipa_blocks(c):
        return True
    if c in _ALLOWED_MISC:
        return True
    # Many IPA symbols are plain Latin letters (p, t, k, a, i, …)
    if "LATIN" in ud.name(c, ""):
        return True
    if c in _ALLOWED_GREEK_FOR_IPA:
        return True
    return False

def _is_ascii_upper(c: str) -> bool:
    return "A" <= c <= "Z"

def _is_invisible(c: str) -> bool:
    return ord(c) in INVISIBLES

# ========================= Input loading (parsed view for validation) =========================

def _load_words_dataset(path: Path) -> List[str]:
    """
    Try the project's parser; fall back to a simple, comment/tag-aware reader.
    """
    try:
        from .data import load_words_list  # type: ignore
        return load_words_list(str(path))
    except Exception:
        pass

    words: List[str] = []
    tag_pattern = re.compile(r"\[[^\]]*\]")  # remove inline [tags]
    header_pattern = re.compile(r"^\s*\[[^#\]]*\]\s*(#.*)?$")  # section headers

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            # Strip comments
            if "#" in line:
                line = line[: line.index("#")]
            if not line.strip():
                continue
            # Skip section headers like [lang=en; mode=narrow]
            if header_pattern.match(line.strip()):
                continue
            # Remove inline [tags]
            line = tag_pattern.sub("", line).strip()
            if line:
                words.append(line)
    return words

def _load_targets(path: Optional[Path]) -> List[str]:
    if not path or not path.exists():
        return []
    targets: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "#" in line:
                line = line[: line.index("#")].strip()
            if line:
                targets.append(line)
    return targets

# ========================= Raw file I/O (for fixing) =========================

def _read_file_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return f.read().splitlines(keepends=True)

def _backup_then_write(path: Path, new_lines: List[str]) -> None:
    bak = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copyfile(path, bak)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.writelines(new_lines)

# ========================= Validation core (line-aware) =========================

@dataclass
class Offense:
    ch: str
    line_no: int
    col_no: int
    context: str  # the word/target or a short excerpt
    source: str   # "dataset" or "target"

@dataclass
class WarningItem:
    kind: str
    message: str
    line_no: int
    col_no: int
    sample: str
    source: str   # "dataset" or "target"

def _scan_line(line: str, line_no: int) -> Tuple[List[Offense], List[WarningItem]]:
    offs: List[Offense] = []
    warns: List[WarningItem] = []

    # Character-by-character checks
    for idx, ch in enumerate(line, start=1):
        if ch.isspace():
            continue
        # Invisibles / format gremlins
        if _is_invisible(ch):
            name = INVISIBLES.get(ord(ch), ud.name(ch, "UNKNOWN"))
            warns.append(WarningItem("invisible", f"Invisible/format char {name}", line_no, idx, line, ""))
            continue
        # Explicit hyphen warning (likely morpheme boundary)
        if ch == "-":
            warns.append(WarningItem("morpheme-hyphen", "Hyphen '-' detected; likely morpheme boundary. Remove it from IPA transcriptions.", line_no, idx, line, ""))
            # fall through to hard validity check, which will flag it as an offense too
        # Confusable hints (warning; may be valid but suspicious)
        if ch in CONFUSABLE_HINTS:
            sugg = CONFUSABLE_HINTS[ch]
            warns.append(WarningItem("confusable", f"'{ch}' looks like IPA '{sugg}'", line_no, idx, line, ""))
        # Uppercase ASCII chars (likely accidental)
        if _is_ascii_upper(ch):
            warns.append(WarningItem("uppercase", f"Uppercase ASCII '{ch}' is unusual in IPA", line_no, idx, line, ""))
        # Syllable dot presence (allowed but warn so user knows how analyzer treats it)
        if ch == ".":
            warns.append(WarningItem("syllable-dot", "Syllable dot '.' found (allowed). Ensure analyzer handles it as intended.", line_no, idx, line, ""))
        # Hard validity check
        if not _is_allowed_ipa_char(ch):
            offs.append(Offense(ch, line_no, idx, line, ""))

    # Heuristic orthography spill (non-blocking)
    if ("ng" in line) and ("ŋ" not in line):
        warns.append(WarningItem("orthography", "Possible 'ŋ' intended (found 'ng')", line_no, 1, line, ""))
    for dg in ("th", "sh", "zh", "ch"):
        if dg in line:
            warns.append(WarningItem("orthography", f"Orthographic digraph detected ('{dg}')", line_no, 1, line, ""))

    return offs, warns

def _collect_issues(words: Iterable[str], targets: Iterable[str]):
    offenders: Dict[str, List[str]] = defaultdict(list)
    offenses: List[Offense] = []
    warnings: List[WarningItem] = []

    # targets first
    for i, t in enumerate(targets, start=1):
        o, w = _scan_line(t, i)
        for item in w:
            warnings.append(WarningItem(item.kind, f"(target) {item.message}", item.line_no, item.col_no, t, "target"))
        for off in o:
            offenders[off.ch].append(f"(target L{i}): {t}")
            offenses.append(Offense(off.ch, i, off.col_no, t, "target"))

    # dataset
    for i, wline in enumerate(words, start=1):
        o, w = _scan_line(wline, i)
        for item in w:
            warnings.append(WarningItem(item.kind, item.message, item.line_no, item.col_no, wline, "dataset"))
        for off in o:
            if wline not in offenders[off.ch]:
                offenders[off.ch].append(f"L{i}: {wline}")
            offenses.append(Offense(off.ch, i, off.col_no, wline, "dataset"))

    return offenders, offenses, warnings

def _render_text(offenders: Dict[str, List[str]], dataset: Path, targets: Optional[Path]) -> str:
    lines: List[str] = []
    lines.append("Validation error: Non-IPA or unsupported characters were found; analysis should not proceed.")
    lines.append("These characters can break segmentation and yield misleading results.")
    lines.append(f"Dataset: {dataset}")
    if targets:
        lines.append(f"Targets: {targets}")
    lines.append("")
    lines.append("Offending characters (char • code point • Unicode name) and where they appear:")
    for ch in sorted(offenders.keys(), key=lambda c: ord(c)):
        cp = f"U+{ord(ch):04X}"
        nm = ud.name(ch, "UNKNOWN")
        examples = offenders[ch]
        shown = ", ".join(examples[:5])
        if len(examples) > 5:
            shown += f" (+{len(examples) - 5} more)"
        hint = f"  (hint: did you mean '{CONFUSABLE_HINTS[ch]}'?)" if ch in CONFUSABLE_HINTS else ""
        lines.append(f"  {ch} • {cp} • {nm}: {shown}{hint}")
    return "\n".join(lines)

def _render_warnings(warnings: List[WarningItem]) -> str:
    if not warnings:
        return ""
    lines: List[str] = []
    lines.append("Warnings (non-fatal):")
    for w in warnings[:20]:
        src = "target" if w.source == "target" or "(target)" in w.message else "dataset"
        lines.append(f"  [{src}] L{w.line_no}:{w.col_no} {w.kind}: {w.message}  ⇒  {w.sample}")
    if len(warnings) > 20:
        lines.append(f"  …and {len(warnings) - 20} more warnings")
    return "\n".join(lines)

# ========================= Auto-fix mechanics =========================

def _fix_content_segment(s: str) -> str:
    """
    Apply safe, local fixes to a content segment (not including trailing comments).
    Order matters: clean invisibles, then confusables, then remove hyphens (morpheme markers).
    """
    # 1) Invisibles & spacing
    s = s.replace("\u00A0", " ")   # NBSP -> space
    s = s.replace("\u00AD", "")    # SOFT HYPHEN -> remove
    for cp in (0x200B, 0x200C, 0x200D, 0xFEFF):
        s = s.replace(chr(cp), "")  # zero-width variants, BOM -> remove

    # 2) Common confusables (no hyphen handling here)
    for bad, good in CONFUSABLE_HINTS.items():
        if bad in s:
            s = s.replace(bad, good)

    # 3) Remove literal hyphens (likely morpheme boundaries)
    if "-" in s:
        s = s.replace("-", "")

    return s

def _fix_line_preserving_comment(line: str) -> str:
    """Fix line content but preserve trailing comments (# ...)."""
    if "#" in line:
        pre, post = line.split("#", 1)
        fixed_pre = _fix_content_segment(pre)
        return fixed_pre + "#" + post
    return _fix_content_segment(line)

def _propose_fixes_for_file(path: Path) -> Tuple[List[str], List[str], bool]:
    """
    Return (orig_lines, fixed_lines, changed?)
    """
    orig = _read_file_lines(path)
    if not orig:
        return [], [], False
    fixed = [_fix_line_preserving_comment(ln) for ln in orig]
    return orig, fixed, (fixed != orig)

def _print_diff(path: Path, orig: List[str], fixed: List[str], limit: int = 200) -> None:
    print(f"\nProposed changes for {path}:")
    diff = list(difflib.unified_diff(orig, fixed, fromfile=str(path), tofile=f"{path} (fixed)", n=3, lineterm=""))
    if not diff:
        print("  (no visible changes)")
        return
    for i, line in enumerate(diff):
        if i >= limit:
            print(f"... (diff truncated; {len(diff) - limit} more lines)")
            break
        print(line)

def _yes_no(prompt: str, default: bool = False) -> bool:
    yn = "[Y/n]" if default else "[y/N]"
    try:
        ans = input(f"{prompt} {yn} ").strip().lower()
    except EOFError:
        return False
    if not ans:
        return default
    return ans in ("y", "yes")

def _maybe_autofix(dataset: Path, targets: Optional[Path], offenders_exist: bool) -> bool:
    """
    Offer interactive auto-fix if running in a TTY and offenders were found.
    Returns True if any file was modified.
    """
    if not offenders_exist:
        return False
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("\nRun in an interactive terminal to be prompted for auto-fixes.")
        return False

    modified_any = False

    # Dataset proposal
    if dataset.exists():
        orig, fixed, changed = _propose_fixes_for_file(dataset)
        if changed:
            _print_diff(dataset, orig, fixed)
            if _yes_no(f"Remove hyphens and apply other safe fixes? A backup will be written to {dataset.with_suffix(dataset.suffix + '.bak')}."):
                _backup_then_write(dataset, fixed)
                print(f"  ✓ Wrote fixed file and backup: {dataset}")
                modified_any = True
        else:
            print(f"\nNo fixable issues detected in {dataset} (beyond what validator flags).")

    # Targets proposal
    if targets and targets.exists():
        orig, fixed, changed = _propose_fixes_for_file(targets)
        if changed:
            _print_diff(targets, orig, fixed)
            if _yes_no(f"Remove hyphens and apply other safe fixes? A backup will be written to {targets.with_suffix(targets.suffix + '.bak')}."):
                _backup_then_write(targets, fixed)
                print(f"  ✓ Wrote fixed file and backup: {targets}")
                modified_any = True
        else:
            print(f"\nNo fixable issues detected in {targets} (beyond what validator flags).")

    return modified_any

# ========================= Public API =========================

DEFAULT_DATASET = Path("data/dataset.txt")
DEFAULT_TARGETS = Path("data/targets.txt")

def validate(
    dataset: Path = DEFAULT_DATASET,
    targets: Optional[Path] = DEFAULT_TARGETS,
    *,
    interactive_autofix: bool = True,
) -> int:
    """
    Validate dataset (and optional targets). Returns exit code:
      0 = OK, 1 = invalid chars, 2 = I/O error
    If interactive_autofix is True and errors are found, prompts to auto-fix and re-runs once.
    """
    try:
        if not dataset.exists():
            print(f"Error: dataset not found: {dataset}", file=sys.stderr)
            return 2

        words = _load_words_dataset(dataset)
        target_list = _load_targets(targets if targets and targets.exists() else None)

        offenders, offenses, warnings = _collect_issues(words, target_list)

        if offenders:
            print(_render_text(offenders, dataset, targets if targets and targets.exists() else None))
            # Line-aware appendix for quick jumps in editors:
            print("\nFirst 10 offending occurrences with positions:")
            for off in offenses[:10]:
                cp = f"U+{ord(off.ch):04X}"
                nm = ud.name(off.ch, "UNKNOWN")
                src = "target" if off.source == "target" else "dataset"
                print(f"  [{src}] L{off.line_no}:{off.col_no} {off.ch} • {cp} • {nm}  ⇒  {off.context}")

            if interactive_autofix and _maybe_autofix(dataset, targets if targets and targets.exists() else None, offenders_exist=True):
                print("\nRe-validating after fixes...\n")
                # Re-run once without prompting again
                return validate(dataset, targets, interactive_autofix=False)

            return 1  # still invalid

        # If we reach here, still report warnings (non-fatal)
        if warnings:
            print(_render_warnings(warnings))

        if targets and targets.exists() and target_list:
            print(f"✓ Validation passed. No offending characters found in {dataset} and {targets}.")
        else:
            print(f"✓ Validation passed. No offending characters found in {dataset}.")
        return 0

    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 2

# ========================= Module entrypoint =========================

def main() -> None:
    """
    No-argument entrypoint.
    Uses data/dataset.txt and (if present) data/targets.txt.
    """
    code = validate(DEFAULT_DATASET, DEFAULT_TARGETS if DEFAULT_TARGETS.exists() else None, interactive_autofix=True)
    sys.exit(code)

if __name__ == "__main__":
    main()