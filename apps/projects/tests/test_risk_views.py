"""Projects 7.5 Risk & Issue Management — VIEW tests.

The HTTP layer of the sub-module: the four registers, their derived lenses, the seven verbs'
state machines, and the two computed boards (the analysis matrix + seeded Monte Carlo, the
monitoring strip). Model invariants belong to ``test_risk_models.py`` and form validation to
``test_risk_forms.py``; role gating (403), cross-tenant IDOR (404), CSRF and anonymous access
belong to ``test_risk_security.py``. Every request here is made by a TENANT ADMIN
(``risk_admin_client``), so the only thing that can refuse a verb in this lane is its own
state gate.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success (L8), so every page asserts CONTENT — the row's own ``RSK-``/``RRA-``/``ISS-``/
  ``ESC-`` number — and the pinned lens/choice keys by name.
* **A lens that lies.** ``?band=`` is reconstructed from ``(probability, impact)`` columns (a
  property cannot be filtered), so the test compares the lens against the band arithmetic's
  own answer: the critical fixture's number renders, the low/medium/high ones do not.
  ``?overdue=1`` must equal ``?review_due=1`` (the alias, review I4), ``?top=1`` must order by
  the two columns, and junk enums must fall back to the unfiltered register — never a 500,
  never a silently emptied page (L11).
* **A verb that writes when it should refuse.** Realize/close/reopen, complete, escalate/
  resolve/close are each exercised on both sides, the refusal leaving the row byte-identical.
  The realize→issue bridge is the I1 invariant: exactly one linked issue, seeded from the
  risk's own fields.
* **A simulation that drifts.** The seeded Monte Carlo must be byte-reproducible for the same
  seed (CSRF tokens stripped), its mean must equal the documented draw replicated in-test from
  the same population rule (``cost_impact > 0``, status live, id-ascending — review M9), an
  out-of-range ``?iterations=`` must CLAMP while a valid ``?seed=`` survives (review M4), and
  the monitoring lessons lens must follow ``?project=`` (review I10).

Determinism (L16): every date basis is ``_risk_today()``. Message assertions match ASCII
SUBSTRINGs only (several messages carry U+2014 — a copy edit must not turn into a red suite).

Naming (mandatory): every test is ``test_risk_*``, every module-level helper ``_risk_*``.
Scope: views/urls. Models, forms and permissions belong to the other three lanes.
"""
import re
from decimal import Decimal
from random import Random

import pytest
from django.urls import reverse

from apps.projects.models import IssueEscalation, ProjectIssue, ProjectRisk, RiskResponseAction
from apps.projects.tests.conftest import (
    RISK_PAGE_SIZE,
    _risk,
    _risk_action,
    _risk_escalation,
    _risk_fill_risks,
    _risk_issue,
    _risk_project,
    _risk_today,
)

D = Decimal

CSRF_RE = re.compile(rb'name="csrfmiddlewaretoken" value="[^"]*"')


def _risk_strip_csrf(content):
    return CSRF_RE.sub(b"", content)


# ==============================================================================================
# The four registers — content + pinned context (L8: a 200 alone proves nothing)
# ==============================================================================================

def test_risk_list_renders_register_with_pinned_context(risk_admin_client, risk_low):
    response = risk_admin_client.get(reverse("projects:rsk_list"))
    assert response.status_code == 200
    assert risk_low.number in response.content.decode()
    for key in ("projects", "category_choices", "risk_type_choices", "status_choices",
                "strategy_choices", "band_choices", "owners"):
        assert key in response.context, key


def test_risk_action_list_renders_with_pinned_context(risk_admin_client, risk_action_open):
    response = risk_admin_client.get(reverse("projects:rra_list"))
    assert response.status_code == 200
    assert risk_action_open.number in response.content.decode()
    for key in ("risks", "strategy_choices", "status_choices", "owners"):
        assert key in response.context, key


def test_risk_issue_list_renders_with_pinned_context(risk_admin_client, risk_issue_open):
    response = risk_admin_client.get(reverse("projects:iss_list"))
    assert response.status_code == 200
    assert risk_issue_open.number in response.content.decode()
    for key in ("projects", "severity_choices", "status_choices", "issue_type_choices",
                "owners", "risks"):
        assert key in response.context, key


