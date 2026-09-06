"""Procurement 6.17 Risk & Compliance Management — form tests.

This lane owns the NINE forms of the sub-module and nothing else (models, views and security
are their own files):

    ComplianceScreeningForm / ScreeningHitForm / ScreeningHitDispositionForm
    SupplierRiskSignalForm
    FraudAlertForm / FraudScanForm / FraudDispositionForm
    PolicyAttestationForm
    AuditSealForm

**The exclusion contract is the most valuable thing in here.** Section 1 asserts, by NAME and
with a message that says why, every column each form must NOT carry: ``tenant``, the auto
``number``, every ``*_by`` / ``*_at`` system stamp, every workflow column (``status`` /
``disposition`` / ``review_status``), every DERIVED interpretation (``risk_position`` / ``band`` /
``trend`` / ``previous_value`` / the scale triple / the two hit counters / every digest) and
``dedupe_key``. A field silently added to a ``Meta.fields`` list later is exactly the regression
these tests exist to catch (L20 / L22 / L28) — a workflow column on a form is a decision anybody
can type, and a digest on a form turns "these rows hash to this value" into "these rows hash to
whatever the last person to press Save wanted".

The other five things this file pins:

* **No unbound form is a dead end (L39).** Every FK a create page has to fill is asserted
  non-empty on an UNBOUND form given the fixtures. A queryset narrowed by a key that is not known
  yet renders a permanently empty ``<select>`` and the page can never be submitted — one line to
  catch, and it has shipped before.
* **The narrowed ``<select>`` is UX, never the boundary.** Every cross-tenant FK is asserted
  twice: against the narrowed queryset (layer 1, "Select a valid choice") and with the queryset
  deliberately widened to simulate a hand-edited POST (layer 2, ``_reject_foreign``'s explicit
  message) — and the error is asserted to be ON THE FIELD, so it renders next to the control
  instead of as a page-level non-field error.
* **The validation rules that carry real logic** — the risk signal's scale plausibility check and
  its future-date refusal, the scan window cap at both sides of the boundary, the two
  disposition forms' required notes, the screening's ``list_as_of`` / ``method`` rules and the
  attestation's published-only / active-user narrowing.
* **L35 all the way down** — ``NaN``, ``Infinity``, ``-Infinity``, ``1e400``, a 24-digit number
  and plain garbage are FIELD ERRORS on every numeric input, never an ``InvalidOperation`` or a
  ``DataError`` escaping as a 500; and an absent prerequisite (no action, no window) is REJECTED
  rather than falling through to a valid form.
* **``TenantUniqueMixin`` is present where a model ``clean()`` reads ``self.tenant_id``.** Without
  the stamp every CREATE is falsely rejected as cross-tenant, so the happy paths here are load
  bearing.

Dates derive from ``timezone.localdate()`` — never ``date.today()`` — so an exact-date assertion
cannot flake in the hours after local midnight (L16). Every test is ``test_riskcompliance_*`` and
every module-level helper ``_riskcompliance_*`` so no sibling lane can shadow anything here
(L41 §2 / L47).
"""
import datetime
from decimal import Decimal

import pytest
from django import forms
from django.utils import timezone

from apps.procurement.forms import (AuditSealForm, ComplianceScreeningForm, FraudAlertForm,
                                    FraudDispositionForm, FraudScanForm, PolicyAttestationForm,
                                    ScreeningHitDispositionForm, ScreeningHitForm,
                                    SupplierRiskSignalForm)
from apps.procurement.models.RiskComplianceManagement.AuditSeals import AuditSeal
from apps.procurement.models.RiskComplianceManagement.FraudAlerts import (MAX_SCAN_WINDOW_DAYS,
                                                                          FraudAlert)
from apps.procurement.models.RiskComplianceManagement.Policies import PolicyAttestation
from apps.procurement.models.RiskComplianceManagement.RiskSignals import SupplierRiskSignal
from apps.procurement.models.RiskComplianceManagement.Screenings import (SELECTABLE_METHODS,
                                                                        TERMINAL_DISPOSITIONS,
                                                                        ComplianceScreening,
                                                                        ScreeningHit)

pytestmark = pytest.mark.django_db


# -- module-level helpers (every name _riskcompliance_* so no sibling lane can shadow it) --------

#: ``_reject_foreign``'s one message. Asserted verbatim so a reworded guard is a visible failure
#: rather than a test that quietly stops checking anything.
_RISKCOMPLIANCE_FOREIGN = "That record belongs to another workspace."

#: Every column no 6.17 form may EVER carry, whatever the entity. ``tenant`` and ``number`` are
#: the system's, ``dedupe_key`` is detection's, and ``status`` / ``disposition`` / ``review_status``
#: are the workflow verbs'.
_RISKCOMPLIANCE_UNIVERSAL_BAN = {"tenant", "number", "id", "created_at", "updated_at",
                                 "dedupe_key", "status", "disposition", "review_status"}

#: The five ModelForms of the sub-module, paired with the model each one binds.
_RISKCOMPLIANCE_MODEL_FORMS = [
    (ComplianceScreeningForm, ComplianceScreening),
    (ScreeningHitForm, ScreeningHit),
    (SupplierRiskSignalForm, SupplierRiskSignal),
    (FraudAlertForm, FraudAlert),
    (PolicyAttestationForm, PolicyAttestation),
    (AuditSealForm, AuditSeal),
]

#: The four forms whose model ``clean()`` compares a chosen FK's tenant against
#: ``self.tenant_id`` — i.e. the four that MUST mix in ``TenantUniqueMixin``.
_RISKCOMPLIANCE_STAMPING_FORMS = [ComplianceScreeningForm, SupplierRiskSignalForm,
                                  FraudAlertForm, PolicyAttestationForm]


