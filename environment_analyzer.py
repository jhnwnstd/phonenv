from __future__ import annotations

from typing import Dict, List, Set, Tuple, OrderedDict as OrderedDictType
from pathlib import Path
from collections import defaultdict, OrderedDict
from shutil import get_terminal_size

from ipa_processor_v2 import IPAProcessorV2, get_config_for_transcription_mode


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
        "i", "y", "ɨ", "ʉ", "ɯ", "u", "ɪ", "ʏ", "ʊ",
        "e", "ø", "ɘ", "ɵ", "ɤ", "o", "ə", "ɚ", "ɜ", "ɞ", "ʌ", "ɔ", "ɛ", "œ",
        "æ", "ɐ", "a", "ɶ", "ɑ", "ɒ", "ᵻ", "ᵿ",
    }

    def __init__(
        self,
        special_chars_file: str = "data/special_characters.txt",
        use_ipa_processing: bool = True,
        use_professional_ipa: bool = True,
        transcription_mode: str = "narrow",
        no_color: bool = False,
    ):
        self.special_chars_file = Path(special_chars_file)
        self._special_characters: Set[str] = set()
        self.use_ipa_processing = use_ipa_processing
        self.transcription_mode = transcription_mode
        self.no_color = no_color

        if use_ipa_processing:
            # Use transcription mode to configure IPA processing
            config = get_config_for_transcription_mode(transcription_mode)
            self.ipa_processor_v2 = IPAProcessorV2(config)
        else:
            self.ipa_processor_v2 = None

        self._load_special_characters()

    # ------------------------- Special chars I/O -------------------------
    def _load_special_characters(self) -> None:
        try:
            if self.special_chars_file.exists():
                with self.special_chars_file.open("r", encoding="utf-8") as f:
                    self._special_characters = {
                        line.strip() for line in f if line.strip()
                    }
        except (IOError, OSError) as e:
            print(f"Warning: Could not load special characters: {e}")

    def _write_special_characters(self, characters: Set[str]) -> None:
        self.special_chars_file.parent.mkdir(parents=True, exist_ok=True)
        with self.special_chars_file.open("w", encoding="utf-8") as f:
            for char in sorted(characters):
                f.write(f"{char}\n")

    # ----------------------- Preprocessing & helpers ---------------------
    def _prepare_word(self, word: str) -> str:
        processed = word
        for special in self._special_characters:
            processed = processed.replace(special, f"({special})")

        if self.use_ipa_processing and self.ipa_processor_v2:
            processed = self.ipa_processor_v2.normalize_nfc(processed)

        return processed

    @staticmethod
    def _strip_paren_group(token: str) -> str:
        return token[1:-1] if token.startswith("(") and token.endswith(")") else token

    def _segment_base_char(self, token: str) -> str:
        import unicodedata as ud

        s = self._strip_paren_group(token)
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
        return self._segment_base_char(token) in self._IPA_VOWEL_BASES

    def _classify_side(self, token: str) -> str:
        if token == "#":
            return "#"
        return "V" if self._is_vowel_segment(token) else "C"

    def _get_environment(self, word: str, character: str, index: int) -> str:
        # Find left context (skip prosodic markers)
        left_idx = index - 1
        while left_idx >= 0:
            left_char = word[left_idx]
            if self.use_ipa_processing and self.ipa_processor_v2 and left_char in "ˈˌ‖|":
                # Skip prosodic markers
                left_idx -= 1
                continue
            break

        if left_idx < 0:
            left = "#"
        else:
            left_char = word[left_idx]
            if left_char == ")":
                left_start = word.rfind("(", 0, left_idx + 1)
                left = word[left_start:left_idx + 1] if left_start != -1 else left_char
            else:
                left = left_char

        # Find right context (skip prosodic markers)
        right_start = index + len(character)
        right_idx = right_start
        while right_idx < len(word):
            right_char = word[right_idx]
            if self.use_ipa_processing and self.ipa_processor_v2 and right_char in "ˈˌ‖|":
                # Skip prosodic markers
                right_idx += 1
                continue
            break

        if right_idx >= len(word):
            right = "#"
        else:
            right_char = word[right_idx]
            if right_char == "(":
                right_end = word.find(")", right_idx)
                right = word[right_idx : right_end + 1] if right_end != -1 else right_char
            else:
                right = right_char

        return f"{left}__{right}"

    def _classify_env(self, env: str) -> str:
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

    # -------- Presentation helpers (simple & readable) -------------------
    def _split_env(self, env: str, target_display: str) -> Tuple[str, str, str]:
        """Turn 'left__right' into (left, target_display, right)."""
        left, right = env.split("__", 1)
        return left, target_display, right

    def _target_for_display(self, raw_query: str) -> str:
        """Pretty target token for the Target column (e.g., '[a]' or '[t͡ʃ]')."""
        q = raw_query
        if self.use_ipa_processing and self.ipa_processor_v2:
            q = self.ipa_processor_v2.normalize_nfc(q)
        return f"[{q}]"

    @staticmethod
    def _format_examples(words: List[str], max_samples: int = 5, max_width: int = 60) -> str:
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
        """
        Compute global widths for Group, Left, Target, Right, Count across ALL rows.
        """
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

    # ------------------------------ Analysis ------------------------------
    def analyze_character(
        self, character: str, file_path: str = "data/input.txt"
    ) -> Dict[str, OrderedDictType[str, List[str]]]:
        """
        Return grouped, per-group-sorted environments:
        { macro_group: OrderedDict({ env: [examples...] }) }
        """
        try:
            words = self._load_words(file_path)
        except (IOError, OSError) as e:
            print(f"Error reading file {file_path}: {e}")
            return {}

        q = character
        if self.use_ipa_processing and self.ipa_processor_v2:
            q = self.ipa_processor_v2.normalize_nfc(q)

        target = f"({q})" if q in self._special_characters else q

        env2words: Dict[str, List[str]] = defaultdict(list)

        for original in words:
            processed = self._prepare_word(original)

            if self.use_ipa_processing:
                # Use IPA segmentation for more accurate analysis
                if self.ipa_processor_v2:
                    segments = self.ipa_processor_v2.ipa_segments(processed)
                else:
                    segments = []

                if segments:
                    self._analyze_segments(segments, target, original, env2words)
                else:
                    # Fall back to character-by-character analysis
                    self._analyze_characters(processed, target, env2words)
            else:
                # Fall back to character-by-character analysis
                self._analyze_characters(processed, target, env2words)

        grouped: Dict[str, OrderedDictType[str, List[str]]] = {k: OrderedDict() for k in self._ORDER}

        partitioned: Dict[str, List[Tuple[str, List[str]]]] = defaultdict(list)
        for env, lst in env2words.items():
            macro = self._classify_env(env)
            partitioned[macro].append((env, lst))

        for macro in self._ORDER:
            items = partitioned.get(macro, [])
            if not items:
                continue
            items.sort(key=lambda kv: (-len(kv[1]), kv[0]))
            grouped[macro] = OrderedDict((env, lst) for env, lst in items)

        return {k: v for k, v in grouped.items() if v}

    def _analyze_segments(self, segments: List[str], target: str, original_word: str, env2words: Dict[str, List[str]]) -> None:
        """Analyze target in IPA segments list using phonetic matching."""
        occurrence_count = 0
        for i, segment in enumerate(segments):
            # Use intelligent phonetic matching
            if self.use_ipa_processing and self.ipa_processor_v2:
                matches = self.ipa_processor_v2.phoneme_matches(target, segment)
            else:
                matches = (segment == target)

            if matches:
                # Get left context
                left = "#" if i == 0 else segments[i - 1]

                # Get right context
                right = "#" if i == len(segments) - 1 else segments[i + 1]

                env = f"{left}__{right}"
                # Create clean highlighted example for this specific occurrence
                highlighted = self._create_clean_example(segments, target, i, occurrence_count)
                env2words[env].append(highlighted)
                occurrence_count += 1

    def _analyze_characters(self, processed: str, target: str, env2words: Dict[str, List[str]]) -> None:
        """Fall back to character-by-character analysis (legacy mode)."""
        idx = 0
        nth = 0
        while idx < len(processed):
            found = processed.find(target, idx)
            if found == -1:
                break

            paren_start = processed.rfind("(", 0, found)
            paren_end = processed.find(")", found)
            if paren_start != -1 and paren_end != -1 and paren_start < found < paren_end:
                idx = found + len(target)
                continue

            env = self._get_environment(processed, target, found)
            highlighted = self._highlight_character(processed, target, nth)
            env2words[env].append(highlighted)

            idx = found + len(target)
            nth += 1

    def _create_clean_example(self, segments: List[str], target_segment: str, segment_index: int, occurrence_count: int) -> str:
        """Create a clean highlighted example showing only the specific target occurrence."""
        result_segments = []

        for i, segment in enumerate(segments):
            if i == segment_index:
                # If target is found within a larger segment (like ɪ in aɪ), highlight just the target
                if target_segment in segment and target_segment != segment:
                    # Find the position of target within the segment
                    target_pos = segment.find(target_segment)
                    if target_pos != -1:
                        before = segment[:target_pos]
                        after = segment[target_pos + len(target_segment):]
                        highlighted = f"{before}[{target_segment}]{after}"
                        result_segments.append(highlighted)
                    else:
                        # Fallback: highlight the whole segment
                        result_segments.append(f"[{segment}]")
                else:
                    # Target is the whole segment
                    result_segments.append(f"[{target_segment}]")
            else:
                result_segments.append(segment)

        return "".join(result_segments)

    def _highlight_segment_in_word(self, original_word: str, target_segment: str, segment_index: int, segments: List[str]) -> str:
        """Legacy method - kept for backward compatibility."""
        return self._create_clean_example(segments, target_segment, segment_index, 0)

    # ------------------------------- I/O ---------------------------------
    @staticmethod
    def _load_words(file_path: str) -> List[str]:
        p = Path(file_path)
        with p.open("r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    # ----------------------------- Presentation --------------------------
    def print_analysis(
        self,
        character: str,
        file_path: str = "data/input.txt",
        show_unicode_info: bool = False,
        max_examples_per_env: int = 5,
        compact_groups: bool = True,   # only print group name on the first row of each group
        encoding: str = "utf-8",
    ) -> None:
        """
        Pretty-print grouped analysis with globally aligned columns.
        Single table: Group | Left | Target | Right | Count | Examples
        Uses 'rich' if available; falls back to stdlib.
        """
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
        group_w, left_w, targ_w, right_w, count_w = self._compute_global_widths(grouped, target_disp)

        # Build a flat list of rows (group, left, target, right, count, examples, is_separator)
        rows: List[Tuple[str, str, str, str, int, str, bool]] = []
        group_count = 0
        for macro_group in self._ORDER:
            env_map = grouped.get(macro_group)
            if not env_map:
                continue

            # Add separator before group (except first one)
            if group_count > 0:
                rows.append(("", "", "", "", 0, "", True))  # separator row

            first = True
            for env, words in env_map.items():
                left, tgt, right = self._split_env(env, target_disp)
                cnt = len(words)
                rows.append((macro_group if (first or not compact_groups) else "", left, target_disp, right, cnt, ", ".join(words), False))
                first = False
            group_count += 1

        # Try Rich first
        try:
            from rich.console import Console
            from rich.table import Table
            from rich.rule import Rule
            from rich import box
            from rich.markup import escape as rich_escape

            console = Console()
            term_w = get_terminal_size((100, 20)).columns

            console.print(Rule(f"[bold]Phonetic environments for '{rich_escape(character)}'[/bold]"))

            table = Table(box=box.SIMPLE_HEAVY, show_lines=False, expand=True, pad_edge=False)
            table.add_column("Group", justify="left", no_wrap=True, width=group_w)
            table.add_column("Left", justify="right", no_wrap=True, style="cyan", width=left_w)
            table.add_column("Target", justify="center", no_wrap=True, style="bold", width=targ_w)
            table.add_column("Right", justify="left", no_wrap=True, style="cyan", width=right_w)
            table.add_column("Count", justify="right", no_wrap=True, style="magenta", width=count_w)
            table.add_column("Examples", overflow="fold")

            # Examples column width (remaining space)
            examples_width = max(24, term_w - (group_w + left_w + targ_w + right_w + count_w + 14))

            # Emit rows
            for group, left, tgt, right, cnt, examples, is_separator in rows:
                if is_separator:
                    # Add a visual separator
                    table.add_row("", "", "", "", "", "", end_section=True)
                else:
                    table.add_row(
                        rich_escape(group),
                        rich_escape(left),
                        rich_escape(tgt),
                        rich_escape(right),
                        str(cnt) if cnt > 0 else "",
                        rich_escape(self._format_examples(examples.split(", "), max_examples_per_env, examples_width)),
                    )

            console.print(table)
            return

        except Exception:
            pass  # fall through to stdlib

        # Stdlib fallback (aligned with the same global widths)
        term_w = get_terminal_size((100, 20)).columns
        examples_header_w = max(8, term_w - (group_w + left_w + targ_w + right_w + count_w + 16))
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
                # Print separator line
                print("─" * term_w)
            else:
                ex_width = max(20, term_w - (group_w + left_w + targ_w + right_w + count_w + 16))
                ex_str = self._format_examples(examples.split(", "), max_examples_per_env, ex_width)
                count_str = str(cnt) if cnt > 0 else ""
                print(
                    f"{group:<{group_w}}  "
                    f"{left:>{left_w}}  "
                    f"{tgt:^{targ_w}}  "
                    f"{right:<{right_w}}  "
                    f"{count_str:>{count_w}}  "
                    f"{ex_str}"
                )

    # -------------------------- Config management ------------------------
    def add_special_character(
        self, character: str, delete: bool = False, erase: bool = False
    ) -> None:
        try:
            current = set()
            if self.special_chars_file.exists():
                with self.special_chars_file.open("r", encoding="utf-8") as f:
                    current = {line.strip() for line in f if line.strip()}

            if delete:
                self.special_chars_file.write_text("", encoding="utf-8")
                self._special_characters.clear()
                print("Cleared all special characters")
                return

            if erase:
                if character in current:
                    current.remove(character)
                    self._write_special_characters(current)
                    self._special_characters.discard(character)
                    print(f"Removed '{character}' from special_characters.txt")
                else:
                    print(f"'{character}' not found in special_characters.txt")
                return

            if character not in current:
                current.add(character)
                self._write_special_characters(current)
                self._special_characters.add(character)
                print(f"Added '{character}' to special_characters.txt")
            else:
                print(f"'{character}' already exists in special_characters.txt")

        except (IOError, OSError) as e:
            print(f"Error managing special characters: {e}")


# --------------------------- Back-compat helpers ---------------------------
def analyze_character(character: str, file: str = "data/input.txt") -> Dict[str, OrderedDict]:
    analyzer = PhoneticAnalyzer(use_ipa_processing=True)
    return analyzer.analyze_character(character, file)


def analyze_character_print(character: str, file: str = "data/input.txt") -> None:
    analyzer = PhoneticAnalyzer(use_ipa_processing=True)
    analyzer.print_analysis(character, file)


def add_special_character(character: str, delete: bool = False, erase: bool = False) -> None:
    analyzer = PhoneticAnalyzer(use_ipa_processing=True)
    analyzer.add_special_character(character, delete, erase)