def test_risk_escalation_list_renders_with_pinned_context(risk_admin_client,
                                                          risk_issue_escalated):
    row = _risk_escalation(risk_issue_escalated, level=3)
    response = risk_admin_client.get(reverse("projects:esc_list"))
    assert response.status_code == 200
    assert row.number in response.content.decode()
    for key in ("issues", "level_choices", "owners"):
        assert key in response.context, key


def test_risk_detail_pages_render_the_row_identity(risk_admin_client, risk_high,
                                                   risk_issue_open, risk_action_open):
    for url_name, obj in (("projects:rsk_detail", risk_high),
                          ("projects:rra_detail", risk_action_open),
                          ("projects:iss_detail", risk_issue_open)):
        response = risk_admin_client.get(reverse(url_name, args=[obj.pk]))
        assert response.status_code == 200, url_name
        assert str(obj) in response.content.decode(), url_name  # L8


def test_risk_escalation_detail_renders_the_path_step(risk_admin_client, risk_issue_escalated):
    response = risk_admin_client.get(
        reverse("projects:esc_detail", args=[risk_issue_escalated.escalations.first().pk]))
    assert response.status_code == 200
    assert str(risk_issue_escalated.escalations.first()) in response.content.decode()


def test_risk_form_pages_render_for_create_and_edit(risk_admin_client, risk_project_a, risk_low):
    create = risk_admin_client.get(reverse("projects:rsk_create"))
    assert create.status_code == 200 and "form" in create.context
    edit = risk_admin_client.get(reverse("projects:rsk_edit", args=[risk_low.pk]))
    assert edit.status_code == 200 and edit.context["form"].instance.pk == risk_low.pk


# ==============================================================================================
# The derived lenses — ?band= / ?top=1 / ?overdue= alias / ?escalated=1 / junk fallback
# ==============================================================================================

def test_risk_band_lens_matches_the_band_arithmetic(risk_admin_client, risk_low, risk_medium,
                                                    risk_high, risk_critical):
    critical = risk_admin_client.get(reverse("projects:rsk_list"), {"band": "critical"})
    body = critical.content.decode()
    assert risk_critical.number in body
    for other in (risk_low, risk_medium, risk_high):
        assert other.number not in body
    low = risk_admin_client.get(reverse("projects:rsk_list"), {"band": "low"})
    low_body = low.content.decode()
    assert risk_low.number in low_body and risk_critical.number not in low_body


def test_risk_band_lens_junk_falls_back_to_the_register(risk_admin_client, risk_low):
    response = risk_admin_client.get(reverse("projects:rsk_list"), {"band": "nope"})
    assert response.status_code == 200
    assert risk_low.number in response.content.decode()


def test_risk_top_lens_orders_by_the_two_columns(risk_admin_client, risk_low, risk_critical):
    body = risk_admin_client.get(
        reverse("projects:rsk_list"), {"top": "1"}).content.decode()
    assert body.index(risk_critical.number) < body.index(risk_low.number)


def test_risk_overdue_alias_equals_review_due_lens(risk_admin_client, risk_overdue, risk_low):
    for param in ("overdue", "review_due"):
        body = risk_admin_client.get(
            reverse("projects:rsk_list"), {param: "1"}).content.decode()
        assert risk_overdue.number in body, param
        assert risk_low.number not in body, param


def test_risk_escalated_lens_narrows_the_issue_log(risk_admin_client, risk_issue_open,
                                                   risk_issue_escalated):
    body = risk_admin_client.get(
        reverse("projects:iss_list"), {"escalated": "1"}).content.decode()
    assert risk_issue_escalated.number in body
    assert risk_issue_open.number not in body


def test_risk_junk_params_never_empty_or_500_the_register(risk_admin_client, risk_low):
    for params in ({"status": "nope"}, {"category": "nope"}, {"project": "0"},
                   {"page": "abc"}, {"page": "9999"}):
        response = risk_admin_client.get(reverse("projects:rsk_list"), params)
        assert response.status_code == 200, params
        assert risk_low.number in response.content.decode(), params
    # A search term that matches nothing legitimately shows the empty state — it only has to
    # stay a 200 (L11's "junk enum never empties a register" does not apply to free text).
    response = risk_admin_client.get(reverse("projects:rsk_list"), {"q": "' --"})
    assert response.status_code == 200


