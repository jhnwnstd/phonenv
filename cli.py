"""Command-line interface for phonetic environment analysis.

This module provides both interactive and command-line interfaces for
phonetic environment analysis, including batch processing capabilities.
"""

from __future__ import annotations

from pathlib import Path
import os, shutil
import sys
import argparse
import unicodedata as ud
from typing import Dict, List, Optional, Mapping

from analysis import PhoneticAnalyzer
from data import DictionaryProcessor, TargetsProcessor, create_sample_targets_file, targets_exist
from phonenv_io import get_cache, clear_cache, get_cache_stats, AutoOutputWriter

# ========================= DIACRITIC PANEL =========================

COMMON_DIACRITICS: Dict[str, Dict[str, str | bool | None]] = {
    # Length (spacing, mutually exclusive)
    "long":        {"glyph": "ː",   "kind": "spacing",   "scope": "any",       "group": "length"},
    "half-long":   {"glyph": "ˑ",   "kind": "spacing",   "scope": "any",       "group": "length"},
    # Added: extra-short (spacing, same group)
    "extra-short": {"glyph": "˘",   "kind": "spacing",   "scope": "any",       "group": "length"},   # U+02D8

    # Voicing (combining, mutually exclusive)
    "voiceless":       {"glyph": "\u0325", "kind": "combining", "scope": "any", "group": "voice"},    # ◌̥
    "voiced":          {"glyph": "\u032C", "kind": "combining", "scope": "any", "group": "voice"},    # ◌̬
    # Added: ring above variant for voiceless (combining, same group)
    "voiceless-above": {"glyph": "\u030A", "kind": "combining", "scope": "any", "group": "voice"},    # ◌̊

    # Syllabicity (mutually exclusive via shared group)
    "syllabic":  {"glyph": "\u0329", "kind": "combining", "scope": "consonant", "group": "syll"},     # ◌̩
    "non-syl":   {"glyph": "\u032F", "kind": "combining", "scope": "vowel",     "group": "syll"},     # ◌̯

    # Common vowel/consonant effects
    "nasal":      {"glyph": "\u0303", "kind": "combining", "scope": "any",       "group": None},      # ◌̃
    "no-release": {"glyph": "\u031A", "kind": "combining", "scope": "consonant", "group": None},      # ◌̚

    # Secondary articulations (spacing)
    "aspirated": {"glyph": "ʰ", "kind": "spacing", "scope": "consonant", "group": None},
    "palatalized":   {"glyph": "ʲ", "kind": "spacing", "scope": "consonant", "group": None},
    "labialized":    {"glyph": "ʷ", "kind": "spacing", "scope": "consonant", "group": None},
    "velarized": {"glyph": "ˠ", "kind": "spacing", "scope": "consonant", "group": None},
    "pharyngealized":   {"glyph": "ˤ", "kind": "spacing", "scope": "consonant", "group": None},

    # Place tweak (combining)
    "dental":    {"glyph": "\u032A", "kind": "combining", "scope": "consonant", "group": None},      # ◌̪

    # -------------------- Additional IPA diacritics --------------------

    # Phonation / voice quality (combining)
    "breathy": {"glyph": "\u0324", "kind": "combining", "scope": "any",   "group": None},            # ◌̤
    "creaky":  {"glyph": "\u0330", "kind": "combining", "scope": "any",   "group": None},            # ◌̰

    # Vowel rounding (combining, mutually exclusive)
    "more-rounded": {"glyph": "\u0339", "kind": "combining", "scope": "vowel", "group": "round"},    # ◌̹
    "less-rounded": {"glyph": "\u031C", "kind": "combining", "scope": "vowel", "group": "round"},    # ◌̜

    # Centralization (combining, mutually exclusive)
    "centralized":     {"glyph": "\u0308", "kind": "combining", "scope": "vowel", "group": "central"},  # ◌̈
    "mid-centralized": {"glyph": "\u033D", "kind": "combining", "scope": "vowel", "group": "central"},  # ◌̽

    # Height shift (combining, mutually exclusive)
    "raised":  {"glyph": "\u031D", "kind": "combining", "scope": "vowel", "group": "height"},        # ◌̝
    "lowered": {"glyph": "\u031E", "kind": "combining", "scope": "vowel", "group": "height"},        # ◌̞

    # Front/back advancement (combining, mutually exclusive)
    "advanced":  {"glyph": "\u031F", "kind": "combining", "scope": "any", "group": "adv"},           # ◌̟
    "retracted": {"glyph": "\u0320", "kind": "combining", "scope": "any", "group": "adv"},           # ◌̠

    # Tongue-root position (combining, mutually exclusive)
    "ATR": {"glyph": "\u0318", "kind": "combining", "scope": "vowel", "group": "tongue_root"},       # ◌̘
    "RTR": {"glyph": "\u0319", "kind": "combining", "scope": "vowel", "group": "tongue_root"},       # ◌̙

    # Coronal articulation detail (combining)
    "apical":       {"glyph": "\u033A", "kind": "combining", "scope": "consonant", "group": None},   # ◌̺
    "laminal":      {"glyph": "\u033B", "kind": "combining", "scope": "consonant", "group": None},   # ◌̻
    "linguolabial": {"glyph": "\u033C", "kind": "combining", "scope": "consonant", "group": None},   # ◌̼

    # Rhoticity (spacing; note: ɚ/ɝ are precomposed alternatives)
    "rhoticity": {"glyph": "˞", "kind": "spacing", "scope": "vowel", "group": None},                 # U+02DE

    # Stop releases / coarticulation (spacing)
    "nasal-release":   {"glyph": "\u207F", "kind": "spacing", "scope": "consonant", "group": None},  # ⁿ
    "lateral-release": {"glyph": "ˡ",      "kind": "spacing", "scope": "consonant", "group": None},  # ˡ
}

