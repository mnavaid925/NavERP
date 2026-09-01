"""Procurement 6.14 Spend Analytics & Reporting - form tests.

This lane owns the crafted-POST boundary for the sub-module's THREE forms
(``SpendClassificationRuleForm``, ``MaverickSpendFindingForm``, ``SpendReportForm``) and the
two documented form EXEMPTIONS (``SpendReportSnapshot`` and the computed-dashboard lane, which
declare no form at all). Five things are asserted over and over:

1. **Nothing system-owned reaches a form field** (L20/L22). ``tenant``, the auto-numbers
   (``MSF-`` / ``SPR-``), the verb-only workflow ``status``, the authorship stamp ``owner``,
   the derived ``leakage_amount`` / ``dedupe_key``, the usage stamps ``match_count`` /
   ``last_matched_at`` / ``last_run_at`` and every system ``*_at`` timestamp stay OFF the form.
   Asserted twice: once as an explicit name list, once generically - EVERY ``editable=False``
   column of all three models is checked against its own form.
2. **Every FK ``<select>`` is tenant-scoped** - a field offered to tenant A never contains a
   tenant B row, and a tenant-less form (the superuser has ``tenant=None`` by design) offers
   nothing at all.
3. **The narrowed ``<select>`` is UX, not the boundary.** Each cross-tenant case is asserted
   TWICE: once against the narrowed queryset (layer 1, "Select a valid choice") and once with
   the queryset deliberately widened to simulate a hand-edited POST (layer 2, the explicit
   ``_reject_foreign`` / model ``clean()`` message).
4. **Every ``clean()`` rule is exercised** - the per-``match_type`` required subject, the
   invoice-type/committed contradiction, the "no evidence" refusal, the duplicated axis, the
   half-filled custom range and the reversed one.
5. **Every money field is friendly, never a 500** (L35) - ``NaN``, ``Infinity``, garbage,
   negatives and over-``max_digits`` figures land as FIELD errors.

Dates derive from ``timezone.localdate()`` - never ``date.today()`` - so exact-date assertions
stay stable in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django import forms
from django.utils import timezone

from apps.accounting.models import GLAccount
from apps.core.models import Party
from apps.procurement.forms import (
    MaverickSpendFindingForm,
    SpendClassificationRuleForm,
    SpendReportForm,
)
from apps.procurement.models import (
    CatalogItem,
    MaverickSpendFinding,
    SpendClassificationRule,
    SpendReport,
    SpendReportSnapshot,
    SupplierInvoice,
    SupplierInvoiceLine,
)
from apps.scm.models import ItemCategory

pytestmark = pytest.mark.django_db


# -- local helpers (module-level names are _spend_* so a later sub-module cannot shadow) --------

_SPEND_FOREIGN = "That record belongs to another workspace."


def _spend_day(offset=0):
    """A date derived from the SAME basis the models use (L16)."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _spend_iso(offset=0):
    return _spend_day(offset).strftime("%Y-%m-%d")


def _spend_widen(form, name, queryset):
    """Simulate a crafted POST: drop the narrowing so layer 2 (the explicit re-check) is what
    has to refuse the foreign pk."""
    form.fields[name].queryset = queryset
    return form


def _spend_rule_post(vendor=None, category=None, **overrides):
    """The minimum a classification-rule POST carries: a name, a match_type, its subject and the
    one required FK (``category``)."""
    data = {"name": "Meridian -> Office Supplies", "match_type": "vendor",
            "vendor": "", "gl_account": "", "org_unit": "", "keyword": "",
            "invoice_type": "", "category": "", "priority": "100",
            "applies_to": "both", "is_active": "on", "notes": ""}
    if vendor is not None:
        data["vendor"] = str(vendor.pk)
    if category is not None:
        data["category"] = str(category.pk)
    data.update(overrides)
    return data


def _spend_finding_post(vendor=None, invoice=None, **overrides):
    data = {"reason": "no_contract", "severity": "medium",
            "supplier_invoice": "", "invoice_line": "", "purchase_order": "",
            "vendor": "", "category": "", "org_unit": "", "contract": "",
            "catalog_item": "", "document_date": _spend_iso(),
            "amount": "250.00", "benchmark_amount": "", "is_addressable": "on",
            "detail": "Bought with no contract in force."}
    if vendor is not None:
        data["vendor"] = str(vendor.pk)
    if invoice is not None:
        data["supplier_invoice"] = str(invoice.pk)
    data.update(overrides)
    return data


def _spend_report_post(**overrides):
    data = {"name": "Top suppliers, last 90 days", "description": "",
            "basis": "invoiced", "measure": "net_spend",
            "dimension_1": "supplier", "dimension_2": "none",
            "date_range": "last_90", "date_from": "", "date_to": "",
            "vendor": "", "category": "", "org_unit": "", "gl_account": "",
            "min_amount": "", "chart_type": "bar", "top_n": "20",
            "is_shared": "on"}
    data.update(overrides)
    return data


def _spend_inactive_category(tenant, name="Retired taxonomy"):
    return ItemCategory.objects.create(tenant=tenant, name=name, is_active=False)