def _riskcompliance_day(offset=0):
    """A date on the SAME basis the models use (L16) — never ``datetime.date.today()``."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _riskcompliance_iso(offset=0):
    return _riskcompliance_day(offset).strftime("%Y-%m-%d")


def _riskcompliance_is_valid(form):
    """``form.is_valid()`` with L35's promise made explicit.

    Junk in a numeric or date input is a FIELD ERROR. If an ``InvalidOperation`` / ``DataError`` /
    anything else escapes, that is a 500 on a POST and the test says so by name rather than
    surfacing as an opaque error.
    """
    try:
        return form.is_valid()
    except Exception as exc:  # noqa: BLE001 — the whole point is that NOTHING escapes
        pytest.fail(f"{type(form).__name__}.is_valid() raised "
                    f"{type(exc).__name__}: {exc} — a junk input must be a field error, not a 500")


def _riskcompliance_widen(form, name, queryset):
    """Simulate a hand-edited POST: drop the narrowing so layer 2 (the explicit re-check in
    ``clean()``) is what has to refuse the foreign row."""
    form.fields[name].queryset = queryset
    return form


def _riskcompliance_role(party, role="supplier"):
    """Make a ``core.Party`` a supplier.

    The 6.17 fixtures deliberately do NOT attach a role (a screening is run against whoever was
    checked), but both ``party`` dropdowns narrow to ``roles__role__in=("supplier", "vendor")`` —
    so a form-level test needs the role the FORM asks for.
    """
    from apps.core.models import PartyRole
    return PartyRole.objects.create(tenant=party.tenant, party=party, role=role)


def _riskcompliance_document(tenant, name="csl-search-result.pdf"):
    from apps.core.models import Document
    return Document.objects.create(tenant=tenant, name=name,
                                   file="documents/2026/09/csl-search-result.pdf")


def _riskcompliance_party(tenant, name="Contoso Fasteners", kind="organization"):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind=kind)


def _riskcompliance_user(tenant, email, username, is_active=True):
    from apps.accounts.models import User
    return User.objects.create_user(email=email, username=username, password="TestPass123!",
                                    tenant=tenant, is_active=is_active)


def _riskcompliance_policy(tenant, title, status="published", **overrides):
    """One 6.19 ``ProcurementPolicy``. ``published`` is the only status a sign-off may be filed
    against (``ATTESTABLE_POLICY_STATUS``)."""
    from apps.procurement.models import ProcurementPolicy
    fields = dict(tenant=tenant, title=title, policy_type="supplier_code_of_conduct",
                  summary="What buyers and suppliers are held to.", body="Read it, then sign.",
                  version_number="1.0", status=status,
                  effective_from=_riskcompliance_day(-7), requires_acknowledgment=True)
    fields.update(overrides)
    policy = ProcurementPolicy.objects.create(**fields)
    if status == "published":
        policy.published_at = timezone.now()
        policy.save(update_fields=["published_at", "updated_at"])
    return policy


def _riskcompliance_suspension(tenant, supplier, **overrides):
    """One 6.4 ``VendorSuspension`` — what ``FraudDispositionForm.suspension`` LINKS. 6.17 never
    raises one."""
    from apps.procurement.models import VendorSuspension
    fields = dict(tenant=tenant, supplier=supplier, kind="suspension",
                  reason_category="other", reason="Blocked pending the fraud review.",
                  status="active", starts_on=_riskcompliance_day(-2))
    fields.update(overrides)
    return VendorSuspension.objects.create(**fields)


def _riskcompliance_screening_post(party=None, **overrides):
    """The minimum a screening POST carries. Nothing here is a workflow or a derived column."""
    data = {"party": "", "list_source": "csl_consolidated", "checkpoint": "onboarding",
            "method": "manual_lookup", "screened_on": _riskcompliance_iso(),
            "list_as_of": _riskcompliance_iso(-1), "reference": "CSL-2026-1001",
            "result": "clear", "match_threshold": "85",
            "threshold_rationale": "ITA CSL default fuzzy threshold.",
            "next_rescreen_on": "", "evidence": "", "notes": ""}
    if party is not None:
        data["party"] = str(party.pk)
    data.update(overrides)
    return data


def _riskcompliance_hit_post(**overrides):
    data = {"matched_name": "NORTHWIND COMPONENTS LLC", "matched_list": "ofac_sdn",
            "match_score": "96", "match_type": "name", "entry_reference": "SDN-19472",
            "program": "UKRAINE-EO13662", "country": "Cyprus", "remarks": "Consolidated search."}
    data.update(overrides)
    return data


def _riskcompliance_signal_post(party=None, **overrides):
    """The INPUTS of one observation. The scale triple, the position, the band, the trend and the
    previous value are never part of it."""
    data = {"party": "", "provider": "dnb", "metric": "ser_rating",
            "observed_on": _riskcompliance_iso(), "value": "4.00",
            "next_refresh_on": _riskcompliance_iso(90),
            "source_ref": "Provider report page 2", "evidence": "", "notes": ""}
    if party is not None:
        data["party"] = str(party.pk)
    data.update(overrides)
    return data


def _riskcompliance_alert_post(vendor=None, **overrides):
    data = {"rule": "new_vendor_rush", "severity": "medium",
            "document_date": _riskcompliance_iso(-3), "amount": "48000.00",
            "detail": "First order is 48,000.00 six days after approval.", "matched_on": "",
            "assigned_to": "", "vendor": "", "related_party": "", "requisition": "",
            "purchase_order": "", "supplier_invoice": "", "approval": "", "screening": ""}
    if vendor is not None:
        data["vendor"] = str(vendor.pk)
    data.update(overrides)
    return data


def _riskcompliance_attestation_post(policy=None, user=None, **overrides):
    data = {"policy": "", "user": "", "due_on": _riskcompliance_iso(10)}
    if policy is not None:
        data["policy"] = str(policy.pk)
    if user is not None:
        data["user"] = str(user.pk)
    data.update(overrides)
    return data


def _riskcompliance_scan_post(start_offset=-30, end_offset=0, **overrides):
    data = {"start": _riskcompliance_iso(start_offset), "end": _riskcompliance_iso(end_offset)}
    data.update(overrides)
    return data


# =================================================================================================
# 1. The exclusion contract — every field that must NOT be there, by name (L20 / L22 / L28)
# =================================================================================================

def test_riskcompliance_screening_form_meta_fields_match_the_contract_exactly():
    assert ComplianceScreeningForm.Meta.fields == [
        "party", "list_source", "checkpoint", "method", "screened_on", "list_as_of",
        "reference", "result", "match_threshold", "threshold_rationale",
        "next_rescreen_on", "evidence", "notes"]


def test_riskcompliance_screening_form_excludes_every_workflow_and_system_column(tenant_a):
    """``status`` moves only through clear() / escalate() / block(); the two hit counters are
    recounted from the hits; ``suspension`` is stamped by block() from an EXISTING 6.4 block; and
    "who ran this check" is an attribution a form field would let anybody forge."""
    banned = ["tenant", "number", "status", "hit_count", "open_hit_count", "suspension",
              "screened_by", "decided_by", "decided_at", "decision_note",
              "id", "created_at", "updated_at"]
    fields = ComplianceScreeningForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, (
            f"ComplianceScreeningForm exposes {name!r} — a workflow / derived / system column on "
            f"a form is a value anybody can POST")
        assert name not in ComplianceScreeningForm.Meta.fields
    assert set(fields) == set(ComplianceScreeningForm.Meta.fields)


def test_riskcompliance_hit_form_meta_fields_match_the_contract_exactly():
    assert ScreeningHitForm.Meta.fields == [
        "matched_name", "matched_list", "match_score", "match_type", "entry_reference",
        "program", "country", "remarks"]


def test_riskcompliance_hit_form_excludes_screening_because_it_comes_from_the_url(tenant_a):
    """``screening`` as a POST field is a straightforward IDOR onto another workspace's screening:
    the view resolves it from the URL with ``screening__tenant=request.tenant``, which is the one
    place that boundary belongs."""
    fields = ScreeningHitForm(tenant=tenant_a).fields
    assert "screening" not in fields, (
        "ScreeningHitForm exposes 'screening' — accepting the parent from a POST would let a hit "
        "be attached to another workspace's screening")
    assert "screening" not in ScreeningHitForm.Meta.fields


def test_riskcompliance_hit_form_excludes_every_adjudication_column(tenant_a):
    """Adjudication is ``dispose()``'s job — and it requires a note and stamps who and when."""
    banned = ["disposition", "disposition_note", "disposed_by", "disposed_at", "id", "created_at",
              "tenant"]
    fields = ScreeningHitForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, f"ScreeningHitForm exposes {name!r} — dispose() owns it"
    assert set(fields) == set(ScreeningHitForm.Meta.fields)


def test_riskcompliance_hit_form_carries_no_foreign_key_at_all(tenant_a):
    """The docstring's claim, asserted: after excluding ``screening`` there is no FK left, which
    is why this is the one 6.17 form with no ``_reject_foreign`` call."""
    fields = ScreeningHitForm(tenant=tenant_a).fields
    model_choice = [name for name, field in fields.items()
                    if isinstance(field, forms.ModelChoiceField)]
    assert model_choice == [], f"ScreeningHitForm grew an FK field: {model_choice}"


def test_riskcompliance_signal_form_meta_fields_match_the_contract_exactly():
    assert SupplierRiskSignalForm.Meta.fields == [
        "party", "provider", "metric", "observed_on", "value", "next_refresh_on",
        "source_ref", "evidence", "notes"]


def test_riskcompliance_signal_form_excludes_every_derived_and_review_column(tenant_a):
    """The named exclusion list from the contract.

    A form field for "what band is this?" would defeat the entire entity: two people entering the
    same D&B report would produce two different bands, and the inverted scales would stop being
    enforced anywhere.
    """
    banned = ["scale_min", "scale_max", "higher_is_better", "risk_position", "band",
              "previous_value", "trend", "review_status", "review_note", "reviewed_by",
              "reviewed_at", "captured_by", "alert", "tenant", "number",
              "id", "created_at", "updated_at"]
    fields = SupplierRiskSignalForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, (
            f"SupplierRiskSignalForm exposes {name!r} — the interpretation is derive()'s, the "
            f"review columns are the three verbs', and the rest is the system's")
        assert name not in SupplierRiskSignalForm.Meta.fields
    assert set(fields) == set(SupplierRiskSignalForm.Meta.fields)


def test_riskcompliance_alert_form_meta_fields_match_the_contract_exactly():
    assert FraudAlertForm.Meta.fields == [
        "rule", "severity", "document_date", "amount", "detail", "matched_on",
        "assigned_to", "vendor", "related_party", "requisition", "purchase_order",
        "supplier_invoice", "approval", "screening"]


def test_riskcompliance_alert_form_excludes_dedupe_detection_and_resolution(tenant_a):
    """``dedupe_key`` and ``detected_at`` belong to detection; ``status`` / ``resolution_note`` /
    ``resolved_by`` / ``resolved_at`` / ``suspension`` move only through the four verbs."""
    banned = ["dedupe_key", "status", "detected_at", "resolution_note", "resolved_by",
              "resolved_at", "suspension", "tenant", "number", "id", "created_at", "updated_at"]
    fields = FraudAlertForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, (
            f"FraudAlertForm exposes {name!r} — a disposition anybody can POST is not a "
            f"disposition")
        assert name not in FraudAlertForm.Meta.fields
    assert set(fields) == set(FraudAlertForm.Meta.fields)


def test_riskcompliance_alert_form_keeps_severity_on_purpose(tenant_a):
    """The deliberate INCLUSION, pinned so a later "tidy-up" cannot quietly remove it: severity is
    a default the rule stamped, not a verdict, so a reviewer must be able to re-grade a row the
    engine over-called."""
    assert "severity" in FraudAlertForm(tenant=tenant_a).fields


def test_riskcompliance_attestation_form_meta_fields_match_the_contract_exactly():
    assert PolicyAttestationForm.Meta.fields == ["policy", "user", "due_on"]


def test_riskcompliance_attestation_form_excludes_every_signature_column(tenant_a):
    """A form field for "acknowledged at" would let anybody type a signature — which is the one
    column in this module whose value IS the evidence."""
    banned = ["status", "acknowledged_at", "acknowledgement_note", "exempt_reason", "exempted_by",
              "exempted_at", "alert", "tenant", "id", "created_at", "updated_at"]
    fields = PolicyAttestationForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, (
            f"PolicyAttestationForm exposes {name!r} — acknowledge() and mark_exempt() are the "
            f"only writers of the ledger's contents")
        assert name not in PolicyAttestationForm.Meta.fields
    assert set(fields) == set(PolicyAttestationForm.Meta.fields)


