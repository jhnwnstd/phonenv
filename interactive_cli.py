#!/usr/bin/env python3
"""Interactive CLI interface for phonetic environment analysis (with diacritic panel)."""

from __future__ import annotations

import sys
import unicodedata as ud
from typing import Dict, List, Optional, Set
from environment_analyzer import PhoneticAnalyzer


# ----------------------- Common diacritic toggles -----------------------
# Small, high-coverage set; no combinatorial explosion in the UI.
COMMON_DIACRITICS: Dict[str, Dict[str, str | bool | None]] = {
    # Length (spacing, mutually exclusive)
    "long":      {"glyph": "ː",   "kind": "spacing",   "scope": "any",       "group": "length"},
    "half-long": {"glyph": "ˑ",   "kind": "spacing",   "scope": "any",       "group": "length"},

    # Voicing (combining, mutually exclusive)
    "voiceless": {"glyph": "\u0325", "kind": "combining", "scope": "any",    "group": "voice"},  # ◌̥
    "voiced":    {"glyph": "\u032C", "kind": "combining", "scope": "any",    "group": "voice"},  # ◌̬

    # Syllabicity (mutually exclusive by scope convention)
    "syllabic":  {"glyph": "\u0329", "kind": "combining", "scope": "consonant", "group": "syll"},  # ◌̩
    "non-syl":   {"glyph": "\u032F", "kind": "combining", "scope": "vowel",     "group": "syl"},   # ◌̯

    # Common vowel/consonant effects
    "nasal":     {"glyph": "\u0303", "kind": "combining", "scope": "vowel",     "group": None},    # ◌̃
    "no-release":{"glyph": "\u031A", "kind": "combining", "scope": "consonant", "group": None},    # ◌̚

    # Secondary articulations (spacing)
    "aspirated": {"glyph": "ʰ",   "kind": "spacing",   "scope": "consonant", "group": None},
    "palatal":   {"glyph": "ʲ",   "kind": "spacing",   "scope": "consonant", "group": None},
    "labial":    {"glyph": "ʷ",   "kind": "spacing",   "scope": "consonant", "group": None},
    "velarized": {"glyph": "ˠ",   "kind": "spacing",   "scope": "consonant", "group": None},
    "pharyng":   {"glyph": "ˤ",   "kind": "spacing",   "scope": "consonant", "group": None},

    # Place tweak (combining)
    "dental":    {"glyph": "\u032A", "kind": "combining", "scope": "consonant", "group": None},    # ◌̪
}


def _compose(base: str, toggle_names: List[str], catalog: Dict[str, Dict[str, str | bool | None]]) -> str:
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