def _spend_inactive_gl(tenant, code="5999"):
    return GLAccount.objects.create(tenant=tenant, code=code, name="Retired expense",
                                    account_type="expense", is_active=False)


def _spend_roleless_party(tenant, name="Unroled Holdings"):
    """A Party with NO PartyRole - invisible to every 6.14 supplier dropdown by design."""
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _spend_editable_false(model):
    return {f.name for f in model._meta.fields if not f.editable}


# ===============================================================================================
# 1. Meta.fields contract - the mass-assignment guard (L20/L22)
# ===============================================================================================

def test_spend_rule_form_meta_fields_match_contract_exactly():
    assert SpendClassificationRuleForm.Meta.fields == [
        "name", "match_type", "vendor", "gl_account", "org_unit", "keyword",
        "invoice_type", "category", "priority", "applies_to", "is_active", "notes",
    ]


def test_spend_rule_form_never_exposes_tenant_or_usage_stamps(tenant_a):
    banned = {"tenant", "match_count", "last_matched_at", "created_at", "updated_at", "id"}
    assert not banned & set(SpendClassificationRuleForm.Meta.fields)
    form = SpendClassificationRuleForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(SpendClassificationRuleForm.Meta.fields)


def test_spend_rule_model_has_no_number_and_no_status_to_leak():
    """The configuration-master counter-example: no auto-number and no workflow column exist on
    this table at all, so there is nothing there for a form to ship."""
    names = {f.name for f in SpendClassificationRule._meta.get_fields()}
    assert "number" not in names
    assert "status" not in names
    assert getattr(SpendClassificationRule, "NUMBER_PREFIX", "") == ""


def test_spend_finding_form_meta_fields_match_contract_exactly():
    assert MaverickSpendFindingForm.Meta.fields == [
        "reason", "severity", "supplier_invoice", "invoice_line", "purchase_order",
        "vendor", "category", "org_unit", "contract", "catalog_item", "document_date",
        "amount", "benchmark_amount", "is_addressable", "detail",
    ]


def test_spend_finding_form_never_exposes_number_status_or_derived_columns(tenant_a):
    banned = {"tenant", "number", "status", "dedupe_key", "leakage_amount", "detected_at",
              "resolution_note", "resolved_by", "resolved_at", "created_at", "updated_at", "id"}
    assert not banned & set(MaverickSpendFindingForm.Meta.fields)
    form = MaverickSpendFindingForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(MaverickSpendFindingForm.Meta.fields)


def test_spend_finding_workflow_status_is_verb_only_not_a_posted_field(tenant_a, spend_vendor_a,
                                                                      spend_invoice_a):
    """A crafted POST carrying ``status=remediated`` must be IGNORED - the saved row is open."""
    data = _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                               status="remediated", number="MSF-99999",
                               leakage_amount="9999.00", resolution_note="hijacked")
    form = MaverickSpendFindingForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "open"
    assert obj.number == "MSF-00001"
    assert obj.resolution_note == ""
    assert obj.resolved_by_id is None and obj.resolved_at is None


def test_spend_report_form_meta_fields_match_contract_exactly():
    assert SpendReportForm.Meta.fields == [
        "name", "description", "basis", "measure", "dimension_1", "dimension_2",
        "date_range", "date_from", "date_to", "vendor", "category", "org_unit",
        "gl_account", "min_amount", "chart_type", "top_n", "is_favorite", "is_shared",
    ]


def test_spend_report_form_never_exposes_tenant_number_owner_or_last_run_at(tenant_a):
    banned = {"tenant", "number", "owner", "last_run_at", "created_at", "updated_at", "id"}
    assert not banned & set(SpendReportForm.Meta.fields)
    form = SpendReportForm(tenant=tenant_a)
    assert not banned & set(form.fields)
    assert set(form.fields) == set(SpendReportForm.Meta.fields)


