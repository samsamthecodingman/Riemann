"""Extra faithfulness checks on short model-written items: dates, cite overlap, and
(log-only) dropped negations. Each drops, or warns, deterministically."""
import datetime
import logging

import pytest

from riemann.abstraction import build, checks
from riemann.abstraction.build import _clean_essentials, _validate_key_fact
from riemann.abstraction.model import Node

SRC = "The report is due on Friday 14 November at 5 pm. Late work is not accepted unless you have an approved extension."


def _leaf(text=SRC, id_="l1"):
    return Node(id=id_, depth=1, text=text, source_span=(0, len(text)), is_leaf=True, words=len(text.split()))


def _ess(items, text=SRC):
    leaf = _leaf(text)
    return _clean_essentials(items, {"l1": leaf}, {"l1"})


# --- (a) dates ------------------------------------------------------------------------------

def test_a_wrong_weekday_drops_the_essential():
    out = _ess([{"label": "Due", "value": "Monday 14 November", "cites": ["l1"]}, {"label": "Due2", "value": "Friday 14 November", "cites": ["l1"]}])
    assert [e.label for e in out] == ["Due2"]


def test_a_wrong_month_drops_the_essential():
    out = _ess([{"label": "Due", "value": "14 October", "cites": ["l1"]}, {"label": "Due2", "value": "14 Nov", "cites": ["l1"]}])
    assert [e.label for e in out] == ["Due2"]


def test_abbreviated_weekdays_and_months_match_their_full_names_either_way():
    assert checks.dates_ok("Fri 14 Nov", SRC) and checks.dates_ok("Friday 14 November", "due Fri 14 Nov")
    assert not checks.dates_ok("Thu 14 Nov", SRC)


def test_the_modal_may_and_plain_words_are_not_dates():
    assert checks.dates_ok("You may submit it early and sat down to check", "nothing about dates here")
    assert not checks.dates_ok("Due 5 May", "due 5 June")
    assert checks.dates_ok("Due 5 May", "due 5 May")
    assert checks.dates_ok("the sun is out on Sunday", "meet on Sunday")


def test_numeric_dates_in_the_source_count_for_the_month():
    assert checks.dates_ok("14 November", "due 14/11/2025") and checks.dates_ok("11 December", "due 12/11/2025")
    assert checks.dates_ok("14 November", "due 2025-11-14")
    assert not checks.dates_ok("14 March", "due 14/11/2025")


def test_key_facts_get_the_same_date_check():
    nodes = {"l1": _leaf()}
    ok = {"big": "Friday", "detail": "the report is due", "cites": ["l1"]}
    bad = {"big": "Tuesday", "detail": "the report is due", "cites": ["l1"]}
    assert _validate_key_fact(ok, nodes, ["l1"]) is not None
    assert _validate_key_fact(bad, nodes, ["l1"]) is None


def test_an_essential_with_a_weekday_but_no_valid_cite_is_dropped_like_one_with_a_number():
    out = _clean_essentials([{"label": "Due", "value": "Friday", "cites": ["nope"]}, {"label": "Rules", "value": "see the brief", "cites": []}], {"l1": _leaf()}, {"l1"})
    assert [e.label for e in out] == ["Rules"]


# --- (b) cite overlap -----------------------------------------------------------------------

def test_an_essential_sharing_no_words_with_its_cited_leaf_is_dropped():
    out = _ess(
        [
            {"label": "Penalty", "value": "late work loses marks", "cites": ["l1"]},  # paraphrase: shares "late", "work"
            {"label": "Format", "value": "single PDF via Moodle", "cites": ["l1"]},  # nothing here says so
        ]
    )
    assert [e.label for e in out] == ["Penalty"]


def test_not_stated_is_exempt_from_the_overlap_check():
    out = _ess([{"label": "Weight", "value": "not stated", "cites": []}, {"label": "Weight2", "value": "not stated", "cites": ["l1"]}])
    assert [e.label for e in out] == ["Weight", "Weight2"]


def test_a_value_with_no_content_words_is_left_to_the_other_checks():
    assert checks.overlap_ok("5 pm", "something unrelated entirely", 0.5) is False  # "5" is a content token
    assert checks.overlap_ok("it is", "anything", 0.9) is True


def test_a_key_fact_must_overlap_its_cites():
    nodes = {"l1": _leaf()}
    assert _validate_key_fact({"big": "5 pm", "detail": "the report is due on Friday", "cites": ["l1"]}, nodes, ["l1"]) is not None
    unrelated = {"big": "5 pm", "detail": "kangaroos jump over fences nightly", "cites": ["l1"]}
    assert _validate_key_fact(unrelated, nodes, ["l1"]) is None


