"""Procurement 6.6 - RFx Management view flows (builder, lifecycle, comparison, library,
scoring, response repository).

Every surface is exercised through rendered bytes, context keys and real redirects. The
load-bearing contracts: template-library rows never leak into the event register, the lifecycle
verbs are POST-only and guarded (issue once, close/cancel/delete refusals, reorder locks on
issue), the comparison matrix ranks admissible submissions best-first, response recording
pre-creates one blank answer per question, and the repository keeps every submitted bid.
"""
from decimal import Decimal

import pytest

from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party
from apps.procurement.models import RfxAnswer, RfxEvent, RfxQuestion, RfxResponse

pytestmark = pytest.mark.django_db


def _party(tenant, name):
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _event(tenant, **overrides):
    fields = dict(tenant=tenant, rfx_type="rfp", title="RFx view-flow event", status="draft")
    fields.update(overrides)
    return RfxEvent.objects.create(**fields)


def _question(event, prompt="Describe your approach", order=1, weight="1.00", **overrides):
    fields = dict(event=event, prompt=prompt, order=order, weight=Decimal(weight),
                  answer_type="text")
    fields.update(overrides)
    return RfxQuestion.objects.create(**fields)


def _response(tenant, event, party, **overrides):
    fields = dict(tenant=tenant, event=event, supplier=party)
    fields.update(overrides)
    return RfxResponse.objects.create(**fields)


def _answer(response, question, text="", score=None):
    return RfxAnswer.objects.create(response=response, question=question,
                                    answer_text=text, score=score)


def _formset(prefix, total, initial=0):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "60",
    }


def _header(**overrides):
    fields = {"title": "Server room upgrade", "rfx_type": "rfp", "description": "",
              "requisition": "", "response_due": ""}
    fields.update(overrides)
    return fields


def _flash(resp):
    return [str(m) for m in get_messages(resp.wsgi_request)]


def _pk_from_url(url):
    return int(url.rstrip("/").rsplit("/", 1)[-1])


# -- event register --------------------------------------------------------------------------------


def test_rfx_view_list_hides_templates_searches_titles_and_filters_status(client_a, tenant_a):
    live = _event(tenant_a, title="Campus network RFP")
    _event(tenant_a, is_template=True, title="Blueprint network RFP")
    closed = _event(tenant_a, title="Fleet renewal RFQ", status="closed")

    r = client_a.get(reverse("procurement:rfx_list"))
    assert r.status_code == 200
    body = r.content.decode()
    assert live.title in body and closed.title in body
    assert "Blueprint network RFP" not in body

    body = client_a.get(reverse("procurement:rfx_list"), {"q": "network"}).content.decode()
    assert live.title in body
    assert closed.title not in body

    body = client_a.get(reverse("procurement:rfx_list"), {"status": "closed"}).content.decode()
    assert closed.title in body and live.title not in body


def test_rfx_view_list_compare_mode_shows_only_twice_submitted_events(client_a, tenant_a):
    thin = _event(tenant_a, title="Single-bidder event")
    rich = _event(tenant_a, title="Contested event")
    alpha, beta, gamma = (_party(tenant_a, n) for n in ("Alpha Co", "Beta Co", "Gamma Co"))
    _response(tenant_a, thin, alpha, status="submitted")
    _response(tenant_a, rich, alpha, status="submitted")
    _response(tenant_a, rich, beta, status="under_review")
    _response(tenant_a, rich, gamma, status="draft")

    r = client_a.get(reverse("procurement:rfx_list"), {"compare": "1"})
    assert r.status_code == 200
    body = r.content.decode()
    assert rich.title in body
    assert thin.title not in body
    assert "two or more submitted responses" in body


# -- event detail ----------------------------------------------------------------------------------