def test_spend_report_owner_cannot_be_posted_by_a_colleague(tenant_a, member_user):
    """``owner`` is the authorship stamp taken from ``request.user`` on create only - a POST that
    names somebody else is dropped on the floor, not honoured."""
    form = SpendReportForm(_spend_report_post(owner=str(member_user.pk)), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.owner_id is None
    assert obj.last_run_at is None
    assert obj.number == "SPR-00001"


@pytest.mark.parametrize("model,form_class", [
    (SpendClassificationRule, SpendClassificationRuleForm),
    (MaverickSpendFinding, MaverickSpendFindingForm),
    (SpendReport, SpendReportForm),
])
def test_spend_no_editable_false_column_is_ever_a_form_field(tenant_a, model, form_class):
    """The generic form of assertions 1-2: every system-owned column (``editable=False``, which
    covers ``number``, the verb-only ``status``, the derived money and every ``auto_now*``
    stamp) is absent from the form that binds this model."""
    system_owned = _spend_editable_false(model)
    assert system_owned, "expected at least one system-owned column on this model"
    assert not system_owned & set(form_class(tenant=tenant_a).fields)


def test_spend_snapshot_has_no_form_anywhere():
    """The documented CRUD exemption: a snapshot is minted ONLY by the ``spendreport_snapshot``
    POST from a freshly computed result, so there is nothing to hand-type."""
    import apps.procurement.forms as procurement_forms
    from apps.procurement.forms.SpendAnalyticsReporting import SpendReports as report_forms

    assert not hasattr(procurement_forms, "SpendReportSnapshotForm")
    assert not hasattr(report_forms, "SpendReportSnapshotForm")
    bound = [obj for obj in vars(report_forms).values()
             if isinstance(obj, type) and issubclass(obj, forms.ModelForm)
             and getattr(getattr(obj, "Meta", None), "model", None) is SpendReportSnapshot]
    assert bound == []


def test_spend_dashboards_lane_declares_no_form_at_all():
    """The three computed pages are GET-driven and whitelist their parameters in the view - a
    ``Form`` would turn a hand-edited report URL into red text instead of an ignored filter."""
    from apps.procurement.forms.SpendAnalyticsReporting import SpendDashboards

    assert SpendDashboards.__all__ == []
    assert [obj for obj in vars(SpendDashboards).values()
            if isinstance(obj, type) and issubclass(obj, forms.BaseForm)] == []


# ===============================================================================================
# 2. SpendClassificationRuleForm - required fields and the per-match_type subject rule
# ===============================================================================================

def test_spend_rule_form_requires_name_and_category(tenant_a):
    form = SpendClassificationRuleForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "category" in form.errors


def test_spend_rule_form_valid_post_saves_against_the_request_tenant(tenant_a, spend_vendor_a,
                                                                    spend_category_a):
    form = SpendClassificationRuleForm(
        _spend_rule_post(vendor=spend_vendor_a, category=spend_category_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.category_id == spend_category_a.pk
    # The usage stamps are untouched by a create - they belong to the preview verb.
    assert obj.match_count == 0
    assert obj.last_matched_at is None


@pytest.mark.parametrize("match_type,missing_field", [
    ("vendor", "vendor"),
    ("gl_account", "gl_account"),
    ("keyword", "keyword"),
    ("invoice_type", "invoice_type"),
    ("org_unit", "org_unit"),
])
def test_spend_rule_form_rejects_a_rule_whose_subject_is_missing(tenant_a, spend_category_a,
                                                                match_type, missing_field):
    """A subject-less rule would match EVERY line on both bases and swallow the whole cube into
    one category - the single most damaging thing this table can do."""
    form = SpendClassificationRuleForm(
        _spend_rule_post(category=spend_category_a, match_type=match_type), tenant=tenant_a)
    assert not form.is_valid()
    assert missing_field in form.errors
    assert "needs this field set" in " ".join(form.errors[missing_field])
    assert SpendClassificationRule.objects.count() == 0


def test_spend_rule_form_rejects_an_unknown_match_type(tenant_a, spend_category_a):
    form = SpendClassificationRuleForm(
        _spend_rule_post(category=spend_category_a, match_type="astrology"), tenant=tenant_a)
    assert not form.is_valid()
    assert "match_type" in form.errors


def test_spend_rule_form_rejects_free_text_invoice_type(tenant_a, spend_category_a):
    """``invoice_type`` is a plain CharField on the model; the form re-declares it as a
    ChoiceField so a typo cannot create a rule that can never match and never say why."""
    form = SpendClassificationRuleForm(
        _spend_rule_post(category=spend_category_a, match_type="invoice_type",
                         invoice_type="totally-made-up"), tenant=tenant_a)
    assert not form.is_valid()
    assert "invoice_type" in form.errors
    assert isinstance(SpendClassificationRuleForm(tenant=tenant_a).fields["invoice_type"],
                      forms.ChoiceField)


def test_spend_rule_form_invoice_type_choices_come_from_the_invoice_vocabulary(tenant_a):
    field = SpendClassificationRuleForm(tenant=tenant_a).fields["invoice_type"]
    offered = [value for value, _label in field.choices]
    assert offered[0] == ""
    assert offered[1:] == [value for value, _label in SupplierInvoice.INVOICE_TYPE_CHOICES]
    assert field.required is False


def test_spend_rule_form_accepts_a_known_invoice_type(tenant_a, spend_category_a):
    form = SpendClassificationRuleForm(
        _spend_rule_post(category=spend_category_a, match_type="invoice_type",
                         invoice_type="service"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().invoice_type == "service"


def test_spend_rule_form_rejects_an_invoice_type_rule_on_the_committed_basis(tenant_a,
                                                                            spend_category_a):
    """A purchase order has no invoice type at all - the contradiction is keyed on applies_to."""
    form = SpendClassificationRuleForm(
        _spend_rule_post(category=spend_category_a, match_type="invoice_type",
                         invoice_type="credit_memo", applies_to="committed"), tenant=tenant_a)
    assert not form.is_valid()
    assert "applies_to" in form.errors
    assert "committed" in " ".join(form.errors["applies_to"])


def test_spend_rule_form_rejects_an_over_length_keyword(tenant_a, spend_category_a):
    form = SpendClassificationRuleForm(
        _spend_rule_post(category=spend_category_a, match_type="keyword",
                         keyword="x" * 121), tenant=tenant_a)
    assert not form.is_valid()
    assert "keyword" in form.errors


def test_spend_rule_form_rejects_a_negative_priority(tenant_a, spend_vendor_a, spend_category_a):
    form = SpendClassificationRuleForm(
        _spend_rule_post(vendor=spend_vendor_a, category=spend_category_a, priority="-5"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "priority" in form.errors


def test_spend_rule_form_allows_two_same_shaped_rules_at_different_priorities(
        tenant_a, spend_vendor_a, spend_category_a, spend_rule_vendor_a):
    """There is NO unique_together on this table by design: a workspace-wide rule PLUS a narrower
    exception is a legitimate configuration, and the resolver's (priority, id) order decides."""
    form = SpendClassificationRuleForm(
        _spend_rule_post(vendor=spend_vendor_a, category=spend_category_a,
                         name="Meridian exception", priority="5"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert SpendClassificationRule.objects.filter(tenant=tenant_a,
                                                 vendor=spend_vendor_a).count() == 2
    assert obj.priority == 5


def test_spend_rule_form_edit_keeps_the_usage_stamps_it_never_offered(tenant_a,
                                                                     spend_rule_vendor_a,
                                                                     spend_vendor_a,
                                                                     spend_category_a):
    stamped_at = timezone.now()
    SpendClassificationRule.objects.filter(pk=spend_rule_vendor_a.pk).update(
        match_count=7, last_matched_at=stamped_at)
    spend_rule_vendor_a.refresh_from_db()
    form = SpendClassificationRuleForm(
        _spend_rule_post(vendor=spend_vendor_a, category=spend_category_a,
                         name="Renamed rule"),
        tenant=tenant_a, instance=spend_rule_vendor_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.name == "Renamed rule"
    assert obj.match_count == 7
    assert obj.last_matched_at == stamped_at


# ===============================================================================================
# 3. SpendClassificationRuleForm - tenant-scoped dropdowns and the crafted-POST re-check
# ===============================================================================================

def test_spend_rule_form_dropdowns_are_scoped_to_the_workspace(
        tenant_a, spend_vendor_a, spend_vendor_b, spend_category_a, spend_category_b,
        gl_expense_a, gl_expense_b, org_unit_a, org_unit_b):
    form = SpendClassificationRuleForm(tenant=tenant_a)
    assert list(form.fields["vendor"].queryset) == [spend_vendor_a]
    assert spend_vendor_b not in form.fields["vendor"].queryset
    assert list(form.fields["category"].queryset) == [spend_category_a]
    assert spend_category_b not in form.fields["category"].queryset
    assert list(form.fields["gl_account"].queryset) == [gl_expense_a]
    assert gl_expense_b not in form.fields["gl_account"].queryset
    assert list(form.fields["org_unit"].queryset) == [org_unit_a]
    assert org_unit_b not in form.fields["org_unit"].queryset


def test_spend_rule_form_only_category_is_required_among_the_fks(tenant_a):
    form = SpendClassificationRuleForm(tenant=tenant_a)
    assert form.fields["category"].required is True
    for name in ("vendor", "gl_account", "org_unit"):
        assert form.fields[name].required is False


def test_spend_rule_form_hides_inactive_masters(tenant_a, spend_category_a, gl_expense_a):
    retired_category = _spend_inactive_category(tenant_a)
    retired_gl = _spend_inactive_gl(tenant_a)
    form = SpendClassificationRuleForm(tenant=tenant_a)
    assert retired_category not in form.fields["category"].queryset
    assert retired_gl not in form.fields["gl_account"].queryset
    assert spend_category_a in form.fields["category"].queryset
    assert gl_expense_a in form.fields["gl_account"].queryset


def test_spend_rule_form_vendor_dropdown_skips_a_party_with_no_supplier_role(tenant_a,
                                                                            spend_vendor_a):
    roleless = _spend_roleless_party(tenant_a)
    form = SpendClassificationRuleForm(tenant=tenant_a)
    assert spend_vendor_a in form.fields["vendor"].queryset
    assert roleless not in form.fields["vendor"].queryset


def test_spend_rule_form_with_no_tenant_offers_nothing(spend_vendor_a, spend_category_a,
                                                       gl_expense_a, org_unit_a):
    """The superuser has ``tenant=None`` by design; a tenant-less form must not be able to see
    OR post another workspace's rows."""
    form = SpendClassificationRuleForm(tenant=None)
    for name in ("vendor", "gl_account", "org_unit", "category"):
        assert list(form.fields[name].queryset) == []


def test_spend_rule_form_layer1_narrowed_select_refuses_a_foreign_category(tenant_a,
                                                                          spend_vendor_a,
                                                                          spend_category_b):
    form = SpendClassificationRuleForm(
        _spend_rule_post(vendor=spend_vendor_a, category=spend_category_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["category"])
    assert not SpendClassificationRule.objects.filter(category=spend_category_b).exists()


@pytest.mark.parametrize("field_name", ["vendor", "gl_account", "org_unit", "category"])
def test_spend_rule_form_layer2_rejects_a_crafted_foreign_pk(
        tenant_a, spend_vendor_a, spend_vendor_b, spend_category_a, spend_category_b,
        gl_expense_b, org_unit_b, field_name):
    """A narrowed ``<select>`` is UX; the hand-edited POST never goes near it. Widen the queryset
    and the explicit re-check is what has to refuse the row."""
    foreign = {"vendor": spend_vendor_b, "gl_account": gl_expense_b,
               "org_unit": org_unit_b, "category": spend_category_b}[field_name]
    payload = _spend_rule_post(vendor=spend_vendor_a, category=spend_category_a)
    payload[field_name] = str(foreign.pk)
    if field_name in ("gl_account", "org_unit"):
        payload["match_type"] = field_name
        payload["vendor"] = ""
    form = SpendClassificationRuleForm(payload, tenant=tenant_a)
    _spend_widen(form, field_name, type(foreign).objects.all())
    assert not form.is_valid()
    assert _SPEND_FOREIGN in form.errors[field_name]
    assert not SpendClassificationRule.objects.filter(**{field_name: foreign}).exists()


# ===============================================================================================
# 4. MaverickSpendFindingForm - required fields, evidence and the clean() rules
# ===============================================================================================

def test_spend_finding_form_requires_reason_vendor_date_and_amount(tenant_a):
    form = MaverickSpendFindingForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("reason", "vendor", "document_date", "amount"):
        assert name in form.errors, f"expected {name} to be required"


def test_spend_finding_form_valid_post_saves_against_the_request_tenant(tenant_a, spend_vendor_a,
                                                                       spend_invoice_a):
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("MSF-")
    assert obj.document_date == _spend_day()
    assert obj.dedupe_key == f"no_contract:inv:{spend_invoice_a.pk}"


def test_spend_finding_form_refuses_a_finding_with_no_evidence(tenant_a, spend_vendor_a):
    """Absent-prerequisite must be REJECTED, not fall through to a saved row (L35)."""
    form = MaverickSpendFindingForm(_spend_finding_post(vendor=spend_vendor_a), tenant=tenant_a)
    assert not form.is_valid()
    assert "no evidence" in " ".join(form.errors["supplier_invoice"])
    assert MaverickSpendFinding.objects.count() == 0


def test_spend_finding_form_refuses_a_line_from_a_different_invoice(
        tenant_a, spend_vendor_a, spend_invoice_a, spend_invoice_line_a, usd):
    other_invoice = SupplierInvoice.objects.create(
        tenant=tenant_a, vendor=spend_vendor_a, invoice_number="SUP-4402",
        invoice_date=_spend_day(), status="approved", invoice_type="standard", currency=usd)
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=other_invoice,
                            invoice_line=str(spend_invoice_line_a.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "different invoice" in " ".join(form.errors["invoice_line"])


def test_spend_finding_form_refuses_a_benchmark_above_the_amount(tenant_a, spend_vendor_a,
                                                                 spend_invoice_a):
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                            amount="200.00", benchmark_amount="250.00"), tenant=tenant_a)
    assert not form.is_valid()
    assert "no leakage to record" in " ".join(form.errors["benchmark_amount"])


def test_spend_finding_form_derives_leakage_it_never_offered(tenant_a, spend_vendor_a,
                                                             spend_invoice_a):
    """``leakage_amount`` is DERIVED in save() from amount - benchmark; it is not a stored,
    editable balance (L29) and it is not a form field."""
    assert "leakage_amount" not in MaverickSpendFindingForm(tenant=tenant_a).fields
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                            amount="250.00", benchmark_amount="200.00"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().leakage_amount == Decimal("50.00")


def test_spend_finding_form_equal_benchmark_is_zero_leakage(tenant_a, spend_vendor_a,
                                                            spend_invoice_a):
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                            amount="250.00", benchmark_amount="250.00"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().leakage_amount == Decimal("0.00")


def test_spend_finding_form_refuses_an_unknown_reason(tenant_a, spend_vendor_a, spend_invoice_a):
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                            reason="because_i_said_so"), tenant=tenant_a)
    assert not form.is_valid()
    assert "reason" in form.errors


def test_spend_finding_form_refuses_a_duplicate_of_the_same_document(tenant_a, spend_vendor_a,
                                                                     spend_invoice_a,
                                                                     spend_finding_open_a):
    """The ``(tenant, dedupe_key)`` unique_together renders as a friendly field error, never an
    IntegrityError 500 out of the POST."""
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                            reason=spend_finding_open_a.reason), tenant=tenant_a)
    assert not form.is_valid()
    assert "already exists" in " ".join(form.errors["reason"])
    assert MaverickSpendFinding.objects.filter(tenant=tenant_a).count() == 1


def test_spend_finding_form_refuses_a_document_date_outside_the_calendar(tenant_a, spend_vendor_a,
                                                                        spend_invoice_a):
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                            document_date="1800-01-01"), tenant=tenant_a)
    assert not form.is_valid()
    assert "document_date" in form.errors


def test_spend_finding_form_document_date_uses_a_native_date_widget(tenant_a):
    form = MaverickSpendFindingForm(tenant=tenant_a)
    widget = form.fields["document_date"].widget
    assert isinstance(widget, forms.DateInput)
    # Django's Input.__init__ POPS "type" out of attrs onto widget.input_type, so input_type is
    # where the convention lives - attrs keeps only the styling class. Same assertion the sibling
    # 6.10 / 6.12 date-widget tests make.
    assert widget.input_type == "date"
    assert widget.format == "%Y-%m-%d"
    # The contract that actually matters is what the browser gets.
    assert 'type="date"' in str(form["document_date"])


@pytest.mark.parametrize("field_name", ["amount", "benchmark_amount"])
@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity", "not-a-number", "-1",
                                  "12345678901234567890.00"])
def test_spend_finding_form_money_junk_is_a_field_error_never_a_crash(
        tenant_a, spend_vendor_a, spend_invoice_a, field_name, junk):
    """L35: every hand-parsed money surface degrades to a friendly field error."""
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                            **{field_name: junk}), tenant=tenant_a)
    assert not form.is_valid()
    assert field_name in form.errors
    assert MaverickSpendFinding.objects.count() == 0


