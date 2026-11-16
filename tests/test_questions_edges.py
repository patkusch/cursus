from cursus.answers import ANSWER, parse_answers, questions_markdown, text_with_answers
from cursus.model import Process


def process(questions, steps=None):
    base = {"title": "Expense claim", "lanes": [{"id": "l", "name": "Staff"}], "steps": steps or [], "flows": [], "questions": questions}
    return Process.model_validate(base)


def test_a_reading_with_no_questions_says_so_on_the_page():
    page = questions_markdown(process([]))
    assert page.splitlines()[0] == "# Questions: Expense claim"
    assert "The reading raised no questions." in page
    assert page.count(ANSWER) == 1, "only the instruction line mentions the word"


def test_a_question_pointing_at_a_step_that_does_not_exist_is_still_listed_without_that_line(expense):
    first = expense.model_copy(deep=True)
    first.questions[0].about = "no-such-step"
    page = questions_markdown(first)
    assert "## 1." in page
    assert "About the step:" not in page.split("## 2.")[0]


def test_extra_spaces_and_line_breaks_in_a_question_or_quote_are_tidied_onto_one_line(expense):
    messy = expense.model_copy(deep=True)
    messy.questions[0].text = "What   happens\n when it fails?"
    messy.questions[0].quote = "  the   text\nsays  "
    page = questions_markdown(messy)
    assert "## 1. What happens when it fails?" in page
    assert 'The text says: "the text says"' in page


def test_only_questions_with_a_real_answer_are_returned_and_whitespace_is_collapsed():
    page = "\n".join([
        "# Questions: x", "",
        "## 1. First?", "", "Answer:    Yes,   after\n   two days.", "",
        "## 2. Second?", "", "Answer: ", "",
        "## 3. Third?", "", "no answer line at all", "",
        "## 4. Fourth?", "", "Answer: No.", "",
    ])
    assert parse_answers(page) == [("First?", "Yes, after two days."), ("Fourth?", "No.")]


def test_numbering_is_dropped_from_the_question_but_the_wording_is_kept():
    assert parse_answers("## 12. What is the limit?\n\nAnswer: 500\n") == [("What is the limit?", "500")]
    assert parse_answers("## Unnumbered?\n\nAnswer: yes\n") == [("Unnumbered?", "yes")]


def test_text_with_no_headings_has_no_answers():
    assert parse_answers("") == []
    assert parse_answers("Answer: floating text\n") == []


def test_answers_are_added_after_the_source_so_they_can_be_quoted_and_nothing_is_added_when_there_are_none():
    source = "Staff submit a claim.\n"
    out = text_with_answers(source, "## 1. Limit?\n\nAnswer: 500 euros\n")
    assert out.startswith("Staff submit a claim.")
    assert "Answer: 500 euros" in out
    assert out.index("Answer: 500 euros") > out.index("Staff submit a claim.")
    assert text_with_answers(source, "## 1. Limit?\n\nAnswer: \n") == source
