"""Command-line interface for phonetic environment analysis.

This module provides both interactive and command-line interfaces for
phonetic environment analysis, including batch processing capabilities.
"""

from __future__ import annotations

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

    # IPA consonant categories with common symbols
    CONSONANT_CATEGORIES = {
        "Stops/Plosives": {
            "Bilabial": ["p", "b"],
            "Dental/Alveolar": ["t", "d", "t̪", "d̪"],
            "Retroflex": ["ɖ", "ʈ"],
            "Palatal": ["c", "ɟ"],
            "Velar": ["k", "ɡ"],
            "Uvular": ["q", "ɢ"],
            "Glottal": ["ʔ"],
        },
        "Fricatives": {
            # FIX: use IPA ɸ (U+0278), not Greek φ
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
        "Affricates": {
            "Bilabial": ["p͡ɸ", "b͡β"],
            "Labiodental": ["p͡f", "b͡v"],
            "Alveolar": ["t͡s", "d͡z"],
            "Postalveolar": ["t͡ʃ", "d͡ʒ"],
            "Retroflex": ["ʈ͡ʂ", "ɖ͡ʐ"],
            # RENAME: Palatoalveolar -> Alveolo-palatal (for t͡ɕ, d͡ʑ)
            "Alveolo-palatal": ["t͡ɕ", "d͡ʑ"],
            "Palatal": ["c͡ç", "ɟ͡ʝ"],
            "Velar": ["k͡x", "ɡ͡ɣ"],
            "Uvular": ["q͡χ", "ɢ͡ʁ"],
        },
        "Nasals": {
            # Keep bases; narrow variants can be added via diacritic panel if desired.
            "Bilabial": ["m"],
            "Dental/Alveolar": ["n", "n̪"],
            "Retroflex": ["ɳ"],
            "Palatal": ["ɲ"],
            "Velar": ["ŋ"],
            "Uvular": ["ɴ"],
        },
        "Liquids": {
            # Keep base laterals only (diacritic variants removed for cleaner menu)
            "Lateral": ["l", "ɭ", "ʎ", "ʟ"],
            "Rhotic": ["r", "ɾ", "ɹ", "ɻ", "ʀ", "ʁ", "ɽ"],
        },
        "Glides/Approximants": {
            "Palatal": ["j", "ɥ"],
            "Velar": ["w", "ɰ"],
            # Remove duplicate ɻ (already under Liquids→Rhotic) and narrow ɹ-variants
            "Other": ["ʋ"],
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

    def __init__(self, file_path: str = "data/dataset.txt"):
        """Initialize the interactive CLI."""
        self.file_path = file_path
        self.transcription_mode = "broad"
        self.analyzer: Optional[PhoneticAnalyzer] = None
        self.dict_processor = DictionaryProcessor(file_path)
        self._create_analyzer()

    def _create_analyzer(self):
        """Create analyzer based on current transcription mode."""
        from analysis import get_config_for_transcription_mode, IPAProcessorV2

        config = get_config_for_transcription_mode(self.transcription_mode)

        self.analyzer = PhoneticAnalyzer(
            use_ipa_processing=True,
            use_professional_ipa=True,
        )
        if getattr(self.analyzer, "ipa_processor_v2", None) is not None:
            self.analyzer.ipa_processor_v2 = IPAProcessorV2(config)

    def run(self) -> None:
        """Run the interactive CLI."""
        print("Phonenv - Interactive Phonetic Environment Analysis")
        print("=" * 55)
        print()

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
                    print(
                        f"\nAnalyzing phonetic environments for '{character}' ({self.transcription_mode} transcription)..."
                    )
                    print()
                    self.analyzer.print_analysis(character, self.file_path, show_unicode_info=False)
                else:
                    print("\nError: Analyzer could not be initialized. Please check the configuration.")

                print("\n" + "-" * 55)
                if not self._continue_prompt():
                    print("\nGoodbye!")
                    break

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")
                print("Please try again.\n")

    def _set_transcription_mode(self):
        """Set the transcription mode (broad vs narrow)."""
        print("Select transcription analysis mode:")
        print()
        print("1. Narrow transcription")
        print("   - Distinguishes diacritic variants (p ≠ pʰ)")
        print("   - Focus on surface phonetic detail")
        print()
        print("2. Broad transcription")
        print("   - Treats diacritic variants as the same (p = pʰ)")
        print("   - Focus on underlying phonological patterns")
        print()

        while True:
            choice = input("Select mode (1-2): ").strip()
            if choice == "1":
                self.transcription_mode = "narrow"
                break
            elif choice == "2":
                self.transcription_mode = "broad"
                break
            else:
                print("Please enter 1 for narrow or 2 for broad.")

        print(f"\nMode set to: {self.transcription_mode} transcription")
        self._create_analyzer()

    def _get_character_choice(self) -> Optional[str]:
        """Get character choice from user via interactive menus."""
        while True:
            print("Select character type:")
            print("1. Consonants")
            print("2. Vowels")
            print("3. Change transcription mode")
            print("4. Advanced: paste IPA segment")
            print("5. Batch processing (targets.txt)")
            print("6. Dictionary management")
            print("7. Exit")
            print()

            choice = input("Enter your choice (1-7): ").strip()
            if choice == "1":
                return self._select_consonant()
            elif choice == "2":
                return self._select_vowel()
            elif choice == "3":
                self._set_transcription_mode()
                # loop continues and redraws the menu
            elif choice == "4":
                pasted = input("Paste IPA segment (NFC recommended): ").strip()
                return ud.normalize("NFC", pasted) if pasted else None
            elif choice == "5":
                self._batch_processing_menu()  # returns here; loop redraws
            elif choice == "6":
                self._dictionary_menu()        # returns here; loop redraws
            elif choice == "7":
                return None
            else:
                print("Invalid choice. Please enter 1–7.\n")

    def _select_consonant(self) -> Optional[str]:
        """Interactive consonant selection."""
        print("\nConsonant Categories:")
        categories = list(self.CONSONANT_CATEGORIES.keys())

        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        print(f"{len(categories) + 1}. ← Previous menu")
        print()

        while True:
            try:
                choice = input(f"Select category (1-{len(categories) + 1}): ").strip()
                choice_num = int(choice)

                if choice_num == len(categories) + 1:
                    return self._get_character_choice()
                elif 1 <= choice_num <= len(categories):
                    category = categories[choice_num - 1]
                    return self._select_from_subcategory(category, self.CONSONANT_CATEGORIES[category], "consonant")
                else:
                    print(f"Please enter a number between 1 and {len(categories) + 1}.")
            except ValueError:
                print("Please enter a valid number.")

    def _select_vowel(self) -> Optional[str]:
        """Interactive vowel selection."""
        print("\nVowel Categories:")
        categories = list(self.VOWEL_CATEGORIES.keys())

        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        print(f"{len(categories) + 1}. ← Previous menu")
        print()

        while True:
            try:
                choice = input(f"Select category (1-{len(categories) + 1}): ").strip()
                choice_num = int(choice)

                if choice_num == len(categories) + 1:
                    return self._get_character_choice()
                elif 1 <= choice_num <= len(categories):
                    category = categories[choice_num - 1]
                    return self._select_from_subcategory(category, self.VOWEL_CATEGORIES[category], "vowel")
                else:
                    print(f"Please enter a number between 1 and {len(categories) + 1}.")
            except ValueError:
                print("Please enter a valid number.")

    def _select_from_subcategory(
        self, main_category: str, subcategories: Dict[str, List[str]], sound_type: str
    ) -> Optional[str]:
        """Select from subcategory."""
        print(f"\n{main_category}:")
        subcategory_names = list(subcategories.keys())

        for i, subcat in enumerate(subcategory_names, 1):
            sounds = subcategories[subcat]
            print(f"{i}. {subcat}: {' '.join(sounds)}")
        print(f"{len(subcategory_names) + 1}. ← Previous menu")
        print()

        while True:
            try:
                choice = input(f"Select subcategory (1-{len(subcategory_names) + 1}): ").strip()
                choice_num = int(choice)

                if choice_num == len(subcategory_names) + 1:
                    if sound_type == "consonant":
                        return self._select_consonant()
                    else:
                        return self._select_vowel()
                elif 1 <= choice_num <= len(subcategory_names):
                    subcat = subcategory_names[choice_num - 1]
                    sounds = subcategories[subcat]
                    return self._select_specific_sound(sounds, subcat, sound_type)
                else:
                    print(f"Please enter a number between 1 and {len(subcategory_names) + 1}.")
            except ValueError:
                print("Please enter a valid number.")

    def _select_specific_sound(
        self, sounds: List[str], subcategory: str, sound_type: str
    ) -> Optional[str]:
        """Select specific sound from list."""
        print(f"\n{subcategory} {sound_type}s:")

        for i, sound in enumerate(sounds, 1):
            print(f"{i}. {sound}")
        print(f"{len(sounds) + 1}. Apply diacritics")
        print(f"{len(sounds) + 2}. ← Previous menu")
        print()

        while True:
            try:
                choice = input(f"Select sound (1-{len(sounds) + 2}): ").strip()
                choice_num = int(choice)

                if choice_num == len(sounds) + 2:
                    return self._select_from_subcategory(
                        # Need to find the main category - this is a limitation of the current structure
                        subcategory, {subcategory: sounds}, sound_type
                    )
                elif choice_num == len(sounds) + 1:
                    # Choose base sound first
                    base_choice = input(f"Choose base sound (1-{len(sounds)}): ").strip()
                    try:
                        base_idx = int(base_choice) - 1
                        if 0 <= base_idx < len(sounds):
                            base_sound = sounds[base_idx]
                            return self._diacritic_quick_panel(base_sound, sound_type)
                        else:
                            print(f"Please enter a number between 1 and {len(sounds)}.")
                    except ValueError:
                        print("Please enter a valid number.")
                elif 1 <= choice_num <= len(sounds):
                    return sounds[choice_num - 1]
                else:
                    print(f"Please enter a number between 1 and {len(sounds) + 2}.")
            except ValueError:
                print("Please enter a valid number.")

    def _diacritic_quick_panel(self, base: str, scope: str) -> str:
        """Quick diacritic selection panel."""
        print(f"\nApplying diacritics to: {base}")
        print("Available diacritics (enter numbers separated by spaces, or press Enter when done):")

        # Filter diacritics by scope
        available = {
            name: spec for name, spec in COMMON_DIACRITICS.items()
            if spec["scope"] == "any" or spec["scope"] == scope
        }

        diacritic_list = list(available.keys())
        for i, name in enumerate(diacritic_list, 1):
            spec = available[name]
            glyph = spec["glyph"]
            print(f"{i}. {name}: {base}{glyph}")

        print()
        selected_indices = input("Select diacritic numbers (space-separated): ").strip()

        if not selected_indices:
            return base

        try:
            indices = [int(x) - 1 for x in selected_indices.split()]

            # Preserve user order and enforce mutual exclusion by group
            selected_order: List[str] = []
            for idx in indices:
                if 0 <= idx < len(diacritic_list):
                    name = diacritic_list[idx]
                    selected_order = _apply_mutex_list(selected_order, name, COMMON_DIACRITICS)

            result = _compose(base, selected_order, COMMON_DIACRITICS)
            print(f"Result: {result}")
            return result

        except ValueError:
            print("Invalid input. Returning base character.")
            return base

    def _continue_prompt(self) -> bool:
        """Ask user if they want to continue."""
        while True:
            choice = input("\nAnalyze another character? (y/n): ").strip().lower()
            if choice in ["y", "yes"]:
                return True
            elif choice in ["n", "no"]:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")

    def _dictionary_menu(self) -> None:
        """Dictionary management menu."""
        while True:
            print("\n" + "="*50)
            print("DICTIONARY MANAGEMENT")
            print("="*50)

            try:
                stats = self.dict_processor.get_stats()
                print(f"Current dataset: {stats['total_words']} words")
                if stats['longest_word']:
                    print(f"Range: {stats['shortest_word']} to {stats['longest_word']}")
                print()
            except Exception as e:
                print(f"Error reading dictionary: {e}\n")

            print("1. Show all words")
            print("2. Add word")
            print("3. Remove words containing...")
            print("4. Clear dictionary")
            print("5. Dictionary statistics")
            print("6. ← Back to analysis")
            print()

            choice = input("Choose option (1-6): ").strip()

            try:
                if choice == "1":
                    self.dict_processor.print_dictionary()
                elif choice == "2":
                    word = input("Enter IPA word to add: ").strip()
                    if word:
                        if self.dict_processor.add_word(word):
                            print(f"Added '{word}' to dictionary")
                        else:
                            print(f"Word '{word}' already exists")
                elif choice == "3":
                    substring = input("Remove words containing: ").strip()
                    if substring:
                        removed = self.dict_processor.remove_words_containing(substring)
                        print(f"Removed {removed} words containing '{substring}'")
                elif choice == "4":
                    confirm = input("Clear entire dictionary? (y/N): ").strip().lower()
                    if confirm in ["y", "yes"]:
                        self.dict_processor.clear_dictionary()
                        print("Dictionary cleared")
                elif choice == "5":
                    stats = self.dict_processor.get_stats()
                    print(f"\nDictionary Statistics:")
                    print(f"   Total words: {stats['total_words']}")
                    print(f"   Unique letters: {stats['unique_letters']}")
                    print(f"   Average length: {stats['avg_word_length']:.2f}")
                    print(f"   Longest: {stats['longest_word']}")
                    print(f"   Shortest: {stats['shortest_word']}")
                elif choice == "6":
                    break
                else:
                    print("Please enter 1-6")
            except Exception as e:
                print(f"Error: {e}")

    def _batch_processing_menu(self) -> None:
        """Batch processing menu for targets.txt."""
        while True:
            print("\n" + "="*50)
            print("BATCH PROCESSING (targets.txt)")
            print("="*50)

            if targets_exist():
                try:
                    processor = TargetsProcessor(
                        dataset_path=self.file_path,
                        analyzer=self.analyzer
                    )
                    summary = processor.get_targets_summary()

                    # Safer field access with defaults
                    total = summary.get("total_targets", 0)
                    ds_file = summary.get("dataset_file", self.file_path)
                    ds_exists = bool(summary.get("dataset_exists", False))

                    print(f"Targets file: data/targets.txt ({total} targets)")
                    print(f"Dataset: {ds_file} ({'exists' if ds_exists else 'missing'})")

                    # Preview up to 5 unique targets in stable order
                    targets_list = summary.get("targets") or []
                    seen = set()
                    uniq_list = []
                    for t in targets_list:
                        if t not in seen:
                            seen.add(t)
                            uniq_list.append(t)

                    if uniq_list:
                        head = ", ".join(uniq_list[:5])
                        more = len(uniq_list) - 5
                        print(f"Targets: {head}" + (f" (+{more} more)" if more > 0 else ""))

                except Exception as e:
                    print(f"Error reading targets: {e}")
            else:
                print("No targets.txt file found")

            print()
            print("1. Run batch analysis")
            print("2. Create sample targets.txt")
            print("3. View targets summary")
            print("4. Cache management")
            print("5. ← Back to main menu")
            print()

            choice = input("Choose option (1-5): ").strip()

            try:
                if choice == "1":
                    self._run_batch_analysis()
                elif choice == "2":
                    self._create_sample_targets()
                elif choice == "3":
                    self._show_targets_summary()  # <-- apply the same safe preview logic there too
                elif choice == "4":
                    self._cache_management_menu()
                elif choice == "5":
                    break
                else:
                    print("Please enter 1-5")
            except Exception as e:
                print(f"Error: {e}")

    def _run_batch_analysis(self) -> None:
        """Run batch analysis on all targets."""
        if not targets_exist():
            print("No targets.txt file found. Create one first!")
            return

        try:
            print("\nStarting batch analysis...")

            processor = TargetsProcessor(
                dataset_path=self.file_path,
                analyzer=self.analyzer
            )

            cache = get_cache()
            output_writer = AutoOutputWriter()

            results = []
            targets = processor.load_targets()

            print(f"Processing {len(targets)} targets...")

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

            output_format = input("\nOutput format (jsonl/json/csv/txt) [text]: ").strip().lower()
            if not output_format:
                output_format = "txt"

            output_paths = output_writer.write_batch_results(results, output_format)

            print(f"\nBatch analysis complete!")
            print(f"Results written to: {list(output_paths.values())[0]}")
            print(f"Analyzed {len(results)} targets")
            print(f"Total occurrences: {sum(r.total_occurrences for r in results)}")

            cache.save()

        except Exception as e:
            print(f"Batch analysis failed: {e}")

    def _create_sample_targets(self) -> None:
        """Create a sample targets.txt file."""
        try:
            create_sample_targets_file()
            print("Created sample targets.txt file with common IPA targets")
            print("Edit data/targets.txt to customize your target list")
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

            print(f"\nTargets Summary:")
            print(f"   File: {summary['targets_file']}")
            print(f"   Dataset: {summary['dataset_file']}")
            print(f"   Total targets: {summary['total_targets']}")
            print(f"   Unique targets: {summary['unique_targets']}")
            print(f"   Targets exist: {summary['targets_exist']}")
            print(f"   Dataset exists: {summary['dataset_exists']}")

            if summary.get('targets'):
                print(f"\nTarget list:")
                for target in summary['targets']:
                    print(f"   • {target}")

        except Exception as e:
            print(f"Error reading targets: {e}")

    def _cache_management_menu(self) -> None:
        """Cache management submenu."""
        while True:
            print("\n" + "-"*40)
            print("CACHE MANAGEMENT")
            print("-"*40)

            try:
                stats = get_cache_stats()
                print(f"Cache entries: {stats['total_entries']}")
                print(f"Unique targets: {stats['unique_targets']}")
                print(f"Cache dir: {stats['cache_dir']}")
                if stats['total_entries'] > 0:
                    print(f"Latest: {stats['newest_entry']}")
            except Exception as e:
                print(f"Error reading cache: {e}")

            print()
            print("1. View cache statistics")
            print("2. Clear entire cache")
            print("3. Clear cache for current dataset")
            print("4. ← Back")
            print()

            choice = input("Choose option (1-4): ").strip()

            try:
                if choice == "1":
                    stats = get_cache_stats()
                    print(f"\nDetailed Cache Statistics:")
                    for key, value in stats.items():
                        if key == 'targets' and isinstance(value, list):
                            print(f"   {key}: {', '.join(value[:10])}" +
                                  (f" (+{len(value)-10} more)" if len(value) > 10 else ""))
                        else:
                            print(f"   {key}: {value}")
                elif choice == "2":
                    confirm = input("Clear entire cache? (y/N): ").strip().lower()
                    if confirm in ["y", "yes"]:
                        clear_cache()
                        print("Cache cleared")
                elif choice == "3":
                    cache = get_cache()
                    removed = cache.clear_dataset(self.file_path)
                    print(f"Removed {removed} entries for current dataset")
                elif choice == "4":
                    break
                else:
                    print("Please enter 1-4")
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

        analyzer = PhoneticAnalyzer(use_ipa_processing=True)
        analyzer.ipa_processor_v2 = IPAProcessorV2(
            get_config_for_transcription_mode(args.mode)
        )

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