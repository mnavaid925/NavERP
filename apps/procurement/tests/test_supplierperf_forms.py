"""Procurement 6.16 Supplier Performance & Evaluation — FORM tests.

This lane owns the four forms of the sub-module and nothing else (the model invariants,
``clean()``, ``score_and_band()`` and ``generate_scorecard_lines()`` belong to
``test_supplierperf_models.py``; the registers, the boards and the verbs to
``test_supplierperf_views.py``; the authorization matrix and cross-tenant IDOR to
``test_supplierperf_security.py``):

    SupplierKpiForm  /  SupplierKpiScoreEditForm  /  SupplierFeedbackForm  /
    SupplierImprovementPlanForm

**The exclusion contract is the most valuable thing in here.** ``Meta.fields`` is an ALLOWLIST
and the absences are the design: ``tenant`` (stamped), the auto ``number``
(``TenantNumbered.save()``), every workflow column (``status`` / ``outcome``), the
one-way-door flag ``manual_override``, every ``editable=False`` stamp — the seven frozen
``*_at_time`` / denormalised columns on a score line, ``breakdown``, ``respondent_count``,
``computed_at`` / ``computed_by``, ``acknowledged_at`` / ``acknowledged_by``, ``verified_at`` /
``verified_by``, ``actual_close_date``, ``closure_note``, ``requested_at`` / ``requested_by`` and
``submitted_at`` — plus the two DERIVED score columns (``score`` / ``band``) and the frozen
``weight_applied``. A field silently added to a ``Meta.fields`` list later is exactly the
regression these tests exist to catch (L20 / L22): a workflow column on a form is a decision
anybody can POST, and a stamp anybody can type stops being evidence of anything. Every banned
name is asserted twice — absent from ``form.fields`` AND unbindable from a crafted POST that
names it.

The other five things this file pins:

* **``SupplierKpiScoreEditForm`` exposes EXACTLY two fields** — ``measured_value`` and
  ``comment``. Asserted as a set equality, not a membership test, so a third field is a failure.
* **Tenant narrowing on every FK a form exposes**, and ``_reject_foreign`` refusing a crafted
  POST as a FIELD error rather than leaking a row. Every cross-tenant FK is asserted at BOTH
  layers: against the narrowed queryset (layer 1, "Select a valid choice") and with the queryset
  deliberately widened to simulate a hand-edited POST (layer 2, ``_reject_foreign``'s explicit
  message on the field).
* **No unbound form is a dead end (L39)** — every FK a create page has to fill offers at least
  one row given the fixtures.
* **``clean_evidence``** — the extension allowlist and the size cap from
  ``apps/core/forms/_common.py`` (``.svg`` is refused; ``.pdf`` is not), and ``evidence_url``
  refusing ``javascript:`` and ``data:``.
* **The two NEUTRAL-OPTION fixes (review finding I6).** Both selects used to submit their first
  option when untouched: the feedback submit filed rating **1 — Poor** and the plan close filed
  **Successful** irreversibly, stamping ``verified_by``. Neither verb goes through a form, so the
  refusal is asserted over HTTP at the POST level — an empty value is refused with a message and
  the row does not move — and the rendered ``<option value="">`` is asserted too, because the
  message is only reachable when the browser stops pre-selecting a real answer.

L35 all the way down: ``NaN``, ``Infinity``, ``-Infinity``, ``1e400``, an over-``max_digits``
figure, a negative one and plain garbage are FIELD ERRORS on every numeric input here, never an
``InvalidOperation`` or a ``DataError`` escaping as a 500.

Determinism (L16): every reference date derives from ``timezone.localdate()`` — never
``datetime.date.today()`` — so an exact-date assertion cannot flake in the hours after local
midnight. Every test is ``test_supplierperf_*`` and every module-level helper
``_supplierperf_*`` so no sibling lane can shadow anything here (L47).
"""
import datetime
from decimal import Decimal

import pytest
from django import forms
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES
from apps.procurement.forms import (SupplierFeedbackForm, SupplierImprovementPlanForm,
                                    SupplierKpiForm, SupplierKpiScoreEditForm)
from apps.procurement.models import (SupplierFeedback, SupplierImprovementPlan, SupplierKpi,
                                     SupplierKpiScore)

pytestmark = pytest.mark.django_db


# =================================================================================================
# module-level helpers — every name _supplierperf_* so a sibling lane cannot shadow one (L47)
# =================================================================================================

#: ``_reject_foreign``'s one sentence. Asserted verbatim so a reworded guard is a visible failure
#: rather than a test that quietly stops checking anything.
_SUPPLIERPERF_FOREIGN = "That record belongs to another workspace."

#: Never a form field on ANY 6.16 form, whatever the entity: the tenant is stamped, the number is
#: allocated once by ``TenantNumbered.save()``, and the three base columns are the ORM's.
_SUPPLIERPERF_UNIVERSAL_BAN = ("tenant", "number", "id", "created_at", "updated_at")

#: The four ModelForms, paired with the model each one binds. Drives the generic sweeps below.
_SUPPLIERPERF_MODEL_FORMS = [
    (SupplierKpiForm, SupplierKpi),
    (SupplierKpiScoreEditForm, SupplierKpiScore),
    (SupplierFeedbackForm, SupplierFeedback),
    (SupplierImprovementPlanForm, SupplierImprovementPlan),
]

#: Every numeric string that must land as a FIELD error rather than as a 500 (L35).
_SUPPLIERPERF_JUNK_NUMBERS = ["NaN", "nan", "Infinity", "-Infinity", "inf", "1e400",
                              "not-a-number", "", " ", "12,34", "0x10"]


