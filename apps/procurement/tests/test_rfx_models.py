"""Procurement 6.6 - RFx Management model tests.

Load-bearing contracts: per-tenant RFX-/RXR- auto-numbering, the draft->issued->closed
lifecycle verbs that refuse out-of-order moves, derived scoring aggregates that count only
scored questions (possible = 10 x summed weight), clone-as-copy semantics for the template
library, the guarded response status machine (with the cancelled-event freeze), and the
batch map helpers agreeing with the per-object properties.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.core.models import Party
from apps.procurement.models import RfxAnswer, RfxEvent, RfxQuestion, RfxResponse
from apps.procurement.models.RfxManagement.Responses import (
    earned_score_map,
    possible_points_map,
    weighted_percent,
)

pytestmark = pytest.mark.django_db


# -- local factories ---------------------------------------------------------------------------------

def _event(tenant, user=None, **overrides):
    fields = dict(
        tenant=tenant,
        title="Laptop fleet refresh RFP",
        rfx_type="rfp",
        description="Answer every line; attach your proposal.",
        created_by=user,
    )
    fields.update(overrides)
    return RfxEvent.objects.create(**fields)


def _question(event, prompt="What is your lead time?", order=0, weight="1.00",
              answer_type="text", options="", is_scored=True, **overrides):
    fields = dict(
        event=event,
        section="Commercial",
        prompt=prompt,
        help_text="",
        answer_type=answer_type,
        options=options,
        weight=Decimal(weight),
        is_scored=is_scored,
        order=order,
    )
    fields.update(overrides)
    return RfxQuestion.objects.create(**fields)


_SEQ = [0]


def _supplier(tenant):
    _SEQ[0] += 1
    return Party.objects.create(tenant=tenant, name=f"Supplier {_SEQ[0]:03d}",
                                kind="organization")


def _response(event, status="draft", **overrides):
    fields = dict(
        tenant=event.tenant,
        event=event,
        supplier=_supplier(event.tenant),
        status=status,
        notes="Recorded by staff on the supplier's behalf.",
    )
    fields.update(overrides)
    return RfxResponse.objects.create(**fields)


def _answer(response, question, score=None, text="42 units"):
    return RfxAnswer.objects.create(
        response=response, question=question, answer_text=text, score=score)


# -- 1. numbering ------------------------------------------------------------------------------------

def test_rfx_event_number_auto_per_tenant(tenant_a, tenant_b, admin_user):
    a1 = _event(tenant_a, admin_user)
    a2 = _event(tenant_a, admin_user)
    b1 = _event(tenant_b, admin_user)
    assert a1.number == "RFX-00001"
    assert a2.number == "RFX-00002"
    assert b1.number == "RFX-00001"
    assert RfxEvent.objects.filter(tenant=tenant_a, number=a1.number).count() == 1


def test_rfx_event_unique_together_tenant_number(tenant_a, admin_user):
    _event(tenant_a, admin_user, number="RFX-DUP")
    with pytest.raises(IntegrityError):
        _event(tenant_a, admin_user, number="RFX-DUP")


# -- 2. lifecycle ------------------------------------------------------------------------------------

def test_rfx_issue_stamps_issued_at(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    _question(ev)
    assert ev.issue() is True
    ev.refresh_from_db()
    assert ev.status == "issued" and ev.issued_at is not None


def test_rfx_issue_refused_without_questions(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    assert ev.issue() is False
    ev.refresh_from_db()
    assert ev.status == "draft" and ev.issued_at is None


def test_rfx_issue_refused_twice(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    _question(ev)
    assert ev.issue() is True
    assert ev.issue() is False
    ev.refresh_from_db()
    assert ev.status == "issued"


def test_rfx_close_stamps_closed_at_and_refuses_draft(tenant_a, admin_user):
    issued = _event(tenant_a, admin_user)
    _question(issued)
    issued.issue()
    assert issued.close() is True
    issued.refresh_from_db()
    assert issued.status == "closed" and issued.closed_at is not None

    draft = _event(tenant_a, admin_user)
    _question(draft)
    assert draft.close() is False
    draft.refresh_from_db()
    assert draft.status == "draft" and draft.closed_at is None


def test_rfx_cancel_from_draft_and_issued_refused_from_closed(tenant_a, admin_user):
    draft = _event(tenant_a, admin_user)
    assert draft.cancel() is True
    draft.refresh_from_db()
    assert draft.status == "cancelled"

    issued = _event(tenant_a, admin_user)
    _question(issued)
    issued.issue()
    assert issued.cancel() is True
    issued.refresh_from_db()
    assert issued.status == "cancelled"

    closed = _event(tenant_a, admin_user)
    _question(closed)
    closed.issue()
    closed.close()
    assert closed.cancel() is False
    closed.refresh_from_db()
    assert closed.status == "closed"


# -- 3. scoring aggregates ---------------------------------------------------------------------------

def test_rfx_total_weight_and_possible_count_only_scored(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    _question(ev, weight="2.00", order=1)
    _question(ev, weight="3.50", order=2)
    _question(ev, weight="9.99", order=3, is_scored=False)
    assert ev.total_weight == Decimal("5.50")
    assert ev.possible_points == Decimal("55.00")


def test_rfx_scoring_aggregates_zero_on_empty_event(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    assert ev.total_weight == Decimal("0")
    assert ev.possible_points == Decimal("0")


# -- 4. clone_as -------------------------------------------------------------------------------------

def test_rfx_clone_as_copies_header_and_all_questions(tenant_a, admin_user, member_user):
    src = _event(tenant_a, admin_user, is_template=True, title="Master questionnaire",
                 description="Standard boilerplate.")
    _question(src, prompt="Pick a colour", order=1, answer_type="choice",
              options="Red\nGreen\nBlue", weight="2.00")
    _question(src, prompt="Describe delivery plan", order=2, answer_type="longtext",
              weight="3.00")
    _question(src, prompt="Reference links", order=3, is_scored=False, weight="1.00")

    clone = src.clone_as(member_user)

    assert clone.pk != src.pk
    assert clone.tenant_id == src.tenant_id
    assert clone.rfx_type == src.rfx_type
    assert clone.title == "Master questionnaire"
    assert clone.description == "Standard boilerplate."
    assert clone.status == "draft" and clone.is_template is False
    assert clone.created_by == member_user
    assert clone.number.startswith("RFX-") and clone.number != src.number

    def shape(ev):
        return [(q.order, q.answer_type, str(q.weight), q.is_scored, q.prompt, q.options)
                for q in ev.questions.all()]

    assert shape(clone) == shape(src)


def test_rfx_clone_leaves_source_untouched(tenant_a, admin_user, member_user):
    src = _event(tenant_a, admin_user, is_template=True)
    _question(src, order=1)
    _question(src, order=2)
    before = src.questions.count()

    clone = src.clone_as(member_user)
    src.refresh_from_db()

    assert src.status == "draft" and src.is_template is True
    assert src.questions.count() == before == clone.questions.count()
    assert all(q.event_id == src.pk for q in src.questions.all())


# -- 5. RfxQuestion clean / options / max_points ------------------------------------------------------

def test_rfx_question_clean_requires_choice_options(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    blank = RfxQuestion(event=ev, prompt="Pick one", answer_type="choice", options="   ")
    with pytest.raises(ValidationError) as err:
        blank.clean()
    assert "options" in err.value.message_dict


def test_rfx_question_ordered_options_strips_and_blanks_non_choice(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    choice = _question(ev, answer_type="choice", options=" Red \n\n Green\n")
    assert choice.ordered_options() == ["Red", "Green"]
    numeric = _question(ev, answer_type="number", options="")
    numeric.clean()
    assert numeric.ordered_options() == []


def test_rfx_question_max_points_scored_vs_unscored(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    scored = _question(ev, weight="2.50")
    unscored = _question(ev, weight="9.99", is_scored=False)
    assert scored.max_points == Decimal("25.00")
    assert unscored.max_points == Decimal("0")


# -- 6. RfxResponse.submit() -------------------------------------------------------------------------

def test_rfx_response_submit_stamps_while_event_live(tenant_a, admin_user):
    for stage in ("draft", "issued"):
        ev = _event(tenant_a, admin_user, title=f"Live-in-{stage}")
        _question(ev)
        if stage == "issued":
            assert ev.issue() is True
        resp = _response(ev)
        assert resp.submit() is True
        resp.refresh_from_db()
        assert resp.status == "submitted" and resp.submitted_at is not None


def test_rfx_response_submit_refused_when_closed_or_repeated(tenant_a, admin_user):
    closed = _event(tenant_a, admin_user)
    _question(closed)
    closed.issue()
    closed.close()
    resp = _response(closed)
    assert resp.submit() is False
    resp.refresh_from_db()
    assert resp.status == "draft" and resp.submitted_at is None

    open_ev = _event(tenant_a, admin_user, title="Still open")
    _question(open_ev)
    twice = _response(open_ev)
    assert twice.submit() is True
    stamp = twice.submitted_at
    assert twice.submit() is False
    twice.refresh_from_db()
    assert twice.status == "submitted" and twice.submitted_at == stamp


# -- 7. RfxResponse.transition() ---------------------------------------------------------------------

def test_rfx_response_transition_full_legal_flow(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    _question(ev)
    resp = _response(ev)
    assert resp.transition("scored") is False
    assert resp.submit() is True
    assert resp.transition("scored") is False
    assert resp.transition("under_review") is True
    assert resp.transition("scored") is True
    resp.refresh_from_db()
    assert resp.status == "scored"
    assert resp.transition("disqualified") is False
    resp.refresh_from_db()
    assert resp.status == "scored"


def test_rfx_response_disqualified_reinstates_on_live_only(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    _question(ev)
    ev.issue()

    live = _response(ev)
    assert live.submit() is True
    assert live.transition("disqualified") is True
    assert live.is_locked
    assert live.transition("under_review") is True
    live.refresh_from_db()
    assert live.status == "under_review"

    dead = _response(ev)
    assert dead.submit() is True
    dead.transition("disqualified")
    assert ev.cancel() is True
    assert dead.transition("under_review") is False
    dead.refresh_from_db()
    assert dead.status == "disqualified"


def test_rfx_response_transition_to_submitted_needs_live_event(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    _question(ev)
    ev.issue()
    resp = _response(ev)
    ev.close()
    assert resp.transition("submitted") is False
    resp.refresh_from_db()
    assert resp.status == "draft" and resp.submitted_at is None


# -- 8. RfxAnswer.weighted_points --------------------------------------------------------------------

def test_rfx_answer_weighted_points_math_and_nones(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    heavy = _question(ev, prompt="Total price", weight="3.15", order=1)
    light = _question(ev, prompt="Logo quality", weight="1.11", order=2)
    unscored = _question(ev, prompt="Comments", weight="5.00", order=3, is_scored=False)

    resp = _response(ev)
    scored_heavy = _answer(resp, heavy, Decimal("8.33"))
    assert scored_heavy.weighted_points == Decimal("26.24")

    unanswered = _answer(resp, light)
    assert unanswered.weighted_points is None

    ignored = _answer(resp, unscored, Decimal("10"))
    assert ignored.weighted_points is None

    unanswered.score = Decimal("7.00")
    unanswered.save()
    assert resp.earned_points == Decimal("34.01")


# -- 9. batch helpers --------------------------------------------------------------------------------

def test_rfx_batch_maps_match_per_object_properties(tenant_a, admin_user):
    ev1 = _event(tenant_a, admin_user, title="Two-question event")
    q_a = _question(ev1, weight="2.00", order=1)
    q_b = _question(ev1, weight="3.00", order=2)
    ev2 = _event(tenant_a, admin_user, title="Single-question event")
    q_c = _question(ev2, weight="1.00", order=1)

    r1 = _response(ev1)
    _answer(r1, q_a, Decimal("8"))
    _answer(r1, q_b, Decimal("6"))
    r2 = _response(ev1)
    _answer(r2, q_a, Decimal("10"))
    r3 = _response(ev2)
    _answer(r3, q_c, Decimal("5"))

    earned = earned_score_map([r1.pk, r2.pk, r3.pk])
    for resp in (r1, r2, r3):
        assert earned[resp.pk] == resp.earned_points
    assert earned[r1.pk] == Decimal("34.00")

    possible = possible_points_map([ev1.pk, ev2.pk])
    for ev in (ev1, ev2):
        assert possible[ev.pk] == ev.possible_points
    assert possible[ev1.pk] == Decimal("50.00")

    assert weighted_percent(r1.earned_points, ev1.possible_points) \
        == r1.score_percent == Decimal("68.0")


def test_rfx_weighted_percent_none_without_scoreable_content(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    assert ev.possible_points == Decimal("0")
    assert weighted_percent(Decimal("10"), ev.possible_points) is None
    assert weighted_percent(None, Decimal("0")) is None
    assert weighted_percent(Decimal("25"), Decimal("200")) == Decimal("12.5")
    assert earned_score_map([]) == {}
    assert possible_points_map([]) == {}


# -- 10. Meta ordering -------------------------------------------------------------------------------

def test_rfx_meta_orders_questions_by_order_and_answers_by_question(tenant_a, admin_user):
    ev = _event(tenant_a, admin_user)
    late = _question(ev, prompt="Asked second", order=2)
    early = _question(ev, prompt="Asked first", order=0)
    middle = _question(ev, prompt="Asked in the middle", order=1)
    assert [q.pk for q in ev.questions.all()] == [early.pk, middle.pk, late.pk]

    resp = _response(ev)
    a_late = _answer(resp, late, Decimal("5"))
    a_early = _answer(resp, early, Decimal("5"))
    a_middle = _answer(resp, middle, Decimal("5"))
    assert [a.pk for a in resp.answers.all()] == [a_early.pk, a_middle.pk, a_late.pk]
