"""Phonetic environment analysis and IPA processing functionality.

This module consolidates the core analysis capabilities including:
- Phonetic environment analysis
- IPA text processing and normalization
- Segmentation and feature analysis
"""

from __future__ import annotations

import unicodedata as ud
from dataclasses import dataclass
from typing import (
    Dict,
    List,
    Set,
    Tuple,
    OrderedDict as OrderedDictType,
    Optional,
    Any,
)
from collections import defaultdict, OrderedDict
from shutil import get_terminal_size
from utils import (
    normalize_tiebar,
    normalize_ascii_to_ipa,
    in_ipa_blocks,
    is_combining,
    is_spacing_modifier,
    TIE_ABOVE,
    TIE_BELOW,
)

# ========================= IPA PROCESSING =========================


@dataclass
class IPAConfig:
    use_panphon: bool = False
    tie_bar_clusters: Optional[List[str]] = None
    diphthong_patterns: Optional[List[str]] = None
    normalization_mode: str = "NFC"
    match_mode: str = "broad"  # "narrow" | "broad"

    def __post_init__(self):
        if self.tie_bar_clusters is None:
            self.tie_bar_clusters = [
                "t͡s",
                "d͡z",
                "t͡ʃ",
                "d͡ʒ",
                "t͡ɕ",
                "d͡ʑ",
                "ʈ͡ʂ",
                "ɖ͡ʐ",
                "t͡θ",
                "d͡ð",
                "p͡f",
                "b͡v",
                "c͡ç",
                "ɟ͡ʝ",
                "k͡x",
                "ɡ͡ɣ",
                "q͡χ",
                "ɢ͡ʁ",
                "t͡ɬ",
                "d͡ɮ",
                "p͡ɸ",
                "b͡β",
            ]
        if self.diphthong_patterns is None:
            self.diphthong_patterns = [
                "aɪ",
                "eɪ",
                "ɔɪ",
                "aʊ",
                "oʊ",
                "ou",
                "ɪə",
                "eə",
                "ʊə",
                "ai",
                "au",
                "ei",
                "eu",
                "oi",
                "ou",
                "iu",
                "ui",
                "ie",
                "uo",
                "aːɪ",
                "aːʊ",
                "eːɪ",
                "oːʊ",
            ]


# Suprasegmentals to ignore when picking context neighbors
_SUPRA: Set[str] = {"ˈ", "ˌ", "|", "‖"}


def _skip_left(segments: List[str], i: int) -> int:
    j = i - 1
    while j >= 0 and segments[j] in _SUPRA:
        j -= 1
    return j


def _skip_right(segments: List[str], i: int) -> int:
    j = i + 1
    while j < len(segments) and segments[j] in _SUPRA:
        j += 1
    return j


def _strip_all_nonbase(s: str) -> str:
    """Remove all non-base characters (combining marks + spacing modifiers)."""
    nfd = ud.normalize("NFD", s)
    return "".join(c for c in nfd if not (is_combining(c) or is_spacing_modifier(c)))