def _apply_mutex(toggled: Set[str], newly: str, catalog: Dict[str, Dict[str, str | bool | None]]) -> Set[str]:
    """Ensure at most one member in each mutual-exclusion group."""
    group = catalog[newly].get("group")
    if not group:
        return toggled
    return {n for n in toggled if catalog[n].get("group") != group}


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
            "Bilabial": ["φ", "β"],
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
            "Palatoalveolar": ["t͡ɕ", "d͡ʑ"],
            "Palatal": ["c͡ç", "ɟ͡ʝ"],
            "Velar": ["k͡x", "ɡ͡ɣ"],
            "Uvular": ["q͡χ", "ɢ͡ʁ"]
        },
        "Nasals": {
            "Bilabial": ["m", "m̥"],
            "Dental/Alveolar": ["n", "n̥", "n̪"],
            "Retroflex": ["ɳ", "ɳ̊"],
            "Palatal": ["ɲ", "ɲ̊"],
            "Velar": ["ŋ", "ŋ̊"],
            "Uvular": ["ɴ", "ɴ̥"],
        },
        "Liquids": {
            "Lateral": ["l", "ɭ", "ʎ", "ʟ", "l̥", "ɭ̊", "ʎ̝̊", "ʟ̝̊"],
            "Rhotic": ["r", "ɾ", "ɹ", "ɻ", "ʀ", "ʁ", "ɽ"],
        },
        "Glides/Approximants": {
            "Palatal": ["j", "ɥ"],
            "Velar": ["w", "ɰ"],
            "Other": ["ɹ̠", "ɻ", "ʋ", "ɹ̝", "ɹ̝̊"],
        },
    }

    # IPA vowel categories
    VOWEL_CATEGORIES = {
        "Close": {
            "Front": ["i", "y"],
            "Central": ["ɨ", "ʉ"],
            "Back vowels": ["ɯ", "u"],
        },
        "Near-Close": {
            "Front": ["ɪ", "ʏ"],
            "Back vowels": ["ʊ"],
        },
        "Close-Mid": {
            "Front": ["e", "ø"],
            "Central": ["ɘ", "ɵ"],
            "Back vowels": ["ɤ", "o"],
        },
        "Mid": {
            "Central": ["ə", "ɚ"],
        },
        "Open-Mid": {
            "Front": ["ɛ", "œ"],
            "Central": ["ɜ", "ɞ", "ʌ"],
            "Back vowels": ["ɔ"],
        },
        "Near-Open": {
            "Front": ["æ"],
            "Central": ["ɐ"],
        },
        "Open": {
            "Front": ["a", "ɶ"],
            "Back vowels": ["ɑ", "ɒ"],
        },
        "Diphthongs": {
            "Closing": ["aɪ", "eɪ", "ɔɪ", "aʊ", "oʊ"],
            "Opening": ["ɪə", "eə", "ʊə"],
            "Centering": ["aɪə", "aʊə"],
        },
        "Triphthongs": {
            "Common": ["aɪə", "aʊə", "eɪə", "oʊə"],
        },
    }

    def __init__(self, file_path: str = "data/input.txt"):
        """Initialize the interactive CLI.

        Args:
            file_path: Default file path for analysis
        """
        self.file_path = file_path
        self.transcription_mode = "broad"  # default to broad
        self.analyzer: Optional[PhoneticAnalyzer] = None  # Will be created based on mode
        self._create_analyzer()  # Ensure analyzer is initialized

    def _create_analyzer(self):
        """Create analyzer based on current transcription mode."""
        from ipa_processor_v2 import get_config_for_transcription_mode, IPAProcessorV2

        config = get_config_for_transcription_mode(self.transcription_mode)

        self.analyzer = PhoneticAnalyzer(
            use_ipa_processing=True,
            use_professional_ipa=True,
        )
        # Update the analyzer's IPA processor config
        if getattr(self.analyzer, "ipa_processor_v2", None) is not None:
            self.analyzer.ipa_processor_v2 = IPAProcessorV2(config)

    def run(self) -> None:
        """Run the interactive CLI."""
        print("Phonenv - Interactive Phonetic Environment Analysis")
        print("=" * 55)
        print()

        # Set initial transcription mode
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
        print()
        self._create_analyzer()

    def _get_character_choice(self) -> Optional[str]:
        """Get character choice from user via interactive menus."""
        print("Select character type:")
        print("1. Consonants")
        print("2. Vowels")
        print("3. Change transcription mode")
        print("4. Advanced: paste full IPA segment")
        print("5. Exit")
        print()

        while True:
            choice = input("Enter your choice (1-5): ").strip()

            if choice == "1":
                return self._select_consonant()
            elif choice == "2":
                return self._select_vowel()
            elif choice == "3":
                self._set_transcription_mode()
                continue  # Stay in this menu after mode change
            elif choice == "4":
                pasted = input("Paste full IPA segment (NFC recommended): ").strip()
                return ud.normalize("NFC", pasted) if pasted else None
            elif choice == "5":
                return None
            else:
                print("Invalid choice. Please enter 1, 2, 3, 4, or 5.")

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
        """Select from subcategories and then specific sounds."""
        print(f"\n{main_category} {sound_type.title()}s:")
        subcat_names = list(subcategories.keys())

        for i, subcat in enumerate(subcat_names, 1):
            sounds_preview = ", ".join(subcategories[subcat][:3])
            if len(subcategories[subcat]) > 3:
                sounds_preview += "..."
            print(f"{i}. {subcat} ({sounds_preview})")
        print(f"{len(subcat_names) + 1}. ← Previous menu")
        print()

        while True:
            try:
                choice = input(f"Select subcategory (1-{len(subcat_names) + 1}): ").strip()
                choice_num = int(choice)

                if choice_num == len(subcat_names) + 1:
                    if sound_type == "consonant":
                        return self._select_consonant()
                    else:
                        return self._select_vowel()
                elif 1 <= choice_num <= len(subcat_names):
                    subcat = subcat_names[choice_num - 1]
                    return self._select_specific_sound(main_category, subcat, subcategories[subcat], sound_type)
                else:
                    print(f"Please enter a number between 1 and {len(subcat_names) + 1}.")
            except ValueError:
                print("Please enter a valid number.")

    def _select_specific_sound(
        self, main_category: str, subcategory: str, sounds: List[str], sound_type: str
    ) -> Optional[str]:
        """Select specific IPA sound from list; then open the common-diacritics panel."""
        print(f"\n{main_category} -> {subcategory}:")
        for i, sound in enumerate(sounds, 1):
            print(f"{i}. {sound}")
        print(f"{len(sounds) + 1}. ← Previous menu")
        print()

        while True:
            try:
                choice = input(f"Select {sound_type} (1-{len(sounds) + 1}): ").strip()
                choice_num = int(choice)

                if choice_num == len(sounds) + 1:
                    if sound_type == "consonant":
                        return self._select_from_subcategory(
                            main_category, self.CONSONANT_CATEGORIES[main_category], sound_type
                        )
                    else:
                        return self._select_from_subcategory(
                            main_category, self.VOWEL_CATEGORIES[main_category], sound_type
                        )
                elif 1 <= choice_num <= len(sounds):
                    base = sounds[choice_num - 1]
                    scope = "vowel" if sound_type == "vowel" else "consonant"
                    # Offer the compact diacritic panel. Users can also paste a full segment here.
                    segment = self._diacritic_quick_panel(base, scope)
                    return segment
                else:
                    print(f"Please enter a number between 1 and {len(sounds) + 1}.")
            except ValueError:
                print("Please enter a valid number.")

    # ----------------------- Diacritic quick panel -----------------------

    def _diacritic_quick_panel(self, base: str, scope: str) -> str:
        """
        Offer a small, high-coverage set of diacritic toggles.
        scope: 'consonant' | 'vowel' | 'any' (heuristic based on menu path).
        Returns NFC-composed segment (may be just base).
        """
        catalog = COMMON_DIACRITICS
        applicable = [k for k, v in catalog.items() if v["scope"] in (scope, "any")]
        toggled: Set[str] = set()

        while True:
            preview = _compose(base, sorted(toggled), catalog)
            print("\nBase:", base)
            print("Selected diacritics:", ", ".join(sorted(toggled)) or "(none)")
            print("Preview:", preview)
            print("\nToggle common diacritics:")
            for i, name in enumerate(applicable, 1):
                mark = "✓" if name in toggled else " "
                glyph = catalog[name]["glyph"]  # type: ignore[index]
                print(f"  {i:>2}. [{mark}] {name:10s} {glyph}")
            adv = len(applicable) + 1
            clr = adv + 1
            cont = clr + 1
            back = cont + 1
            print(f"  {adv:>2}. Advanced… (paste arbitrary IPA segment)")
            print(f"  {clr:>2}. Clear all")
            print(f"  {cont:>2}. Continue")
            print(f"  {back:>2}. Back")

            choice = input(f"Choice (1-{back}): ").strip()
            if not choice.isdigit():
                print("Enter a number.")
                continue
            num = int(choice)

            if 1 <= num <= len(applicable):
                name = applicable[num - 1]
                if name in toggled:
                    toggled.remove(name)
                else:
                    toggled = _apply_mutex(toggled, name, catalog)
                    toggled.add(name)
                continue

            if num == adv:
                pasted = input("Paste full IPA segment (NFC recommended): ").strip()
                if pasted:
                    return ud.normalize("NFC", pasted)
                continue
            if num == clr:
                toggled.clear()
                continue
            if num == cont:
                return preview
            if num == back:
                return ud.normalize("NFC", base)
            print("Out of range.")

    # --------------------------------------------------------------------

    def _continue_prompt(self) -> bool:
        """Ask if user wants to continue."""
        while True:
            choice = input("\nAnalyze another character? (y/n): ").strip().lower()
            if choice in ["y", "yes", ""]:
                return True
            elif choice in ["n", "no"]:
                return False
            else:
                print("Please enter 'y' for yes or 'n' for no.")


def main():
    """Main entry point for interactive CLI."""
    try:
        cli = InteractivePhonenvCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\n Goodbye!")
    except Exception as e:
        print(f"\n Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()