from cursus.check import Finding
from cursus.model import Flow, Lane, Process, Question, Step
from cursus.report import to_markdown


def process(**over):
    base = dict(
        title="Expense claim",
        lanes=[Lane(id="emp", name="Employee"), Lane(id="mgr", name="Manager")],
        steps=[
            Step(id="s", kind="start", text="Start"),
            Step(id="a", kind="task", text="Submit claim", lane="emp", quote="The employee submits the claim."),
            Step(id="b", kind="task", text="Approve claim", lane="mgr", quote="", assumed=True),
            Step(id="e", kind="end", text="End"),
        ],
        flows=[Flow(**{"from": "s", "to": "a"}), Flow(**{"from": "a", "to": "b"}), Flow(**{"from": "b", "to": "e"})],
    )
    base.update(over)
    return Process(**base)


def test_the_page_starts_with_the_title_and_the_picture():
    md = to_markdown(process(), [])
    assert md.startswith("# Expense claim\n")
    assert "```mermaid" in md


def test_each_step_is_listed_with_who_does_it_and_the_sentence_it_came_from():
    md = to_markdown(process(), [])
    assert '| Submit claim | Employee | "The employee submits the claim." |' in md


def test_a_step_the_text_never_states_says_so():
    md = to_markdown(process(), [])
    assert "| Approve claim | Manager | *Not stated in the text* |" in md


def test_plain_start_and_end_boxes_are_left_out_of_the_table():
    table = to_markdown(process(), []).split("## Where each step came from")[1].split("## Checks")[0]
    assert "| Start |" not in table
    assert "| End |" not in table


def test_a_pipe_in_a_quote_does_not_break_the_table():
    p = process(steps=[Step(id="a", kind="task", text="Pick a | b", lane="emp", quote="choose a | b\nnow")])
    md = to_markdown(p, [])
    assert "| Pick a \\| b | Employee | \"choose a \\| b now\" |" in md


def test_no_questions_says_none():
    assert "## Questions for the author\n\nNone." in to_markdown(process(), [])


def test_a_question_shows_the_step_it_is_about_and_the_text_that_raised_it():
    p = process(questions=[Question(about="a", text="Is there a limit?", quote="submits the claim")])
    md = to_markdown(p, [])
    assert "- Is there a limit? (about: Submit claim)" in md
    assert '  - The text says: "submits the claim"' in md


def test_a_question_with_no_step_has_no_about_part():
    md = to_markdown(process(questions=[Question(text="Who signs off?")]), [])
    assert "- Who signs off?\n" in md
    assert "(about:" not in md


def test_checks_either_pass_or_are_listed_with_level_and_place():
    assert "## Checks\n\nAll passed." in to_markdown(process(), [])
    f = Finding(level="error", code="no-exit", where="step b", message="Nothing follows this step")
    md = to_markdown(process(), [f])
    assert "- **error** (step b): Nothing follows this step" in md
    assert "All passed." not in md


def test_the_page_ends_with_one_newline():
    md = to_markdown(process(), [])
    assert md.endswith("\n") and not md.endswith("\n\n")
