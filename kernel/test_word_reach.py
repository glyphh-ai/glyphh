"""word_reach (kernel 3.16.0): a text role's words read past their own neighbours. 1 is the reading before 3.16.0;
2 and 3 add a word's plain form and that many steps of neighbours' neighbours."""

from __future__ import annotations

import numpy as np
import pytest

import glyphh_kernel as kernel
from glyphh_lexicon import LEXICON
from glyphh_spec import Model, Settings, Spec, SpecError

needs_seeds = pytest.mark.skipif(not LEXICON.available, reason="the lexicon seeds are not here")

SPEC = {
    "name": "notes",
    "seed": 3,
    "dimension": 2048,
    "layers": [{"name": "t", "segments": [{"name": "s", "roles": [{"name": "text", "text_encoding": "bag_of_words"}]}]}],
}


def cos(a: np.ndarray, b: np.ndarray) -> float:
    x, y = a.astype(float), b.astype(float)
    return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))


def test_the_setting_is_checked_and_reach_1_is_the_default() -> None:
    assert Settings().word_reach == 1 and Settings().reading == 1
    assert Settings().with_changes({"word_reach": 3}).reading == 3
    assert Settings().with_changes({"word_reach": 2, "lexicon": False}).reading == 0
    for bad in (0, 4, 1.5, True):
        with pytest.raises(SpecError):
            Settings().with_changes({"word_reach": bad})
    assert "word_reach" not in Settings().to_json()  # a spec that names none says none back


def test_reach_is_a_number_and_true_is_one() -> None:
    assert (kernel._reach(False), kernel._reach(True), kernel._reach(2), kernel._reach(9)) == (0, 1, 2, 3)


@needs_seeds
def test_reach_1_reads_every_word_as_before() -> None:
    for word in ("charge", "refund", "charged", "zzzz"):
        assert np.array_equal(LEXICON.glyph(word, 5, 1024), LEXICON._near_glyph(word, 5, 1024))
        assert np.array_equal(LEXICON.glyph(word, 5, 1024, reach=1), LEXICON.glyph(word, 5, 1024))


@needs_seeds
def test_a_plain_form_is_found_only_where_it_is_one() -> None:
    assert [LEXICON.lemma(w) for w in ("charged", "billed", "cards", "stolen", "stopped", "fees")] == [
        "charge", "bill", "card", "steal", "stop", "fee"
    ]
    assert [LEXICON.lemma(w) for w in ("news", "charge", "business", "zzzzed")] == [None, None, None, None]


@needs_seeds
def test_reach_2_brings_related_words_together_and_leaves_others_apart() -> None:
    def at(a: str, b: str, r: int) -> float:
        return cos(LEXICON.glyph(a, 5, 4096, r), LEXICON.glyph(b, 5, 4096, r))

    assert at("angry", "furious", 2) > at("angry", "furious", 1) + 0.15
    assert at("charged", "charge", 2) > 0.4 > at("charged", "charge", 1)  # a plain form reads with its word
    assert abs(at("charge", "apple", 2)) < 0.06 and abs(at("arrive", "stolen", 2)) < 0.06


@needs_seeds
def test_a_model_reads_at_its_reach_and_moving_it_rereads_the_store() -> None:
    m = Model(Spec.from_json({**SPEC, "settings": {"word_reach": 2}}), path=None)
    assert m.space.lexicon == 2
    rid = m.record({"t": {"s": {"text": "I was charged twice"}}}, "billing")
    before = m.space._glyphs[0].copy()
    m.configure(word_reach=1)
    assert m.space.lexicon == 1 and not np.array_equal(before, m.space._glyphs[0])
    m.configure(lexicon=False)
    assert m.space.lexicon == 0
    assert rid