def test_risk_second_page_renders_real_rows(risk_admin_client, risk_project_a, risk_low):
    _risk_fill_risks(risk_low.tenant, risk_project_a, RISK_PAGE_SIZE)  # 1 fixture + 15 = 16 rows
    page1 = risk_admin_client.get(reverse("projects:rsk_list"), {"page": "1"})
    assert "Backlog risk 15" in page1.content.decode()  # newest-first: the fill tops page 1
    page2 = risk_admin_client.get(reverse("projects:rsk_list"), {"page": "2"})
    assert page2.status_code == 200
    assert risk_low.number in page2.content.decode()  # the oldest row lands on page 2


# ==============================================================================================
# The lifecycle verbs — realize / close / reopen (admin) on the risk, complete on the action
# ==============================================================================================

def test_risk_realize_mints_the_linked_issue(risk_admin_client, risk_low):
    response = risk_admin_client.post(reverse("projects:rsk_realize", args=[risk_low.pk]))
    assert response.status_code == 302
    risk_low.refresh_from_db()
    assert risk_low.status == "realized"
    issue = ProjectIssue.objects.get(risk=risk_low)
    assert issue.project_id == risk_low.project_id
    assert issue.severity == "low"  # the risk's own band seeds the issue's severity
    assert issue.title == risk_low.title


def test_risk_realize_twice_is_a_reported_noop(risk_admin_client, risk_low):
    risk_admin_client.post(reverse("projects:rsk_realize", args=[risk_low.pk]))
    risk_admin_client.post(reverse("projects:rsk_realize", args=[risk_low.pk]))
    risk_low.refresh_from_db()
    assert risk_low.status == "realized"
    assert ProjectIssue.objects.filter(risk=risk_low).count() == 1


def test_risk_realize_on_closed_refused(risk_admin_client, risk_closed):
    response = risk_admin_client.post(reverse("projects:rsk_realize", args=[risk_closed.pk]))
    assert response.status_code == 302
    risk_closed.refresh_from_db()
    assert risk_closed.status == "closed"
    assert not ProjectIssue.objects.filter(risk=risk_closed).exists()


def test_risk_close_captures_the_lesson(risk_admin_client, risk_high):
    response = risk_admin_client.post(reverse("projects:rsk_close", args=[risk_high.pk]),
                                      {"lessons_learned": "Double-source the vendor."})
    assert response.status_code == 302
    risk_high.refresh_from_db()
    assert risk_high.status == "closed" and risk_high.closed_at is not None
    assert risk_high.lessons_learned == "Double-source the vendor."


def test_risk_close_twice_refuses_the_second_write(risk_admin_client, risk_high):
    risk_admin_client.post(reverse("projects:rsk_close", args=[risk_high.pk]),
                           {"lessons_learned": "First."})
    closed_at = risk_high.__class__.objects.get(pk=risk_high.pk).closed_at
    response = risk_admin_client.post(reverse("projects:rsk_close", args=[risk_high.pk]),
                                      {"lessons_learned": "Second."})
    assert response.status_code == 302
    risk_high.refresh_from_db()
    assert risk_high.lessons_learned == "First."
    assert risk_high.closed_at == closed_at


def test_risk_reopen_returns_a_closed_risk_to_monitoring(risk_admin_client, risk_closed):
    response = risk_admin_client.post(reverse("projects:rsk_reopen", args=[risk_closed.pk]))
    assert response.status_code == 302
    risk_closed.refresh_from_db()
    assert risk_closed.status == "monitoring" and risk_closed.closed_at is None


def test_risk_reopen_on_a_live_risk_refused(risk_admin_client, risk_low):
    response = risk_admin_client.post(reverse("projects:rsk_reopen", args=[risk_low.pk]))
    assert response.status_code == 302
    risk_low.refresh_from_db()
    assert risk_low.status == "identified"