def test_spend_finding_form_money_fields_mirror_the_model_column(tenant_a):
    form = MaverickSpendFindingForm(tenant=tenant_a)
    for name, required in (("amount", True), ("benchmark_amount", False)):
        field = form.fields[name]
        assert isinstance(field, forms.DecimalField)
        assert field.max_digits == 18 and field.decimal_places == 2
        assert field.min_value == 0
        assert field.required is required


# ===============================================================================================
# 5. MaverickSpendFindingForm - tenant-scoped dropdowns and the crafted-POST re-check
# ===============================================================================================

def test_spend_finding_form_dropdowns_are_scoped_to_the_workspace(
        tenant_a, spend_invoice_a, spend_invoice_b, spend_invoice_line_a, spend_invoice_line_b,
        spend_po_a, spend_po_b, spend_vendor_a, spend_vendor_b, spend_category_a,
        spend_category_b, org_unit_a, org_unit_b, spend_contract_a, spend_contract_b,
        spend_catalog_item_a, catalog_item_b):
    form = MaverickSpendFindingForm(tenant=tenant_a)
    mine = {"supplier_invoice": spend_invoice_a, "invoice_line": spend_invoice_line_a,
            "purchase_order": spend_po_a, "vendor": spend_vendor_a,
            "category": spend_category_a, "org_unit": org_unit_a,
            "contract": spend_contract_a, "catalog_item": spend_catalog_item_a}
    theirs = {"supplier_invoice": spend_invoice_b, "invoice_line": spend_invoice_line_b,
              "purchase_order": spend_po_b, "vendor": spend_vendor_b,
              "category": spend_category_b, "org_unit": org_unit_b,
              "contract": spend_contract_b, "catalog_item": catalog_item_b}
    for name, row in mine.items():
        assert row in form.fields[name].queryset, f"{name} should offer this workspace's row"
    for name, row in theirs.items():
        assert row not in form.fields[name].queryset, f"{name} leaked a tenant-B row"


