from cursus.check import check, check_shape, check_source, has_errors, quote_found
from cursus.model import Flow, Process, Question, Step, with_stubs


def codes(findings, level="error"):
    return {f.code for f in findings if f.level == level}


def simple(**changes):
    base = dict(
        title="t",
        steps=[
            Step(id="a", kind="start", text="Start"),
            Step(id="b", kind="task", text="Do it", quote="do it"),
            Step(id="c", kind="end", text="End"),
        ],
        flows=[Flow(from_id="a", to_id="b"), Flow(from_id="b", to_id="c")],
    )
    base.update(changes)
    return Process(**base)


def test_examples_pass(expense, expense_source, hello):
    findings = check(expense, expense_source)
    assert not has_errors(findings)
    assert codes(findings, "warning") == {"open-decision"}
    assert check(hello, "A customer sends in an order. The warehouse packs the order.") == []


def test_arrow_to_a_step_that_does_not_exist():
    p = simple(flows=[Flow(from_id="a", to_id="b"), Flow(from_id="b", to_id="zzz"), Flow(from_id="b", to_id="c")])
    assert "unknown-step" in codes(check_shape(p))


def test_no_start_and_no_end():
    p = Process(title="t", steps=[Step(id="b", kind="task", text="x", quote="x")])
    assert {"no-start", "no-end"} <= codes(check_shape(p))


def test_step_nothing_leads_to():
    p = simple()
    p.steps.append(Step(id="d", kind="task", text="Orphan", quote="q"))
    p.flows.append(Flow(from_id="d", to_id="c"))
    assert "unreachable" in codes(check_shape(p))


def test_flow_that_stops_without_an_end():
    p = simple(flows=[Flow(from_id="a", to_id="b")])
    assert "dead-end" in codes(check_shape(p))


def test_loop_with_no_way_out():
    p = simple()
    p.steps.append(Step(id="d", kind="task", text="Spin", quote="q"))
    p.steps.append(Step(id="e", kind="task", text="Spin again", quote="q"))
    p.flows = [Flow(from_id="a", to_id="d"), Flow(from_id="d", to_id="e"), Flow(from_id="e", to_id="d"), Flow(from_id="b", to_id="c")]
    found = codes(check_shape(p))
    assert "no-way-out" in found


def test_two_arrows_out_of_a_plain_step():
    p = simple()
    p.steps.append(Step(id="c2", kind="end", text="End 2"))
    p.flows.append(Flow(from_id="b", to_id="c2"))
    assert "hidden-decision" in codes(check_shape(p))


def decision(exits, questions=()):
    return Process(
        title="t",
        steps=[
            Step(id="a", kind="start", text="Start"),
            Step(id="d", kind="decision", text="OK?", quote="ok"),
            Step(id="y", kind="end", text="Yes end"),
            Step(id="n", kind="end", text="No end"),
        ],
        flows=[Flow(from_id="a", to_id="d")] + exits,
        questions=list(questions),
    )


def test_decision_exits_need_distinct_labels():
    assert "unlabelled-exit" in codes(check_shape(decision([Flow(from_id="d", to_id="y", label="Yes"), Flow(from_id="d", to_id="n")])))
    assert "repeated-label" in codes(check_shape(decision([Flow(from_id="d", to_id="y", label="Yes"), Flow(from_id="d", to_id="n", label="yes")])))


def test_one_exit_decision_is_an_error_unless_a_question_owns_up_to_it():
    one = [Flow(from_id="d", to_id="y", label="Yes")]
    silent = decision(one)
    silent.steps = [s for s in silent.steps if s.id != "n"]
    assert "one-exit-decision" in codes(check_shape(silent))

    asked = decision(one, [Question(about="d", text="What if not?")])
    asked.steps = [s for s in asked.steps if s.id != "n"]
    findings = check_shape(asked)
    assert not has_errors(findings)
    assert "open-decision" in codes(findings, "warning")

    drawn = with_stubs(asked)
    stub = [s for s in drawn.steps if s.assumed]
    assert len(stub) == 1 and stub[0].text == "Not stated"
    assert not has_errors(check_shape(drawn))


def test_a_question_that_quotes_the_decisions_passage_counts_without_naming_it():
    one = [Flow(from_id="d", to_id="y", label="Yes")]
    by_quote = decision(one, [Question(text="What if not?", quote="OK")])
    by_quote.steps = [s for s in by_quote.steps if s.id != "n"]
    assert not has_errors(check_shape(by_quote))

    elsewhere = decision(one, [Question(text="What if not?", quote="something else entirely")])
    elsewhere.steps = [s for s in elsewhere.steps if s.id != "n"]
    assert "one-exit-decision" in codes(check_shape(elsewhere))

    named_other = decision(one, [Question(about="a", text="What if not?", quote="ok")])
    named_other.steps = [s for s in named_other.steps if s.id != "n"]
    assert "one-exit-decision" in codes(check_shape(named_other))  # it names a different step, so it is about that step


def test_start_and_end_take_the_lane_next_to_them():
    from cursus.model import Lane, settle

    p = simple(lanes=[Lane(id="x", name="X")])
    p.steps[1].lane = "x"
    assert "no-lane" in codes(check_shape(p))
    settle(p)
    assert [s.lane for s in p.steps] == ["x", "x", "x"] and check_shape(p) == []

    q = simple(lanes=[Lane(id="x", name="X")])  # a real step with no lane is still a fault: code cannot know whose it is
    assert "no-lane" in codes(check_shape(settle(q)))


def test_lanes_all_or_nothing():
    from cursus.model import Lane

    p = simple(lanes=[Lane(id="x", name="X")])
    assert "no-lane" in codes(check_shape(p))
    p = simple()
    p.steps[1].lane = "ghost"
    assert "unknown-lane" in codes(check_shape(p))


def test_quote_must_be_in_the_text():
    p = simple()
    assert check_source(p, "First you do it, then stop.") == []
    assert "quote-not-found" in codes(check_source(p, "Nothing of the kind."))
    p.steps[1].quote = ""
    assert "no-quote" in codes(check_source(p, "do it"))
    p.steps[1].assumed = True
    findings = check_source(p, "do it")
    assert not has_errors(findings) and "assumed" in codes(findings, "warning")


def test_quote_matching_forgives_line_breaks_case_and_curly_quotes():
    source = "The manager\n   checks the  claim.\nIt’s then “approved”."
    assert quote_found("the manager checks the claim", source)
    assert quote_found("It's then \"approved\".", source)
    assert not quote_found("the manager approves the claim", source)
    assert not quote_found("", source)
