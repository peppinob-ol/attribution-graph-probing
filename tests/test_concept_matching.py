"""Tests for _match_concept_to_supernodes and related helpers in 03_ct_steering.py.

Covers forward matching, reverse (fragment) matching, initials, function-word
filtering, single-word concepts, and numeric concepts.
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_ct_steering():
    steering_path = SCRIPTS_DIR / "03_ct_steering.py"
    spec = importlib.util.spec_from_file_location("ct_steering", steering_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["ct_steering"] = module
    spec.loader.exec_module(module)
    return module


ct = _load_ct_steering()
_FUNCTION_WORDS = ct._FUNCTION_WORDS
_is_reverse_match_candidate = ct._is_reverse_match_candidate
_match_concept_to_supernodes = ct._match_concept_to_supernodes
_parse_initial_letters = ct._parse_initial_letters


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_df(supernode_names: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """Build a minimal grouping DataFrame + lowercased names Series."""
    df = pd.DataFrame({
        "supernode_name": supernode_names,
        "layer": range(len(supernode_names)),
        "feature": range(len(supernode_names)),
    })
    names = df["supernode_name"].astype(str).str.lower()
    return df, names


def _matched_names(df, names, concept: str) -> set[str]:
    result = _match_concept_to_supernodes(df, names, concept.lower())
    return set(result["supernode_name"].tolist())


# ------------------------------------------------------------------
# _parse_initial_letters
# ------------------------------------------------------------------

class TestParseInitialLetters:
    def test_jrr(self):
        assert _parse_initial_letters("j.r.r.") == ["j", "r"]

    def test_jk(self):
        assert _parse_initial_letters("j.k.") == ["j", "k"]

    def test_no_dots(self):
        assert _parse_initial_letters("tolkien") == []


# ------------------------------------------------------------------
# _is_reverse_match_candidate
# ------------------------------------------------------------------

class TestReverseMatchCandidate:
    def test_digit_single(self):
        assert _is_reverse_match_candidate("4") is True

    def test_digit_multi(self):
        assert _is_reverse_match_candidate("19") is True

    def test_function_word(self):
        assert _is_reverse_match_candidate("the") is False

    def test_short_alpha(self):
        assert _is_reverse_match_candidate("is") is False
        assert _is_reverse_match_candidate("ol") is False

    def test_long_alpha(self):
        assert _is_reverse_match_candidate("dosto") is True
        assert _is_reverse_match_candidate("bird") is True

    def test_and_is_function_word(self):
        assert "and" in _FUNCTION_WORDS
        assert _is_reverse_match_candidate("and") is False


# ------------------------------------------------------------------
# _match_concept_to_supernodes: forward matching (existing behaviour)
# ------------------------------------------------------------------

class TestForwardMatching:
    def test_full_concept_in_name(self):
        """'tolstoy' matches 'Say (Tolstoy)'."""
        df, names = _make_df(["Say (Tolstoy)", "Kill", "bird"])
        assert _matched_names(df, names, "tolstoy") == {"Say (Tolstoy)"}

    def test_per_word_forward(self):
        """'harper' as a word in 'Harper Lee' matches supernodes containing it."""
        df, names = _make_df(["Harper", "Say (Harper)", "bird", "Kill"])
        hits = _matched_names(df, names, "harper lee")
        assert "Harper" in hits
        assert "Say (Harper)" in hits

    def test_initials(self):
        df, names = _make_df(["j", "k", "Say (j)", "Say (k)", "Rowling"])
        hits = _matched_names(df, names, "j.k. rowling")
        assert "j" in hits or "Say (j)" in hits
        assert "k" in hits or "Say (k)" in hits
        assert "Rowling" in hits


# ------------------------------------------------------------------
# _match_concept_to_supernodes: reverse matching (new behaviour)
# ------------------------------------------------------------------

class TestReverseMatching:
    def test_mockingbird_fragments(self):
        """'Mocking' and 'bird' are fragments of the word 'mockingbird'."""
        supernodes = [
            "Kill", "(Kill) related", "Say (Kill)",
            "Mocking", "bird", "Scout", "Finch",
        ]
        df, names = _make_df(supernodes)
        hits = _matched_names(df, names, "to kill a mockingbird")
        assert "Mocking" in hits
        assert "bird" in hits
        assert "Kill" in hits

    def test_dostoevsky_fragments(self):
        """'Dosto' and 'evsky' are fragments of the word 'dostoevsky'."""
        supernodes = [
            "Crime", "(Crime) related", "Punishment",
            "Dosto", "evsky", "(Dosto) related", "Rask",
            "odor", "author", "book",
        ]
        df, names = _make_df(supernodes)
        hits = _matched_names(df, names, "fyodor dostoevsky")
        assert "Dosto" in hits
        assert "evsky" in hits
        assert "odor" in hits, "'odor' is a substring of 'fyodor'"
        assert "Rask" not in hits, "'Rask' should not match Dostoevsky"

    def test_crime_and_punishment(self):
        """'and' is now a function word and should be skipped."""
        supernodes = [
            "Crime", "Punishment", "(Crime) related", "author",
        ]
        df, names = _make_df(supernodes)
        hits = _matched_names(df, names, "crime and punishment")
        assert "Crime" in hits
        assert "Punishment" in hits
        assert "author" not in hits

    def test_no_spurious_short_matches(self):
        """Short alphabetic names (< 3 chars) should not reverse-match."""
        supernodes = ["is", "ol", "Dosto", "Kill"]
        df, names = _make_df(supernodes)
        hits = _matched_names(df, names, "dostoevsky")
        assert "Dosto" in hits
        assert "is" not in hits
        assert "ol" not in hits


# ------------------------------------------------------------------
# Single-word concepts (including numeric)
# ------------------------------------------------------------------

class TestSingleWordConcepts:
    def test_numeric_1984(self):
        """Digit supernodes '4' and '8' should match concept '1984'."""
        supernodes = ["4", "8", "Winston", "Smith", "author", "book"]
        df, names = _make_df(supernodes)
        hits = _matched_names(df, names, "1984")
        assert "4" in hits
        assert "8" in hits
        assert "author" not in hits

    def test_single_word_reverse(self):
        """A single long word should still trigger reverse matching."""
        supernodes = ["mock", "bird", "Kill", "author"]
        df, names = _make_df(supernodes)
        hits = _matched_names(df, names, "mockingbird")
        assert "mock" in hits
        assert "bird" in hits
        assert "author" not in hits

    def test_single_word_forward_still_works(self):
        """If the full concept is a substring of a name, forward match wins."""
        supernodes = ["Say (Tolstoy)", "Tolstoy", "author"]
        df, names = _make_df(supernodes)
        hits = _matched_names(df, names, "tolstoy")
        assert "Say (Tolstoy)" in hits
        assert "Tolstoy" in hits


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_result_when_nothing_matches(self):
        supernodes = ["author", "book", "person"]
        df, names = _make_df(supernodes)
        result = _match_concept_to_supernodes(df, names, "xyz123")
        assert result.empty

    def test_function_word_only_concept(self):
        """A concept made entirely of function words / short tokens."""
        supernodes = ["the", "and", "of"]
        df, names = _make_df(supernodes)
        result = _match_concept_to_supernodes(df, names, "the and of")
        assert result.empty

    def test_deduplication(self):
        """Rows matched by both forward and reverse should not duplicate."""
        supernodes = ["Kill", "Kill"]
        df, names = _make_df(supernodes)
        hits = _match_concept_to_supernodes(df, names, "to kill a mockingbird")
        assert len(hits) <= 2