def test_spend_finding_form_invoice_line_is_scoped_through_its_header(tenant_a,
                                                                     spend_invoice_line_a,
                                                                     spend_invoice_line_b):
    """``SupplierInvoiceLine`` carries NO tenant column - it is narrowed through
    ``invoice__tenant``, which is why it is also re-checked separately in clean()."""
    line_field = MaverickSpendFindingForm(tenant=tenant_a).fields["invoice_line"]
    assert "tenant" not in {f.name for f in SupplierInvoiceLine._meta.fields}
    assert list(line_field.queryset) == [spend_invoice_line_a]
    assert spend_invoice_line_b not in line_field.queryset


def test_spend_finding_form_edit_narrows_lines_to_the_named_invoice(
        tenant_a, spend_vendor_a, spend_invoice_a, spend_invoice_line_a, usd):
    other_invoice = SupplierInvoice.objects.create(
        tenant=tenant_a, vendor=spend_vendor_a, invoice_number="SUP-4403",
        invoice_date=_spend_day(), status="approved", invoice_type="standard", currency=usd)
    other_line = SupplierInvoiceLine.objects.create(
        invoice=other_invoice, description="Unrelated line", sku_hint="ZZZ-1",
        quantity=Decimal("1"), unit_price=Decimal("10.00"))
    finding = MaverickSpendFinding.objects.create(
        tenant=tenant_a, vendor=spend_vendor_a, supplier_invoice=spend_invoice_a,
        reason="no_contract", document_date=_spend_day(), amount=Decimal("250.00"))
    form = MaverickSpendFindingForm(tenant=tenant_a, instance=finding)
    assert spend_invoice_line_a in form.fields["invoice_line"].queryset
    assert other_line not in form.fields["invoice_line"].queryset