def _compose(base: str, toggle_names: List[str], catalog: Mapping[str, Mapping[str, str | bool | None]]) -> str:
    """Attach combining marks (Mn) first, then spacing modifiers (Sk); normalize NFC."""
    combining: List[str] = []
    spacing: List[str] = []
    for name in toggle_names:
        spec = catalog[name]
        if spec["kind"] == "combining":
            combining.append(spec["glyph"])  # type: ignore[arg-type]
        else:
            spacing.append(spec["glyph"])    # type: ignore[arg-type]
    return ud.normalize("NFC", base + "".join(combining) + "".join(spacing))

def _apply_mutex_list(toggled: List[str], newly: str, catalog: Mapping[str, Mapping[str, str | bool | None]]) -> List[str]:
    """Like _apply_mutex but preserves order; replaces any prior member of the same group."""
    group = catalog[newly].get("group")
    if not group:
        return toggled + ([newly] if newly not in toggled else [])
    # filter out any prior item from the same group
    filtered = [n for n in toggled if catalog[n].get("group") != group]
    # append newly (last write wins)
    if newly not in filtered:
        filtered.append(newly)
    return filtered

# ========================= INTERACTIVE CLI =========================

class InteractivePhonenvCLI:
    """Interactive command line interface for phonetic environment analysis."""

    # UI Constants
    DEFAULT_TERMINAL_WIDTH = 100
    DEFAULT_TERMINAL_HEIGHT = 20
    PREVIEW_TRUNCATE_LENGTH = 25
    REPORT_SEPARATOR_WIDTH = 60
    NARROW_SEPARATOR_WIDTH = 40

    # File paths
    DEFAULT_DATASET_PATH = "data/dataset.txt"
    DEFAULT_TARGETS_PATH = "data/targets.txt"
    DEFAULT_OUTPUT_DIR = "data/output"

    # Transcription modes
    class TranscriptionMode:
        NARROW = "narrow"
        BROAD = "broad"

    @staticmethod
    def _format_error(operation: str, error: Exception) -> str:
        """Standardized error message formatting."""
        return f"Error {operation}: {error}"

    @staticmethod
    def _normalize_user_input(text: str) -> str:
        """Normalize user input: strip whitespace and convert to lowercase."""
        return text.strip().lower()

    @property
    def _terminal_width(self) -> int:
        """Cached terminal width to avoid repeated system calls."""
        if not hasattr(self, '_term_width_cache'):
            self._term_width_cache = shutil.get_terminal_size((self.DEFAULT_TERMINAL_WIDTH, self.DEFAULT_TERMINAL_HEIGHT)).columns
        return self._term_width_cache

    # IPA consonant categories with common symbols
    CONSONANT_CATEGORIES = {
        "Stops/Plosives": {
            "Bilabial": ["p", "b"],
            "Dental": ["t̪", "d̪"],
            "Alveolar": ["t", "d"],
            "Retroflex": ["ʈ", "ɖ"],
            "Palatal": ["c", "ɟ"],
            "Velar": ["k", "g"],
            "Uvular": ["q", "ɢ"],
            "Glottal": ["ʔ"],
        },
        "Affricates": {
            "Bilabial": ["p͡ɸ", "b͡β"],
            "Labiodental": ["p͡f", "b͡v"],
            "Alveolar": ["t͡s", "d͡z"],
            "Postalveolar": ["t͡ʃ", "d͡ʒ"],
            "Retroflex": ["ʈ͡ʂ", "ɖ͡ʐ"],
            "Alveolo-palatal": ["t͡ɕ", "d͡ʑ"],
            "Palatal": ["c͡ç", "ɟ͡ʝ"],
            "Velar": ["k͡x", "g͡ɣ"],
            "Uvular": ["q͡χ", "ɢ͡ʁ"],
        },
        "Nasals": {
            "Bilabial": ["m"],
            "Labiodental": ["ɱ"],
            "Alveolar": ["n"],
            "Retroflex": ["ɳ"],
            "Palatal": ["ɲ"],
            "Velar": ["ŋ"],
            "Uvular": ["ɴ"],
        },
        "Trills": {
            "Bilabial": ["ʙ"],
            "Alveolar": ["r"],
            "Uvular": ["ʀ"],
        },
        "Taps/Flaps": {
            "Alveolar": ["ɾ"],
            "Retroflex": ["ɽ"],
        },
        "Fricatives": {
            "Bilabial": ["ɸ", "β"],
            "Labiodental": ["f", "v"],
            "Dental": ["θ", "ð"],
            "Alveolar": ["s", "z"],
            "Postalveolar": ["ʃ", "ʒ"],
            "Retroflex": ["ʂ", "ʐ"],
            "Palatal": ["ç", "ʝ"],
            "Velar": ["x", "ɣ"],
            "Uvular": ["χ", "ʁ"],
            "Pharyngeal": ["ħ", "ʕ"],
            "Glottal": ["h", "ɦ"],
        },
        "Lateral Fricatives": {
            "Alveolar": ["ɬ", "ɮ"],
        },
        "Approximants": {
            "Labiovelar": ["w"],
            "Bilabial": ["ʋ"],
            "Alveolar": ["ɹ"],
            "Retroflex": ["ɻ"],
            "Palatal": ["j"],
            "Velar": ["ɰ"],
        },
        "Lateral Approximants": {
            "Alveolar": ["l"],
            "Retroflex": ["ɭ"],
            "Palatal": ["ʎ"],
            "Velar": ["ʟ"],
        },
    }

    # IPA vowel categories
    VOWEL_CATEGORIES = {
        "Close": {
            "Front": ["i", "y"],
            "Central": ["ɨ", "ʉ"],
            # STANDARDIZE: "Back vowels" -> "Back"
            "Back": ["ɯ", "u"],
        },
        "Near-Close": {
            "Front": ["ɪ", "ʏ"],
            "Back": ["ʊ"],
        },
        "Close-Mid": {
            "Front": ["e", "ø"],
            "Central": ["ɘ", "ɵ"],
            "Back": ["ɤ", "o"],
        },
        "Mid": {
            "Central": ["ə", "ɚ"],
        },
        "Open-Mid": {
            "Front": ["ɛ", "œ"],
            "Central": ["ɜ", "ɞ", "ʌ"],
            "Back": ["ɔ"],
        },
        "Near-Open": {
            "Front": ["æ"],
            "Central": ["ɐ"],
        },
        "Open": {
            "Front": ["a", "ɶ"],
            "Back": ["ɑ", "ɒ"],
        },
        "Diphthongs": {
            "Closing": ["aɪ", "eɪ", "ɔɪ", "aʊ", "oʊ"],
            # Note: ɪə, eə, ʊə are traditionally "centring" diphthongs; keep naming as in your UI.
            "Opening": ["ɪə", "eə", "ʊə"],
            # REMOVE: triphthongs from diphthongs
            # "Centering": ["aɪə", "aʊə"],
        },
        "Triphthongs": {
            "Common": ["aɪə", "aʊə", "eɪə", "oʊə"],
        },
    }

    def _hr(self, ch: str = "─") -> None:
        print(ch * self._terminal_width)

    def _clear(self) -> None:
        """Clear terminal screen safely."""
        try:
            if os.name == "nt":
                os.system("cls")  # Windows
            else:
                print("\033[2J\033[H", end="")  # ANSI escape sequence for Unix/Linux
        except Exception:
            pass  # Graceful fallback if clearing fails

    def _banner(self, title: str, *, clear: bool = True, subtitle: str | None = None) -> None:
        if clear:
            self._clear()
        line = f" {title} ".center(self._terminal_width, "═")
        print(line)
        status = f"[ Mode: {self.transcription_mode} | Dataset: {Path(self.file_path).name} ]"
        print(status.center(self._terminal_width))
        if subtitle:
            print(subtitle.center(self._terminal_width))
        print()  # spacer

    def _menu(self, options: list[str], back_label: str | None = None, prompt: str | None = None) -> int | None:
        """
        Render a numbered list with aligned numbers.
        Returns: 1-based index, or None if user chose Back.
        """
        total = len(options) + (1 if back_label else 0)
        width = len(str(total))
        for i, text in enumerate(options, 1):
            print(f"  {i:>{width}}. {text}")
        if back_label:
            print(f"  {total:>{width}}. {back_label}")
        print()
        prompt = prompt or f"Choose (1–{total}) › "
        choice = self._normalize_user_input(input(prompt))

        # Empty Enter serves as back/exit
        if not choice:
            return None

        if back_label and choice in {str(total), "b", "back"}:
            return None

        if choice.isdigit():
            n = int(choice)
            if 1 <= n <= len(options):
                return n
            else:
                print(f"Please enter a number between 1 and {len(options)}.\n")
        else:
            print("Please enter a valid number.\n")

        return self._menu(options, back_label, prompt)  # re-prompt

    def _status(self) -> None:
        """One-line status bar shown under banners."""
        print(f"[ Mode: {self.transcription_mode} | Dataset: {Path(self.file_path).name} ]\n")

    def __init__(self, file_path: str = None):
        """Initialize the interactive CLI."""
        self.file_path = file_path or self.DEFAULT_DATASET_PATH
        self.transcription_mode = "broad"
        self.analyzer: Optional[PhoneticAnalyzer] = None
        self.dict_processor = DictionaryProcessor(self.file_path)
        self._create_analyzer()

    def _create_analyzer(self):
        from analysis import get_config_for_transcription_mode, IPAProcessorV2
        config = get_config_for_transcription_mode(self.transcription_mode)
        self.analyzer = PhoneticAnalyzer(
            use_ipa_processing=True,
            use_professional_ipa=True,
            transcription_mode=self.transcription_mode,  # ← add this
        )
        if getattr(self.analyzer, "ipa_processor_v2", None) is not None:
            self.analyzer.ipa_processor_v2 = IPAProcessorV2(config)

    def run(self) -> None:
        """Run the interactive CLI."""
        self._banner("Phonenv — Interactive Phonetic Environment Analysis")
        self._set_transcription_mode()

        while True:
            try:
                character = self._get_character_choice()
                if character is None:
                    print("\nGoodbye!")
                    break
                if not self.analyzer:
                    self._create_analyzer()
                if self.analyzer:
                    print(f"\nAnalyzing phonetic environments for '{character}' ({self.transcription_mode} transcription)...\n")
                    self.analyzer.print_analysis(character, self.file_path, show_unicode_info=False)
                else:
                    print(f"\n{self._format_error('initializing analyzer', 'Please check the configuration.')}")

                self._hr()
                if not self._continue_prompt():
                    print("\nGoodbye!")
                    break

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n{self._format_error('during analysis', e)}")
                print("Please try again.\n")

    def _set_transcription_mode(self, allow_back: bool = False) -> None:
        """Set the transcription mode (broad vs narrow)."""
        while True:
            # Header
            self._banner("TRANSCRIPTION MODE")
            cur = getattr(self, "transcription_mode", "broad")

            # Menu (mark current)
            print(f"Current mode: {cur}\n")
            print(f"  1. Narrow transcription{'   [current]' if cur == 'narrow' else ''}")
            print("     - Distinguishes diacritic variants (p ≠ pʰ)")
            print("     - Focus on surface phonetic detail\n")
            print(f"  2. Broad transcription{'    [current]' if cur == 'broad' else ''}")
            print("     - Treats diacritic variants as the same (p = pʰ)")
            print("     - Focus on underlying phonological patterns\n")
            if allow_back:
                print("  3. ← Back\n")

            prompt = "Select mode (1-2): " if not allow_back else "Select mode (1-2) or '3'/'b' to go back: "
            choice = self._normalize_user_input(input(prompt))

            if allow_back and choice in {"3", "b", "back"}:
                return

            mapping = {"1": "narrow", "narrow": "narrow", "2": "broad", "broad": "broad"}
            if choice not in mapping:
                print("Please enter 1 for narrow or 2 for broad.\n")
                continue

            new_mode = mapping[choice]
            if new_mode == cur:
                print(f"\nMode unchanged ({cur}).\n")
                return

            self.transcription_mode = new_mode
            print(f"\nMode set to: {self.transcription_mode} transcription\n")
            self._create_analyzer()
            return

    def _get_character_choice(self) -> Optional[str]:
        while True:
            self._banner("MAIN MENU")
            idx = self._menu([
                "Consonants",
                "Vowels",
                "Advanced: paste IPA segment",
                "Batch processing (targets.txt)",
                "Change transcription mode",
                "Dictionary management",
                "Exit",
            ])
            # Handle empty Enter as exit for main menu
            if idx is None:
                return None
            if idx == 1:
                res = self._select_consonant()
                if res is not None:
                    return res
                continue  # back to main menu
            if idx == 2:
                res = self._select_vowel()
                if res is not None:
                    return res
                continue
            if idx == 3:
                pasted = input("Paste IPA segment (NFC recommended): ").strip()
                return ud.normalize("NFC", pasted) if pasted else None
            if idx == 4:
                self._batch_processing_menu()
                continue
            if idx == 5:
                self._set_transcription_mode(allow_back=True)
                continue
            if idx == 6:
                self._dictionary_menu()
                continue
            if idx == 7:
                return None

    def _select_character_category(self, categories_dict: dict, category_type: str) -> Optional[str]:
        """Generic character category selection for consonants or vowels."""
        self._banner(category_type.upper())
        categories = list(categories_dict.keys())  # Keep list for indexing
        idx = self._menu(categories, back_label="← Back")
        if idx is None:
            return None
        category = categories[idx - 1]
        return self._select_from_subcategory(category, categories_dict[category], category_type.rstrip('s'))

    def _select_consonant(self) -> Optional[str]:
        return self._select_character_category(self.CONSONANT_CATEGORIES, "consonants")

    def _select_vowel(self) -> Optional[str]:
        return self._select_character_category(self.VOWEL_CATEGORIES, "vowels")

    def _select_from_subcategory(
        self, main_category: str, subcategories: Dict[str, List[str]], sound_type: str
    ) -> Optional[str]:
        self._banner(main_category.upper(), subtitle=sound_type.capitalize())
        sub_names = list(subcategories.keys())  # Keep list for indexing
        # show each with preview of sounds on same line (truncate if too long)
        options = []
        for name in sub_names:
            preview = ' '.join(subcategories[name])
            if len(preview) > self.PREVIEW_TRUNCATE_LENGTH:  # truncate long lists
                preview = preview[:self.PREVIEW_TRUNCATE_LENGTH-3] + "..."
            options.append(f"{name}: {preview}")
        idx = self._menu(options, back_label="← Back")
        if idx is None:
            return None
        subcat = sub_names[idx - 1]
        sounds = subcategories[subcat]
        return self._select_specific_sound(sounds, subcat, sound_type)

    def _select_specific_sound(
        self, sounds: List[str], subcategory: str, sound_type: str
    ) -> Optional[str]:
        self._banner(subcategory.upper(), subtitle=f"{sound_type.capitalize()}s")
        options = sounds + ["Apply diacritics"]
        idx = self._menu(options, back_label="← Back")
        if idx is None:
            return None

        # Apply diacritics flow
        if idx == len(options):
            self._banner("APPLY DIACRITICS", subtitle=f"Base: choose a {sound_type}")
            base_idx = self._menu(sounds, back_label="← Back")
            if base_idx is None:
                return None
            base_sound = sounds[base_idx - 1]
            return self._diacritic_quick_panel(base_sound, sound_type)

        # Regular pick
        return sounds[idx - 1]

    def _diacritic_quick_panel(self, base: str, scope: str) -> str:
        """Quick diacritic selection panel."""
        print(f"\nApplying diacritics to: {base}")
        print("Available diacritics (enter numbers like '1 3 5', or press Enter for none):")

        # Filter diacritics by scope
        available = {
            name: spec for name, spec in COMMON_DIACRITICS.items()
            if spec["scope"] == "any" or spec["scope"] == scope
        }

        diacritic_list = list(available.keys())  # Keep list for indexing
        for i, name in enumerate(diacritic_list, 1):
            spec = available[name]
            glyph = spec["glyph"]
            print(f"{i}. {name}: {base}{glyph}")

        print()
        selected_indices = input("Choose diacritics › ").strip()

        if not selected_indices:
            return base

        try:
            # Validate that all parts are valid integers
            parts = selected_indices.split()
            indices = []
            for x in parts:
                if not x.isdigit():
                    print(f"Invalid input '{x}'. Please enter numbers only.")
                    return base
                indices.append(int(x) - 1)

            # Preserve user order and enforce mutual exclusion by group
            selected_order: List[str] = []
            invalid_numbers = []
            for i, idx in enumerate(indices):
                if 0 <= idx < len(diacritic_list):
                    name = diacritic_list[idx]
                    selected_order = _apply_mutex_list(selected_order, name, COMMON_DIACRITICS)
                else:
                    invalid_numbers.append(parts[i])

            if invalid_numbers:
                print(f"Invalid selection(s): {', '.join(invalid_numbers)}. Valid range: 1-{len(diacritic_list)}")
                if not selected_order:  # If no valid selections, return base
                    return base

            result = _compose(base, selected_order, COMMON_DIACRITICS)
            print(f"Result: {result}")
            return result

        except ValueError:
            print("Invalid input. Returning base character.")
            return base

    def _continue_prompt(self) -> bool:
        """Ask user if they want to continue."""
        while True:
            choice = self._normalize_user_input(input("\nAnalyze another character? (y/n): "))
            if choice in ["y", "yes"]:
                return True
            elif choice in ["n", "no"]:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")

    def _dictionary_menu(self) -> None:
        while True:
            self._banner("DICTIONARY MANAGEMENT")
            try:
                stats = self.dict_processor.get_stats()
                print(f"Current dataset: {stats.get('total_words', 0)} words")
                if stats.get('longest_word'):
                    print(f"Range: {stats.get('shortest_word','')} to {stats.get('longest_word','')}")
                print()
            except Exception as e:
                print(f"{self._format_error('reading dictionary', e)}\n")

            idx = self._menu([
                "Show all words",
                "Add word",
                "Remove words containing…",
                "Clear dictionary",
                "Dictionary statistics",
            ], back_label="← Back")

            if idx is None:
                break
            try:
                if idx == 1:
                    self.dict_processor.print_dictionary()
                elif idx == 2:
                    word = input("Enter IPA word to add: ").strip()
                    if word:
                        if self.dict_processor.add_word(word):
                            print(f"Added '{word}' to dictionary")
                        else:
                            print(f"Word '{word}' already exists")
                elif idx == 3:
                    substring = input("Remove words containing: ").strip()
                    if substring:
                        removed = self.dict_processor.remove_words_containing(substring)
                        print(f"Removed {removed} words containing '{substring}'")
                elif idx == 4:
                    confirm = self._normalize_user_input(input("Clear entire dictionary? (y/N): "))
                    if confirm in {"y", "yes"}:
                        self.dict_processor.clear_dictionary()
                        print("Dictionary cleared")
                elif idx == 5:
                    stats = self.dict_processor.get_stats()
                    print("\nDictionary Statistics:")
                    print(f"   Total words: {stats.get('total_words', 0)}")
                    print(f"   Unique letters: {stats.get('unique_letters', 0)}")
                    avg_len = stats.get('avg_word_length', 0.0)
                    print(f"   Average length: {avg_len:.2f}")
                    print(f"   Longest: {stats.get('longest_word','')}")
                    print(f"   Shortest: {stats.get('shortest_word','')}")
            except Exception as e:
                print(f"{self._format_error('in dictionary operation', e)}")

    def _batch_processing_menu(self) -> None:
        while True:
            self._banner("BATCH PROCESSING (targets.txt)")
            if targets_exist():
                try:
                    processor = TargetsProcessor(dataset_path=self.file_path, analyzer=self.analyzer)
                    summary = processor.get_targets_summary()
                    total    = summary.get("total_targets", 0)
                    ds_file  = summary.get("dataset_file", self.file_path)
                    ds_exist = bool(summary.get("dataset_exists", False))
                    print(f"Targets file: {self.DEFAULT_TARGETS_PATH} ({total} targets)")
                    print(f"Dataset: {ds_file} ({'exists' if ds_exist else 'missing'})")

                    seen, uniq = set(), []
                    for t in (summary.get("targets") or []):
                        if t not in seen:
                            seen.add(t)
                            uniq.append(t)
                    if uniq:
                        head = ", ".join(uniq[:5])
                        more = len(uniq) - 5
                        print(f"Targets: {head}" + (f" (+{more} more)" if more > 0 else ""))
                except Exception as e:
                    print(f"Error reading targets: {e}")
            else:
                print("No targets.txt file found")
            print()

            idx = self._menu([
                "Run batch analysis",
                "Create sample targets.txt",
                "View targets summary",
                "Cache management",
            ], back_label="← Back")

            if idx is None:
                break
            try:
                if idx == 1:
                    self._run_batch_analysis()
                elif idx == 2:
                    self._create_sample_targets()
                elif idx == 3:
                    self._show_targets_summary()
                elif idx == 4:
                    self._cache_management_menu()
            except Exception as e:
                print(f"Error: {e}")

    def _run_batch_analysis(self) -> None:
        """Run batch analysis on all targets."""
        if not targets_exist():
            print("No targets.txt file found. Create one first!")
            return

        def _normalize_format(fmt: str) -> str:
            m = {
                "txt": "txt", "text": "txt", "plain": "txt", "plaintext": "txt",
                "json": "json",
                "jsonl": "jsonl", "jsonlines": "jsonl", "ndjson": "jsonl",
                "csv": "csv",
            }
            return m.get(fmt, "")

        try:
            print("\nStarting batch analysis...")

            processor = TargetsProcessor(
                dataset_path=self.file_path,
                analyzer=self.analyzer
            )

            cache = get_cache()
            output_writer = AutoOutputWriter()

            targets = processor.load_targets()
            if not targets:
                print("No targets found in data/targets.txt.")
                return

            print(f"Processing {len(targets)} targets...")

            results = []
            for i, target in enumerate(targets, 1):
                print(f"  [{i}/{len(targets)}] Analyzing '{target}'...", end=" ")
                cached_result = cache.get(target, self.file_path, self.analyzer)
                if cached_result:
                    print("(cached)")
                    results.append(cached_result)
                else:
                    result = processor.analyze_target(target)
                    cache.put(target, self.file_path, self.analyzer, result)
                    print("(analyzed)")
                    results.append(result)

            fmt_in = input("\nOutput format (jsonl/json/csv/txt) [txt]: ").strip().lower()
            fmt = _normalize_format(fmt_in) or "txt"
            if fmt_in and not _normalize_format(fmt_in):
                print(f"Unknown format '{fmt_in}', falling back to 'txt'.")

            output_paths = output_writer.write_batch_results(results, fmt)

            # Summary
            print("\nBatch analysis complete!")
            print(f"Results written to: {list(output_paths.values())[0]}")
            print(f"Analyzed {len(results)} targets")
            # If your TargetResult has total_occurrences per target:
            try:
                total_occ = sum(getattr(r, "total_occurrences", 0) for r in results)
                print(f"Total occurrences: {total_occ}")
            except Exception:
                pass

            cache.save()

        except Exception as e:
            print(f"Batch analysis failed: {e}")

    def _create_sample_targets(self) -> None:
        """Create a sample targets.txt file."""
        try:
            create_sample_targets_file()
            print("Created sample targets.txt with common IPA targets.")
            print("Edit data/targets.txt to customize your target list.")
        except Exception as e:
            print(f"Failed to create targets file: {e}")

    def _show_targets_summary(self) -> None:
        """Show detailed targets summary."""
        if not targets_exist():
            print("No targets.txt file found")
            return

        try:
            processor = TargetsProcessor(
                dataset_path=self.file_path,
                analyzer=self.analyzer
            )
            summary = processor.get_targets_summary()

            print("\nTargets Summary:")
            print(f"   File: {summary.get('targets_file', 'data/targets.txt')}")
            print(f"   Dataset: {summary.get('dataset_file', self.file_path)}")
            print(f"   Total targets: {summary.get('total_targets', 0)}")
            print(f"   Unique targets: {summary.get('unique_targets', 0)}")
            print(f"   Targets exist: {summary.get('targets_exist', False)}")
            print(f"   Dataset exists: {summary.get('dataset_exists', False)}")

            targets_list = list(summary.get('targets') or [])
            if targets_list:
                print("\nTarget list:")
                # Show in stable order, but don't flood the screen
                preview_cap = 50
                for t in targets_list[:preview_cap]:
                    print(f"   • {t}")
                if len(targets_list) > preview_cap:
                    print(f"   … (+{len(targets_list) - preview_cap} more)")

        except Exception as e:
            print(f"Error reading targets: {e}")

    def _cache_management_menu(self) -> None:
        while True:
            self._banner("CACHE MANAGEMENT")
            try:
                stats = get_cache_stats()
                print(f"Cache entries:  {stats.get('total_entries', 0)}")
                print(f"Unique targets: {stats.get('unique_targets', 0)}")
                print(f"Cache dir:      {stats.get('cache_dir', '')}")
                if stats.get('total_entries', 0) > 0:
                    print(f"Latest:         {stats.get('newest_entry', '')}")
            except Exception as e:
                print(f"Error reading cache: {e}")
            print()

            idx = self._menu([
                "View cache statistics",
                "Clear entire cache",
                "Clear cache for current dataset",
            ], back_label="← Back")

            if idx is None:
                break
            try:
                if idx == 1:
                    stats = get_cache_stats()
                    print("\nDetailed Cache Statistics:")
                    for key, value in stats.items():
                        if key == "targets" and isinstance(value, list):
                            head = ", ".join(value[:10])
                            more = len(value) - 10
                            print(f"   {key}: {head}" + (f" (+{more} more)" if more > 0 else ""))
                        else:
                            print(f"   {key}: {value}")
                elif idx == 2:
                    confirm = input("Clear entire cache? (y/N): ").strip().lower()
                    if confirm in {"y", "yes"}:
                        clear_cache()
                        print("Cache cleared")
                elif idx == 3:
                    cache = get_cache()
                    removed = cache.clear_dataset(self.file_path)
                    print(f"Removed {removed} entries for current dataset")
            except Exception as e:
                print(f"Error: {e}")