def test_rfx_view_detail_context_keys_and_n_comparable_gating(client_a, tenant_a):
    event = _event(tenant_a)
    q1 = _question(event, prompt="First?", order=1)
    q2 = _question(event, prompt="Second?", order=2, weight="2.00")
    alpha = _party(tenant_a, "Alpha Co")
    sub = _response(tenant_a, event, alpha, status="submitted")
    review = _response(tenant_a, event, _party(tenant_a, "Beta Co"), status="under_review")
    dq = _response(tenant_a, event, _party(tenant_a, "Gamma Co"), status="disqualified")
    working = _response(tenant_a, event, _party(tenant_a, "Delta Co"), status="draft")

    r = client_a.get(reverse("procurement:rfx_detail", args=[event.pk]))
    assert r.status_code == 200
    assert r.context["obj"].pk == event.pk
    assert [q.pk for q in r.context["questions"]] == [q1.pk, q2.pk]
    shown = {row["response"].pk for row in r.context["response_rows"]}
    assert shown == {sub.pk, review.pk, dq.pk}
    assert working.pk not in shown
    assert r.context["n_comparable"] == 2
    assert r.context["possible_points"] == Decimal("30.00")
    compare_url = reverse("procurement:rfx_compare", args=[event.pk])
    assert compare_url in r.content.decode()

    thin = _event(tenant_a, title="Thin event")
    _question(thin)
    _response(tenant_a, thin, alpha, status="submitted")
    r2 = client_a.get(reverse("procurement:rfx_detail", args=[thin.pk]))
    assert r2.context["n_comparable"] == 1
    assert reverse("procurement:rfx_compare", args=[thin.pk]) not in r2.content.decode()


# -- questionnaire builder -------------------------------------------------------------------------


def test_rfx_view_builder_get_renders_formset_and_post_builds_draft_with_questions(
        client_a, tenant_a, admin_user):
    r = client_a.get(reverse("procurement:rfx_create"))
    assert r.status_code == 200
    assert b'name="questions-TOTAL_FORMS"' in r.content
    assert r.context["is_edit"] is False

    data = _header()
    data.update(_formset("questions", 2))
    data.update({
        "questions-0-section": "Technical",
        "questions-0-prompt": "Describe your hardware roadmap",
        "questions-0-answer_type": "text",
        "questions-0-weight": "2.00",
        "questions-0-is_scored": "on",
        "questions-1-prompt": "What is your lead time?",
        "questions-1-answer_type": "text",
        "questions-1-weight": "1.00",
    })
    r = client_a.post(reverse("procurement:rfx_create"), data)
    assert r.status_code == 302
    event = RfxEvent.objects.get(tenant=tenant_a, title="Server room upgrade")
    assert r.url == reverse("procurement:rfx_detail", args=[event.pk])
    assert event.status == "draft" and event.created_by == admin_user
    assert event.number.startswith("RFX-")
    questions = list(event.questions.order_by("order"))
    assert [(q.prompt, q.order, q.weight) for q in questions] == [
        ("Describe your hardware roadmap", 1, Decimal("2.00")),
        ("What is your lead time?", 2, Decimal("1.00")),
    ]
    assert AuditLog.objects.filter(object_id=event.pk, action="create").exists()


def test_rfx_view_edit_refuses_issued_and_updates_draft_appending_after_max_order(
        client_a, tenant_a):
    locked = _event(tenant_a, status="issued")
    r = client_a.get(reverse("procurement:rfx_edit", args=[locked.pk]))
    assert r.status_code == 302
    assert r.url == reverse("procurement:rfx_detail", args=[locked.pk])
    assert any("only drafts can be edited" in m.lower() for m in _flash(r))

    draft = _event(tenant_a)
    old = _question(draft, prompt="Original prompt", order=3)
    data = _header(title="Renegotiated scope", description="Updated instructions")
    data.update(_formset("questions", 2, initial=1))
    data.update({
        "questions-0-id": str(old.pk),
        "questions-0-prompt": "Rewritten prompt",
        "questions-0-answer_type": "text",
        "questions-0-weight": "1.00",
        "questions-1-prompt": "Appended after the existing max",
        "questions-1-answer_type": "text",
        "questions-1-weight": "2.00",
    })
    r = client_a.post(reverse("procurement:rfx_edit", args=[draft.pk]), data)
    assert r.status_code == 302
    draft.refresh_from_db()
    assert draft.title == "Renegotiated scope"
    assert draft.description == "Updated instructions"
    questions = list(draft.questions.order_by("order"))
    assert [(q.prompt, q.order) for q in questions] == [
        ("Rewritten prompt", 3),
        ("Appended after the existing max", 4),
    ]


# -- lifecycle verbs -------------------------------------------------------------------------------