def test_spend_finding_form_catalog_dropdown_offers_only_approved_active_entries(
        tenant_a, spend_catalog_item_a):
    pending = CatalogItem.objects.create(
        tenant=tenant_a, source_type="supplier_product", name="Pending gloves",
        supplier_part_no="NW-GLOVE-D1", base_price=Decimal("34.90"), status="pending_approval")
    retired = CatalogItem.objects.create(
        tenant=tenant_a, source_type="supplier_product", name="Retired gloves",
        supplier_part_no="NW-GLOVE-D2", base_price=Decimal("30.00"), status="approved",
        is_active=False)
    field = MaverickSpendFindingForm(tenant=tenant_a).fields["catalog_item"]
    assert spend_catalog_item_a in field.queryset
    assert pending not in field.queryset
    assert retired not in field.queryset


def test_spend_finding_form_with_no_tenant_offers_nothing(
        spend_invoice_a, spend_invoice_line_a, spend_po_a, spend_vendor_a, spend_category_a,
        org_unit_a, spend_contract_a, spend_catalog_item_a):
    form = MaverickSpendFindingForm(tenant=None)
    for name in ("supplier_invoice", "invoice_line", "purchase_order", "vendor", "category",
                 "org_unit", "contract", "catalog_item"):
        assert list(form.fields[name].queryset) == [], f"{name} offered rows with no tenant"


