"""
Professional IPA text processing using established libraries.

Robust handling of IPA text with Unicode best practices and mature IPA libs:
- panphon: segmentation & articulatory features (optional but preferred)
- unicodedata: NFC/NFD normalization (UAX #15)
- regex: Unicode grapheme clusters (UAX #29)
This version:
- Attaches arbitrary combining diacritics (Mn) to their base (no lists)
- Attaches spacing modifier letters (Sk) to preceding segment when appropriate
- Preserves tie bars (͡/͜) to keep bundled segments/affricates atomic
- Groups vocoid runs into n-phthong nuclei (feature-driven)
- Provides diacritic-aware matching policies and Unicode-block validation
"""

from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import unicodedata as ud
import regex as re

try:
    import panphon
    from panphon.segment import Segmenter
    PANPHON_AVAILABLE = True
except ImportError:
    PANPHON_AVAILABLE = False

# ----------------------- Config & Utilities -----------------------

@dataclass(frozen=True)
class IPAConfig:
    prefer_diphthong: bool = True        # unmarked vocoid runs → single nucleus
    strip_stress_in_output: bool = True
    # Matching policy for phoneme_matches:
    # "exact": exact string equality
    # "base": ignore length+diacritics+ties (compare base phones)
    # "len": ignore length only
    # "contains": substring check (e.g., for complex nuclei)
    match_policy: str = "len"

_TIE_RE = re.compile(r"[\u0361\u035C]")        # ͡ or ͜
_LEN_RE = re.compile(r"[ːˑ]")                  # spacing length marks
_PROSODIC_RE = re.compile(r"[ˈˌ‖|]")           # stress/boundaries (toggleable)
_GC_RE = re.compile(r"\X", re.VERSION1)        # grapheme clusters (UAX #29)

def _is_combining(ch: str) -> bool: return ud.category(ch) == "Mn"
def _is_spacing_modifier(ch: str) -> bool: return ud.category(ch) in ("Sk", "Lm")

# IPA-relevant Unicode blocks + Latin bases (generous acceptance)
_BLOCKS: List[Tuple[int, int]] = [
    (0x0250, 0x02AF),  # IPA Extensions
    (0x02B0, 0x02FF),  # Spacing Modifier Letters
    (0x0300, 0x036F),  # Combining Diacritical Marks
    (0x1D00, 0x1D7F),  # Phonetic Extensions
    (0x1D80, 0x1DBF),  # Phonetic Extensions Supplement
    (0x1DC0, 0x1DFF),  # Combining Diacritical Marks Supplement
    (0xA700, 0xA71F),  # Modifier Tone Letters
    (0x0041, 0x024F),  # Latin (bases)
]
def _in_blocks(ch: str) -> bool:
    cp = ord(ch); return any(lo <= cp <= hi for lo, hi in _BLOCKS)

def _strip_length(s: str) -> str:
    return _LEN_RE.sub("", s)

def _strip_diacritics(s: str) -> str:
    # Remove Mn, Sk, and Lm; keep base and ties
    return "".join(ch for ch in s if not (_is_combining(ch) or _is_spacing_modifier(ch)))

def _strip_all_nonbase(s: str) -> str:
    # Remove Mn, Sk, and tie-bars → base-only
    return _TIE_RE.sub("", _strip_diacritics(s))

# ----------------------- IPA Processor -----------------------