def test_rfx_view_issue_stamps_once_audits_and_get_is_inert(client_a, tenant_a):
    event = _event(tenant_a)
    _question(event)
    url = reverse("procurement:rfx_issue", args=[event.pk])

    r = client_a.post(url)
    assert r.status_code == 302
    event.refresh_from_db()
    assert event.status == "issued" and event.issued_at is not None
    assert AuditLog.objects.filter(object_id=event.pk, action="issue").exists()

    stamp = event.issued_at
    r = client_a.post(url)
    assert r.status_code == 302
    event.refresh_from_db()
    assert event.status == "issued" and event.issued_at == stamp
    assert any("at least one question" in m for m in _flash(r))

    fresh = _event(tenant_a)
    _question(fresh)
    r = client_a.get(reverse("procurement:rfx_issue", args=[fresh.pk]))
    assert r.status_code in (302, 405)
    fresh.refresh_from_db()
    assert fresh.status == "draft" and fresh.issued_at is None


def test_rfx_view_close_and_cancel_transitions_with_refusals(client_a, tenant_a):
    event = _event(tenant_a)
    _question(event)
    close_url = reverse("procurement:rfx_close", args=[event.pk])

    r = client_a.post(close_url)
    assert r.status_code == 302
    event.refresh_from_db()
    assert event.status == "draft"
    assert any("Only issued events" in m for m in _flash(r))

    assert event.issue()
    r = client_a.post(close_url)
    assert r.status_code == 302
    event.refresh_from_db()
    assert event.status == "closed" and event.closed_at is not None
    assert AuditLog.objects.filter(object_id=event.pk, action="close").exists()

    r = client_a.post(reverse("procurement:rfx_cancel", args=[event.pk]))
    event.refresh_from_db()
    assert event.status == "closed"

    other = _event(tenant_a)
    r = client_a.post(reverse("procurement:rfx_cancel", args=[other.pk]))
    assert r.status_code == 302
    other.refresh_from_db()
    assert other.status == "cancelled"
    assert AuditLog.objects.filter(object_id=other.pk, action="cancel").exists()


def test_rfx_view_delete_removes_draft_but_keeps_issued(client_a, tenant_a):
    draft = _event(tenant_a)
    _question(draft)
    r = client_a.post(reverse("procurement:rfx_delete", args=[draft.pk]))
    assert r.status_code == 302
    assert r.url == reverse("procurement:rfx_list")
    assert not RfxEvent.objects.filter(pk=draft.pk).exists()

    issued = _event(tenant_a, status="issued")
    _question(issued)
    r = client_a.post(reverse("procurement:rfx_delete", args=[issued.pk]))
    assert r.status_code == 302
    assert RfxEvent.objects.filter(pk=issued.pk).exists()
    assert any("Only draft or cancelled" in m for m in _flash(r))


# -- questionnaire reorder ---------------------------------------------------------------------------


def test_rfx_view_question_move_swaps_down_and_rejects_unknown_direction(client_a, tenant_a):
    event = _event(tenant_a)
    qa = _question(event, prompt="First", order=1)
    qb = _question(event, prompt="Second", order=2)

    r = client_a.post(reverse("procurement:rfx_question_move", args=[event.pk, qa.pk]),
                      {"direction": "down"})
    assert r.status_code == 302
    qa.refresh_from_db()
    qb.refresh_from_db()
    assert (qa.order, qb.order) == (2, 1)
    assert list(event.questions.order_by("order", "id")) == [qb, qa]

    r = client_a.post(reverse("procurement:rfx_question_move", args=[event.pk, qa.pk]),
                      {"direction": "sideways"})
    assert r.status_code == 302
    assert any("Unknown move direction" in m for m in _flash(r))
    qa.refresh_from_db()
    qb.refresh_from_db()
    assert (qa.order, qb.order) == (2, 1)


def test_rfx_view_question_move_locked_once_issued(client_a, tenant_a):
    event = _event(tenant_a, status="issued")
    qa = _question(event, prompt="First", order=1)
    qb = _question(event, prompt="Second", order=2)

    r = client_a.post(reverse("procurement:rfx_question_move", args=[event.pk, qa.pk]),
                      {"direction": "down"})
    assert r.status_code == 302
    assert any("locked" in m.lower() for m in _flash(r))
    qa.refresh_from_db()
    qb.refresh_from_db()
    assert (qa.order, qb.order) == (1, 2)


# -- side-by-side comparison -----------------------------------------------------------------------