def test_spend_finding_form_layer1_narrowed_select_refuses_a_foreign_invoice(tenant_a,
                                                                            spend_vendor_a,
                                                                            spend_invoice_b):
    form = MaverickSpendFindingForm(
        _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["supplier_invoice"])
    assert MaverickSpendFinding.objects.count() == 0


@pytest.mark.parametrize("field_name", ["supplier_invoice", "purchase_order", "vendor",
                                        "category", "org_unit", "contract", "catalog_item"])
def test_spend_finding_form_layer2_rejects_a_crafted_foreign_pk(
        tenant_a, spend_vendor_a, spend_invoice_a, spend_invoice_b, spend_po_b, spend_vendor_b,
        spend_category_b, org_unit_b, spend_contract_b, catalog_item_b, field_name):
    foreign = {"supplier_invoice": spend_invoice_b, "purchase_order": spend_po_b,
               "vendor": spend_vendor_b, "category": spend_category_b, "org_unit": org_unit_b,
               "contract": spend_contract_b, "catalog_item": catalog_item_b}[field_name]
    payload = _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a)
    payload[field_name] = str(foreign.pk)
    form = MaverickSpendFindingForm(payload, tenant=tenant_a)
    _spend_widen(form, field_name, type(foreign).objects.all())
    assert not form.is_valid()
    assert _SPEND_FOREIGN in form.errors[field_name]
    assert MaverickSpendFinding.objects.count() == 0


def test_spend_finding_form_layer2_rejects_a_crafted_foreign_invoice_line(
        tenant_a, spend_vendor_a, spend_invoice_a, spend_invoice_line_b):
    """The one FK that ``_reject_foreign`` cannot check (no tenant column) is checked by hand
    through ``line.invoice.tenant_id`` - and must carry the SAME message."""
    payload = _spend_finding_post(vendor=spend_vendor_a, invoice=spend_invoice_a,
                                  invoice_line=str(spend_invoice_line_b.pk))
    form = MaverickSpendFindingForm(payload, tenant=tenant_a)
    _spend_widen(form, "invoice_line", SupplierInvoiceLine.objects.all())
    assert not form.is_valid()
    assert _SPEND_FOREIGN in form.errors["invoice_line"]
    assert MaverickSpendFinding.objects.count() == 0


# ===============================================================================================
# 6. SpendReportForm - the builder's clean() rules
# ===============================================================================================

def test_spend_report_form_requires_a_name(tenant_a):
    form = SpendReportForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