def test_riskcompliance_seal_form_has_exactly_one_field(tenant_a):
    """Every other column on ``AuditSeal`` is a computed digest or a system stamp. A digest
    anybody can type is not evidence."""
    form = AuditSealForm(tenant=tenant_a)
    assert set(form.fields) == {"note"}, (
        f"AuditSealForm must carry exactly {{'note'}}, got {sorted(form.fields)} — a form field "
        f"that reached the digest would turn 'these entries hash to this value' into 'these "
        f"entries hash to whatever the last person to press Save wanted'")
    assert AuditSealForm.Meta.fields == ["note"]


def test_riskcompliance_seal_form_excludes_every_digest_range_and_stamp(tenant_a):
    banned = ["from_log_id", "to_log_id", "period_start", "period_end", "row_count", "digest",
              "prev_seal", "prev_digest", "chain_digest", "algorithm", "row_fingerprints",
              "sealed_by", "sealed_at", "last_verified_at", "last_verify_ok",
              "last_verify_detail", "last_verified_by", "tenant", "number"]
    fields = AuditSealForm(tenant=tenant_a).fields
    for name in banned:
        assert name not in fields, f"AuditSealForm exposes {name!r} — it is derived or stamped"


@pytest.mark.parametrize("form_class,model", _RISKCOMPLIANCE_MODEL_FORMS)
def test_riskcompliance_no_editable_false_column_is_ever_a_form_field(tenant_a, form_class, model):
    """The generic form of section 1: every system-owned column (``editable=False`` — which covers
    ``number``, every derived score/band/trend/count/digest and every ``auto_now*`` stamp) is
    absent from the form that binds this model."""
    system_owned = {field.name for field in model._meta.fields if not field.editable}
    assert system_owned, f"expected at least one editable=False column on {model.__name__}"
    leaked = system_owned & set(form_class(tenant=tenant_a).fields)
    assert not leaked, f"{form_class.__name__} exposes system-owned column(s): {sorted(leaked)}"


@pytest.mark.parametrize("form_class,model", _RISKCOMPLIANCE_MODEL_FORMS)
def test_riskcompliance_no_form_carries_a_by_or_at_stamp_or_a_banned_column(tenant_a, form_class,
                                                                           model):
    """Name-shape guard, so a column added later is caught even if nobody updates the lists above:
    no 6.17 form field may end in ``_by`` or ``_at``, and none may be one of the universal bans."""
    names = set(form_class(tenant=tenant_a).fields)
    stamps = {name for name in names if name.endswith("_by") or name.endswith("_at")}
    assert not stamps, f"{form_class.__name__} carries system stamp field(s): {sorted(stamps)}"
    banned = names & _RISKCOMPLIANCE_UNIVERSAL_BAN
    assert not banned, f"{form_class.__name__} carries banned field(s): {sorted(banned)}"


@pytest.mark.parametrize("form_class", _RISKCOMPLIANCE_STAMPING_FORMS)
def test_riskcompliance_form_stamps_the_instance_tenant_before_full_clean(tenant_a, form_class):
    """``TenantUniqueMixin``'s whole job. Each of these models' ``clean()`` compares a chosen FK's
    tenant against ``self.tenant_id``; without the stamp EVERY create is falsely rejected as
    cross-tenant, because the CRUD helpers only assign the real tenant after ``is_valid()``."""
    form = form_class(tenant=tenant_a)
    assert form.instance.tenant_id == tenant_a.pk, (
        f"{form_class.__name__} did not stamp instance.tenant — TenantUniqueMixin is missing, and "
        f"every create through this form will be rejected as cross-tenant")


# =================================================================================================
# 2. Unbound forms are not dead ends (L39)
# =================================================================================================

def test_riskcompliance_screening_form_party_dropdown_is_not_a_dead_end(tenant_a,
                                                                       riskcompliance_party_a):
    """``party`` is REQUIRED, so an empty queryset here is a create page nobody can submit."""
    _riskcompliance_role(riskcompliance_party_a)
    field = ComplianceScreeningForm(tenant=tenant_a).fields["party"]
    assert field.queryset.count() > 0, (
        "ComplianceScreeningForm.party is empty on an unbound form — the create page renders a "
        "permanently unfillable <select>")


def test_riskcompliance_screening_form_evidence_dropdown_is_not_a_dead_end(tenant_a):
    _riskcompliance_document(tenant_a)
    field = ComplianceScreeningForm(tenant=tenant_a).fields["evidence"]
    assert field.queryset.count() > 0
    assert field.empty_label == "- none attached -"
    assert field.required is False


def test_riskcompliance_signal_form_dropdowns_are_not_dead_ends(tenant_a, riskcompliance_party_a):
    _riskcompliance_role(riskcompliance_party_a)
    _riskcompliance_document(tenant_a, "dnb-report.pdf")
    form = SupplierRiskSignalForm(tenant=tenant_a)
    assert form.fields["party"].queryset.count() > 0, (
        "SupplierRiskSignalForm.party is empty on an unbound form — the capture page cannot be "
        "submitted")
    assert form.fields["evidence"].queryset.count() > 0


def test_riskcompliance_alert_form_pointer_dropdowns_are_not_dead_ends(
        tenant_a, riskcompliance_party_a, riskcompliance_screening_open, admin_user):
    """At least ONE pointer has to be fillable or the form can never validate: ``clean()`` refuses
    an alert that points at nothing."""
    _riskcompliance_role(riskcompliance_party_a)
    form = FraudAlertForm(tenant=tenant_a)
    for name in ("vendor", "related_party", "screening", "assigned_to"):
        assert form.fields[name].queryset.count() > 0, (
            f"FraudAlertForm.{name} is empty on an unbound form given rows that exist — the "
            f"hand-raise page would have no way to point the alert at anything")


def test_riskcompliance_attestation_form_dropdowns_are_not_dead_ends(
        tenant_a, riskcompliance_policy_published, riskcompliance_member_a):
    """Both are REQUIRED. ``policy`` needs a published policy — a real precondition the page
    states and links to 6.19 for, not a silent empty ``<select>``."""
    form = PolicyAttestationForm(tenant=tenant_a)
    assert form.fields["policy"].queryset.count() > 0, (
        "PolicyAttestationForm.policy is empty although a published policy exists")
    assert form.fields["user"].queryset.count() > 0, (
        "PolicyAttestationForm.user is empty although the workspace has active members")


def test_riskcompliance_fraud_disposition_suspension_dropdown_is_not_a_dead_end(
        tenant_a, riskcompliance_fraud_open, riskcompliance_party_a):
    """Optional, but it must not be empty when a block against this alert's own supplier exists —
    that is the only row it is ever supposed to offer."""
    suspension = _riskcompliance_suspension(tenant_a, riskcompliance_party_a)
    form = FraudDispositionForm(tenant=tenant_a, alert=riskcompliance_fraud_open)
    assert form.fields["suspension"].queryset.count() > 0
    assert suspension in form.fields["suspension"].queryset


def test_riskcompliance_fraud_disposition_offers_nothing_without_an_alert(tenant_a,
                                                                         riskcompliance_party_a):
    """The deliberate empty case: with no alert (or no vendor on it) there is no supplier to
    narrow by, so offering ANY block would be offering the wrong one."""
    _riskcompliance_suspension(tenant_a, riskcompliance_party_a)
    assert FraudDispositionForm(tenant=tenant_a, alert=None).fields["suspension"].queryset.count() == 0
    assert FraudDispositionForm(tenant=None, alert=None).fields["suspension"].queryset.count() == 0


# =================================================================================================
# 3. Tenant scoping of the dropdowns (and the tenant-less superuser)
# =================================================================================================

def test_riskcompliance_screening_form_party_dropdown_is_scoped_to_the_workspace(
        tenant_a, tenant_b, riskcompliance_party_a, riskcompliance_party_b):
    _riskcompliance_role(riskcompliance_party_a)
    _riskcompliance_role(riskcompliance_party_b)
    queryset = ComplianceScreeningForm(tenant=tenant_a).fields["party"].queryset
    assert riskcompliance_party_a in queryset
    assert riskcompliance_party_b not in queryset, "party <select> leaked a tenant-B supplier"


def test_riskcompliance_screening_form_party_dropdown_offers_only_suppliers(
        tenant_a, riskcompliance_party_a):
    """The EXTRA rule per axis, on top of the tenant boundary: only a party carrying a supplier /
    vendor role is offered. (The MODEL is deliberately more permissive — a screening can be run
    against a prospect — so this is the form's own opinion, pinned here so a change is visible.)"""
    unroled = _riskcompliance_party(tenant_a, "Prospect With No Role")
    _riskcompliance_role(riskcompliance_party_a, role="vendor")
    queryset = ComplianceScreeningForm(tenant=tenant_a).fields["party"].queryset
    assert riskcompliance_party_a in queryset
    assert unroled not in queryset


def test_riskcompliance_screening_form_evidence_dropdown_is_scoped_to_the_workspace(tenant_a,
                                                                                   tenant_b):
    mine = _riskcompliance_document(tenant_a)
    theirs = _riskcompliance_document(tenant_b, "globex-search.pdf")
    queryset = ComplianceScreeningForm(tenant=tenant_a).fields["evidence"].queryset
    assert mine in queryset
    assert theirs not in queryset, "evidence <select> leaked a tenant-B document"