def test_rfx_view_compare_matrix_admissible_only_best_first(client_a, tenant_a):
    event = _event(tenant_a)
    qa = _question(event, prompt="Architecture", order=1, weight="2.00")
    qb = _question(event, prompt="Lead time", order=2)
    lo = _response(tenant_a, event, _party(tenant_a, "Beta Co"), status="under_review")
    hi = _response(tenant_a, event, _party(tenant_a, "Alpha Co"), status="submitted")
    RfxResponse.objects.filter(pk=lo.pk).update(
        created_at=timezone.now() - timezone.timedelta(minutes=5))
    a_hi_1 = _answer(hi, qa, "Solid plan", Decimal("8"))
    _answer(hi, qb, "Six weeks", Decimal("8"))
    a_lo_1 = _answer(lo, qa, "Partial", Decimal("5"))
    _answer(lo, qb, "Eight weeks", Decimal("4"))
    dq = _response(tenant_a, event, _party(tenant_a, "Gamma Co"), status="disqualified")
    dr = _response(tenant_a, event, _party(tenant_a, "Delta Co"), status="draft")

    r = client_a.get(reverse("procurement:rfx_compare", args=[event.pk]))
    assert r.status_code == 200
    scored = r.context["scored_rows"]
    assert [row["response"].pk for row in scored] == [hi.pk, lo.pk]
    assert [row["pct"] for row in scored] == [Decimal("80.0"), Decimal("46.7")]
    assert [resp.pk for resp in r.context["responses"]] == [hi.pk, lo.pk]
    matrix = r.context["matrix"]
    assert [row["question"].pk for row in matrix] == [qa.pk, qb.pk]
    assert matrix[0]["cells"] == [a_hi_1, a_lo_1]
    body = r.content.decode()
    assert "Alpha Co" in body and "Beta Co" in body
    assert dq.supplier.name not in body and dr.supplier.name not in body


def test_rfx_view_compare_empty_state_without_admissible_rows(client_a, tenant_a):
    event = _event(tenant_a)
    _question(event)
    _response(tenant_a, event, _party(tenant_a, "Alpha Co"), status="draft")
    _response(tenant_a, event, _party(tenant_a, "Beta Co"), status="disqualified")

    r = client_a.get(reverse("procurement:rfx_compare", args=[event.pk]))
    assert r.status_code == 200
    assert r.context["responses"] == []
    assert "Nothing to compare yet" in r.content.decode()


# -- template library ------------------------------------------------------------------------------


