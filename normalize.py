"""Centralized character normalization mappings for Phonenv.

This module provides a single source of truth for ASCII→IPA and confusable
character mappings, shared between the automatic normalization pipeline
(utils.normalize_ascii_to_ipa) and the validation system (validate.py).

Design Philosophy:
- UNAMBIGUOUS_MAPPINGS: Always-safe automatic transformations
- CONFUSABLE_HINTS: Context-dependent suggestions (validation warnings)
- ORTHOGRAPHY_PATTERNS: Common spelling→IPA patterns for detection
"""

from __future__ import annotations
from typing import Dict, Mapping, Tuple

# ========================= TIER 1: Automatic Normalization =========================
# Keep this *minimal* and unambiguous. These are applied automatically.

UNAMBIGUOUS_MAPPINGS = {
    "g": "ɡ",
    ":": "ː",
    # Non-ASCII but unambiguous colon-like marks → IPA length
    "\u02f8": "ː",  # MODIFIER LETTER RAISED COLON
    "\u2236": "ː",  # RATIO
    "\ua789": "ː",  # MODIFIER LETTER COLON
    "\uff1a": "ː",  # FULLWIDTH COLON
    # Tie-bar normalization (canonicalize to U+0361)
    "\u035c": (
        "\u0361"
    ),  # COMBINING DOUBLE BREVE BELOW → DOUBLE INVERTED BREVE (tie-bar)
    # Fullwidth Latin that appears in pasted text
    "\uff47": "ɡ",  # FULLWIDTH 'g' → IPA script g
}
TRANSLATE_TABLE = str.maketrans(UNAMBIGUOUS_MAPPINGS)

# ========================= TIER 2: Validation Hints =========================
# These are *not* applied automatically; they generate warnings/suggestions.

CONFUSABLE_HINTS: Mapping[str, str] = {
    # Greek letters often confused with IPA symbols
    "φ": "ɸ",  # U+03C6 → U+0278 (Greek phi → IPA bilabial fricative)
    "γ": "ɣ",  # U+03B3 → U+0263 (Greek gamma → IPA voiced velar fricative)
    # Punctuation used as IPA (context-dependent)
    ";": "ˑ",  # U+003B → U+02D1 (semicolon → half-long)
    "'": "ˈ",  # U+0027 → U+02C8 (ASCII apostrophe → primary stress)
    "\u2019": (
        "ˈ"
    ),  # U+2019 RIGHT SINGLE QUOTATION MARK → U+02C8 primary stress
    ",": "ˌ",  # U+002C → U+02CC (comma → secondary stress)
    "?": "ʔ",  # U+003F → U+0294 (question mark → glottal stop)
    # Cyrillic homoglyphs (Latin/IPA look-alikes)
    "а": "a",  # U+0430 CYRILLIC SMALL LETTER A
    "е": "e",  # U+0435 CYRILLIC SMALL LETTER IE
    "о": "o",  # U+043E CYRILLIC SMALL LETTER O
    "р": "p",  # U+0440 CYRILLIC SMALL LETTER ER
    "с": "c",  # U+0441 CYRILLIC SMALL LETTER ES
    "у": "y",  # U+0443 CYRILLIC SMALL LETTER U
    "х": "x",  # U+0445 CYRILLIC SMALL LETTER HA
    "і": "i",  # U+0456 CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    "ј": "j",  # U+0458 CYRILLIC SMALL LETTER JE
    "к": "k",  # U+043A CYRILLIC SMALL LETTER KA
    "т": "t",  # U+0442 CYRILLIC SMALL LETTER TE
    # Greek homoglyphs (Latin/IPA look-alikes)
    "α": "ɑ",  # Greek alpha → IPA small script A (U+0251)
    "ρ": "p",  # Greek rho → Latin p
    "ν": "v",  # Greek nu → Latin v
    "χ": "x",  # Greek chi → Latin x
    "λ": "ʎ",  # Greek lambda → IPA palatal lateral approximant (U+028E)
    # ASCII capital homoglyphs (validate-only; not auto-normalized)
    "N": "ɴ",  # Latin capital N → IPA small capital N (U+0274)
    "R": "ʀ",  # Latin capital R → IPA small capital R (U+0280)
    "G": "ɢ",  # Latin capital G → IPA small capital G (U+0262)
    "L": "ʟ",  # Latin capital L → IPA small capital L (U+029F)
    "Y": "ʏ",  # Latin capital Y → IPA small capital Y (U+028F)
}

# ========================= TIER 3: Orthography Detection =========================
# Heuristics to *flag* likely orthographic spill; not auto-fixed.

ORTHOGRAPHY_PATTERNS: Mapping[str, Tuple[str, ...]] = {
    # Common orthographic digraphs that should be IPA symbols
    "ng": ("ŋ",),  # U+014B (velar nasal)
    "th": ("θ", "ð"),  # voiceless/voiced dental fricative
    "sh": ("ʃ",),  # U+0283 (voiceless postalveolar fricative)
    "ch": ("t͡ʃ", "ç"),  # affricate or voiceless palatal fricative
    "zh": ("ʒ",),  # U+0292 (voiced postalveolar fricative)
}

# ========================= Utility Functions =========================


def get_all_hints() -> Dict[str, str]:
    """Get merged dictionary of all character hints (unambiguous + confusable).

    Useful for comprehensive validation that checks for all known issues.
    """
    # Materialize as dict so callers can safely mutate their own copy if needed.
    return {**UNAMBIGUOUS_MAPPINGS, **CONFUSABLE_HINTS}


def explain_mapping(char: str) -> str:
    """Get human-readable explanation for why a character mapping exists.

    Returns:
        A short explanation string, or "" if the character is unknown.
    """
    if char in UNAMBIGUOUS_MAPPINGS:
        ipa = UNAMBIGUOUS_MAPPINGS[char]
        return (
            f"ASCII '{char}' (U+{ord(char):04X}) should be "
            f"IPA '{ipa}' (U+{ord(ipa):04X}) — unambiguous, always safe"
        )
    if char in CONFUSABLE_HINTS:
        ipa = CONFUSABLE_HINTS[char]
        return (
            f"'{char}' (U+{ord(char):04X}) might be "
            f"IPA '{ipa}' (U+{ord(ipa):04X}) — context-dependent, verify manually"
        )
    return ""


def is_unambiguous(char: str) -> bool:
    """True if character has a safe automatic mapping."""
    return char in UNAMBIGUOUS_MAPPINGS


def is_confusable(char: str) -> bool:
    """True if character is a known confusable (validation warning)."""
    return char in CONFUSABLE_HINTS


__all__ = [
    "UNAMBIGUOUS_MAPPINGS",
    "CONFUSABLE_HINTS",
    "ORTHOGRAPHY_PATTERNS",
    "TRANSLATE_TABLE",
    "get_all_hints",
    "explain_mapping",
    "is_unambiguous",
    "is_confusable",
]