def test_risk_edit_refuses_a_locked_row(risk_admin_client, risk_realized):
    response = risk_admin_client.get(reverse("projects:rsk_edit", args=[risk_realized.pk]))
    assert response.status_code == 302  # redirected back with the frozen-evidence message
    risk_realized.refresh_from_db()
    assert risk_realized.status == "realized"


def test_risk_complete_stamps_exactly_once(risk_admin_client, risk_action_open):
    risk_admin_client.post(reverse("projects:rra_complete", args=[risk_action_open.pk]))
    first = RiskResponseAction.objects.get(pk=risk_action_open.pk)
    assert first.status == "completed" and first.completed_at is not None
    risk_admin_client.post(reverse("projects:rra_complete", args=[risk_action_open.pk]))
    second = RiskResponseAction.objects.get(pk=risk_action_open.pk)
    assert second.completed_at == first.completed_at  # the stamp is written once


# ==============================================================================================
# Issue verbs — escalate / resolve / close
# ==============================================================================================

def test_risk_escalate_bumps_the_level_and_mints_the_row(risk_admin_client, risk_issue_open):
    response = risk_admin_client.post(
        reverse("projects:iss_escalate", args=[risk_issue_open.pk]),
        {"level": "2", "reason": "Blocked beyond the delivery team.", "target_role": "PM"})
    assert response.status_code == 302
    risk_issue_open.refresh_from_db()
    assert risk_issue_open.escalation_level == 2
    assert risk_issue_open.escalated_at is not None
    row = risk_issue_open.escalations.get()
    assert row.level == 2 and row.escalated_by_id is not None


def test_risk_escalate_on_a_resolved_issue_refused(risk_admin_client, risk_issue_resolved):
    response = risk_admin_client.post(
        reverse("projects:iss_escalate", args=[risk_issue_resolved.pk]),
        {"level": "3", "reason": "Too late."})
    assert response.status_code == 302
    risk_issue_resolved.refresh_from_db()
    assert risk_issue_resolved.escalation_level == 0
    assert not risk_issue_resolved.escalations.exists()


def test_risk_resolve_stamps_the_evidence_once(risk_admin_client, risk_issue_open):
    response = risk_admin_client.post(
        reverse("projects:iss_resolve", args=[risk_issue_open.pk]),
        {"root_cause": "No monitoring on the queue.", "resolution_note": "Alarm added."})
    assert response.status_code == 302
    risk_issue_open.refresh_from_db()
    assert risk_issue_open.status == "resolved"
    assert risk_issue_open.resolved_by_id is not None
    assert risk_issue_open.resolved_at is not None
    assert risk_issue_open.resolution_note == "Alarm added."
    risk_admin_client.post(reverse("projects:iss_resolve", args=[risk_issue_open.pk]),
                           {"resolution_note": "Overwrite attempt."})
    risk_issue_open.refresh_from_db()
    assert risk_issue_open.resolution_note == "Alarm added."  # the verb refuses a replay


def test_risk_issue_close_only_from_resolved(risk_admin_client, risk_issue_open,
                                             risk_issue_resolved):
    risk_admin_client.post(reverse("projects:iss_close", args=[risk_issue_open.pk]))
    risk_issue_open.refresh_from_db()
    assert risk_issue_open.status == "open"  # an open issue cannot be closed
    risk_admin_client.post(reverse("projects:iss_close", args=[risk_issue_resolved.pk]))
    risk_issue_resolved.refresh_from_db()
    assert risk_issue_resolved.status == "closed"


# ==============================================================================================
# The computed boards — analysis (matrix + Monte Carlo) and monitoring
# ==============================================================================================