def test_riskcompliance_signal_form_dropdowns_are_scoped_to_the_workspace(
        tenant_a, tenant_b, riskcompliance_party_a, riskcompliance_party_b):
    _riskcompliance_role(riskcompliance_party_a)
    _riskcompliance_role(riskcompliance_party_b)
    mine = _riskcompliance_document(tenant_a)
    theirs = _riskcompliance_document(tenant_b, "globex-report.pdf")
    form = SupplierRiskSignalForm(tenant=tenant_a)
    assert riskcompliance_party_a in form.fields["party"].queryset
    assert riskcompliance_party_b not in form.fields["party"].queryset
    assert mine in form.fields["evidence"].queryset
    assert theirs not in form.fields["evidence"].queryset


def test_riskcompliance_alert_form_dropdowns_are_scoped_to_the_workspace(
        tenant_a, tenant_b, riskcompliance_party_a, riskcompliance_party_b,
        riskcompliance_screening_open, riskcompliance_screening_b, admin_user, admin_b):
    _riskcompliance_role(riskcompliance_party_a)
    _riskcompliance_role(riskcompliance_party_b)
    form = FraudAlertForm(tenant=tenant_a)
    assert riskcompliance_party_a in form.fields["vendor"].queryset
    assert riskcompliance_party_b not in form.fields["vendor"].queryset
    assert riskcompliance_party_a in form.fields["related_party"].queryset
    assert riskcompliance_party_b not in form.fields["related_party"].queryset
    assert riskcompliance_screening_open in form.fields["screening"].queryset
    assert riskcompliance_screening_b not in form.fields["screening"].queryset
    assert admin_user in form.fields["assigned_to"].queryset
    assert admin_b not in form.fields["assigned_to"].queryset


def test_riskcompliance_alert_form_related_party_is_not_narrowed_to_suppliers(
        tenant_a, riskcompliance_party_a):
    """Deliberate: the second party of an overlap is an EMPLOYEE in rule 1 and a SECOND SUPPLIER
    in rule 3, so narrowing it either way would make one of the two rules un-raisable by hand."""
    person = _riskcompliance_party(tenant_a, "R. Okonkwo", kind="person")
    queryset = FraudAlertForm(tenant=tenant_a).fields["related_party"].queryset
    assert person in queryset, "related_party must offer non-suppliers — rule 1 needs an employee"


def test_riskcompliance_attestation_form_user_dropdown_is_scoped_and_active_only(
        tenant_a, tenant_b, riskcompliance_member_a, admin_b):
    """``user`` is narrowed to ACTIVE members of this workspace: a deactivated account cannot
    sign, and a roster must not be able to name somebody from another workspace."""
    retired = _riskcompliance_user(tenant_a, "gone@acme.com", "gone_acme", is_active=False)
    queryset = PolicyAttestationForm(tenant=tenant_a).fields["user"].queryset
    assert riskcompliance_member_a in queryset
    assert retired not in queryset, "user <select> offered a deactivated account"
    assert admin_b not in queryset, "user <select> leaked a tenant-B account"


def test_riskcompliance_attestation_form_policy_dropdown_offers_only_published(
        tenant_a, tenant_b, riskcompliance_policy_published, riskcompliance_policy_draft,
        riskcompliance_policy_no_ack):
    """A draft is not yet the rule and an archived one no longer is. ``requires_acknowledgment``
    is a DIFFERENT question — 6.19's statement of intent for the bulk roster — so a published
    policy with the flag off is still individually assignable, on purpose."""
    archived = _riskcompliance_policy(tenant_a, "Retired Travel Rule", status="archived")
    foreign = _riskcompliance_policy(tenant_b, "Globex Code of Conduct")
    queryset = PolicyAttestationForm(tenant=tenant_a).fields["policy"].queryset
    assert riskcompliance_policy_published in queryset
    assert riskcompliance_policy_no_ack in queryset, (
        "a published policy with requires_acknowledgment=False must still be individually "
        "assignable — the flag governs the bulk roster, not one named person")
    assert riskcompliance_policy_draft not in queryset, "policy <select> offered a draft"
    assert archived not in queryset, "policy <select> offered an archived policy"
    assert foreign not in queryset, "policy <select> leaked a tenant-B policy"


@pytest.mark.parametrize("form_class,names", [
    (ComplianceScreeningForm, ["party", "evidence"]),
    (SupplierRiskSignalForm, ["party", "evidence"]),
    (FraudAlertForm, ["vendor", "related_party", "requisition", "purchase_order",
                      "supplier_invoice", "approval", "screening", "assigned_to"]),
    (PolicyAttestationForm, ["policy", "user"]),
])
def test_riskcompliance_form_with_no_tenant_offers_nothing(tenant_a, tenant_b,
                                                           riskcompliance_party_a,
                                                           riskcompliance_party_b,
                                                           riskcompliance_policy_published,
                                                           form_class, names):
    """The superuser has ``tenant=None`` by design; a tenant-less form must not be able to SEE or
    POST any workspace's rows."""
    _riskcompliance_role(riskcompliance_party_a)
    _riskcompliance_role(riskcompliance_party_b)
    _riskcompliance_document(tenant_a)
    form = form_class(tenant=None)
    for name in names:
        assert list(form.fields[name].queryset) == [], (
            f"{form_class.__name__}.{name} offered rows to a tenant-less form")


# =================================================================================================
# 4. Cross-tenant rejection — the error is ON THE FIELD, so it renders (_reject_foreign)
# =================================================================================================

def test_riskcompliance_screening_form_narrowed_select_refuses_a_foreign_party(
        tenant_a, tenant_b, riskcompliance_party_b):
    """Layer 1: the narrowed ``<select>`` never offers the row, so its pk is an invalid choice."""
    _riskcompliance_role(riskcompliance_party_b)
    form = ComplianceScreeningForm(_riskcompliance_screening_post(party=riskcompliance_party_b),
                                   tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors
    assert "Select a valid choice" in " ".join(form.errors["party"])
    assert ComplianceScreening.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_screening_form_rejects_a_crafted_foreign_party(tenant_a, tenant_b,
                                                                      riskcompliance_party_b):
    """Layer 2: a narrowed ``<select>`` is UX; a hand-edited POST never goes near it."""
    from apps.core.models import Party
    form = ComplianceScreeningForm(_riskcompliance_screening_post(party=riskcompliance_party_b),
                                   tenant=tenant_a)
    _riskcompliance_widen(form, "party", Party.objects.all())
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get("party", []), (
        "the cross-tenant refusal must key onto 'party' so it renders next to the control, not "
        f"into __all__ — got {form.errors.as_data()}")
    assert "__all__" not in form.errors
    assert ComplianceScreening.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_screening_form_rejects_a_crafted_foreign_evidence(tenant_a, tenant_b,
                                                                         riskcompliance_party_a):
    from apps.core.models import Document
    _riskcompliance_role(riskcompliance_party_a)
    foreign = _riskcompliance_document(tenant_b, "globex-search.pdf")
    data = _riskcompliance_screening_post(party=riskcompliance_party_a, evidence=str(foreign.pk))
    form = ComplianceScreeningForm(data, tenant=tenant_a)
    _riskcompliance_widen(form, "evidence", Document.objects.all())
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get("evidence", [])


def test_riskcompliance_signal_form_rejects_a_crafted_foreign_party(tenant_a,
                                                                    riskcompliance_party_b):
    from apps.core.models import Party
    form = SupplierRiskSignalForm(_riskcompliance_signal_post(party=riskcompliance_party_b),
                                  tenant=tenant_a)
    _riskcompliance_widen(form, "party", Party.objects.all())
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get("party", []), (
        f"expected the refusal on 'party', got {form.errors.as_data()}")
    assert "__all__" not in form.errors
    assert SupplierRiskSignal.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_signal_form_rejects_a_crafted_foreign_evidence(tenant_a, tenant_b,
                                                                      riskcompliance_party_a):
    from apps.core.models import Document
    _riskcompliance_role(riskcompliance_party_a)
    foreign = _riskcompliance_document(tenant_b, "globex-report.pdf")
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, evidence=str(foreign.pk))
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    _riskcompliance_widen(form, "evidence", Document.objects.all())
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get("evidence", [])


def test_riskcompliance_signal_form_narrowed_select_refuses_a_foreign_party(
        tenant_a, riskcompliance_party_b):
    _riskcompliance_role(riskcompliance_party_b)
    form = SupplierRiskSignalForm(_riskcompliance_signal_post(party=riskcompliance_party_b),
                                  tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["party"])