class IPAProcessorV2:
    """Advanced IPA text processor with configurable behavior."""

    def __init__(self, config: Optional[IPAConfig] = None):
        self.config = config or IPAConfig()
        self._panphon_ft = None
        self._setup_panphon()

    def _setup_panphon(self) -> None:
        """Setup panphon if available and requested."""
        if self.config.use_panphon:
            try:
                import panphon

                self._panphon_ft = panphon.FeatureTable()
            except (ImportError, AttributeError):
                print(
                    "Warning: panphon not available, falling back to basic processing"
                )
                self.config.use_panphon = False

    def normalize_nfc(self, text: str) -> str:
        """Normalize text to NFC form."""
        return ud.normalize("NFC", text)

    def normalize_nfd(self, text: str) -> str:
        """Normalize text to NFD form."""
        return ud.normalize("NFD", text)

    def ipa_segments(self, text: str) -> List[str]:
        """Segment IPA text into phonetic units."""
        if not text:
            return []

        text = self.normalize_nfc(text)
        text = normalize_ascii_to_ipa(text)
        text = normalize_tiebar(text)

        # 1) Wrap multi-symbol nuclei (diphthongs/triphthongs) first (longest-first).
        for pat in sorted(self.config.diphthong_patterns or [], key=len, reverse=True):
            if pat and pat in text:
                text = text.replace(pat, f"◊{pat}◊")

        chars = list(text)
        segments: List[str] = []
        i = 0

        while i < len(chars):
            ch = chars[i]

            # Unwrap sentinel-wrapped nuclei ◊...◊ as atomic segments;
            # attach trailing marks.
            if ch == "◊":
                j = i + 1
                while j < len(chars) and chars[j] != "◊":
                    j += 1
                if j < len(chars):
                    seg = "".join(chars[i + 1 : j])
                    k = j + 1
                    while k < len(chars) and is_combining(chars[k]):
                        seg += chars[k]
                        k += 1
                    while k < len(chars) and is_spacing_modifier(chars[k]):
                        seg += chars[k]
                        k += 1
                    segments.append(seg)
                    i = k
                    continue
                i += 1
                continue

            # Parenthesized specials "(...)" stay intact.
            if ch == "(":
                j = text.find(")", i + 1)
                if j != -1:
                    seg = text[i : j + 1].replace("◊", "")
                    segments.append(seg)
                    i = j + 1
                    continue
                # unmatched "(": fall through as a single char

            # === Generic tie-bar affricates with lookahead ===
            left_base = chars[i]
            j = i + 1

            # Gather combining on the LEFT base,
            # but stop before a tie bar if we encounter one.
            left_comb = ""
            tie_pos = None
            while j < len(chars) and is_combining(chars[j]):
                if chars[j] in (TIE_ABOVE, TIE_BELOW):
                    tie_pos = j
                    break
                left_comb += chars[j]
                j += 1

            # If we found a tie bar and have a following right base, build the cluster.
            if tie_pos is not None and (tie_pos + 1) < len(chars):
                k = tie_pos + 1
                right_base = chars[k]
                k += 1

                # Collect combining on the RIGHT base (excluding any stray tie bars)
                right_comb = ""
                while (
                    k < len(chars)
                    and is_combining(chars[k])
                    and chars[k] not in (TIE_ABOVE, TIE_BELOW)
                ):
                    right_comb += chars[k]
                    k += 1

                seg = (
                    left_base + left_comb + TIE_ABOVE + right_base + right_comb
                )  # normalize tie below -> above earlier
                # cluster-level combining after the right base (rare but legal)
                while (
                    k < len(chars)
                    and is_combining(chars[k])
                    and chars[k] not in (TIE_ABOVE, TIE_BELOW)
                ):
                    seg += chars[k]
                    k += 1
                # spacing modifiers (length, aspiration, ʷ, ʲ, etc.)
                while k < len(chars) and is_spacing_modifier(chars[k]):
                    seg += chars[k]
                    k += 1

                segments.append(seg)
                i = k
                continue

            # No tie bar: default single segment
            # (left base + any remaining combining/modifiers)
            segment = left_base + left_comb
            i = j
            while i < len(chars) and is_combining(chars[i]):
                segment += chars[i]
                i += 1
            while i < len(chars) and is_spacing_modifier(chars[i]):
                segment += chars[i]
                i += 1
            segments.append(segment)

        return [seg for seg in segments if seg]

    def phoneme_matches(self, target: str, segment: str) -> bool:
        target_norm = normalize_tiebar(self.normalize_nfc(target))
        segment_norm = normalize_tiebar(self.normalize_nfc(segment))
        if self.config.match_mode == "narrow":
            return target_norm == segment_norm
        target_base = _strip_all_nonbase(target_norm)
        segment_base = _strip_all_nonbase(segment_norm)
        return target_base == segment_base

    def get_segment_info(self, segment: str) -> Dict[str, Any]:
        """Get detailed information about a segment."""
        if not segment:
            return {}

        base_char = segment[0] if segment else ""

        return {
            "segment": segment,
            "base_character": base_char,
            "code_point": f"U+{ord(base_char):04X}" if base_char else "",
            "name": ud.name(base_char, "UNKNOWN") if base_char else "",
            "category": ud.category(base_char) if base_char else "",
            "is_ipa_base": in_ipa_blocks(base_char) if base_char else False,
            "is_combining": is_combining(base_char) if base_char else False,
            "length": len(segment),
            "has_combining": any(is_combining(c) for c in segment),
            "has_modifiers": any(is_spacing_modifier(c) for c in segment),
        }


