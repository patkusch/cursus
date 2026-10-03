"""We only write what Visio writes.

Every kind of thing in our files (a cell, the kind of formula in it, a row, an
attachment) must also appear in a file Visio itself saved. The few that do not
are listed below with the reason, so the list of things only real Visio can
confirm stays short and known.
"""
from pathlib import Path

import pytest

from cursus.bench import cases
from cursus.visio import write_vsdx
from visio_words import words_of_file

ROOT = Path(__file__).resolve().parent.parent
SAVED_BY_VISIO = sorted((ROOT / "tests" / "visio_saved").glob("*.vsdx")) + [ROOT / "cursus" / "seed" / "cff_seed.vsdx"]

OURS_ALONE = {
    ("cell", "Property", "Value", "-"): "the source sentence, stored as a typed-in value; Visio's samples only hold values that come from a formula",
    ("cell", "shape", "TxtWidth", "Height*N"): "lane name turned on its side; Visio's own swimlane does the same with a longer formula",
    ("cell", "shape", "TxtHeight", "Width*N"): "the other half of the turned lane name",
}


@pytest.fixture(scope="module")
def visio_words():
    out = set()
    for path in SAVED_BY_VISIO:
        out |= words_of_file(path)
    return out


@pytest.fixture(scope="module")
def our_words(tmp_path_factory):
    folder = tmp_path_factory.mktemp("drawn")
    out = {}
    for name, _, reference in cases(ROOT / "bench"):
        for recalc in (True, False):
            for word in words_of_file(write_vsdx(reference, folder / f"{name}-{recalc}.vsdx", recalc=recalc), parts=("visio/pages/",)):
                out.setdefault(word, name)
    return out


def test_there_is_a_real_sample_to_compare_with(visio_words):
    assert len(SAVED_BY_VISIO) >= 5 and len(visio_words) > 300


def test_everything_we_write_is_something_visio_writes(visio_words, our_words):
    alone = {word: case for word, case in our_words.items() if word not in visio_words and word not in OURS_ALONE}
    assert not alone, f"new kinds of content that no Visio-saved sample has: {alone}"


def test_the_exceptions_are_still_exceptions(visio_words, our_words):
    for word in OURS_ALONE:
        assert word in our_words, f"{word} is listed as ours alone but we no longer write it"
        assert word not in visio_words, f"{word} is now in a Visio-saved sample: take it off the list"


def test_the_cases_exercise_the_awkward_arrows(our_words, visio_words):
    """A dead-straight arrow is stored differently from a bent one. Check we write the straight kind, and that it is Visio's way."""
    assert ("cell", "shape", "Height", "GUARD(NDL)") in our_words  # straight across
    assert ("row", "Geometry", "LineTo", "deleted") in our_words
    # straight up-and-down arrows are rare in our layouts; what we would write for one is what Visio writes
    assert ("cell", "shape", "Width", "GUARD(NDL)") in visio_words
