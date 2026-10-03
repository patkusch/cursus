import json

from cursus.read import parse_reading, read

TEXT = "A customer sends in an order. The warehouse packs the order."


def reading(quote="The warehouse packs the order."):
    return json.dumps({
        "title": "Orders",
        "steps": [
            {"id": "a", "kind": "start", "text": "Start"},
            {"id": "b", "kind": "task", "text": "Pack the order", "quote": quote},
            {"id": "c", "kind": "end", "text": "End"},
        ],
        "flows": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
    })


class Scripted:
    """Stands in for a model: gives back the next canned reply and keeps what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []

    def __call__(self, messages):
        self.seen.append([dict(m) for m in messages])
        return self.replies.pop(0)


def test_good_first_answer_is_taken_as_is():
    model = Scripted(reading())
    result = read(TEXT, model)
    assert result.ok and result.attempts == 1
    assert TEXT in model.seen[0][0]["content"]


def test_faults_go_back_to_the_model_until_the_reading_passes():
    model = Scripted("Sorry, I cannot.", reading(quote="The warehouse ships it."), reading())
    result = read(TEXT, model, repairs=2)
    assert result.ok and result.attempts == 3
    second, third = model.seen[1], model.seen[2]
    assert "no JSON object" in second[-1]["content"]
    assert "The warehouse ships it." in third[-1]["content"]  # told exactly which quote is not in the text
    assert [m["role"] for m in third] == ["user", "assistant", "user"]  # the first request plus the latest failed try only
    assert third[0] == second[0] and "Sorry, I cannot." not in str(third)


def test_gives_up_after_the_allowed_repairs_and_keeps_the_best_try():
    bad = reading(quote="Not in the text.")
    model = Scripted(bad, "garbage", bad)
    result = read(TEXT, model, repairs=2)
    assert not result.ok and result.attempts == 3
    assert result.process is not None and result.errors == 1


def test_nothing_readable_at_all():
    result = read(TEXT, Scripted("no", "still no"), repairs=1)
    assert result.process is None and "no JSON object" in result.fault


def test_a_step_that_quotes_the_text_cannot_hide_behind_assumed():
    raw = json.loads(reading(quote="Not in the text."))
    raw["steps"][1]["assumed"] = True
    result = read(TEXT, Scripted(json.dumps(raw)), repairs=0)
    assert result.errors == 1 and result.process.steps[1].assumed is False


def test_the_model_is_not_offered_the_assumed_field():
    from cursus.prompts import reading_prompt, reading_schema

    assert "assumed" not in json.dumps(reading_schema())
    assert '"assumed"' not in reading_prompt(TEXT)


def test_answer_wrapped_in_a_fence_or_missing_fields():
    assert parse_reading("```json\n" + reading() + "\n```").title == "Orders"
    try:
        parse_reading('{"steps": []}')
    except Exception as e:
        assert "title" in str(e)
    else:
        raise AssertionError("a reading with no title should be refused")