class IPAProcessorV2:
    """
    Unicode-correct IPA processing for arbitrary phonetic transcriptions:
    - NFC for storage/display; NFD available for inspection
    - PanPhon Segmenter (if available) or grapheme fallback (UAX #29)
    - Generic handling of all legal combining diacritics (Mn) + spacing modifiers (Sk)
    - Tie bars preserved to keep affricates/bundles atomic
    - Feature-driven n-phthong grouping (vocoid runs → 1 nucleus)
    - Diacritic-aware matching policies and Unicode-block validation
    """

    _NON_SYLL = "\u032F"  # ◌̯ (non-syllabic, marks glides/offglides)

    def __init__(self, config: IPAConfig | None = None):
        self.cfg = config or IPAConfig()
        self.ft = panphon.FeatureTable() if PANPHON_AVAILABLE else None
        self._seg = Segmenter() if PANPHON_AVAILABLE else None
        # robust method handle: Segmenter may expose `.segments` or `.segment`
        self._segment_fn = None
        if self._seg is not None:
            self._segment_fn = getattr(self._seg, "segments", None) or getattr(self._seg, "segment", None)
        # robust method handle: seg_to_vector or segment_to_vector
        self._seg_to_vec = None
        if self.ft is not None:
            self._seg_to_vec = getattr(self.ft, "seg_to_vector", None) or getattr(self.ft, "segment_to_vector", None)
        # optional: fallback to FeatureTable-based segmentation if Segmenter missing
        self._ft_seg_fn = getattr(self.ft, "ipa_segs", None) if self.ft else None

    # ---- Normalization (UAX #15) ----
    @staticmethod
    def normalize_nfc(text: str) -> str: return ud.normalize("NFC", text)
    @staticmethod
    def normalize_nfd(text: str) -> str: return ud.normalize("NFD", text)

    # ---- Public API: segmentation → nuclei ----
    def ipa_segments(self, text: str) -> List[str]:
        """
        Segment text into phones, rebind diacritics/modifiers, group vocoid runs,
        optionally strip prosodics.
        """
        s = self.normalize_nfc(text)

        # 1) Base segmentation (prefer Segmenter, else FT.ipa_segs, else UAX#29)
        if self._segment_fn is not None:
            base = self._segment_fn(s)
        elif self._ft_seg_fn is not None:
            base = self._ft_seg_fn(s)
        else:
            base = _GC_RE.findall(s)

        # 2) Attach Sk to previous, preserve tie-bar bundles as atomic
        tokens = self._rebind_modifiers_and_ties(base)

        # 3) Collapse contiguous vocoid runs → n-phthong nuclei
        tokens = self._collapse_vocoid_runs_to_nuclei(tokens, self.cfg.prefer_diphthong)

        # 4) Optionally strip stress/intonational marks
        if self.cfg.strip_stress_in_output:
            tokens = [t for t in tokens if not _PROSODIC_RE.match(t)]

        return tokens

    # ---- Rebinding: attach Sk, preserve tie groups ----
    def _rebind_modifiers_and_ties(self, tokens: List[str]) -> List[str]:
        """
        - Attach spacing modifiers (Sk/Lm) to the preceding segment at char-level.
        - Fuse adjacent tokens into one when a tie (U+0361/U+035C) binds them.
        This is robust to tokenizations like ['t͡', 'ʃ'] or ['t', '͡', 'ʃ'] or ['t͡ʃ'].
        """
        out: List[str] = []
        # 1) First, reattach any standalone spacing modifiers to the previous *segment*
        tmp: List[str] = []
        for tok in tokens:
            # Split into codepoints so we don't misclassify mixed tokens.
            chars = list(tok)
            if len(chars) == 1 and (_is_spacing_modifier(chars[0]) or _is_combining(chars[0])):
                if tmp:
                    tmp[-1] = tmp[-1] + chars[0]
                else:
                    # No previous segment: keep as-is (corner case; will be validated later)
                    tmp.append(chars[0])
            else:
                tmp.append(tok)

        # 2) Then, fuse tie-linked neighbors, regardless of where the tie sits.
        i = 0
        n = len(tmp)
        while i < n:
            curr = tmp[i]
            # If current contains a tie or next contains a tie, start bundling
            if _TIE_RE.search(curr):
                bundle = curr
                i += 1
                while i < n and (_TIE_RE.search(tmp[i - 1]) or _TIE_RE.search(tmp[i])):
                    bundle += tmp[i]
                    i += 1
                out.append(bundle)
                continue
            if i + 1 < n and _TIE_RE.search(tmp[i + 1]):
                # Next token (or the boundary between curr/next) bears tie—bundle curr+next (+more if chained)
                bundle = curr + tmp[i + 1]
                i += 2
                while i < n and (_TIE_RE.search(tmp[i - 1]) or _TIE_RE.search(tmp[i])):
                    bundle += tmp[i]
                    i += 1
                out.append(bundle)
                continue
            # No tie around—pass through
            out.append(curr)
            i += 1

        return out
    
    # ---- n-phthong grouping (feature-driven) ----
    def _collapse_vocoid_runs_to_nuclei(self, phones: List[str], prefer_diphthong: bool) -> List[str]:
        out: List[str] = []; i = 0; n = len(phones)
        while i < n:
            seg = phones[i]
            if not self._is_vocoid(seg):
                out.append(seg); i += 1; continue

            # collect vocoid run
            run = [seg]; j = i + 1
            while j < n and self._is_vocoid(phones[j]):
                run.append(phones[j]); j += 1

            # ◌̯ or tie-bars imply SINGLE nucleus (diphthong/triphthong)
            force_single = any(self._NON_SYLL in s for s in run) or any(_TIE_RE.search(s) for s in run)

            if force_single or prefer_diphthong:
                nucleus = "".join(run)     # already diacritics-attached; ties preserved
                out.append(nucleus)
            else:
                # prefer hiatus: split at syllabic peaks; attach non-syllabic to nearest peak
                k = 0; buf: List[str] = []
                while k < len(run):
                    if self._is_syllabic(run[k]) or not buf:
                        if buf: out.append("".join(buf)); buf = []
                        buf.append(run[k])
                    else:
                        buf.append(run[k])
                    k += 1
                if buf: out.append("".join(buf))

            i = j
        return out

    # ---- Feature helpers (PanPhon if available; graceful fallback) ----
    @lru_cache(maxsize=4096)
    def _vec_cached(self, seg: str) -> Optional[Dict[str, int]]:
        if self.ft is None or not self.ft.seg_known(seg) or self._seg_to_vec is None:
            return None
        return self._seg_to_vec(seg)

    def _vec(self, seg: str) -> Optional[Dict[str, int]]:
        return self._vec_cached(seg)

    def _is_vocoid(self, seg: str) -> bool:
        if self._NON_SYLL in seg:
            return True
        v = self._vec(seg)
        if v:
            if v.get("syl", 0) == 1:
                return True
            if v.get("approx", 0) == 1 and v.get("son", 0) == 1:
                return True
        base = _strip_all_nonbase(seg)
        return bool(base) and any(ch in "iyɨʉɯuɪʏʊeøɘɵɤoəɛœɜɞʌɔæɐaɶɑɒ" for ch in base)

    # ---- Matching policies ----
    def phoneme_matches(self, search_target: str, segment: str) -> bool:
        policy = self.cfg.match_policy
        if policy == "exact":
            return search_target == segment
        if policy == "len":
            return _strip_length(search_target) == _strip_length(segment)
        if policy == "base":
            return _strip_all_nonbase(search_target) == _strip_all_nonbase(segment)
        if policy == "contains":
            return search_target in segment
        return search_target == segment

    # ---- Validation (Unicode blocks + PanPhon knowledge) ----
    def is_valid_ipa(self, text: str) -> bool:
        s = self.normalize_nfc(text)
        for ch in s:
            if ch.isspace(): continue
            if not _in_blocks(ch): return False

        if self.ft is None:
            return True

        # Avoid re-tokenizing repeatedly:
        toks = self.ipa_segments(s)
        for tok in toks:
            if _PROSODIC_RE.match(tok):
                continue
            if self.ft.seg_known(tok):
                continue
            base = _strip_all_nonbase(tok)
            if not base or not all(self.ft.seg_known(ch) for ch in base):
                return False
        return True

    # ---- File I/O ----
    @staticmethod
    def read_ipa_file(path: Path) -> str:
        try:
            try:
                content = path.read_text(encoding="utf-8-sig", errors="strict")
            except UnicodeDecodeError:
                content = path.read_text(encoding="utf-8", errors="strict")
            return IPAProcessorV2.normalize_nfc(content)
        except (IOError, OSError, UnicodeDecodeError) as e:
            raise IOError(f"Cannot read IPA file {path}: {e}") from e

    @staticmethod
    def write_ipa_file(path: Path, content: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            normalized = IPAProcessorV2.normalize_nfc(content)
            path.write_text(normalized, encoding="utf-8", errors="strict")
        except (IOError, OSError) as e:
            raise IOError(f"Cannot write IPA file {path}: {e}") from e

    # ---- Introspection ----
    def get_segment_info(self, segment: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "segment": segment,
            "normalized_nfc": self.normalize_nfc(segment),
            "normalized_nfd": self.normalize_nfd(segment),
            "is_known": (self.ft.seg_known(segment) if (self.ft and segment) else None),
        }
        v = self._vec(segment)
        if v:
            info["features"] = v
            info["is_syllabic"] = v.get("syl", 0) == 1
        return info

# ----------------------- Convenience API -----------------------

_default_processor: Optional[Tuple[IPAConfig, IPAProcessorV2]] = None

def get_processor(config: IPAConfig | None = None) -> IPAProcessorV2:
    global _default_processor
    cfg = config or IPAConfig()
    if _default_processor is None or _default_processor[0] != cfg:
        _default_processor = (cfg, IPAProcessorV2(cfg))
    return _default_processor[1]

def get_config_for_transcription_mode(mode: str) -> IPAConfig:
    if mode == "broad":
        return IPAConfig(prefer_diphthong=True, match_policy="base")
    if mode == "narrow":
        return IPAConfig(prefer_diphthong=True, match_policy="exact")
    return IPAConfig(prefer_diphthong=True, match_policy="len")

def ipa_segments(text: str) -> List[str]:
    return get_processor().ipa_segments(text)

def normalize_ipa(text: str) -> str:
    return IPAProcessorV2.normalize_nfc(text)

def validate_ipa(text: str) -> bool:
    return get_processor().is_valid_ipa(text)