# ========================= COMMAND LINE INTERFACE =========================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Phonenv - Interactive Phonetic Environment Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  phonenv                           # Interactive mode
  phonenv --batch                   # Batch process targets.txt
  phonenv --create-targets          # Create sample targets.txt
  phonenv --targets path/targets.txt --output results.txt
        """
    )

    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="Run batch processing on targets.txt file"
    )

    parser.add_argument(
        "--targets", "-t",
        metavar="PATH",
        default="data/targets.txt",
        help="Path to targets file (default: data/targets.txt)"
    )

    parser.add_argument(
        "--dataset", "-d",
        metavar="PATH",
        default="data/dataset.txt",
        help="Path to dataset file (default: data/dataset.txt)"
    )

    parser.add_argument(
        "--output", "-o",
        metavar="PATH",
        help="Output file path (auto-generated if not specified)"
    )

    parser.add_argument(
        "--format", "-f",
        choices=["jsonl", "json", "csv", "txt"],
        default="txt",
        help="Output format for batch processing (default: txt)"
    )

    parser.add_argument(
        "--create-targets",
        action="store_true",
        help="Create sample targets.txt file and exit"
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear analysis cache and exit"
    )

    parser.add_argument(
        "--cache-stats",
        action="store_true",
        help="Show cache statistics and exit"
    )

    parser.add_argument(
        "--mode",
        choices=["narrow", "broad"],
        default="broad",
        help="Transcription mode for batch analysis (default: broad)"
    )

    args = parser.parse_args()

    try:
        # Handle utility flags
        if args.create_targets:
            create_sample_targets_file(args.targets)
            print(f"Created sample targets file: {args.targets}")
            return

        if args.clear_cache:
            clear_cache()
            print("Cache cleared")
            return

        if args.cache_stats:
            stats = get_cache_stats()
            print("Cache Statistics:")
            for key, value in stats.items():
                if key == 'targets' and isinstance(value, list):
                    print(f"   {key}: {', '.join(value[:10])}" +
                          (f" (+{len(value)-10} more)" if len(value) > 10 else ""))
                else:
                    print(f"   {key}: {value}")
            return

        # Handle batch processing
        if args.batch:
            run_batch_cli(args)
            return

        # Default: interactive mode
        cli = InteractivePhonenvCLI(args.dataset)
        cli.run()

    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


def run_batch_cli(args):
    """Run batch processing from command line."""
    if not targets_exist(args.targets):
        print(f"Targets file not found: {args.targets}")
        print("Use --create-targets to create a sample file")
        sys.exit(1)

    try:
        print("Starting batch analysis...")
        print(f"Targets: {args.targets}")
        print(f"Dataset: {args.dataset}")
        print(f"Mode: {args.mode}")

        # Wire up analyzer with the chosen transcription mode
        from analysis import get_config_for_transcription_mode, IPAProcessorV2

        analyzer = PhoneticAnalyzer(use_ipa_processing=True, transcription_mode=args.mode)
        analyzer.ipa_processor_v2 = IPAProcessorV2(get_config_for_transcription_mode(args.mode))

        processor = TargetsProcessor(
            dataset_path=args.dataset,
            targets_path=args.targets,
            analyzer=analyzer,
        )

        cache = get_cache()
        output_writer = AutoOutputWriter()

        targets = processor.load_targets()
        print(f"Processing {len(targets)} targets...")

        results = []
        for i, target in enumerate(targets, 1):
            print(f"  [{i}/{len(targets)}] Analyzing '{target}'...", end=" ")

            cached_result = cache.get(target, args.dataset, analyzer)
            if cached_result:
                print("(cached)")
                results.append(cached_result)
            else:
                result = processor.analyze_target(target)
                cache.put(target, args.dataset, analyzer, result)
                print("(analyzed)")
                results.append(result)

        if args.output:
            output_paths = output_writer.write_batch_results(
                results, args.format, args.output
            )
        else:
            output_paths = output_writer.write_batch_results(results, args.format)

        print("\nBatch analysis complete!")
        print(f"Results written to: {list(output_paths.values())[0]}")
        print(f"Analyzed {len(results)} targets")
        print(f"Total occurrences: {sum(r.total_occurrences for r in results)}")

        cache.save()

    except Exception as e:
        print(f"Batch analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()