def _supplierperf_day(offset=0):
    """A date on the SAME basis the models use (L16) — never ``datetime.date.today()``."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _supplierperf_iso(offset=0):
    return _supplierperf_day(offset).strftime("%Y-%m-%d")


def _supplierperf_valid(form):
    """``form.is_valid()`` with L35's promise made explicit.

    Junk in a numeric, date or file input is a FIELD ERROR. If anything escapes, that is a 500 on
    a POST and this says so by name instead of surfacing as an opaque error somewhere else.
    """
    try:
        return form.is_valid()
    except Exception as exc:            # noqa: BLE001 — the whole point is that NOTHING escapes
        pytest.fail(f"{type(form).__name__}.is_valid() raised {type(exc).__name__}: {exc} — "
                    f"a junk input must be a field error, never an exception")


def _supplierperf_widen(form, name, queryset):
    """Simulate a hand-edited POST: drop the narrowing so LAYER 2 (``_reject_foreign``, run in
    ``clean()``) is what has to refuse the foreign row."""
    form.fields[name].queryset = queryset
    return form


def _supplierperf_messages(response):
    """Works on a 302 too — the storage hangs off the request, not the context."""
    return [str(message) for message in get_messages(response.wsgi_request)]


def _supplierperf_kpi_post(**overrides):
    """The minimum a KPI definition POST carries. The band triple is ordered for
    ``higher_is_better``; flip ``direction`` and the triple has to flip with it."""
    data = {"code": "NEW-01", "name": "First-pass yield", "description": "",
            "category": "quality", "unit": "pct", "direction": "higher_is_better",
            "source": "manual", "derived_metric": "", "weight": "15",
            "target_value": "98", "warning_threshold": "95", "critical_threshold": "90",
            "scoring_method": "band", "maps_to_dimension": "quality", "applies_to": "all",
            "applies_to_tier": "", "review_frequency": "quarterly",
            "industry_benchmark_value": "", "owner": "", "display_order": "50",
            "is_active": "on", "notes": ""}
    data.update(overrides)
    return data


def _supplierperf_feedback_post(supplier=None, **overrides):
    """The minimum a 360 request POST carries. ``status`` / ``requested_by`` / ``requested_at`` /
    ``submitted_at`` are never part of it — the three verbs own the lifecycle."""
    data = {"supplier": "", "scorecard": "", "kpi": "",
            "period_start": _supplierperf_iso(-89), "period_end": _supplierperf_iso(),
            "respondent_kind": "internal", "respondent_function": "procurement",
            "respondent": "", "respondent_name": "", "rating": "", "importance": "5",
            "due_date": _supplierperf_iso(7), "comment": ""}
    if supplier is not None:
        data["supplier"] = str(supplier.pk)
    data.update(overrides)
    return data


def _supplierperf_plan_post(supplier=None, **overrides):
    """The minimum a PIP POST carries. ``status`` / ``outcome`` / every stamp are absent."""
    data = {"title": "Late deliveries on the casting line", "supplier": "", "scorecard": "",
            "kpi": "", "severity": "major",
            "finding": "Four of six shipments arrived after the promised date.",
            "root_cause": "", "corrective_actions": "", "support_provided": "",
            "success_criteria": "", "start_date": _supplierperf_iso(),
            "target_close_date": _supplierperf_iso(30), "next_review_date": "",
            "extended_close_date": "", "owner": "", "supplier_owner_name": "",
            "supplier_owner_email": "", "escalated_suspension": "", "evidence_url": ""}
    if supplier is not None:
        data["supplier"] = str(supplier.pk)
    data.update(overrides)
    return data


def _supplierperf_upload(name, size=None, content=b"%PDF-1.4 evidence"):
    """One uploaded file. ``size`` is overridden rather than materialised — the cap is 20 MB and
    a test that actually built 20 MB of bytes would be paying for the assertion twice."""
    upload = SimpleUploadedFile(name, content, content_type="application/octet-stream")
    if size is not None:
        upload.size = size
    return upload


def _supplierperf_suspension_b(tenant, supplier):
    """A tenant-B ``VendorSuspension`` — the crafted-FK target for the plan form's escalation
    pointer. The shared conftest only mints tenant A's."""
    from apps.procurement.models import VendorSuspension
    return VendorSuspension.objects.create(
        tenant=tenant, supplier=supplier, kind="suspension", reason_category="delivery",
        reason="Globex-only block.", status="active")


# =================================================================================================
# 1. The exclusion contract — every field that must NOT be there, by name (L20 / L22)
# =================================================================================================

def test_supplierperf_kpi_form_meta_fields_match_the_contract_exactly():
    assert SupplierKpiForm.Meta.fields == [
        "code", "name", "description", "category", "unit", "direction", "source",
        "derived_metric", "weight", "target_value", "warning_threshold", "critical_threshold",
        "scoring_method", "maps_to_dimension", "applies_to", "applies_to_tier",
        "review_frequency", "industry_benchmark_value", "owner", "display_order", "is_active",
        "notes"]


def test_supplierperf_kpi_form_excludes_tenant_number_and_the_base_stamps(tenant_a):
    """A KPI is a definition, so almost every column IS a human's decision — but the tenant is
    stamped by ``TenantUniqueMixin`` / ``crud_create`` and ``number`` is allocated once by
    ``TenantNumbered.save()``. A form field for either is a value anybody can POST."""
    fields = SupplierKpiForm(tenant=tenant_a).fields
    for name in _SUPPLIERPERF_UNIVERSAL_BAN:
        assert name not in fields, f"SupplierKpiForm exposes {name!r} — it is the system's"
        assert name not in SupplierKpiForm.Meta.fields
    assert set(fields) == set(SupplierKpiForm.Meta.fields)


def test_supplierperf_score_edit_form_exposes_exactly_two_fields(tenant_a):
    """TWO FIELDS. Nothing else, ever — the form's own docstring, asserted.

    Everything else on a score line is the line's identity (``scorecard`` / ``kpi``, which
    ``unique_together`` exists to keep stable), a frozen-at-generation column, or derived in
    ``save()`` from ``kpi.score_and_band()``.
    """
    form = SupplierKpiScoreEditForm(tenant=tenant_a)
    assert set(form.fields) == {"measured_value", "comment"}, (
        f"SupplierKpiScoreEditForm must carry exactly {{'measured_value', 'comment'}}, got "
        f"{sorted(form.fields)} — a third field here breaks the one-scale rule that a hand-typed "
        f"figure is banded by the same score_and_band() a derived one goes through")
    assert SupplierKpiScoreEditForm.Meta.fields == ["measured_value", "comment"]


def test_supplierperf_score_edit_form_excludes_every_frozen_derived_and_identity_column(tenant_a):
    """The named exclusion list from the contract, one reason each.

    ``score`` / ``band`` are DERIVED in ``save()``; ``weight_applied`` and the six
    ``*_at_time`` / denormalised columns are FROZEN at generation so a retune cannot rewrite a
    closed period; ``breakdown`` / ``respondent_count`` / ``computed_at`` / ``computed_by`` are
    ``editable=False`` provenance; and ``scorecard`` / ``kpi`` are the line's identity.
    """
    banned = ["scorecard", "kpi", "score", "band", "weight_applied", "target_at_time",
              "direction_at_time", "source_at_time", "unit_at_time", "kpi_name", "kpi_category",
              "breakdown", "respondent_count", "computed_at", "computed_by",
              *_SUPPLIERPERF_UNIVERSAL_BAN]
    fields = SupplierKpiScoreEditForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, (
            f"SupplierKpiScoreEditForm exposes {name!r} — a frozen, derived or identity column "
            f"on a form is a measurement anybody can retype")
        assert name not in SupplierKpiScoreEditForm.Meta.fields


def test_supplierperf_feedback_form_meta_fields_match_the_contract_exactly():
    assert SupplierFeedbackForm.Meta.fields == [
        "supplier", "scorecard", "kpi", "period_start", "period_end", "respondent_kind",
        "respondent_function", "respondent", "respondent_name", "rating", "importance",
        "due_date", "comment"]


def test_supplierperf_feedback_form_excludes_status_and_every_raise_stamp(tenant_a):
    """``status`` belongs to submit / decline / expire; ``requested_by`` / ``requested_at`` /
    ``submitted_at`` are stamps. A typed status is a claim with nothing behind it, and a raise
    stamp anybody can edit stops being evidence that the request was ever made."""
    banned = ["status", "requested_by", "requested_at", "submitted_at",
              *_SUPPLIERPERF_UNIVERSAL_BAN]
    fields = SupplierFeedbackForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, (
            f"SupplierFeedbackForm exposes {name!r} — the lifecycle belongs to the three POST "
            f"verbs and the stamps belong to the system")
        assert name not in SupplierFeedbackForm.Meta.fields
    assert set(fields) == set(SupplierFeedbackForm.Meta.fields)


def test_supplierperf_feedback_form_keeps_rating_on_purpose(tenant_a):
    """The deliberate INCLUSION, pinned so a later tidy-up cannot quietly remove it: a paper
    survey collected offline is filed complete on the create page. It stays OPTIONAL — the
    model's own rule (a *submitted* response needs a rating) is what keeps that honest."""
    field = SupplierFeedbackForm(tenant=tenant_a).fields["rating"]
    assert field.required is False