def test_spend_report_form_valid_post_saves_against_the_request_tenant(tenant_a):
    form = SpendReportForm(_spend_report_post(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == "SPR-00001"
    assert obj.basis == "invoiced" and obj.measure == "net_spend"
    assert obj.is_shared is True and obj.is_favorite is False


def test_spend_report_form_refuses_the_same_dimension_twice(tenant_a):
    form = SpendReportForm(
        _spend_report_post(dimension_1="supplier", dimension_2="supplier"), tenant=tenant_a)
    assert not form.is_valid()
    assert "dimension_2" in form.errors
    assert "different second dimension" in " ".join(form.errors["dimension_2"])


def test_spend_report_form_allows_none_on_both_axes(tenant_a):
    """"none" twice is the legitimate single-figure report, not a duplicated axis."""
    form = SpendReportForm(
        _spend_report_post(dimension_1="none", dimension_2="none"), tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("missing", ["date_from", "date_to"])
def test_spend_report_form_refuses_a_half_filled_custom_range(tenant_a, missing):
    payload = _spend_report_post(date_range="custom", date_from=_spend_iso(-30),
                                 date_to=_spend_iso())
    payload[missing] = ""
    form = SpendReportForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert missing in form.errors
    assert "custom range needs" in " ".join(form.errors[missing])


def test_spend_report_form_refuses_a_reversed_custom_range(tenant_a):
    form = SpendReportForm(
        _spend_report_post(date_range="custom", date_from=_spend_iso(),
                           date_to=_spend_iso(-30)), tenant=tenant_a)
    assert not form.is_valid()
    assert "date_from" in form.errors
    assert "cannot be after" in " ".join(form.errors["date_from"])


@pytest.mark.parametrize("bound", ["date_from", "date_to"])
def test_spend_report_form_refuses_a_date_outside_1900_9999(tenant_a, bound):
    payload = _spend_report_post(date_range="custom", date_from=_spend_iso(-30),
                                 date_to=_spend_iso())
    payload[bound] = "1899-12-31"
    form = SpendReportForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert bound in form.errors


def test_spend_report_form_accepts_a_well_formed_custom_range(tenant_a):
    form = SpendReportForm(
        _spend_report_post(date_range="custom", date_from=_spend_iso(-30),
                           date_to=_spend_iso()), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.date_from == _spend_day(-30) and obj.date_to == _spend_day()
    assert obj.is_custom_range is True


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "not-a-number", "-1",
                                  "12345678901234567890.00"])
def test_spend_report_form_min_amount_junk_is_a_field_error_never_a_crash(tenant_a, junk):
    form = SpendReportForm(_spend_report_post(min_amount=junk), tenant=tenant_a)
    assert not form.is_valid()
    assert "min_amount" in form.errors
    assert SpendReport.objects.count() == 0


def test_spend_report_form_min_amount_mirrors_the_model_column(tenant_a):
    field = SpendReportForm(tenant=tenant_a).fields["min_amount"]
    assert isinstance(field, forms.DecimalField)
    assert field.max_digits == 18 and field.decimal_places == 2
    assert field.min_value == 0 and field.required is False


@pytest.mark.parametrize("value", ["0", "101", "-3"])
def test_spend_report_form_refuses_a_top_n_outside_1_100(tenant_a, value):
    form = SpendReportForm(_spend_report_post(top_n=value), tenant=tenant_a)
    assert not form.is_valid()
    assert "top_n" in form.errors


@pytest.mark.parametrize("field_name", ["basis", "measure", "dimension_1", "dimension_2",
                                        "date_range", "chart_type"])
def test_spend_report_form_refuses_an_off_vocabulary_choice(tenant_a, field_name):
    form = SpendReportForm(_spend_report_post(**{field_name: "vibes"}), tenant=tenant_a)
    assert not form.is_valid()
    assert field_name in form.errors


# ===============================================================================================
# 7. SpendReportForm - tenant-scoped dropdowns and the crafted-POST re-check
# ===============================================================================================

def test_spend_report_form_dropdowns_are_scoped_to_the_workspace(
        tenant_a, spend_vendor_a, spend_vendor_b, spend_category_a, spend_category_b,
        org_unit_a, org_unit_b, gl_expense_a, gl_expense_b):
    form = SpendReportForm(tenant=tenant_a)
    assert list(form.fields["vendor"].queryset) == [spend_vendor_a]
    assert list(form.fields["category"].queryset) == [spend_category_a]
    assert list(form.fields["org_unit"].queryset) == [org_unit_a]
    assert list(form.fields["gl_account"].queryset) == [gl_expense_a]
    for name, foreign in (("vendor", spend_vendor_b), ("category", spend_category_b),
                          ("org_unit", org_unit_b), ("gl_account", gl_expense_b)):
        assert foreign not in form.fields[name].queryset


def test_spend_report_form_narrowing_dropdowns_are_optional_and_labelled_any(tenant_a):
    form = SpendReportForm(tenant=tenant_a)
    for name in ("vendor", "category", "org_unit", "gl_account"):
        assert form.fields[name].required is False
        assert form.fields[name].empty_label == "- any -"


def test_spend_report_form_hides_inactive_masters(tenant_a, spend_category_a, gl_expense_a):
    retired_category = _spend_inactive_category(tenant_a)
    retired_gl = _spend_inactive_gl(tenant_a)
    form = SpendReportForm(tenant=tenant_a)
    assert retired_category not in form.fields["category"].queryset
    assert retired_gl not in form.fields["gl_account"].queryset


def test_spend_report_form_vendor_dropdown_skips_a_party_with_no_supplier_role(tenant_a,
                                                                               spend_vendor_a):
    roleless = _spend_roleless_party(tenant_a, "Reportless Holdings")
    field = SpendReportForm(tenant=tenant_a).fields["vendor"]
    assert spend_vendor_a in field.queryset
    assert roleless not in field.queryset


def test_spend_report_form_with_no_tenant_offers_nothing(spend_vendor_a, spend_category_a,
                                                         org_unit_a, gl_expense_a):
    form = SpendReportForm(tenant=None)
    for name in ("vendor", "category", "org_unit", "gl_account"):
        assert list(form.fields[name].queryset) == []


def test_spend_report_form_layer1_narrowed_select_refuses_a_foreign_vendor(tenant_a,
                                                                          spend_vendor_b):
    form = SpendReportForm(_spend_report_post(vendor=str(spend_vendor_b.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["vendor"])
    assert SpendReport.objects.count() == 0


@pytest.mark.parametrize("field_name", ["vendor", "category", "org_unit", "gl_account"])
def test_spend_report_form_layer2_rejects_a_crafted_foreign_pk(
        tenant_a, spend_vendor_b, spend_category_b, org_unit_b, gl_expense_b, field_name):
    foreign = {"vendor": spend_vendor_b, "category": spend_category_b,
               "org_unit": org_unit_b, "gl_account": gl_expense_b}[field_name]
    form = SpendReportForm(_spend_report_post(**{field_name: str(foreign.pk)}), tenant=tenant_a)
    _spend_widen(form, field_name, type(foreign).objects.all())
    assert not form.is_valid()
    assert _SPEND_FOREIGN in form.errors[field_name]
    assert SpendReport.objects.count() == 0