def test_rfx_view_library_lists_template_rows_only(client_a, tenant_a):
    tmpl = _event(tenant_a, is_template=True, title="Cloud migration blueprint")
    _question(tmpl, order=1)
    _question(tmpl, order=2)
    real = _event(tenant_a, title="Live cloud migration RFP")
    _question(real)

    r = client_a.get(reverse("procurement:rfx_library"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Cloud migration blueprint" in body
    assert "Live cloud migration RFP" not in body


def test_rfx_view_clone_copies_blueprint_into_draft_and_get_is_inert(
        client_a, tenant_a, admin_user):
    tmpl = _event(tenant_a, is_template=True, title="Cloud migration blueprint")
    _question(tmpl, prompt="Uptime targets?", order=1, weight="2.00")
    _question(tmpl, prompt="References?", order=2)

    r = client_a.get(reverse("procurement:rfx_clone", args=[tmpl.pk]))
    assert r.status_code in (302, 405)
    assert RfxEvent.objects.filter(
        tenant=tenant_a, is_template=False, title=tmpl.title).count() == 0

    r = client_a.post(reverse("procurement:rfx_clone", args=[tmpl.pk]))
    assert r.status_code == 302
    clone = RfxEvent.objects.get(pk=_pk_from_url(r.url))
    assert clone.is_template is False and clone.status == "draft"
    assert clone.created_by == admin_user
    assert clone.pk != tmpl.pk
    questions = list(clone.questions.order_by("order"))
    assert [(q.prompt, q.order, q.weight) for q in questions] == [
        ("Uptime targets?", 1, Decimal("2.00")),
        ("References?", 2, Decimal("1.00")),
    ]
    audit = AuditLog.objects.filter(object_id=clone.pk, action="create").latest("id")
    assert audit.changes.get("from_template") == tmpl.number


# -- scoring leaderboard ---------------------------------------------------------------------------


def test_rfx_view_scoring_leaderboard_ranked_searched_and_paginated(member_client, tenant_a):
    top_ev = _event(tenant_a, title="Alpha event")
    top_q = _question(top_ev)
    low_ev = _event(tenant_a, title="Beta event")
    low_q = _question(low_ev)
    winner = _response(tenant_a, top_ev, _party(tenant_a, "Alpha Logistics"),
                       status="submitted")
    _answer(winner, top_q, score=Decimal("9"))
    runner = _response(tenant_a, low_ev, _party(tenant_a, "Beta Logistics"), status="scored")
    _answer(runner, low_q, score=Decimal("6"))
    _response(tenant_a, low_ev, _party(tenant_a, "Gamma Logistics"), status="draft")
    _response(tenant_a, low_ev, _party(tenant_a, "Delta Logistics"), status="disqualified")

    url = reverse("procurement:rfx_scoring")
    r = member_client.get(url)
    assert r.status_code == 200
    assert "page_obj" in r.context
    rows = r.context["page_obj"].object_list
    assert [row["response"].pk for row in rows] == [winner.pk, runner.pk]
    assert [row["pct"] for row in rows] == [Decimal("90.0"), Decimal("60.0")]

    r = member_client.get(url, {"q": "Alpha Logistics"})
    assert [row["response"].pk
            for row in r.context["page_obj"].object_list] == [winner.pk]
    r = member_client.get(url, {"q": "Beta event"})
    assert [row["response"].pk
            for row in r.context["page_obj"].object_list] == [runner.pk]
    r = member_client.get(url, {"q": runner.number})
    assert [row["response"].pk
            for row in r.context["page_obj"].object_list] == [runner.pk]


# -- response collection ---------------------------------------------------------------------------


def test_rfx_view_response_create_records_and_precreates_answer_grid(
        client_a, tenant_a, admin_user):
    event = _event(tenant_a, status="issued")
    qa = _question(event, prompt="Architecture", order=1, weight="2.00")
    qb = _question(event, prompt="Pricing", order=2)
    supplier = _party(tenant_a, "Alpha Co")

    r = client_a.post(reverse("procurement:rfx_response_create"),
                      {"event": str(event.pk), "supplier": str(supplier.pk),
                       "notes": "Courier-delivered proposal"})
    assert r.status_code == 302
    resp = RfxResponse.objects.get(event=event, supplier=supplier)
    assert r.url == reverse("procurement:rfx_response_detail", args=[resp.pk])
    assert resp.status == "draft" and resp.recorded_by == admin_user
    grid = list(resp.answers.order_by("question__order"))
    assert [(a.question_id, a.answer_text, a.score) for a in grid] == [
        (qa.pk, "", None),
        (qb.pk, "", None),
    ]
    assert AuditLog.objects.filter(object_id=resp.pk, action="create").exists()


def test_rfx_view_response_create_preselects_event_as_int_initial(client_a, tenant_a):
    event = _event(tenant_a)
    template = _event(tenant_a, is_template=True)
    url = reverse("procurement:rfx_response_create")

    r = client_a.get(url, {"event": str(event.pk)})
    assert r.status_code == 200
    initial = r.context["form"].initial.get("event")
    assert isinstance(initial, int) and initial == event.pk

    r = client_a.get(url, {"event": str(template.pk)})
    assert r.status_code == 200
    assert "event" not in r.context["form"].initial

    r = client_a.get(url, {"event": "not-a-number"})
    assert r.status_code == 200
    assert "event" not in r.context["form"].initial


def test_rfx_view_response_create_refuses_duplicates_and_closed_events(client_a, tenant_a):
    event = _event(tenant_a, status="issued")
    _question(event)
    supplier = _party(tenant_a, "Alpha Co")
    payload = {"event": str(event.pk), "supplier": str(supplier.pk), "notes": ""}
    url = reverse("procurement:rfx_response_create")

    assert client_a.post(url, payload).status_code == 302
    r = client_a.post(url, payload)
    assert r.status_code == 200
    assert "already exists" in r.content.decode()
    assert RfxResponse.objects.filter(event=event, supplier=supplier).count() == 1

    closed = _event(tenant_a, title="Closed round", status="closed")
    r = client_a.post(url, {"event": str(closed.pk), "supplier": str(supplier.pk)})
    assert r.status_code == 200
    assert r.context["form"].errors.get("event")
    assert RfxResponse.objects.filter(event=closed).count() == 0


# -- scoring workspace -----------------------------------------------------------------------------


def test_rfx_view_response_edit_saves_scores_and_detail_shows_weighted_pct(client_a, tenant_a):
    event = _event(tenant_a, status="issued")
    qa = _question(event, prompt="Architecture", order=1, weight="2.00")
    qb = _question(event, prompt="Lead time", order=2)
    supplier = _party(tenant_a, "Alpha Co")
    resp = _response(tenant_a, event, supplier, status="submitted")
    a1 = _answer(resp, qa, "Old")
    a2 = _answer(resp, qb, "Old")

    data = {"supplier": str(supplier.pk), "notes": "Strong technical proposal"}
    data.update(_formset("answers", 2, initial=2))
    data.update({
        "answers-0-id": str(a1.pk),
        "answers-0-answer_text": "Roadmap attached",
        "answers-0-score": "8",
        "answers-1-id": str(a2.pk),
        "answers-1-answer_text": "Six weeks",
        "answers-1-score": "8",
    })
    r = client_a.post(reverse("procurement:rfx_response_edit", args=[resp.pk]), data)
    assert r.status_code == 302
    assert r.url == reverse("procurement:rfx_response_detail", args=[resp.pk])
    resp.refresh_from_db()
    assert resp.notes == "Strong technical proposal"
    assert sorted(resp.answers.values_list("score", flat=True)) == [
        Decimal("8.00"), Decimal("8.00")]

    r = client_a.get(r.url)
    assert r.status_code == 200
    assert r.context["score_earned"] == Decimal("24.00")
    assert r.context["score_possible"] == Decimal("30.00")
    assert r.context["score_pct"] == Decimal("80.0")
    assert "80.0%" in r.content.decode()


def test_rfx_view_response_edit_redirects_frozen_or_cancelled_event_rows(client_a, tenant_a):
    event = _event(tenant_a, status="issued")
    _question(event)
    dq = _response(tenant_a, event, _party(tenant_a, "Alpha Co"), status="disqualified")
    r = client_a.get(reverse("procurement:rfx_response_edit", args=[dq.pk]))
    assert r.status_code == 302
    assert r.url == reverse("procurement:rfx_response_detail", args=[dq.pk])
    assert any("frozen" in m.lower() for m in _flash(r))

    dead = _event(tenant_a, status="issued", title="Cancelled round")
    _question(dead)
    resp = _response(tenant_a, dead, _party(tenant_a, "Beta Co"), status="submitted")
    assert dead.cancel()
    r = client_a.get(reverse("procurement:rfx_response_edit", args=[resp.pk]))
    assert r.status_code == 302
    assert r.url == reverse("procurement:rfx_response_detail", args=[resp.pk])
    assert any("frozen" in m.lower() for m in _flash(r))


# -- evaluation lifecycle --------------------------------------------------------------------------


def test_rfx_view_set_status_legal_moves_audited_illegal_refused(client_a, tenant_a):
    event = _event(tenant_a, status="issued")
    _question(event)
    resp = _response(tenant_a, event, _party(tenant_a, "Alpha Co"))
    url = reverse("procurement:rfx_response_set_status", args=[resp.pk])

    r = client_a.post(url, {"to": "submitted"})
    assert r.status_code == 302
    resp.refresh_from_db()
    assert resp.status == "submitted" and resp.submitted_at is not None
    audit = AuditLog.objects.filter(object_id=resp.pk, action="update").latest("id")
    assert audit.changes == {"status": "submitted"}

    r = client_a.post(url, {"to": "scored"})
    assert r.status_code == 302
    resp.refresh_from_db()
    assert resp.status == "submitted"
    assert any("is not a valid move" in m for m in _flash(r))

    r = client_a.post(url, {"to": "warp"})
    assert r.status_code == 302
    resp.refresh_from_db()
    assert resp.status == "submitted"


def test_rfx_view_response_delete_keeps_submitted_repository_intact(client_a, tenant_a):
    event = _event(tenant_a, status="issued")
    question = _question(event)
    alpha = _party(tenant_a, "Alpha Co")
    draft = _response(tenant_a, event, alpha)
    _answer(draft, question)

    r = client_a.post(reverse("procurement:rfx_response_delete", args=[draft.pk]))
    assert r.status_code == 302
    assert r.url == reverse("procurement:rfx_response_list")
    assert not RfxResponse.objects.filter(pk=draft.pk).exists()
    assert RfxAnswer.objects.count() == 0

    beta = _party(tenant_a, "Beta Co")
    live = _response(tenant_a, event, beta, status="submitted")
    _answer(live, question)
    r = client_a.post(reverse("procurement:rfx_response_delete", args=[live.pk]))
    assert r.status_code == 302
    assert RfxResponse.objects.filter(pk=live.pk).exists()
    assert any("only drafts can be deleted" in m.lower() for m in _flash(r))
