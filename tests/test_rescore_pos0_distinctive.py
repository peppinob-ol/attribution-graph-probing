"""Tests for ``scripts.utils.rescore_pos0_distinctive.pos0_distinctive_hit``.

The metric must
- count a steered first token as a hit only when it matches a distinctive
  target word (one that does not also appear in the source answer);
- accept tokenizer subword splits (e.g. " Dost" matches "Dostoevsky");
- reject loose substrings of the full answer (e.g. " of" matching
  "Persistence of Memory");
- flag answer-level identity pairs via ``no_distinctive``.
"""
from __future__ import annotations

from scripts.utils.rescore_pos0_distinctive import pos0_distinctive_hit


def test_distinctive_first_word_match():
    hit, matched, no_distinctive = pos0_distinctive_hit(
        steered_first_token=" Mark",
        to_answer="Mark Zuckerberg",
        from_answer="Bill Gates",
    )
    assert hit is True
    assert matched == "zuckerberg" or matched == "mark"
    assert no_distinctive is False


def test_distinctive_subword_last_name():
    hit, matched, _ = pos0_distinctive_hit(
        steered_first_token=" Dost",
        to_answer="Fyodor Dostoevsky",
        from_answer="Suzanne Collins",
    )
    assert hit is True
    assert matched == "dostoevsky"


def test_loose_function_word_not_a_hit():
    hit, matched, _ = pos0_distinctive_hit(
        steered_first_token=" of",
        to_answer="Salvador Dali",
        from_answer="Claude Monet",
    )
    assert hit is False
    assert matched is None


def test_punctuation_garbage_not_a_hit():
    for ft in ("'", "<bos>", "AddTagHelper", "."):
        hit, _, _ = pos0_distinctive_hit(
            steered_first_token=ft,
            to_answer="Mark Twain",
            from_answer="J.R.R. Tolkien",
        )
        assert hit is False, f"garbage token {ft!r} unexpectedly counted as hit"


def test_source_collision_blocks_match():
    """When the only matching target word also appears in the source answer
    (here ``finch``), the metric must reject the hit."""
    hit, matched, no_distinctive = pos0_distinctive_hit(
        steered_first_token=" Finch",
        to_answer="Atticus Finch",
        from_answer="Scout Finch",
    )
    assert hit is False
    assert matched is None
    assert no_distinctive is False


def test_answer_level_identity_flagged():
    hit, matched, no_distinctive = pos0_distinctive_hit(
        steered_first_token=" brown",
        to_answer="brown",
        from_answer="brown",
    )
    assert hit is False
    assert matched is None
    assert no_distinctive is True


def test_short_first_token_rejected():
    hit, _, _ = pos0_distinctive_hit(
        steered_first_token=" a",
        to_answer="Salvador Dali",
        from_answer="Claude Monet",
    )
    assert hit is False


def test_full_word_match_when_first_token_is_word():
    hit, matched, _ = pos0_distinctive_hit(
        steered_first_token=" Springfield",
        to_answer="Springfield",
        from_answer="Pierre",
    )
    assert hit is True
    assert matched == "springfield"


def test_uppercase_token_normalised():
    hit, matched, _ = pos0_distinctive_hit(
        steered_first_token=" GREEN",
        to_answer="green",
        from_answer="white",
    )
    assert hit is True
    assert matched == "green"
