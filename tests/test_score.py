from pathlib import Path

import pytest

from cursus.bench import cases
from cursus.check import check, has_errors
from cursus.model import Flow, Question, Step
from cursus.score import likeness, overlap, pair_steps, score, span

BENCH = Path(__file__).resolve().parent.parent / "bench"
CASES = cases(BENCH)


def case(name):
    return next((source, ref) for n, source, ref in CASES if n == name)


def test_there_are_enough_cases_and_every_reference_passes_its_own_checks():
    assert len(CASES) >= 10
    for name, source, ref in CASES:
        assert not has_errors(check(ref, source)), name


@pytest.mark.parametrize("name", [n for n, _, _ in CASES])
def test_a_reference_scores_full_marks_against_itself(name):
    source, ref = case(name)
    s = score(ref, ref, source)
    assert (s.steps_found, s.steps_right, s.arrows_found, s.arrows_right, s.decisions_found, s.roles_right) == (1, 1, 1, 1, 1, 1)
    assert s.gaps_asked == s.gaps and s.gaps_guessed == 0


def test_words_are_compared_without_endings_or_filler():
    assert likeness("Approve the claim", "Approves claims") == 1.0
    assert likeness("Approve the claim", "Schedule payment") == 0.0
    assert 0 < likeness("Send claim back with note", "Sends claim back to employee") < 1


def test_overlap_is_measured_on_the_text_itself():
    text = "the manager checks the claim. if it is fine, the manager approves it."
    whole, part, other = span("If it is fine, the manager approves it.", text), span("the manager approves it", text), span("the manager checks the claim", text)
    assert overlap(whole, part) == 1.0 and overlap(whole, other) == 0.0
    assert span("not there", text) is None and overlap(None, whole) == 0.0


def test_same_step_under_another_name_still_pairs_up():
    source, ref = case("leave-request")
    cand = ref.model_copy(deep=True)
    for s in cand.steps:
        s.id = "x_" + s.id
        s.text = "Reworded " + s.text
    for f in cand.flows:
        f.from_id, f.to_id = "x_" + f.from_id, "x_" + f.to_id
    assert len(pair_steps(ref, cand, source)) == 6
    s = score(ref, cand, source)
    assert s.steps_found == 1 and s.arrows_found == 1


def test_a_missing_step_and_an_extra_step_cost_different_columns():
    source, ref = case("order-packing")
    fewer = ref.model_copy(deep=True)
    fewer.steps = [s for s in fewer.steps if s.id != "t3"]
    fewer.flows = [f for f in fewer.flows if "t3" not in (f.from_id, f.to_id)] + [Flow(from_id="t2", to_id="t4")]
    s = score(ref, fewer, source)
    assert s.steps_found == 0.75 and s.steps_right == 1.0 and s.arrows_found < 1

    more = ref.model_copy(deep=True)
    more.steps.insert(2, Step(id="x", kind="task", text="Weigh the parcel", quote="When an order arrives"))
    s = score(ref, more, source)
    assert s.steps_found == 1.0 and s.steps_right == 0.8


def test_a_decision_drawn_as_a_plain_step_is_not_a_found_decision():
    source, ref = case("document-review")
    cand = ref.model_copy(deep=True)
    cand.step("d1").kind = "task"
    s = score(ref, cand, source)
    assert s.decisions_found == 0 and s.steps_found == 0.8


def test_wrong_role_and_no_roles():
    source, ref = case("leave-request")
    swapped = ref.model_copy(deep=True)
    swapped.step("t2").lane = "employee"
    assert score(ref, swapped, source).roles_right == pytest.approx(5 / 6)
    bare = ref.model_copy(deep=True)
    bare.lanes = []
    for s in bare.steps:
        s.lane = None
    assert score(ref, bare, source).roles_right == 0


def test_gap_asked_guessed_or_lost():
    source, ref = case("customer-refund")
    guessed = ref.model_copy(deep=True)
    guessed.questions = []
    guessed.flows.append(Flow(from_id="d1", to_id="t6", label="No"))
    s = score(ref, guessed, source)
    assert (s.gaps, s.gaps_asked, s.gaps_guessed) == (1, 0, 1)

    lost = ref.model_copy(deep=True)
    lost.questions = [Question(text="What happens when a refund is late?")]  # a question, but not about this gap
    lost.step("d1").kind = "task"
    s = score(ref, lost, source)
    assert (s.gaps_asked, s.gaps_guessed) == (0, 0)