def test_overlap_floor_constants_exist_and_are_sane():
    assert 0.2 <= build.CITE_OVERLAP_FLOOR <= 0.5


def test_stemming_lets_paraphrases_through():
    assert checks.overlap("Submission via Moodle", "You must submit through the Moodle page")[0] >= 2


# --- (c) qualifiers: warn, never drop -------------------------------------------------------

def test_a_dropped_negation_warns_but_keeps_the_item():
    warnings = []
    leaf = _leaf()
    out = _clean_essentials(
        [{"label": "Late work", "value": "Late work is accepted", "cites": ["l1"]}],
        {"l1": leaf},
        {"l1"},
        warn=lambda kind, where, detail: warnings.append((kind, where, detail)),
    )
    assert [e.label for e in out] == ["Late work"]
    assert len(warnings) == 1
    kind, where, detail = warnings[0]
    assert kind == "qualifier_dropped" and "Late work" in where and detail["qualifier"] == "not"
    assert "not accepted" in detail["sentence"]


def test_a_kept_qualifier_does_not_warn():
    warnings = []
    _clean_essentials(
        [{"label": "Late work", "value": "Late work is not accepted without an extension", "cites": ["l1"]}],
        {"l1": _leaf()}, {"l1"}, warn=lambda *a: warnings.append(a),
    )
    assert warnings == []


def test_the_label_and_synonyms_of_no_count_as_keeping_the_qualifier():
    warnings = []
    leaf = _leaf("Generative AI tools may be used to explain a concept, but not to write the report. Late submissions lose 5% a day and no submission is accepted after 7 days.")
    _clean_essentials(
        [
            {"label": "Not allowed", "value": "Generative AI to write the report", "cites": ["l1"]},  # the label says not
            {"label": "Late", "value": "5% a day lost, none accepted after 7 days", "cites": ["l1"]},  # none = no
        ],
        {"l1": leaf}, {"l1"}, warn=lambda *a: warnings.append(a),
    )
    assert warnings == []


def test_qualifier_detection_cases():
    q = checks.qualifier_dropped
    assert q("Staff must share passwords with managers", "Staff must not share passwords with managers or others.")[0] == "must not"
    assert q("Refunds are given within 30 days", "Refunds are given within 30 days unless the item is used.")[0] == "unless"
    assert q("Everyone attends the workshop", "Everyone except the interns attends the workshop.")[0] == "except"
    assert q("Submit by Friday", "You may submit by Friday only if you have approval.")[0] == "only if"
    assert q("Submit the report on Friday", "Submit the report on Friday.") is None
    assert q("Late work penalty", "Unrelated sentence with not in it.") is None  # not the sentence the item is about
    assert q("one", "x") is None


def test_the_warning_is_logged_by_the_python_logger(caplog):
    with caplog.at_level(logging.WARNING, logger="riemann"):
        _clean_essentials(
            [{"label": "Late work", "value": "Late work is accepted", "cites": ["l1"]}],
            {"l1": _leaf()}, {"l1"}, warn=build.log_warning,
        )
    assert any("qualifier_dropped" in r.getMessage() for r in caplog.records)


async def test_a_build_reports_the_warning_as_a_non_fatal_event_in_its_history():
    from riemann.abstraction.summarise import FakeSummariser
    import json

    brief = "# Brief\n\n" + "Late work is not accepted unless you have an approved extension. " * 3 + "\n\n" + "Other words fill this paragraph out for a while. " * 30

    class Sloppy(FakeSummariser):
        async def summarise(self, prompt, system):
            raw = await super().summarise(prompt, system)
            if "Task: overview" in prompt:
                d = json.loads(raw)
                cites = d["essentials"][0]["cites"]
                d["essentials"] = [{"label": "Late work", "value": "Late work is accepted with an approved extension", "cites": cites}]
                raw = json.dumps(d)
            return raw

    b = build.start_build("warn-build", "Brief", brief, Sloppy())
    await b.task
    assert b.tree.status == "done"
    warnings = [data for name, data in b.history if name == "warning"]
    assert warnings and warnings[0]["kind"] == "qualifier_dropped"
    assert b.history[-1][0] == "done"  # the build still finished
    assert [e.label for e in b.tree.overview.essentials] == ["Late work"]
