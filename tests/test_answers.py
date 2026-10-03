from cursus.answers import parse_answers, questions_markdown, text_with_answers
from cursus.check import check, has_errors
from cursus.cli import load_reading, main
from cursus.prompts import reading_prompt

EX = "examples/expense-claim"


def test_questions_page_lists_each_question_with_its_step_and_quote(expense):
    page = questions_markdown(expense)
    assert "## 1. What happens when the finance director does not sign off a claim?" in page
    assert "About the step: Signed off?" in page
    assert page.count("Answer:") == 3  # the instruction line plus one per question
    assert parse_answers(page) == []  # nothing answered yet


def test_only_answered_questions_are_added_to_the_text(expense_source):
    answers = open(f"{EX}/answers.md").read()
    pairs = parse_answers(answers)
    assert len(pairs) == 1 and pairs[0][1].startswith("If the finance director refuses")
    text = text_with_answers(expense_source, answers)
    assert text.startswith(expense_source.rstrip())
    assert "Answer: If the finance director refuses" in text
    assert "five working days?" not in text  # the unanswered question stays out
    assert text_with_answers(expense_source, "## 1. Q?\n\nAnswer: \n") == expense_source


def test_an_answered_gap_becomes_a_step_that_quotes_the_answer(expense_source):
    answered = load_reading(f"{EX}/reading-answered.json")
    assert has_errors(check(answered, expense_source))  # the new step is not in the original text
    findings = check(answered, text_with_answers(expense_source, open(f"{EX}/answers.md").read()))
    assert findings == []  # no errors, and no "Not stated" warning any more


def test_prompt_tells_the_model_about_answers_only_when_there_are_some(expense_source):
    assert "already answered" not in reading_prompt(expense_source)
    assert "already answered" in reading_prompt(expense_source, has_answers=True)


def test_build_with_answers(tmp_path, capsys):
    args = ["build", f"{EX}/reading-answered.json", "--source", f"{EX}/process.txt", "--out", str(tmp_path)]
    assert main(args) == 1
    assert main(args + ["--answers", f"{EX}/answers.md"]) == 0
    assert "Not stated" not in (tmp_path / "reading-answered.svg").read_text()
    assert "Reject claim" in (tmp_path / "reading-answered.svg").read_text()