def get_config_for_transcription_mode(mode: str) -> IPAConfig:
    if mode == "narrow":
        return IPAConfig(use_panphon=True, match_mode="narrow")
    return IPAConfig(use_panphon=False, match_mode="broad")


# ========================= PHONETIC ANALYSIS =========================


class PhoneticAnalyzer:
    """
    Analyzes phonetic environments in word lists and reports occurrences grouped by:
      - INITIAL:  # _ X
      - FINAL:    X _ #
      - MEDIAL V_V, V_C, C_V, C_C (based on vowel/consonant at left/right context)
    """

    _ORDER: List[str] = [
        "INITIAL",
        "FINAL",
        "MEDIAL V_V",
        "MEDIAL V_C",
        "MEDIAL C_V",
        "MEDIAL C_C",
    ]

    _IPA_VOWEL_BASES: Set[str] = {
        "i",
        "y",
        "ɨ",
        "ʉ",
        "ɯ",
        "u",
        "ɪ",
        "ʏ",
        "ʊ",
        "e",
        "ø",
        "ɘ",
        "ɵ",
        "ɤ",
        "o",
        "ə",
        "ɚ",
        "ɜ",
        "ɞ",
        "ʌ",
        "ɔ",
        "ɛ",
        "œ",
        "æ",
        "ɐ",
        "a",
        "ɶ",
        "ɑ",
        "ɒ",
        "ᵻ",
        "ᵿ",
    }

    def __init__(
        self,
        use_ipa_processing: bool = True,
        use_professional_ipa: bool = True,
        transcription_mode: str = "narrow",
        no_color: bool = False,
    ):
        self.use_ipa_processing = use_ipa_processing
        self.transcription_mode = transcription_mode
        self.no_color = no_color

        if use_ipa_processing:
            config = get_config_for_transcription_mode(transcription_mode)
            self.ipa_processor_v2 = IPAProcessorV2(config)
        else:
            self.ipa_processor_v2 = None

    def _prepare_word(self, word: str) -> str:
        processed = word
        if self.use_ipa_processing and self.ipa_processor_v2:
            processed = self.ipa_processor_v2.normalize_nfc(processed)
            processed = normalize_tiebar(processed)
        return processed

    def _segment_base_char(self, token: str) -> str:
        """Get base character from token."""
        s = token
        if not s:
            return ""
        ch0 = s[0]
        if self.use_ipa_processing and self.ipa_processor_v2:
            d = self.ipa_processor_v2.normalize_nfd(ch0)
        else:
            d = ud.normalize("NFD", ch0)

        for c in d:
            if not ud.category(c).startswith("M"):
                return c
        return ch0

    def _is_vowel_segment(self, token: str) -> bool:
        s = token
        nfd = (
            self.ipa_processor_v2.normalize_nfd(s)
            if (self.use_ipa_processing and self.ipa_processor_v2)
            else ud.normalize("NFD", s)
        )
        if "\u0329" in nfd:  # syllabic
            return True
        if "\u032f" in nfd:  # non-syllabic
            return False
        return self._segment_base_char(token) in self._IPA_VOWEL_BASES

    def _classify_side(self, token: str) -> str:
        """Classify token as vowel, consonant, or boundary."""
        if token == "#":
            return "#"
        return "V" if self._is_vowel_segment(token) else "C"

    def _get_environment(self, word: str, character: str, index: int) -> str:
        """Get phonetic environment for character at index."""
        # Find left context (skip prosodic markers)
        left_idx = index - 1
        while left_idx >= 0:
            left_char = word[left_idx]
            if (
                self.use_ipa_processing
                and self.ipa_processor_v2
                and left_char in "ˈˌ‖|"
            ):
                left_idx -= 1
                continue
            break

        if left_idx < 0:
            left = "#"
        else:
            left_char = word[left_idx]
            if left_char == ")":
                left_start = word.rfind("(", 0, left_idx + 1)
                left = (
                    word[left_start : left_idx + 1] if left_start != -1 else left_char
                )
            else:
                left = left_char

        # Find right context (skip prosodic markers)
        right_start = index + len(character)
        right_idx = right_start
        while right_idx < len(word):
            right_char = word[right_idx]
            if (
                self.use_ipa_processing
                and self.ipa_processor_v2
                and right_char in "ˈˌ‖|"
            ):
                right_idx += 1
                continue
            break

        if right_idx >= len(word):
            right = "#"
        else:
            right_char = word[right_idx]
            if right_char == "(":
                right_end = word.find(")", right_idx)
                right = (
                    word[right_idx : right_end + 1] if right_end != -1 else right_char
                )
            else:
                right = right_char

        return f"{left}__{right}"

    def _classify_env(self, env: str) -> str:
        """Classify environment type."""
        left, right = env.split("__", 1)
        L = self._classify_side(left)
        R = self._classify_side(right)
        if L == "#" and R != "#":
            return "INITIAL"
        if L != "#" and R == "#":
            return "FINAL"
        return f"MEDIAL {L}_{R}"

    @staticmethod
    def _highlight_character(word: str, character: str, occurrence_index: int) -> str:
        """Highlight specific occurrence of character in word."""
        count = 0
        i = 0
        while i < len(word):
            j = word.find(character, i)
            if j == -1:
                break
            if count == occurrence_index:
                return word[:j] + f"[{character}]" + word[j + len(character) :]
            count += 1
            i = j + len(character)
        return word

    def _split_env(self, env: str, target_display: str) -> Tuple[str, str, str]:
        """Split environment into left, target, right."""
        left, right = env.split("__", 1)
        return left, target_display, right

    def _target_for_display(self, raw_query: str) -> str:
        q = raw_query
        if self.use_ipa_processing and self.ipa_processor_v2:
            q = self.ipa_processor_v2.normalize_nfc(q)
        q = normalize_tiebar(q)  # <- add this
        return f"[{q}]"

    @staticmethod
    def _format_examples(
        words: List[str], max_samples: int = 5, max_width: int = 60
    ) -> str:
        """Format example words for display."""
        shown = words[:max_samples]
        rest = len(words) - len(shown)
        s = ", ".join(shown)
        if len(s) > max_width:
            s = s[: max_width - 1] + "…"
        if rest > 0:
            s += f"  (+{rest} more)"
        return s

    def _compute_global_widths(
        self,
        grouped: Dict[str, OrderedDictType[str, List[str]]],
        target_disp: str,
    ) -> Tuple[int, int, int, int, int]:
        """Compute column widths for table display."""
        group_w = len("Group")
        left_w = len("Left")
        targ_w = max(len("Target"), len(target_disp))
        right_w = len("Right")
        count_w = len("Count")

        present_groups = [g for g in self._ORDER if grouped.get(g)]
        for g in present_groups:
            group_w = max(group_w, len(g))

        for env_map in grouped.values():
            for env, words in env_map.items():
                left, right = env.split("__", 1)
                left_w = max(left_w, len(left))
                right_w = max(right_w, len(right))
                count_w = max(count_w, len(str(len(words))))

        return group_w, left_w, targ_w, right_w, count_w

    def analyze_character(
        self, character: str, file_path: str = "data/dataset.txt"
    ) -> Dict[str, OrderedDictType[str, List[str]]]:
        """Analyze phonetic environments for a character."""
        try:
            from data import load_words_list

            words = load_words_list(file_path)
        except (IOError, OSError) as e:
            print(f"Error reading file {file_path}: {e}")
            return {}

        q = character
        if self.use_ipa_processing and self.ipa_processor_v2:
            q = self.ipa_processor_v2.normalize_nfc(q)
            q = normalize_tiebar(q)  # ← add this
        target = q
        env2words: Dict[str, List[str]] = defaultdict(list)

        for original in words:
            processed = self._prepare_word(original)

            if self.use_ipa_processing:
                if self.ipa_processor_v2:
                    segments = self.ipa_processor_v2.ipa_segments(processed)
                else:
                    segments = []

                if segments:
                    self._analyze_segments(segments, target, env2words)
                else:
                    self._analyze_characters(processed, target, env2words)
            else:
                self._analyze_characters(processed, target, env2words)

        grouped: Dict[str, OrderedDictType[str, List[str]]] = {
            k: OrderedDict() for k in self._ORDER
        }

        partitioned: Dict[str, List[Tuple[str, List[str]]]] = defaultdict(list)
        for env, lst in list(env2words.items()):
            dedup = list(dict.fromkeys(lst))
            env2words[env] = dedup
            macro = self._classify_env(env)
            partitioned[macro].append((env, dedup))

        for macro in self._ORDER:
            items = partitioned.get(macro, [])
            if not items:
                continue
            items.sort(key=lambda kv: (-len(kv[1]), kv[0]))
            grouped[macro] = OrderedDict((env, lst) for env, lst in items)

        return {k: v for k, v in grouped.items() if v}

    def _analyze_segments(
        self, segments: List[str], target: str, env2words: Dict[str, List[str]]
    ) -> None:
        """Analyze target in IPA segments using phonetic matching."""
        for i, seg in enumerate(segments):
            is_match = (
                self.ipa_processor_v2.phoneme_matches(target, seg)
                if self.use_ipa_processing and self.ipa_processor_v2
                else (seg == target)
            )
            if not is_match:
                continue

            li = _skip_left(segments, i)
            ri = _skip_right(segments, i)

            left = "#" if li < 0 else segments[li]
            right = "#" if ri >= len(segments) else segments[ri]
            env = f"{left}__{right}"

            example = self._create_clean_example(segments, i)
            env2words[env].append(example)

    def _analyze_characters(
        self, processed: str, target: str, env2words: Dict[str, List[str]]
    ) -> None:
        """Character-by-character analysis fallback."""
        idx = 0
        nth = 0
        while idx < len(processed):
            found = processed.find(target, idx)
            if found == -1:
                break

            env = self._get_environment(processed, target, found)
            highlighted = self._highlight_character(processed, target, nth)
            env2words[env].append(highlighted)

            idx = found + len(target)
            nth += 1

    def _create_clean_example(self, segments: List[str], match_index: int) -> str:
        """Bracket exactly the matched segment (includes any diacritics/modifiers)."""
        return "".join(
            f"[{s}]" if idx == match_index else s for idx, s in enumerate(segments)
        )

    def print_analysis(
        self,
        character: str,
        file_path: str = "data/dataset.txt",
        show_unicode_info: bool = False,
        max_examples_per_env: int = 5,
        compact_groups: bool = True,
        encoding: str = "utf-8",
    ) -> None:
        """Pretty-print analysis results."""
        if show_unicode_info and self.use_ipa_processing and self.ipa_processor_v2:
            info = self.ipa_processor_v2.get_segment_info(character)
            print(f"\nUnicode Information for '{character}':")
            print(f"  Code Point: {info.get('code_point', 'N/A')}")
            print(f"  Name: {info.get('name', 'N/A')}")
            print(f"  Category: {info.get('category', 'N/A')}")
            print(f"  Is IPA Base: {info.get('is_ipa_base', False)}")
            print(f"  Is Combining: {info.get('is_combining', False)}")
            print()

        grouped = self.analyze_character(character, file_path)
        if not grouped:
            print(f"No occurrences of '{character}' found in '{file_path}'")
            return

        target_disp = self._target_for_display(character)
        group_w, left_w, targ_w, right_w, count_w = self._compute_global_widths(
            grouped, target_disp
        )

        # Build rows for display
        rows: List[Tuple[str, str, str, str, int, str, bool]] = []
        group_count = 0
        for macro_group in self._ORDER:
            env_map = grouped.get(macro_group)
            if not env_map:
                continue

            if group_count > 0:
                rows.append(("", "", "", "", 0, "", True))  # separator

            first = True
            for env, words in env_map.items():
                left, tgt, right = self._split_env(env, target_disp)
                cnt = len(words)
                rows.append(
                    (
                        macro_group if (first or not compact_groups) else "",
                        left,
                        target_disp,
                        right,
                        cnt,
                        ", ".join(words),
                        False,
                    )
                )
                first = False
            group_count += 1

        # Try Rich formatting first
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.rule import Rule
            from rich import box
            from rich.markup import escape as rich_escape

            console = Console()
            term_w = get_terminal_size((100, 20)).columns

            console.print(
                Rule(
                    f"[bold]Phonetic environments for '{rich_escape(character)}'[/bold]"
                )
            )

            table = Table(
                box=box.SIMPLE_HEAVY,
                show_lines=False,
                expand=True,
                pad_edge=False,
            )
            table.add_column("Group", justify="left", no_wrap=True, width=group_w)
            table.add_column(
                "Left",
                justify="right",
                no_wrap=False,
                style="cyan",
                width=left_w,
            )  # changed
            table.add_column(
                "Target",
                justify="center",
                no_wrap=True,
                style="bold",
                width=targ_w,
            )
            table.add_column(
                "Right",
                justify="left",
                no_wrap=False,
                style="cyan",
                width=right_w,
            )  # changed
            table.add_column(
                "Count",
                justify="right",
                no_wrap=True,
                style="magenta",
                width=count_w,
            )
            table.add_column("Examples", overflow="fold")

            examples_width = max(
                24,
                term_w - (group_w + left_w + targ_w + right_w + count_w + 14),
            )

            for group, left, tgt, right, cnt, examples, is_separator in rows:
                if is_separator:
                    table.add_row("", "", "", "", "", "", end_section=True)
                else:
                    table.add_row(
                        rich_escape(group),
                        rich_escape(left),
                        rich_escape(tgt),
                        rich_escape(right),
                        str(cnt) if cnt > 0 else "",
                        rich_escape(
                            self._format_examples(
                                examples.split(", "),
                                max_examples_per_env,
                                examples_width,
                            )
                        ),
                    )

            console.print(table)
            return

        except Exception:
            pass  # Fall back to plain text

        # Plain text fallback
        term_w = get_terminal_size((100, 20)).columns
        examples_header_w = max(
            8, term_w - (group_w + left_w + targ_w + right_w + count_w + 16)
        )
        print("=" * term_w)
        print(
            f"{'Group':<{group_w}}  "
            f"{'Left':>{left_w}}  "
            f"{'Target':^{targ_w}}  "
            f"{'Right':<{right_w}}  "
            f"{'Count':>{count_w}}  "
            f"{'Examples':<{examples_header_w}}"
        )
        print("=" * term_w)

        for group, left, tgt, right, cnt, examples, is_separator in rows:
            if is_separator:
                print("─" * term_w)
            else:
                ex_width = max(
                    20,
                    term_w - (group_w + left_w + targ_w + right_w + count_w + 16),
                )
                ex_str = self._format_examples(
                    examples.split(", "), max_examples_per_env, ex_width
                )
                count_str = str(cnt) if cnt > 0 else ""
                print(
                    f"{group:<{group_w}}  "
                    f"{left:>{left_w}}  "
                    f"{tgt:^{targ_w}}  "
                    f"{right:<{right_w}}  "
                    f"{count_str:>{count_w}}  "
                    f"{ex_str}"
                )