def test_supplierperf_plan_form_meta_fields_match_the_contract_exactly():
    assert SupplierImprovementPlanForm.Meta.fields == [
        "title", "supplier", "scorecard", "kpi", "severity", "finding", "root_cause",
        "corrective_actions", "support_provided", "success_criteria", "start_date",
        "target_close_date", "next_review_date", "extended_close_date", "owner",
        "supplier_owner_name", "supplier_owner_email", "escalated_suspension", "evidence",
        "evidence_url"]


def test_supplierperf_plan_form_excludes_status_outcome_and_every_signature_stamp(tenant_a):
    """``status`` and ``outcome`` move only through the five verbs; ``closure_note`` and
    ``actual_close_date`` are written by close beside the outcome they explain; the
    acknowledgement and verification stamps are ``editable=False`` evidence.

    A form field for ``outcome`` would be a result nobody signed off, and a form field for
    ``verified_at`` would let anybody type a signature.
    """
    banned = ["status", "outcome", "actual_close_date", "closure_note",
              "acknowledged_by", "acknowledged_at", "verified_by", "verified_at",
              *_SUPPLIERPERF_UNIVERSAL_BAN]
    fields = SupplierImprovementPlanForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, (
            f"SupplierImprovementPlanForm exposes {name!r} — the lifecycle and the sign-off "
            f"belong to the verbs, not to whoever opens the edit page")
        assert name not in SupplierImprovementPlanForm.Meta.fields
    assert set(fields) == set(SupplierImprovementPlanForm.Meta.fields)


def test_supplierperf_plan_form_keeps_extended_close_date_on_purpose(tenant_a):
    """Granting an extension is an ordinary editorial act with a date behind it, not a lifecycle
    transition — so it IS on the form, and the model's strictly-after rule is what stops it being
    a way to quietly re-write what was agreed."""
    assert "extended_close_date" in SupplierImprovementPlanForm(tenant=tenant_a).fields


@pytest.mark.parametrize("form_class,model", _SUPPLIERPERF_MODEL_FORMS)
def test_supplierperf_no_editable_false_column_is_ever_a_form_field(tenant_a, form_class, model):
    """The generic form of section 1: every system-owned column (``editable=False``, which covers
    ``number``, the seven frozen ``*_at_time`` columns, ``breakdown``, ``respondent_count``, both
    ``computed_*``, both ``acknowledged_*``, both ``verified_*``, ``actual_close_date``,
    ``closure_note``, ``requested_*``, ``submitted_at`` and every ``auto_now*`` stamp) is absent
    from the form that binds this model."""
    system_owned = {field.name for field in model._meta.fields if not field.editable}
    assert system_owned, f"expected at least one editable=False column on {model.__name__}"
    leaked = system_owned & set(form_class(tenant=tenant_a).fields)
    assert not leaked, f"{form_class.__name__} exposes system-owned column(s): {sorted(leaked)}"


@pytest.mark.parametrize("form_class,model", _SUPPLIERPERF_MODEL_FORMS)
def test_supplierperf_no_form_carries_a_by_or_at_stamp(tenant_a, form_class, model):
    """Name-shape guard, so a column added LATER is caught even if nobody updates the lists above.

    ``*_by`` is an attribution and ``*_at`` is a moment; both are the system's. The three real
    date inputs (``start_date``, ``target_close_date``, ``due_date`` …) end ``_date``, not
    ``_at``, so nothing legitimate is caught here.
    """
    stamped = [name for name in form_class(tenant=tenant_a).fields
               if name.endswith("_by") or name.endswith("_at")]
    assert stamped == [], f"{form_class.__name__} exposes stamp field(s): {stamped}"


def test_supplierperf_no_form_binds_manual_override_the_one_way_door(tenant_a):
    """``scm.SupplierScorecard.manual_override`` is the flag that takes SCM's signal engine off a
    scorecard for good. 6.16 sets it in ONE place — ``generate_scorecard_lines`` — and no 6.16
    form may offer it, because a checkbox on an edit page is not a hand-over anybody decided."""
    for form_class, _model in _SUPPLIERPERF_MODEL_FORMS:
        assert "manual_override" not in form_class(tenant=tenant_a).fields, (
            f"{form_class.__name__} exposes 'manual_override' — the one-way door belongs to "
            f"generate_scorecard_lines alone")


# =================================================================================================
# 2. A crafted POST cannot BIND a banned column
# =================================================================================================