@pytest.mark.parametrize("field_name", ["vendor", "related_party", "screening"])
def test_riskcompliance_alert_form_rejects_a_crafted_foreign_pointer(
        tenant_a, riskcompliance_party_a, riskcompliance_party_b, riskcompliance_screening_b,
        field_name):
    """Every tenant-scoped pointer is re-checked in ``clean()``; the error keys onto the pointer
    the POST named so it renders where the operator can see it."""
    from apps.core.models import Party

    from apps.procurement.models import ComplianceScreening as ScreeningModel
    _riskcompliance_role(riskcompliance_party_a)
    foreign, queryset = {
        "vendor": (riskcompliance_party_b, Party.objects.all()),
        "related_party": (riskcompliance_party_b, Party.objects.all()),
        "screening": (riskcompliance_screening_b, ScreeningModel.objects.all()),
    }[field_name]
    data = _riskcompliance_alert_post(vendor=riskcompliance_party_a)
    data[field_name] = str(foreign.pk)
    form = FraudAlertForm(data, tenant=tenant_a)
    _riskcompliance_widen(form, field_name, queryset)
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get(field_name, []), (
        f"expected the refusal on {field_name!r}, got {form.errors.as_data()}")
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_alert_form_narrowed_select_refuses_a_foreign_assignee(tenant_a, admin_b):
    """``assigned_to`` is deliberately NOT in ``_POINTER_FKS`` (a tenant-less superuser is a valid
    assignee), so the tenant narrowing is what refuses another workspace's user here."""
    form = FraudAlertForm(_riskcompliance_alert_post(assigned_to=str(admin_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["assigned_to"])


def test_riskcompliance_attestation_form_rejects_a_crafted_foreign_policy(
        tenant_a, tenant_b, riskcompliance_member_a):
    from apps.procurement.models import ProcurementPolicy
    foreign = _riskcompliance_policy(tenant_b, "Globex Code of Conduct")
    data = _riskcompliance_attestation_post(policy=foreign, user=riskcompliance_member_a)
    form = PolicyAttestationForm(data, tenant=tenant_a)
    _riskcompliance_widen(form, "policy", ProcurementPolicy.objects.all())
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get("policy", []), (
        f"expected the refusal on 'policy', got {form.errors.as_data()}")
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_attestation_form_rejects_a_crafted_foreign_user(
        tenant_a, riskcompliance_policy_published, admin_b):
    """accounts.User carries its own nullable tenant, so a roster could otherwise name somebody
    from another workspace — or the tenant-less superuser."""
    from apps.accounts.models import User
    data = _riskcompliance_attestation_post(policy=riskcompliance_policy_published, user=admin_b)
    form = PolicyAttestationForm(data, tenant=tenant_a)
    _riskcompliance_widen(form, "user", User.objects.all())
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get("user", []), (
        f"expected the refusal on 'user', got {form.errors.as_data()}")
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_attestation_form_narrowed_select_refuses_a_foreign_policy(
        tenant_a, tenant_b, riskcompliance_member_a):
    foreign = _riskcompliance_policy(tenant_b, "Globex Code of Conduct")
    form = PolicyAttestationForm(
        _riskcompliance_attestation_post(policy=foreign, user=riskcompliance_member_a),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["policy"])


def test_riskcompliance_fraud_disposition_rejects_a_crafted_foreign_suspension(
        tenant_a, tenant_b, riskcompliance_fraud_open, riskcompliance_party_b):
    from apps.procurement.models import VendorSuspension
    foreign = _riskcompliance_suspension(tenant_b, riskcompliance_party_b)
    form = FraudDispositionForm(
        {"action": "substantiate", "resolution_note": "Confirmed with the bank.",
         "suspension": str(foreign.pk)},
        tenant=tenant_a, alert=riskcompliance_fraud_open)
    _riskcompliance_widen(form, "suspension", VendorSuspension.objects.all())
    assert not form.is_valid()
    assert _RISKCOMPLIANCE_FOREIGN in form.errors.get("suspension", []), (
        f"expected the refusal on 'suspension', got {form.errors.as_data()}")


# =================================================================================================
# 5. SupplierRiskSignalForm — the rules that carry real logic
# =================================================================================================

def test_riskcompliance_signal_form_requires_party_provider_metric_date_and_value(tenant_a):
    form = SupplierRiskSignalForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("party", "provider", "metric", "observed_on", "value"):
        assert name in form.errors, f"{name} must be required on the capture form"
    for name in ("next_refresh_on", "source_ref", "evidence", "notes"):
        assert name not in form.errors


def test_riskcompliance_signal_form_rejects_a_value_outside_the_metric_scale(
        tenant_a, riskcompliance_party_a):
    """A D&B SER typed as 70 instead of 7 CLAMPS silently to 9 and reports the supplier as
    maximally dangerous with no complaint at all. The plausibility question is asked once, here,
    where it can still be a field error the operator can fix."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, metric="ser_rating",
                                       value="70")
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "value" in form.errors, (
        f"a typo'd SER of 70 must be a field error on 'value', got {form.errors.as_data()}")
    assert "well outside the range" in " ".join(form.errors["value"])
    assert SupplierRiskSignal.objects.filter(tenant=tenant_a).count() == 0


@pytest.mark.parametrize("metric,value", [
    ("ser_rating", "7.00"),      # dead centre of 1..9
    ("ser_rating", "10.50"),     # outside the scale but INSIDE the 20%-of-span tolerance (1.6)
    ("fhr", "82.00"),            # dead centre of 1..100
    ("fhr", "119.00"),           # inside the 19.8 tolerance
])
def test_riskcompliance_signal_form_accepts_a_plausible_value(tenant_a, riskcompliance_party_a,
                                                              metric, value):
    """The tolerance is not zero on purpose: providers rescale and backfill, and a value a point
    or two outside a published range is a real observation that clamps correctly."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, metric=metric, value=value)
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors


@pytest.mark.parametrize("metric,value", [
    ("ser_rating", "12"),        # 1.4 past the tolerance
    ("fhr", "500"),
    ("current_ratio", "80"),     # 0..5, tolerance 1.0
    ("dso_days", "-40"),         # below the floor by more than the tolerance
])
def test_riskcompliance_signal_form_rejects_an_implausible_value(tenant_a, riskcompliance_party_a,
                                                                 metric, value):
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, metric=metric, value=value)
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "value" in form.errors


def test_riskcompliance_signal_form_does_not_range_check_an_unscaled_metric(
        tenant_a, riskcompliance_party_a):
    """``other`` has no registered scale, so there is nothing to check against — refusing an
    unscaled number would be inventing a rule."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, metric="other", value="7000")
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors


def test_riskcompliance_signal_form_rejects_a_future_observation(tenant_a,
                                                                 riskcompliance_party_a):
    """A provider cannot have measured this tomorrow. The date basis is ``timezone.localdate()``,
    the same basis the field's default uses (L16)."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a,
                                       observed_on=_riskcompliance_iso(1))
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert "observed_on" in form.errors, (
        f"a future observation must be a field error on 'observed_on', got {form.errors.as_data()}")
    assert "future" in " ".join(form.errors["observed_on"]).lower()


def test_riskcompliance_signal_form_accepts_todays_observation(tenant_a, riskcompliance_party_a):
    """The boundary on the other side: TODAY is a legitimate observation date."""
    _riskcompliance_role(riskcompliance_party_a)
    form = SupplierRiskSignalForm(
        _riskcompliance_signal_post(party=riskcompliance_party_a,
                                    observed_on=_riskcompliance_iso(0)), tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors


@pytest.mark.parametrize("junk", [
    "NaN", "nan", "Infinity", "-Infinity", "inf", "1e400", "1" * 24, "abc", "7; DROP TABLE",
    "", "  ",
])
def test_riskcompliance_signal_form_turns_a_junk_value_into_a_field_error(
        tenant_a, riskcompliance_party_a, junk):
    """L35, the whole of it. ``Decimal("NaN")`` parses without complaint and then raises
    ``InvalidOperation`` on the first ``<``; ``Decimal("Infinity")`` compares fine and then blows
    the column width. Neither may ever reach a comparison or the database."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, value=junk)
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "value" in form.errors, (
        f"{junk!r} must be a field error on 'value', got {form.errors.as_data()}")
    assert SupplierRiskSignal.objects.filter(tenant=tenant_a).count() == 0


@pytest.mark.parametrize("junk", ["not-a-date", "2026-13-45", "0000-00-00", "NaN"])
def test_riskcompliance_signal_form_turns_a_junk_date_into_a_field_error(
        tenant_a, riskcompliance_party_a, junk):
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, observed_on=junk)
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "observed_on" in form.errors


def test_riskcompliance_signal_form_valid_post_saves_with_the_view_tenant_stamp(
        tenant_a, riskcompliance_party_a, admin_user):
    """Happy path exactly as the view does it — and proof the create is NOT falsely rejected as
    cross-tenant (which is what a missing ``TenantUniqueMixin`` would do)."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_signal_post(party=riskcompliance_party_a, metric="fhr",
                                       provider="rapidratings", value="82.00")
    form = SupplierRiskSignalForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.captured_by = admin_user
    obj.save()
    assert obj.pk is not None
    assert obj.tenant_id == tenant_a.pk
    assert obj.party_id == riskcompliance_party_a.pk
    assert obj.value == Decimal("82.00")
    # DERIVED by save(), never posted: 1..100 higher-is-better -> flipped to a low risk position.
    assert obj.band == "low"
    assert obj.risk_position is not None
    assert obj.number.startswith("SRS-")


# =================================================================================================
# 6. FraudScanForm — the window, its cap and both sides of the boundary
# =================================================================================================