def test_risk_analysis_board_renders_matrix_and_emv(risk_admin_client, risk_critical, risk_low):
    response = risk_admin_client.get(reverse("projects:risk_analysis"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Probability" in body and "Largest cell" in body
    for key in ("matrix", "matrix_max", "emv_rows", "emv_total", "projects"):
        assert key in response.context, key


def test_risk_analysis_seed_is_byte_reproducible(risk_admin_client, risk_sim_high,
                                                 risk_sim_rare):
    url = reverse("projects:risk_analysis") + "?seed=7&iterations=200"
    first = _risk_strip_csrf(risk_admin_client.post(url).content)
    second = _risk_strip_csrf(risk_admin_client.post(url).content)
    assert first == second


def test_risk_analysis_mean_matches_the_documented_draw(risk_admin_client, risk_sim_high,
                                                        risk_sim_rare):
    """Replicate the as-built draw over the SAME population rule — ``cost_impact > 0``, status
    live, id-ascending (risk_sim_realized/risk_sim_zero_cost are not pulled, so they are not in
    the DB at all) — and the page's Mean must equal it to the cent."""
    url = reverse("projects:risk_analysis") + "?seed=123&iterations=500"
    body = risk_admin_client.post(url).content.decode()
    draws = [(D("1000.00"), 0.9), (D("500.00"), 0.1)]  # sim_high then sim_rare, id-ascending
    rng = Random(123)
    samples = [sum(cost for cost, p in draws if rng.random() < p) for _ in range(500)]
    mean = (sum(samples) / len(samples)).quantize(D("0.01"))
    assert str(mean) in body


def test_risk_analysis_iterations_clamp_but_seed_survives(risk_admin_client, risk_sim_high,
                                                          risk_sim_rare):
    body = risk_admin_client.post(
        reverse("projects:risk_analysis") + "?seed=123&iterations=99999").content.decode()
    assert "Seed" in body and ">123<" in body
    assert "10000 iterations" in body  # clamped to MAX_ITERATIONS, not discarded
    body = risk_admin_client.post(
        reverse("projects:risk_analysis") + "?seed=123&iterations=500").content.decode()
    assert "500 iterations" in body  # the query string survives an empty-body POST (M4)


def test_risk_monitoring_board_renders_the_strip(risk_admin_client, risk_high, risk_overdue,
                                                 risk_closed):
    response = risk_admin_client.get(reverse("projects:risk_monitoring"))
    assert response.status_code == 200
    for key in ("open_count", "top_risks", "burndown_rows", "review_queue", "tolerance",
                "lessons", "by_band"):
        assert key in response.context, key
    assert risk_high.number in response.content.decode()  # top_risks / tolerance lens rows


def test_risk_monitoring_lessons_follow_the_project_lens(risk_admin_client, risk_issue_resolved,
                                                         risk_sim_project):
    lesson = "Certificate expiry belongs in the ops calendar."
    everywhere = risk_admin_client.get(reverse("projects:risk_monitoring"))
    assert lesson in everywhere.content.decode()
    scoped = risk_admin_client.get(reverse("projects:risk_monitoring"),
                                   {"project": risk_sim_project.pk})
    assert lesson not in scoped.content.decode()  # review I10 — no foreign project's lessons


def test_risk_register_cap_pinned_on_both_boards():
    """Review M13: the working set is capped, not unbounded. The tests do not build 2000 rows
    (that is a smoke-scale exercise); they pin the constant and that both views use it."""
    from apps.projects.views.RiskManagement import RiskAnalysis, RiskMonitoring
    assert RiskAnalysis._REGISTER_CAP == 2000
    assert RiskMonitoring._REGISTER_CAP == 2000
    assert "_REGISTER_CAP" in RiskMonitoring.__doc__ or \
        "register_qs[:_REGISTER_CAP]" in __import__("inspect").getsource(RiskMonitoring)
    assert "register_qs[:_REGISTER_CAP]" in __import__("inspect").getsource(RiskAnalysis)


# ==============================================================================================
# Template hygiene — no Django comment syntax may leak into a rendered page (L3)
# ==============================================================================================

def test_risk_pages_leak_no_comment_markers(risk_admin_client, risk_low, risk_action_open,
                                            risk_issue_open, risk_issue_escalated):
    row = _risk_escalation(risk_issue_escalated, level=3)
    pages = [reverse("projects:rsk_list"), reverse("projects:rra_list"),
             reverse("projects:iss_list"), reverse("projects:esc_list"),
             reverse("projects:risk_analysis"), reverse("projects:risk_monitoring"),
             reverse("projects:rsk_detail", args=[risk_low.pk]),
             reverse("projects:esc_detail", args=[row.pk])]
    for url in pages:
        body = risk_admin_client.get(url).content.decode()
        assert "{#" not in body, url
        assert "{% comment" not in body, url