def test_supplierperf_kpi_form_crafted_post_cannot_set_tenant_or_number(tenant_a, tenant_b):
    """A POST naming ``tenant`` and ``number`` is accepted as VALID and both are ignored: the
    tenant comes from the request and the number from ``TenantNumbered.save()``."""
    form = SupplierKpiForm(_supplierperf_kpi_post(tenant=str(tenant_b.pk),
                                                  number="SKP-99999"), tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save(commit=False)
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == "", "number must still be unallocated before save()"
    obj.save()
    assert obj.number == "SKP-00001"
    assert obj.tenant_id == tenant_a.pk


def test_supplierperf_feedback_form_crafted_post_cannot_set_status_or_the_stamps(
        tenant_a, admin_user, supplierperf_supplier_a):
    """``status`` stays at its ``requested`` default and the three stamps stay unset, whatever the
    POST body claims — that is what makes the submit verb the only thing that can say "answered"."""
    form = SupplierFeedbackForm(
        _supplierperf_feedback_post(supplierperf_supplier_a, status="submitted",
                                    submitted_at="2020-01-01 09:00:00",
                                    requested_by=str(admin_user.pk),
                                    requested_at="2020-01-01 09:00:00", number="SFB-99999"),
        tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save(commit=False)
    assert obj.status == "requested"
    assert obj.submitted_at is None
    assert obj.requested_by_id is None
    assert obj.number == ""


def test_supplierperf_plan_form_crafted_post_cannot_set_status_outcome_or_the_signature(
        tenant_a, admin_user, supplierperf_supplier_a):
    """The close verb's whole payload, POSTed at the edit form: refused by omission.

    ``status`` stays ``draft``, ``outcome`` stays blank, and neither the closure narrative nor the
    verification signature is bound. A plan that could be closed from the edit page would be an
    ending nobody signed.
    """
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a, status="closed", outcome="successful",
                                closure_note="Signed off by nobody.",
                                actual_close_date=_supplierperf_iso(-1),
                                verified_by=str(admin_user.pk),
                                acknowledged_by=str(admin_user.pk), number="SIP-99999"),
        tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save(commit=False)
    assert obj.status == "draft"
    assert obj.outcome == ""
    assert obj.closure_note == ""
    assert obj.actual_close_date is None
    assert obj.verified_by_id is None and obj.verified_at is None
    assert obj.acknowledged_by_id is None and obj.acknowledged_at is None
    assert obj.number == ""


def test_supplierperf_score_edit_form_crafted_post_cannot_retype_the_frozen_history(
        tenant_a, supplierperf_score_manual_a, supplierperf_kpi_manual_a):
    """The measured value is re-banded through ``kpi.score_and_band()``; every frozen column and
    both derived ones ignore the POST body entirely.

    92 -> 97 on MAN-01 (95 / 90 / 85, higher-is-better, band scoring) moves the line from
    ``warning``/70.00 to ``ok``/100.00 — computed, never typed. The POST body asks for a
    different score, a different band, a different weight and six different frozen columns, and
    gets none of them.
    """
    before_weight = supplierperf_score_manual_a.weight_applied
    form = SupplierKpiScoreEditForm(
        {"measured_value": "97", "comment": "Counted by hand off the delivery log.",
         "score": "100", "band": "ok", "weight_applied": "99", "kpi_name": "RENAMED",
         "kpi_category": "cost", "source_at_time": "derived", "unit_at_time": "days",
         "target_at_time": "1", "direction_at_time": "lower_is_better",
         "respondent_count": "42", "breakdown": '{"source": "typed"}'},
        instance=supplierperf_score_manual_a, tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.measured_value == Decimal("97.0000")
    assert obj.score == Decimal("100.00") and obj.band == "ok"
    assert obj.weight_applied == before_weight
    assert obj.kpi_name == supplierperf_kpi_manual_a.name
    assert obj.kpi_category == supplierperf_kpi_manual_a.category
    assert obj.source_at_time == "manual"
    assert obj.unit_at_time == supplierperf_kpi_manual_a.unit
    assert obj.direction_at_time == "higher_is_better"
    assert obj.respondent_count == 0
    assert obj.breakdown["source"] == "manual entry"
    assert Decimal(obj.breakdown["measured_value"]) == Decimal("97")


def test_supplierperf_score_edit_form_rebands_a_worse_figure_through_the_one_scale(
        tenant_a, supplierperf_score_manual_a):
    """The other direction of the same rule: 80 is below MAN-01's critical line of 85, so the
    line lands at ``critical``/30.00 without anybody typing either."""
    form = SupplierKpiScoreEditForm({"measured_value": "80", "comment": ""},
                                    instance=supplierperf_score_manual_a, tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save()
    assert obj.band == "critical"
    assert obj.score == Decimal("30.00")


def test_supplierperf_score_edit_form_blank_value_scores_none_not_zero(
        tenant_a, supplierperf_score_manual_a):
    """Clearing the figure is a MISSING measurement, not a zero — ``score_and_band(None)`` returns
    ``(None, "unknown")`` and a phantom 0 would quietly punish a supplier for a gap in our data."""
    form = SupplierKpiScoreEditForm({"measured_value": "", "comment": "Nobody counted it."},
                                    instance=supplierperf_score_manual_a, tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save()
    assert obj.measured_value is None
    assert obj.score is None
    assert obj.band == "unknown"
    assert obj.breakdown["measured_value"] is None


# =================================================================================================
# 3. Tenant narrowing on every FK, and _reject_foreign as the crafted-POST re-check
# =================================================================================================

def test_supplierperf_kpi_form_owner_is_narrowed_to_live_accounts_in_this_workspace(
        tenant_a, admin_user, member_user, admin_b):
    field = SupplierKpiForm(tenant=tenant_a).fields["owner"]
    offered = set(field.queryset.values_list("pk", flat=True))
    assert {admin_user.pk, member_user.pk} <= offered
    assert admin_b.pk not in offered, "another workspace's user is offered as a KPI owner"
    assert field.empty_label == "- unassigned -"


def test_supplierperf_kpi_form_offers_no_owner_at_all_without_a_tenant(admin_user):
    """A tenant-less user (the superuser carries ``tenant=None``) is offered nothing rather than
    the whole directory — and ``crud_create`` refuses the write before this form is ever saved."""
    assert SupplierKpiForm(tenant=None).fields["owner"].queryset.count() == 0


def test_supplierperf_kpi_form_rejects_another_workspaces_owner_at_both_layers(
        tenant_a, admin_b):
    narrowed = SupplierKpiForm(_supplierperf_kpi_post(owner=str(admin_b.pk)), tenant=tenant_a)
    assert not _supplierperf_valid(narrowed)
    assert "owner" in narrowed.errors

    from apps.accounts.models import User
    widened = SupplierKpiForm(_supplierperf_kpi_post(owner=str(admin_b.pk)), tenant=tenant_a)
    _supplierperf_widen(widened, "owner", User.objects.all())
    assert not _supplierperf_valid(widened)
    assert _SUPPLIERPERF_FOREIGN in widened.errors["owner"], (
        "a crafted POST naming another workspace's user must be a FIELD error, not a leak")


def test_supplierperf_feedback_form_narrows_all_four_foreign_keys(
        tenant_a, supplierperf_supplier_a, supplierperf_supplier2_a, supplierperf_supplier_b,
        supplierperf_scorecard_draft_a, supplierperf_scorecard_b, supplierperf_kpi_survey_a,
        supplierperf_kpi_derived_a, supplierperf_kpi_b, member_user, admin_b):
    """Supplier cohort, this tenant's scorecards, SURVEY KPIs only, live local accounts.

    The KPI narrowing is the one that carries logic: the model refuses a response against a
    derived KPI outright, so offering one in the dropdown would be a trap somebody falls into.
    """
    fields = SupplierFeedbackForm(tenant=tenant_a).fields

    suppliers = set(fields["supplier"].queryset.values_list("pk", flat=True))
    assert suppliers == {supplierperf_supplier_a.pk, supplierperf_supplier2_a.pk}
    assert supplierperf_supplier_b.pk not in suppliers

    scorecards = set(fields["scorecard"].queryset.values_list("pk", flat=True))
    assert scorecards == {supplierperf_scorecard_draft_a.pk}
    assert supplierperf_scorecard_b.pk not in scorecards

    kpis = set(fields["kpi"].queryset.values_list("pk", flat=True))
    assert kpis == {supplierperf_kpi_survey_a.pk}, (
        "only a survey KPI may carry a 360 response — a derived one is computed from the "
        "transaction spine and never looks at feedback")
    assert supplierperf_kpi_derived_a.pk not in kpis
    assert supplierperf_kpi_b.pk not in kpis

    respondents = set(fields["respondent"].queryset.values_list("pk", flat=True))
    assert member_user.pk in respondents
    assert admin_b.pk not in respondents


def test_supplierperf_feedback_form_offers_nothing_at_all_without_a_tenant(
        supplierperf_supplier_a, supplierperf_scorecard_draft_a, supplierperf_kpi_survey_a):
    fields = SupplierFeedbackForm(tenant=None).fields
    for name in ("supplier", "scorecard", "kpi", "respondent"):
        assert fields[name].queryset.count() == 0, (
            f"a tenant-less user is offered {name} rows from other workspaces")


@pytest.mark.parametrize("name", ["supplier", "scorecard", "kpi", "respondent"])
def test_supplierperf_feedback_form_rejects_a_foreign_row_on_every_foreign_key(
        tenant_a, name, supplierperf_supplier_a, supplierperf_supplier_b, supplierperf_scorecard_b,
        supplierperf_kpi_b, admin_b):
    """Layer 2 for all four FKs: with the narrowing removed, ``_reject_foreign`` is what refuses
    a hand-edited POST — and it does so ON THE FIELD, so the error renders next to the control."""
    from apps.accounts.models import User
    from apps.procurement.models import SupplierKpi as Kpi
    from apps.scm.models import SupplierScorecard
    from apps.core.models import Party

    foreign = {"supplier": (supplierperf_supplier_b, Party.objects.all()),
               "scorecard": (supplierperf_scorecard_b, SupplierScorecard.objects.all()),
               "kpi": (supplierperf_kpi_b, Kpi.objects.all()),
               "respondent": (admin_b, User.objects.all())}
    row, everything = foreign[name]

    # The override is applied to the built dict rather than passed as a keyword: ``supplier`` is
    # already a positional argument of the helper, and ``**{name: ...}`` would collide with it.
    data = _supplierperf_feedback_post(supplierperf_supplier_a)
    data[name] = str(row.pk)

    form = SupplierFeedbackForm(data, tenant=tenant_a)
    _supplierperf_widen(form, name, everything)
    assert not _supplierperf_valid(form)
    assert _SUPPLIERPERF_FOREIGN in form.errors.get(name, []), (
        f"{name}: a crafted POST naming another workspace's row must be a field error")


def test_supplierperf_plan_form_narrows_all_five_foreign_keys(
        tenant_a, supplierperf_supplier_a, supplierperf_supplier2_a, supplierperf_supplier_b,
        supplierperf_scorecard_draft_a, supplierperf_scorecard_b, supplierperf_kpi_manual_a,
        supplierperf_kpi_inactive_a, supplierperf_kpi_b, supplierperf_suspension_a,
        admin_user, admin_b):
    """The plan form offers EVERY active KPI (not just survey ones) — a plan may follow any
    failing metric — plus this workspace's suspensions, which is what the escalation points at."""
    fields = SupplierImprovementPlanForm(tenant=tenant_a).fields

    suppliers = set(fields["supplier"].queryset.values_list("pk", flat=True))
    assert suppliers == {supplierperf_supplier_a.pk, supplierperf_supplier2_a.pk}

    scorecards = set(fields["scorecard"].queryset.values_list("pk", flat=True))
    assert scorecards == {supplierperf_scorecard_draft_a.pk}
    assert supplierperf_scorecard_b.pk not in scorecards

    kpis = set(fields["kpi"].queryset.values_list("pk", flat=True))
    assert kpis == {supplierperf_kpi_manual_a.pk}, (
        "a retired KPI must not be offered on a new plan — retirement is is_active=False")
    assert supplierperf_kpi_inactive_a.pk not in kpis
    assert supplierperf_kpi_b.pk not in kpis

    owners = set(fields["owner"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in owners and admin_b.pk not in owners

    suspensions = set(fields["escalated_suspension"].queryset.values_list("pk", flat=True))
    assert suspensions == {supplierperf_suspension_a.pk}


def test_supplierperf_plan_form_offers_nothing_at_all_without_a_tenant(
        supplierperf_supplier_a, supplierperf_scorecard_draft_a, supplierperf_kpi_manual_a,
        supplierperf_suspension_a):
    fields = SupplierImprovementPlanForm(tenant=None).fields
    for name in ("supplier", "scorecard", "kpi", "owner", "escalated_suspension"):
        assert fields[name].queryset.count() == 0, (
            f"a tenant-less user is offered {name} rows from other workspaces")


@pytest.mark.parametrize("name", ["supplier", "scorecard", "kpi", "owner",
                                  "escalated_suspension"])
def test_supplierperf_plan_form_rejects_a_foreign_row_on_every_foreign_key(
        tenant_a, tenant_b, name, supplierperf_supplier_a, supplierperf_supplier_b,
        supplierperf_scorecard_b, supplierperf_kpi_b, admin_b):
    from apps.accounts.models import User
    from apps.core.models import Party
    from apps.procurement.models import SupplierKpi as Kpi, VendorSuspension
    from apps.scm.models import SupplierScorecard

    suspension_b = _supplierperf_suspension_b(tenant_b, supplierperf_supplier_b)
    foreign = {"supplier": (supplierperf_supplier_b, Party.objects.all()),
               "scorecard": (supplierperf_scorecard_b, SupplierScorecard.objects.all()),
               "kpi": (supplierperf_kpi_b, Kpi.objects.all()),
               "owner": (admin_b, User.objects.all()),
               "escalated_suspension": (suspension_b, VendorSuspension.objects.all())}
    row, everything = foreign[name]

    # Built then overridden — ``supplier`` is a positional argument of the helper, so passing it
    # again as ``**{name: ...}`` would collide.
    data = _supplierperf_plan_post(supplierperf_supplier_a)
    data[name] = str(row.pk)

    form = SupplierImprovementPlanForm(data, tenant=tenant_a)
    _supplierperf_widen(form, name, everything)
    assert not _supplierperf_valid(form)
    assert _SUPPLIERPERF_FOREIGN in form.errors.get(name, []), (
        f"{name}: a crafted POST naming another workspace's row must be a field error")


@pytest.mark.parametrize("form_class,fk_names", [
    (SupplierFeedbackForm, ("supplier",)),
    (SupplierImprovementPlanForm, ("supplier", "scorecard", "kpi", "owner",
                                   "escalated_suspension")),
])
def test_supplierperf_no_unbound_create_form_is_a_dead_end(
        tenant_a, form_class, fk_names, supplierperf_supplier_a, supplierperf_scorecard_draft_a,
        supplierperf_kpi_manual_a, supplierperf_suspension_a, admin_user):
    """L39 — a queryset narrowed by a key that is not known yet renders a permanently empty
    ``<select>`` and the page can never be submitted. One line to catch, and it has shipped
    before."""
    fields = form_class(tenant=tenant_a).fields
    for name in fk_names:
        assert fields[name].queryset.exists(), (
            f"{form_class.__name__}.{name} offers NO rows on an unbound form — the create page "
            f"cannot be completed")


# =================================================================================================
# 4. Required fields, workflow rules and L35 numeric hardening
# =================================================================================================

@pytest.mark.parametrize("name", ["code", "name"])
def test_supplierperf_kpi_form_requires_its_identity_columns(tenant_a, name):
    form = SupplierKpiForm(_supplierperf_kpi_post(**{name: ""}), tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert name in form.errors


def test_supplierperf_kpi_form_refuses_a_duplicate_code_in_the_same_workspace(
        tenant_a, supplierperf_kpi_manual_a):
    """``unique_together ("tenant", "code")``, reached through ``TenantUniqueMixin`` — which is
    exactly what the mixin's ``validate_unique`` override exists for."""
    form = SupplierKpiForm(_supplierperf_kpi_post(code=supplierperf_kpi_manual_a.code),
                           tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "code" in form.errors or "__all__" in form.errors


def test_supplierperf_kpi_form_allows_the_same_code_in_another_workspace(
        tenant_b, supplierperf_kpi_manual_a):
    """Two workspaces may both own "MAN-01" — the constraint is per tenant."""
    form = SupplierKpiForm(_supplierperf_kpi_post(code=supplierperf_kpi_manual_a.code),
                           tenant=tenant_b)
    assert _supplierperf_valid(form), form.errors


def test_supplierperf_kpi_form_surfaces_the_models_derived_conjunction(tenant_a):
    """``source="derived"`` with no ``derived_metric`` is refused BY THE MODEL and shown on the
    field — the form deliberately restates none of it."""
    form = SupplierKpiForm(_supplierperf_kpi_post(source="derived", derived_metric=""),
                           tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "A derived KPI has to say which metric computes it." in form.errors["derived_metric"]


def test_supplierperf_kpi_form_surfaces_the_models_tier_conjunction(tenant_a):
    form = SupplierKpiForm(_supplierperf_kpi_post(applies_to="tier", applies_to_tier=""),
                           tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "Say which tier this KPI applies to." in form.errors["applies_to_tier"]


def test_supplierperf_kpi_form_surfaces_the_models_band_ordering_rule(tenant_a):
    """Higher-is-better with a warning line ABOVE the target is refused, and the message names
    both bands rather than just pointing at a field."""
    form = SupplierKpiForm(_supplierperf_kpi_post(target_value="90", warning_threshold="95"),
                           tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert ("The warning threshold must not be above the target for a higher-is-better KPI."
            in form.errors["warning_threshold"])


def test_supplierperf_kpi_form_rejects_a_derived_metric_outside_the_closed_registry(tenant_a):
    """``DERIVED_METRIC_CHOICES`` is a CLOSED registry — a key with no resolver is a KPI that
    reports nothing while looking like it reports something."""
    form = SupplierKpiForm(
        _supplierperf_kpi_post(source="derived", derived_metric="vibes_per_quarter"),
        tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "derived_metric" in form.errors


@pytest.mark.parametrize("junk", _SUPPLIERPERF_JUNK_NUMBERS)
def test_supplierperf_kpi_form_junk_threshold_is_a_field_error_never_a_500(tenant_a, junk):
    """L35 on the four decimal inputs of the definition. ``""`` is the legitimate "no threshold"
    case and must be VALID; everything else — a lone space included, because ``Decimal(" ")``
    raises rather than reading as empty — is a field error."""
    form = SupplierKpiForm(_supplierperf_kpi_post(target_value=junk), tenant=tenant_a)
    valid = _supplierperf_valid(form)
    if junk == "":
        assert valid, form.errors
        assert form.cleaned_data["target_value"] is None
    else:
        assert not valid, f"{junk!r} was accepted as a decimal threshold"
        assert "target_value" in form.errors


def test_supplierperf_kpi_form_rejects_a_threshold_wider_than_the_column(tenant_a):
    """``DecimalField(max_digits=12, decimal_places=4)`` holds 8 integer digits. A 20-digit figure
    is a field error, never a driver ``DataError``."""
    form = SupplierKpiForm(_supplierperf_kpi_post(critical_threshold="12345678901234567890"),
                           tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "critical_threshold" in form.errors


@pytest.mark.parametrize("weight,ok", [("1", True), ("100", True), ("0", False), ("-5", False),
                                       ("101", False), ("NaN", False), ("1e400", False),
                                       ("", False)])
def test_supplierperf_kpi_form_weight_stays_inside_1_to_100(tenant_a, weight, ok):
    """The weight is a share of the composite — 0 would be a KPI that counts for nothing while
    looking like it counts, and a negative one would subtract from the supplier's own score."""
    form = SupplierKpiForm(_supplierperf_kpi_post(weight=weight), tenant=tenant_a)
    assert _supplierperf_valid(form) is ok, (weight, form.errors)
    if not ok:
        assert "weight" in form.errors


@pytest.mark.parametrize("junk", _SUPPLIERPERF_JUNK_NUMBERS)
def test_supplierperf_score_edit_form_junk_measured_value_is_a_field_error_never_a_500(
        tenant_a, supplierperf_score_manual_a, junk):
    """The one hand-typed measurement in 6.16, hardened. A blank clears the figure (see the
    ``score_and_band(None)`` test above); everything else is a field error."""
    form = SupplierKpiScoreEditForm({"measured_value": junk, "comment": ""},
                                    instance=supplierperf_score_manual_a, tenant=tenant_a)
    valid = _supplierperf_valid(form)
    if junk == "":
        assert valid, form.errors
    else:
        assert not valid, f"{junk!r} was accepted as a measured value"
        assert "measured_value" in form.errors


def test_supplierperf_score_edit_form_rejects_a_value_wider_than_the_column(
        tenant_a, supplierperf_score_manual_a):
    """``DecimalField(max_digits=16, decimal_places=4)`` — 12 integer digits. 30 digits is a
    field error, and the line keeps the figure it had."""
    form = SupplierKpiScoreEditForm({"measured_value": "9" * 30, "comment": ""},
                                    instance=supplierperf_score_manual_a, tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "measured_value" in form.errors
    supplierperf_score_manual_a.refresh_from_db()
    assert supplierperf_score_manual_a.measured_value == Decimal("92.0000")


@pytest.mark.parametrize("name", ["supplier", "period_start", "period_end"])
def test_supplierperf_feedback_form_requires_supplier_and_the_window(
        tenant_a, name, supplierperf_supplier_a):
    data = _supplierperf_feedback_post(supplierperf_supplier_a)
    data[name] = ""
    form = SupplierFeedbackForm(data, tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert name in form.errors


def test_supplierperf_feedback_form_surfaces_the_backwards_window_rule(
        tenant_a, supplierperf_supplier_a):
    form = SupplierFeedbackForm(
        _supplierperf_feedback_post(supplierperf_supplier_a, period_start=_supplierperf_iso(),
                                    period_end=_supplierperf_iso(-10)),
        tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "The period ends before it starts." in form.errors["period_end"]


def test_supplierperf_feedback_form_surfaces_the_self_assessment_conjunction(
        tenant_a, member_user, supplierperf_supplier_a):
    """A supplier self-assessment carries a NAME and no internal user account — both halves at
    once, because the model collects its errors rather than raising the first."""
    form = SupplierFeedbackForm(
        _supplierperf_feedback_post(supplierperf_supplier_a, respondent_kind="supplier_self",
                                    respondent=str(member_user.pk), respondent_name=""),
        tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert ("A supplier self-assessment is not filed by an internal user."
            in form.errors["respondent"])
    assert ("Name the person who answered on the supplier's side."
            in form.errors["respondent_name"])


def test_supplierperf_feedback_form_refuses_a_second_response_from_the_same_respondent(
        tenant_a, member_user, supplierperf_feedback_requested_a, supplierperf_supplier_a,
        supplierperf_scorecard_draft_a, supplierperf_kpi_survey_a):
    """The uniqueness rule that lives in ``clean()`` rather than in ``unique_together`` — reached
    through the form, which is where a user meets it."""
    form = SupplierFeedbackForm(
        _supplierperf_feedback_post(supplierperf_supplier_a,
                                    scorecard=str(supplierperf_scorecard_draft_a.pk),
                                    kpi=str(supplierperf_kpi_survey_a.pk),
                                    respondent=str(member_user.pk)),
        tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert ("This respondent has already answered for that supplier, period document and KPI."
            in form.errors["respondent"])


@pytest.mark.parametrize("rating,ok", [("1", True), ("5", True), ("", True),
                                       ("0", False), ("6", False), ("-1", False),
                                       ("NaN", False), ("1e400", False), ("999999999999", False)])
def test_supplierperf_feedback_form_rating_stays_on_the_1_to_5_scale(
        tenant_a, supplierperf_supplier_a, rating, ok):
    form = SupplierFeedbackForm(
        _supplierperf_feedback_post(supplierperf_supplier_a, rating=rating), tenant=tenant_a)
    assert _supplierperf_valid(form) is ok, (rating, form.errors)
    if not ok:
        assert "rating" in form.errors


@pytest.mark.parametrize("importance,ok", [("0", True), ("10", True), ("11", False),
                                           ("-1", False), ("NaN", False), ("", False)])
def test_supplierperf_feedback_form_importance_stays_inside_0_to_10(
        tenant_a, supplierperf_supplier_a, importance, ok):
    """0 IS legal and is not the same as absent: a response filed at importance 0 weighs nothing
    in the aggregate and is still counted as a respondent."""
    form = SupplierFeedbackForm(
        _supplierperf_feedback_post(supplierperf_supplier_a, importance=importance),
        tenant=tenant_a)
    assert _supplierperf_valid(form) is ok, (importance, form.errors)
    if not ok:
        assert "importance" in form.errors


@pytest.mark.parametrize("name", ["title", "supplier", "finding", "start_date",
                                  "target_close_date"])
def test_supplierperf_plan_form_requires_the_five_columns_a_plan_cannot_exist_without(
        tenant_a, name, supplierperf_supplier_a):
    data = _supplierperf_plan_post(supplierperf_supplier_a)
    data[name] = ""
    form = SupplierImprovementPlanForm(data, tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert name in form.errors


def test_supplierperf_plan_form_surfaces_the_backwards_date_rule(
        tenant_a, supplierperf_supplier_a):
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a, start_date=_supplierperf_iso(),
                                target_close_date=_supplierperf_iso(-1)),
        tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "The plan closes before it starts." in form.errors["target_close_date"]


@pytest.mark.parametrize("offset,ok", [(31, True), (30, False), (29, False)])
def test_supplierperf_plan_form_extension_must_fall_strictly_after_the_target(
        tenant_a, supplierperf_supplier_a, offset, ok):
    """Both sides of the boundary. An extension granted ON the agreed date is not an extension —
    allowing it would be a way to quietly re-write what was agreed and make ``is_overdue`` read
    clean."""
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a,
                                extended_close_date=_supplierperf_iso(offset)),
        tenant=tenant_a)
    assert _supplierperf_valid(form) is ok, (offset, form.errors)
    if not ok:
        assert ("An extension has to fall after the original target date."
                in form.errors["extended_close_date"])


def test_supplierperf_plan_form_refuses_an_escalation_against_a_different_supplier(
        tenant_a, supplierperf_supplier2_a, supplierperf_suspension_a):
    """The suspension is against supplier A; the plan is opened against supplier 2. A pointer at
    somebody else's block would show a block on this plan's page that does not block this
    supplier at all."""
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier2_a,
                                escalated_suspension=str(supplierperf_suspension_a.pk)),
        tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert ("That suspension is against a different supplier."
            in form.errors["escalated_suspension"])


def test_supplierperf_plan_form_rejects_a_malformed_supplier_owner_email(
        tenant_a, supplierperf_supplier_a):
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a, supplier_owner_email="not-an-address"),
        tenant=tenant_a)
    assert not _supplierperf_valid(form)
    assert "supplier_owner_email" in form.errors


# =================================================================================================
# 5. clean_evidence — the extension allowlist, the size cap, and the evidence_url schemes
# =================================================================================================

def test_supplierperf_plan_form_evidence_allowlist_matches_the_shared_constant():
    """The allowlist is ``apps/core/forms/_common.py``'s, not a second local copy that can drift.
    ``.svg`` is NOT in it — an SVG is a script container, and one served inline is stored XSS."""
    assert ".pdf" in ALLOWED_DOC_EXTENSIONS
    assert ".svg" not in ALLOWED_DOC_EXTENSIONS
    assert ".html" not in ALLOWED_DOC_EXTENSIONS
    assert MAX_UPLOAD_BYTES == 20 * 1024 * 1024


@pytest.mark.parametrize("filename", ["capa.svg", "capa.html", "capa.exe", "capa.js",
                                      "capa.pdf.svg"])
def test_supplierperf_plan_form_evidence_rejects_a_disallowed_extension(
        tenant_a, supplierperf_supplier_a, filename):
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a), tenant=tenant_a,
        files={"evidence": _supplierperf_upload(filename)})
    assert not _supplierperf_valid(form)
    ext = filename[filename.rfind("."):]
    assert f"File type '{ext}' is not allowed." in form.errors["evidence"]


@pytest.mark.parametrize("filename", ["capa.pdf", "CAPA.PDF", "ncr-pack.docx", "photos.zip"])
def test_supplierperf_plan_form_evidence_accepts_an_allowlisted_extension(
        tenant_a, supplierperf_supplier_a, filename):
    """The check is case-insensitive — ``.PDF`` is the same allowlist entry as ``.pdf``."""
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a), tenant=tenant_a,
        files={"evidence": _supplierperf_upload(filename)})
    assert _supplierperf_valid(form), form.errors


def test_supplierperf_plan_form_evidence_rejects_a_file_over_the_size_cap(
        tenant_a, supplierperf_supplier_a):
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a), tenant=tenant_a,
        files={"evidence": _supplierperf_upload("capa.pdf", size=MAX_UPLOAD_BYTES + 1)})
    assert not _supplierperf_valid(form)
    assert "File exceeds the 20 MB limit." in form.errors["evidence"]


def test_supplierperf_plan_form_evidence_accepts_a_file_exactly_at_the_cap(
        tenant_a, supplierperf_supplier_a):
    """The boundary itself is legal — the rule is ``>``, not ``>=``."""
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a), tenant=tenant_a,
        files={"evidence": _supplierperf_upload("capa.pdf", size=MAX_UPLOAD_BYTES)})
    assert _supplierperf_valid(form), form.errors


@pytest.mark.parametrize("url", ["javascript:alert(1)", "JavaScript:alert(1)",
                                 "data:text/html;base64,PHNjcmlwdD4=",
                                 "vbscript:msgbox(1)", "file:///etc/passwd", "not a url"])
def test_supplierperf_plan_form_evidence_url_rejects_a_dangerous_scheme(
        tenant_a, supplierperf_supplier_a, url):
    """``evidence_url`` is rendered as a link on the plan detail page, so a ``javascript:`` or
    ``data:`` value would be a one-click XSS against every member of the workspace.
    ``URLField``'s scheme allowlist is http / https / ftp / ftps and nothing else."""
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a, evidence_url=url), tenant=tenant_a)
    assert not _supplierperf_valid(form), f"{url!r} was accepted as an evidence link"
    assert "evidence_url" in form.errors


def test_supplierperf_plan_form_evidence_url_accepts_an_ordinary_https_link(
        tenant_a, supplierperf_supplier_a):
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a,
                                evidence_url="https://qms.example/capa/4471"),
        tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors


# =================================================================================================
# 6. The two NEUTRAL-OPTION fixes (review finding I6) — refused at the POST, not silently filed
# =================================================================================================

def test_supplierperf_submit_with_an_empty_rating_is_refused_not_filed_as_poor(
        client_a, supplierperf_feedback_requested_a):
    """I6, half one. The select used to submit its FIRST option when untouched, so pressing
    *Submit response* without opening it filed the supplier at **1 — Poor** and the view accepted
    it as a deliberate choice. With the neutral option in place the POST carries ``""`` and the
    verb refuses it with a message; the response stays ``requested`` and unrated."""
    url = reverse("procurement:supplierfeedback_submit",
                  args=[supplierperf_feedback_requested_a.pk])
    response = client_a.post(url, {"rating": ""})

    assert response.status_code == 302
    supplierperf_feedback_requested_a.refresh_from_db()
    assert supplierperf_feedback_requested_a.status == "requested"
    assert supplierperf_feedback_requested_a.rating is None
    assert supplierperf_feedback_requested_a.submitted_at is None
    assert any("Pick a rating on the 1-5 scale" in message
               for message in _supplierperf_messages(response))


def test_supplierperf_submit_with_no_rating_key_at_all_is_refused(
        client_a, supplierperf_feedback_requested_a):
    """The same refusal with the key ABSENT rather than empty — a hand-rolled POST, or an older
    cached page whose select had a different name."""
    response = client_a.post(reverse("procurement:supplierfeedback_submit",
                                     args=[supplierperf_feedback_requested_a.pk]), {})
    assert response.status_code == 302
    supplierperf_feedback_requested_a.refresh_from_db()
    assert supplierperf_feedback_requested_a.status == "requested"
    assert supplierperf_feedback_requested_a.rating is None


def test_supplierperf_feedback_detail_renders_a_neutral_first_rating_option(
        client_a, supplierperf_feedback_requested_a):
    """The template half of I6: an unrated, still-open response must offer a SELECTED empty
    option, or the browser picks "1 — Poor" and the refusal above is never reachable."""
    response = client_a.get(reverse("procurement:supplierfeedback_detail",
                                    args=[supplierperf_feedback_requested_a.pk]))
    html = response.content.decode()
    assert response.status_code == 200
    assert 'name="rating"' in html
    assert '<option value="" selected>Choose a rating' in html.replace("&#x27;", "'"), (
        "the rating select does not carry a SELECTED neutral option — an untouched submit files "
        "the supplier at rating 1")


def test_supplierperf_close_with_an_empty_outcome_is_refused_not_filed_as_successful(
        client_a, supplierperf_plan_overdue_a):
    """I6, half two, and worse than half one: closing is admin-only, irreversible, stamps
    ``verified_by`` / ``verified_at`` and writes the ending the supplier is shown. An untouched
    select used to file **Successful**."""
    url = reverse("procurement:improvementplan_close", args=[supplierperf_plan_overdue_a.pk])
    response = client_a.post(url, {"outcome": "", "closure_note": "Nothing decided."})

    assert response.status_code == 302
    supplierperf_plan_overdue_a.refresh_from_db()
    assert supplierperf_plan_overdue_a.status == "active"
    assert supplierperf_plan_overdue_a.outcome == ""
    assert supplierperf_plan_overdue_a.verified_by_id is None
    assert supplierperf_plan_overdue_a.verified_at is None
    assert supplierperf_plan_overdue_a.actual_close_date is None
    assert supplierperf_plan_overdue_a.closure_note == ""
    assert any("Pick how this plan ended before closing it" in message
               for message in _supplierperf_messages(response))


@pytest.mark.parametrize("outcome", ["", "   ", "successfull", "SUCCESSFUL", "1", "None"])
def test_supplierperf_close_refuses_anything_outside_outcome_choices(
        client_a, supplierperf_plan_overdue_a, outcome):
    """The close verb goes through no form, so ``OUTCOME_CHOICES`` is checked in the view — and a
    near-miss spelling is refused exactly like a blank one."""
    response = client_a.post(
        reverse("procurement:improvementplan_close", args=[supplierperf_plan_overdue_a.pk]),
        {"outcome": outcome})
    assert response.status_code == 302
    supplierperf_plan_overdue_a.refresh_from_db()
    assert supplierperf_plan_overdue_a.status == "active"
    assert supplierperf_plan_overdue_a.outcome == ""


def test_supplierperf_plan_detail_renders_a_neutral_first_outcome_option(
        client_a, supplierperf_plan_overdue_a):
    response = client_a.get(reverse("procurement:improvementplan_detail",
                                    args=[supplierperf_plan_overdue_a.pk]))
    html = response.content.decode()
    assert response.status_code == 200
    assert response.context["can_close"] is True
    assert '<option value="" selected>Choose how it ended' in html, (
        "the outcome select does not carry a SELECTED neutral option — an untouched close signs "
        "the plan 'Successful'")


# =================================================================================================
# 7. The happy paths — TenantUniqueMixin's stamp is what makes every create possible
# =================================================================================================

def test_supplierperf_kpi_form_saves_a_definition_into_the_request_tenant(tenant_a, admin_user):
    form = SupplierKpiForm(_supplierperf_kpi_post(owner=str(admin_user.pk)), tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.code == "NEW-01"
    assert obj.owner_id == admin_user.pk
    assert obj.number.startswith("SKP-")
    assert obj.is_active is True


def test_supplierperf_feedback_form_saves_a_request_into_the_request_tenant(
        tenant_a, member_user, supplierperf_supplier_a, supplierperf_scorecard_draft_a,
        supplierperf_kpi_survey_a):
    form = SupplierFeedbackForm(
        _supplierperf_feedback_post(supplierperf_supplier_a,
                                    scorecard=str(supplierperf_scorecard_draft_a.pk),
                                    kpi=str(supplierperf_kpi_survey_a.pk),
                                    respondent=str(member_user.pk),
                                    respondent_function="quality"),
        tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.status == "requested"
    assert obj.number.startswith("SFB-")
    assert obj.kpi_id == supplierperf_kpi_survey_a.pk
    assert obj.respondent_id == member_user.pk


def test_supplierperf_plan_form_saves_a_draft_into_the_request_tenant(
        tenant_a, admin_user, supplierperf_supplier_a, supplierperf_scorecard_draft_a,
        supplierperf_kpi_manual_a, supplierperf_suspension_a):
    form = SupplierImprovementPlanForm(
        _supplierperf_plan_post(supplierperf_supplier_a,
                                scorecard=str(supplierperf_scorecard_draft_a.pk),
                                kpi=str(supplierperf_kpi_manual_a.pk),
                                owner=str(admin_user.pk),
                                escalated_suspension=str(supplierperf_suspension_a.pk),
                                severity="critical"),
        tenant=tenant_a)
    assert _supplierperf_valid(form), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.status == "draft"
    assert obj.outcome == ""
    assert obj.number.startswith("SIP-")
    assert obj.escalated_suspension_id == supplierperf_suspension_a.pk
    assert obj.effective_close_date == _supplierperf_day(30)


@pytest.mark.parametrize("form_class", [SupplierKpiForm, SupplierKpiScoreEditForm,
                                        SupplierFeedbackForm, SupplierImprovementPlanForm])
def test_supplierperf_every_form_mixes_in_the_tenant_stamp(form_class):
    """``TenantUniqueMixin`` FIRST in the MRO, on all four. Without the stamp every CREATE is
    falsely rejected as cross-tenant, because the CRUD helpers only assign the real tenant AFTER
    ``is_valid()`` — the model ``clean()``s all read ``self.tenant_id``."""
    from apps.procurement.forms._common import TenantUniqueMixin
    from apps.core.forms import TenantModelForm

    mro = form_class.__mro__
    assert TenantUniqueMixin in mro, f"{form_class.__name__} does not stamp instance.tenant"
    assert mro.index(TenantUniqueMixin) < mro.index(TenantModelForm), (
        f"{form_class.__name__} mixes TenantUniqueMixin in AFTER TenantModelForm — the stamp "
        f"has to land before full_clean() runs")


@pytest.mark.parametrize("form_class", [SupplierKpiForm, SupplierKpiScoreEditForm,
                                        SupplierFeedbackForm, SupplierImprovementPlanForm])
def test_supplierperf_every_form_accepts_the_tenant_keyword_crud_always_passes(tenant_a,
                                                                              form_class):
    """``crud_create`` / ``crud_edit`` always pass ``tenant=``; a form that dropped the keyword
    would ``TypeError`` at request time rather than at import time."""
    form = form_class(tenant=tenant_a)
    assert form.tenant is tenant_a
    assert isinstance(form, forms.ModelForm)