def test_riskcompliance_scan_form_requires_both_ends_of_the_window(tenant_a):
    """L35b: the prerequisite gets its own rejection, not a silent fall-through — a scan with no
    bounds is not a narrower scan, it is every record in the workspace."""
    form = FraudScanForm({}, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "start" in form.errors
    assert "end" in form.errors


def test_riskcompliance_scan_form_rejects_an_end_before_its_start(tenant_a):
    form = FraudScanForm(_riskcompliance_scan_post(start_offset=-1, end_offset=-10),
                         tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "end" in form.errors, (
        f"the ordering error must key onto 'end', got {form.errors.as_data()}")
    assert "after its start" in " ".join(form.errors["end"])


def test_riskcompliance_scan_form_rejects_an_end_equal_to_its_start(tenant_a):
    """The end date is EXCLUSIVE, so start == end is an empty window, not a one-day scan."""
    same = _riskcompliance_iso(-5)
    form = FraudScanForm({"start": same, "end": same}, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "end" in form.errors


def test_riskcompliance_scan_form_accepts_a_window_exactly_at_the_cap(tenant_a):
    """The boundary, asserted both ways. Exactly ``MAX_SCAN_WINDOW_DAYS`` is allowed."""
    form = FraudScanForm(_riskcompliance_scan_post(start_offset=-MAX_SCAN_WINDOW_DAYS,
                                                   end_offset=0), tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    assert (form.cleaned_data["end"] - form.cleaned_data["start"]).days == MAX_SCAN_WINDOW_DAYS


def test_riskcompliance_scan_form_rejects_a_window_one_day_over_the_cap(tenant_a):
    form = FraudScanForm(_riskcompliance_scan_post(start_offset=-(MAX_SCAN_WINDOW_DAYS + 1),
                                                   end_offset=0), tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "end" in form.errors, (
        f"the window cap must be a FIELD error on 'end', got {form.errors.as_data()}")
    message = " ".join(form.errors["end"])
    assert str(MAX_SCAN_WINDOW_DAYS) in message
    assert str(MAX_SCAN_WINDOW_DAYS + 1) in message


@pytest.mark.parametrize("junk", ["not-a-date", "9999-99-99", "NaN", "Infinity", "1e400"])
def test_riskcompliance_scan_form_turns_a_junk_bound_into_a_field_error(tenant_a, junk):
    form = FraudScanForm({"start": junk, "end": _riskcompliance_iso()}, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "start" in form.errors


def test_riskcompliance_scan_form_leaves_rules_optional_and_reports_none_for_all(tenant_a):
    """``selected_rules()`` returns ``None`` rather than the full list so the model's
    "unknown names are ignored" path is never asked to read an empty selection as "run nothing"."""
    form = FraudScanForm(_riskcompliance_scan_post(), tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    assert form.selected_rules() is None


def test_riskcompliance_scan_form_returns_the_chosen_rules(tenant_a):
    data = _riskcompliance_scan_post()
    data["rules"] = ["self_approval", "backdated_po"]
    form = FraudScanForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    assert form.selected_rules() == ["self_approval", "backdated_po"]


def test_riskcompliance_scan_form_rejects_an_unknown_rule(tenant_a):
    """L11 — it arrives from a POST, so it is refused here rather than reaching the engine."""
    data = _riskcompliance_scan_post()
    data["rules"] = ["definitely_not_a_rule"]
    form = FraudScanForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "rules" in form.errors


def test_riskcompliance_scan_form_accepts_the_tenant_kwarg_for_signature_parity(tenant_a):
    form = FraudScanForm(tenant=tenant_a)
    assert form.tenant is tenant_a
    assert set(form.fields) == {"start", "end", "rules"}


# =================================================================================================
# 7. ScreeningHitForm + ScreeningHitDispositionForm
# =================================================================================================

def test_riskcompliance_hit_form_requires_the_name_list_score_and_type(tenant_a):
    form = ScreeningHitForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("matched_name", "matched_list", "match_score", "match_type"):
        assert name in form.errors


def test_riskcompliance_hit_form_rejects_a_whitespace_only_matched_name(tenant_a):
    form = ScreeningHitForm(_riskcompliance_hit_post(matched_name="   "), tenant=tenant_a)
    assert not form.is_valid()
    assert "matched_name" in form.errors
    assert "must name the list entry" in " ".join(form.errors["matched_name"])


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "abc", "-5", "101", "1" * 24])
def test_riskcompliance_hit_form_turns_a_junk_score_into_a_field_error(tenant_a, junk):
    """0-100 is the provider's own range; anything else — junk, negative, over the top or wider
    than the column — is a field error, never a 500 or a silently clamped badge."""
    form = ScreeningHitForm(_riskcompliance_hit_post(match_score=junk), tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "match_score" in form.errors
    assert ScreeningHit.objects.count() == 0


def test_riskcompliance_hit_form_valid_post_saves_against_the_url_screening(
        tenant_a, riskcompliance_screening_open):
    """The parent comes from the URL and is stamped by the view — exactly how the form avoids
    being an IDOR."""
    form = ScreeningHitForm(_riskcompliance_hit_post(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    hit = form.save(commit=False)
    hit.screening = riskcompliance_screening_open
    hit.save()
    assert hit.pk is not None
    assert hit.screening_id == riskcompliance_screening_open.pk
    assert hit.disposition == "open", "a new hit is never pre-adjudicated"


def test_riskcompliance_disposition_form_offers_only_terminal_dispositions(tenant_a):
    """Re-opening an adjudicated hit is not a thing this module does, so ``open`` is not on the
    menu."""
    form = ScreeningHitDispositionForm(tenant=tenant_a)
    offered = [value for value, _label in form.fields["disposition"].choices]
    assert offered == list(TERMINAL_DISPOSITIONS)
    assert "open" not in offered


def test_riskcompliance_disposition_form_refuses_a_crafted_open_disposition(tenant_a):
    form = ScreeningHitDispositionForm(
        {"disposition": "open", "disposition_note": "Putting it back."}, tenant=tenant_a)
    assert not form.is_valid()
    assert "disposition" in form.errors


@pytest.mark.parametrize("note", ["", "   ", "\n\t "])
def test_riskcompliance_disposition_form_requires_a_note_for_every_disposition(tenant_a, note):
    """A cleared false positive with no recorded reasoning is indistinguishable from a check that
    was never performed — which is exactly the finding a recordkeeping examination writes up."""
    form = ScreeningHitDispositionForm(
        {"disposition": "false_positive", "disposition_note": note}, tenant=tenant_a)
    assert not form.is_valid()
    assert "disposition_note" in form.errors, (
        f"an adjudication with no reason must be refused on the note field, "
        f"got {form.errors.as_data()}")


@pytest.mark.parametrize("disposition", list(TERMINAL_DISPOSITIONS))
def test_riskcompliance_disposition_form_accepts_a_terminal_call_with_a_note(tenant_a,
                                                                            disposition):
    form = ScreeningHitDispositionForm(
        {"disposition": disposition, "disposition_note": "  Different tax id and address.  "},
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["disposition"] == disposition
    assert form.cleaned_data["disposition_note"] == "Different tax id and address."


def test_riskcompliance_disposition_form_rejects_a_missing_disposition(tenant_a):
    """L35b — the absent prerequisite is REJECTED, never allowed to fall through to a recorded
    adjudication."""
    form = ScreeningHitDispositionForm({"disposition_note": "Cleared."}, tenant=tenant_a)
    assert not form.is_valid()
    assert "disposition" in form.errors


# =================================================================================================
# 8. FraudAlertForm + FraudDispositionForm
# =================================================================================================

def test_riskcompliance_alert_form_requires_rule_severity_and_document_date(tenant_a):
    form = FraudAlertForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("rule", "severity", "document_date"):
        assert name in form.errors
    assert form.fields["amount"].required is False, (
        "a conflict-of-interest overlap has no amount — forcing one makes somebody type 0")
    assert form.fields["document_date"].required is True


def test_riskcompliance_alert_form_refuses_an_alert_that_points_at_nothing(tenant_a):
    """An accusation with no evidence cannot be reviewed. The error keys onto ``vendor`` so it
    renders next to a control instead of as a page-level non-field error."""
    data = _riskcompliance_alert_post()
    form = FraudAlertForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert "vendor" in form.errors, (
        f"expected the 'point it at something' refusal on 'vendor', got {form.errors.as_data()}")
    assert "Point the alert at something" in " ".join(form.errors["vendor"])
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_alert_form_rejects_a_future_document_date(tenant_a,
                                                                 riskcompliance_party_a):
    """``document_date`` is the date of the FACT, so a future one is either a typo or an attempt
    to park an alert outside every ageing bucket."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_alert_post(vendor=riskcompliance_party_a,
                                      document_date=_riskcompliance_iso(1))
    form = FraudAlertForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert "document_date" in form.errors
    assert "future" in " ".join(form.errors["document_date"]).lower()


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity", "1e400", "9" * 24, "abc"])
def test_riskcompliance_alert_form_turns_a_junk_amount_into_a_field_error(
        tenant_a, riskcompliance_party_a, junk):
    """L35 on the money column: ``Decimal("NaN")`` parses fine and raises ``InvalidOperation`` on
    the first magnitude comparison, which would be an unhandled 500 on this POST."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_alert_post(vendor=riskcompliance_party_a, amount=junk)
    form = FraudAlertForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "amount" in form.errors, (
        f"{junk!r} must be a field error on 'amount', got {form.errors.as_data()}")
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_alert_form_accepts_a_blank_amount(tenant_a, riskcompliance_party_a):
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_alert_post(vendor=riskcompliance_party_a, amount="")
    form = FraudAlertForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    assert form.cleaned_data["amount"] is None


def test_riskcompliance_alert_form_rejects_the_same_party_on_both_sides(tenant_a,
                                                                       riskcompliance_party_a):
    """The two sides of an overlap have to be two different parties."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_alert_post(vendor=riskcompliance_party_a,
                                      related_party=str(riskcompliance_party_a.pk),
                                      rule="vendor_employee_match", severity="high")
    form = FraudAlertForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert "related_party" in form.errors


def test_riskcompliance_alert_form_rejects_a_hand_raised_duplicate(tenant_a,
                                                                  riskcompliance_party_a,
                                                                  riskcompliance_fraud_open):
    """The dedupe key is pre-checked so a duplicate is a friendly field error instead of the
    unique constraint 500ing the POST."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_alert_post(vendor=riskcompliance_party_a, rule="new_vendor_rush")
    form = FraudAlertForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "rule" in form.errors, (
        f"a duplicate must be a field error, not an IntegrityError — got {form.errors.as_data()}")
    assert "already exists" in " ".join(form.errors["rule"])


def test_riskcompliance_alert_form_valid_post_saves_with_the_view_tenant_stamp(
        tenant_a, riskcompliance_party_a):
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_alert_post(vendor=riskcompliance_party_a, severity="high")
    form = FraudAlertForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    alert = form.save(commit=False)
    alert.tenant = tenant_a
    alert.save()
    assert alert.pk is not None
    assert alert.tenant_id == tenant_a.pk
    assert alert.vendor_id == riskcompliance_party_a.pk
    assert alert.severity == "high", "a reviewer's re-grade must stick"
    # DERIVED, never posted.
    assert alert.status == "open"
    assert alert.dedupe_key
    assert alert.number.startswith("FRD-")


def test_riskcompliance_fraud_disposition_requires_a_note_to_close(tenant_a,
                                                                  riskcompliance_fraud_open):
    """Closing a fraud alert with no stated reasoning is indistinguishable from an alert nobody
    looked at — and here the closure being explained is an accusation being dropped."""
    for action in ("substantiate", "unsubstantiate", "refer"):
        form = FraudDispositionForm({"action": action, "resolution_note": "  "},
                                    tenant=tenant_a, alert=riskcompliance_fraud_open)
        assert not form.is_valid(), f"{action} was accepted with no note"
        assert "resolution_note" in form.errors, (
            f"{action}: expected the refusal on 'resolution_note', got {form.errors.as_data()}")


def test_riskcompliance_fraud_disposition_lets_investigate_through_without_a_note(
        tenant_a, riskcompliance_fraud_open):
    """Parking a question open is not a closure, so it does not demand one."""
    form = FraudDispositionForm({"action": "investigate", "resolution_note": ""},
                                tenant=tenant_a, alert=riskcompliance_fraud_open)
    assert form.is_valid(), form.errors
    assert form.verb_name == "investigate"


@pytest.mark.parametrize("action", ["", "approve", "delete", "OPEN", "substantiate; drop"])
def test_riskcompliance_fraud_disposition_rejects_an_unknown_action(tenant_a,
                                                                   riskcompliance_fraud_open,
                                                                   action):
    """L35b — without its own rejection branch a missing action skips every rule below and the
    form reports VALID, which is how a POST with no action becomes an approved disposition."""
    form = FraudDispositionForm({"action": action, "resolution_note": "Anything."},
                                tenant=tenant_a, alert=riskcompliance_fraud_open)
    assert not _riskcompliance_is_valid(form)
    assert "action" in form.errors, (
        f"{action!r} must be refused on 'action', got {form.errors.as_data()}")
    assert form.verb_name is None


def test_riskcompliance_fraud_disposition_narrows_suspensions_to_this_alerts_vendor(
        tenant_a, riskcompliance_fraud_open, riskcompliance_party_a):
    """A block against a different supplier is not evidence about this one."""
    mine = _riskcompliance_suspension(tenant_a, riskcompliance_party_a)
    other_party = _riskcompliance_party(tenant_a, "Contoso Fasteners")
    theirs = _riskcompliance_suspension(tenant_a, other_party)
    queryset = FraudDispositionForm(tenant=tenant_a,
                                    alert=riskcompliance_fraud_open).fields["suspension"].queryset
    assert mine in queryset
    assert theirs not in queryset, "the picker offered a block against a different supplier"


def test_riskcompliance_fraud_disposition_refuses_a_block_against_another_supplier(
        tenant_a, riskcompliance_fraud_open):
    """Layer 2 for the same rule: widen the picker and the explicit re-check has to refuse it."""
    from apps.procurement.models import VendorSuspension
    other_party = _riskcompliance_party(tenant_a, "Contoso Fasteners")
    theirs = _riskcompliance_suspension(tenant_a, other_party)
    form = FraudDispositionForm(
        {"action": "substantiate", "resolution_note": "Confirmed with the bank.",
         "suspension": str(theirs.pk)},
        tenant=tenant_a, alert=riskcompliance_fraud_open)
    _riskcompliance_widen(form, "suspension", VendorSuspension.objects.all())
    assert not form.is_valid()
    assert "suspension" in form.errors
    assert "different supplier" in " ".join(form.errors["suspension"])


def test_riskcompliance_fraud_disposition_refuses_a_block_on_a_non_substantiating_action(
        tenant_a, riskcompliance_fraud_open, riskcompliance_party_a):
    """Parking a question and stopping a supplier trading are different decisions."""
    mine = _riskcompliance_suspension(tenant_a, riskcompliance_party_a)
    form = FraudDispositionForm(
        {"action": "investigate", "resolution_note": "", "suspension": str(mine.pk)},
        tenant=tenant_a, alert=riskcompliance_fraud_open)
    assert not form.is_valid()
    assert "suspension" in form.errors
    assert "substantiated" in " ".join(form.errors["suspension"])


def test_riskcompliance_fraud_disposition_accepts_a_substantiation_with_its_own_block(
        tenant_a, riskcompliance_fraud_open, riskcompliance_party_a):
    mine = _riskcompliance_suspension(tenant_a, riskcompliance_party_a)
    form = FraudDispositionForm(
        {"action": "substantiate", "resolution_note": "  Confirmed with HR.  ",
         "suspension": str(mine.pk)},
        tenant=tenant_a, alert=riskcompliance_fraud_open)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["suspension"] == mine
    assert form.cleaned_data["resolution_note"] == "Confirmed with HR."
    assert form.verb_name == "substantiate"


# =================================================================================================
# 9. ComplianceScreeningForm — the two rules that carry logic
# =================================================================================================

def test_riskcompliance_screening_form_requires_its_five_mandatory_inputs(tenant_a):
    form = ComplianceScreeningForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("party", "list_source", "checkpoint", "method", "screened_on", "result",
                 "match_threshold"):
        assert name in form.errors, f"{name} must be required on the screening form"
    for name in ("list_as_of", "reference", "threshold_rationale", "next_rescreen_on",
                 "evidence", "notes"):
        assert name not in form.errors


def test_riskcompliance_screening_form_refuses_a_list_date_after_the_screening_date(
        tenant_a, riskcompliance_party_a):
    """A list cannot have been published after the search that used it — and a clear result is
    only as fresh as the list behind it."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_screening_post(party=riskcompliance_party_a,
                                          screened_on=_riskcompliance_iso(-3),
                                          list_as_of=_riskcompliance_iso(-1))
    form = ComplianceScreeningForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert "list_as_of" in form.errors, (
        f"expected the refusal on 'list_as_of', got {form.errors.as_data()}")
    assert ComplianceScreening.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_screening_form_accepts_a_list_date_equal_to_the_screening_date(
        tenant_a, riskcompliance_party_a):
    """The boundary: same-day is fine — the list was current when it was searched."""
    _riskcompliance_role(riskcompliance_party_a)
    same = _riskcompliance_iso(-1)
    data = _riskcompliance_screening_post(party=riskcompliance_party_a, screened_on=same,
                                          list_as_of=same)
    form = ComplianceScreeningForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors


def test_riskcompliance_screening_form_offers_only_the_selectable_methods(tenant_a):
    """``api_feed`` stays in the MODEL's vocabulary so a future list connector writes the same
    rows with no migration — but a person filling this form did not run an automated feed."""
    offered = [value for value, _label in ComplianceScreeningForm(tenant=tenant_a)
               .fields["method"].choices if value]
    assert offered == list(SELECTABLE_METHODS)
    assert "api_feed" not in offered


def test_riskcompliance_screening_form_refuses_a_crafted_api_feed_method(tenant_a,
                                                                        riskcompliance_party_a):
    """The hand-crafted POST, which never goes near the narrowed ``<select>``."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_screening_post(party=riskcompliance_party_a, method="api_feed")
    form = ComplianceScreeningForm(data, tenant=tenant_a)
    assert not form.is_valid()
    assert "method" in form.errors, (
        f"a claimed automated feed must be refused on 'method', got {form.errors.as_data()}")
    assert ComplianceScreening.objects.filter(tenant=tenant_a).count() == 0


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "abc", "-1", "0", "101", "1" * 24])
def test_riskcompliance_screening_form_turns_a_junk_threshold_into_a_field_error(
        tenant_a, riskcompliance_party_a, junk):
    """1-100 is the whole range a fuzzy score can occupy; junk, zero, negative, over the top and
    over the column width are all field errors rather than a 500."""
    _riskcompliance_role(riskcompliance_party_a)
    data = _riskcompliance_screening_post(party=riskcompliance_party_a, match_threshold=junk)
    form = ComplianceScreeningForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "match_threshold" in form.errors


def test_riskcompliance_screening_form_valid_post_saves_with_the_view_tenant_stamp(
        tenant_a, riskcompliance_party_a, admin_user):
    _riskcompliance_role(riskcompliance_party_a)
    evidence = _riskcompliance_document(tenant_a)
    data = _riskcompliance_screening_post(party=riskcompliance_party_a,
                                          evidence=str(evidence.pk),
                                          result="potential_match", checkpoint="pre_award")
    form = ComplianceScreeningForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    screening = form.save(commit=False)
    screening.tenant = tenant_a
    screening.screened_by = admin_user
    screening.save()
    assert screening.pk is not None
    assert screening.tenant_id == tenant_a.pk
    assert screening.party_id == riskcompliance_party_a.pk
    assert screening.evidence_id == evidence.pk
    # DERIVED / workflow, never posted.
    assert screening.status == "pending_review"
    assert screening.hit_count == 0
    assert screening.open_hit_count == 0
    assert screening.suspension_id is None
    assert screening.number.startswith("SCR-")


# =================================================================================================
# 10. PolicyAttestationForm — published-only, the owner, and the two disabled fields
# =================================================================================================

def test_riskcompliance_attestation_form_requires_policy_and_user(tenant_a):
    form = PolicyAttestationForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "policy" in form.errors
    assert "user" in form.errors
    assert "due_on" not in form.errors, "blank means no deadline was set"


def test_riskcompliance_attestation_form_refuses_a_crafted_draft_policy(
        tenant_a, riskcompliance_policy_draft, riskcompliance_member_a):
    """The narrowed ``<select>`` is presentation; ``clean_policy`` runs against the RESOLVED
    object, so a policy archived between the page rendering and the POST is caught too."""
    from apps.procurement.models import ProcurementPolicy
    data = _riskcompliance_attestation_post(policy=riskcompliance_policy_draft,
                                            user=riskcompliance_member_a)
    form = PolicyAttestationForm(data, tenant=tenant_a)
    _riskcompliance_widen(form, "policy", ProcurementPolicy.objects.all())
    assert not form.is_valid()
    assert "policy" in form.errors, (
        f"a draft must be refused on 'policy', got {form.errors.as_data()}")
    assert "published policy" in " ".join(form.errors["policy"])
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_attestation_form_refuses_a_second_row_for_the_same_person(
        tenant_a, riskcompliance_attestation_pending, riskcompliance_policy_published,
        riskcompliance_member_a):
    """One obligation per person per policy is what makes the roster countable — and with
    ``TenantUniqueMixin`` stamping the tenant it is a form error with a sentence on it rather than
    an ``IntegrityError`` 500."""
    data = _riskcompliance_attestation_post(policy=riskcompliance_policy_published,
                                            user=riskcompliance_member_a)
    form = PolicyAttestationForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "already has an attestation" in " ".join(form.errors.get("__all__", [])), (
        f"expected the unique_together sentence, got {form.errors.as_data()}")
    assert PolicyAttestation.objects.filter(tenant=tenant_a).count() == 1


def test_riskcompliance_attestation_form_create_leaves_policy_and_user_editable(tenant_a):
    form = PolicyAttestationForm(tenant=tenant_a)
    assert form.fields["policy"].disabled is False
    assert form.fields["user"].disabled is False


def test_riskcompliance_attestation_form_disables_policy_and_user_on_an_existing_row(
        tenant_a, riskcompliance_attestation_pending):
    """On an existing row the deadline is the only amendable thing. Re-pointing ``policy`` or
    ``user`` would move an obligation off one person onto another, silently taking the first
    person off the overdue board."""
    form = PolicyAttestationForm(instance=riskcompliance_attestation_pending, tenant=tenant_a)
    assert form.fields["policy"].disabled is True, (
        "policy must be disabled on an edit — Django then ignores a POSTed value entirely")
    assert form.fields["user"].disabled is True


def test_riskcompliance_attestation_edit_ignores_a_posted_policy_and_user(
        tenant_a, riskcompliance_attestation_pending, riskcompliance_policy_no_ack, admin_user,
        riskcompliance_member_a):
    """``disabled=True`` is what makes the rule hold against a CRAFTED POST: Django falls back to
    the instance's own value, so the obligation cannot be moved to somebody else."""
    original_policy_id = riskcompliance_attestation_pending.policy_id
    data = _riskcompliance_attestation_post(policy=riskcompliance_policy_no_ack, user=admin_user,
                                            due_on=_riskcompliance_iso(30))
    form = PolicyAttestationForm(data, instance=riskcompliance_attestation_pending,
                                 tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    row = form.save()
    row.refresh_from_db()
    assert row.user_id == riskcompliance_member_a.pk, (
        "a POSTed user changed the obligation's owner — the disabled field is not holding")
    assert row.policy_id == original_policy_id, "a POSTed policy re-pointed the obligation"
    assert row.due_on == _riskcompliance_day(30), "the deadline IS amendable"


def test_riskcompliance_attestation_form_valid_post_saves_with_the_view_tenant_stamp(
        tenant_a, riskcompliance_policy_published, riskcompliance_member_a):
    data = _riskcompliance_attestation_post(policy=riskcompliance_policy_published,
                                            user=riskcompliance_member_a)
    form = PolicyAttestationForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    row = form.save(commit=False)
    row.tenant = tenant_a
    row.save()
    assert row.pk is not None
    assert row.tenant_id == tenant_a.pk
    assert row.due_on == _riskcompliance_day(10)
    # The signature columns are the verbs', never the form's.
    assert row.status == "pending"
    assert row.acknowledged_at is None
    assert row.acknowledgement_note == ""
    assert row.exempted_by_id is None


def test_riskcompliance_attestation_form_accepts_a_blank_deadline(
        tenant_a, riskcompliance_policy_published, riskcompliance_member_a):
    data = _riskcompliance_attestation_post(policy=riskcompliance_policy_published,
                                            user=riskcompliance_member_a, due_on="")
    form = PolicyAttestationForm(data, tenant=tenant_a)
    assert _riskcompliance_is_valid(form), form.errors
    assert form.cleaned_data["due_on"] is None


@pytest.mark.parametrize("junk", ["not-a-date", "2026-02-31", "NaN", "1e400"])
def test_riskcompliance_attestation_form_turns_a_junk_deadline_into_a_field_error(
        tenant_a, riskcompliance_policy_published, riskcompliance_member_a, junk):
    data = _riskcompliance_attestation_post(policy=riskcompliance_policy_published,
                                            user=riskcompliance_member_a, due_on=junk)
    form = PolicyAttestationForm(data, tenant=tenant_a)
    assert not _riskcompliance_is_valid(form)
    assert "due_on" in form.errors


# =================================================================================================
# 11. AuditSealForm — one field, and it cannot create a seal
# =================================================================================================

def test_riskcompliance_seal_form_note_is_optional_and_stripped(tenant_a):
    form = AuditSealForm({"note": "   Month-end close.   "}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["note"] == "Month-end close."


def test_riskcompliance_seal_form_accepts_an_empty_note(tenant_a):
    """Sealing is a POST button with an optional note beside it, not a page you fill in."""
    form = AuditSealForm({"note": "   "}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["note"] == ""
    assert AuditSealForm({}, tenant=tenant_a).is_valid()


def test_riskcompliance_seal_form_enforces_the_models_own_length_limit(tenant_a):
    """``TenantModelForm`` rather than a plain ``forms.Form`` so the 255 limit is inherited from
    the column instead of a second copy drifting out of step."""
    form = AuditSealForm({"note": "x" * 300}, tenant=tenant_a)
    assert not form.is_valid()
    assert "note" in form.errors
    assert form.fields["note"].max_length == 255


def test_riskcompliance_seal_form_cannot_save_a_seal(tenant_a):
    """A ``form.save()`` would write a seal with an empty digest, a zero range and no chain — a
    row that LOOKS like evidence and is not. The range is chosen under a lock by ``seal_now()``."""
    form = AuditSealForm({"note": "Month-end close."}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    with pytest.raises(NotImplementedError) as excinfo:
        form.save()
    assert "seal_now" in str(excinfo.value)
    assert AuditSeal.objects.filter(tenant=tenant_a).count() == 0


def test_riskcompliance_seal_form_binds_an_existing_seal_without_offering_its_digest(
        tenant_a, riskcompliance_seal):
    """Even bound to a real sealed row, the form still renders exactly one control — the digest,
    the chain and the range are not reachable from it."""
    form = AuditSealForm(instance=riskcompliance_seal, tenant=tenant_a)
    assert set(form.fields) == {"note"}
    assert form.initial.get("note") == riskcompliance_seal.note


# =================================================================================================
# 12. Signature parity — every form in the sub-module takes tenant=
# =================================================================================================

@pytest.mark.parametrize("form_class", [
    ComplianceScreeningForm, ScreeningHitForm, ScreeningHitDispositionForm,
    SupplierRiskSignalForm, FraudAlertForm, FraudScanForm, PolicyAttestationForm, AuditSealForm,
])
def test_riskcompliance_every_form_accepts_the_tenant_kwarg(tenant_a, form_class):
    """The call site never needs a special case: a ``forms.Form`` that REJECTED ``tenant=`` would
    be the one needing one."""
    form = form_class(tenant=tenant_a)
    assert form.tenant is tenant_a


def test_riskcompliance_fraud_disposition_accepts_tenant_and_alert(tenant_a,
                                                                   riskcompliance_fraud_open):
    form = FraudDispositionForm(tenant=tenant_a, alert=riskcompliance_fraud_open)
    assert form.tenant is tenant_a
    assert form.alert is riskcompliance_fraud_open
    assert set(form.fields) == {"action", "resolution_note", "suspension"}
