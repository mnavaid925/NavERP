"""Procurement 6.14 - Spend Analytics & Reporting MODEL tests.

The invariants this lane owns:

* ``SpendClassificationRule`` as a CONFIGURATION MASTER - ``TenantOwned``, no ``number``, no
  ``status`` and deliberately NO ``unique_together``: two same-shaped rules at different
  priorities are a legitimate configuration, and the resolver (not a database constraint) decides
  which one wins;
* the rule engine itself - ``matches()`` (the PURE row-level authority), ``line_filter()`` (its
  SQL mirror, whose ``None`` means "can match nothing on this basis", never "no filter"),
  ``matching_lines()``, ``preview()`` and the ``resolve()`` classmethod that re-filters a
  caller-supplied rule list by the LINE's own workspace;
* per-tenant ``MSF-`` / ``SPR-`` auto-numbering (prefix, five-digit padding, sequence, and no
  collision across tenants) plus ``unique_together`` with ``tenant`` on both numbered models AND
  on ``MaverickSpendFinding.dedupe_key``;
* every REASON / SEVERITY / STATUS / BASIS / MEASURE / DIMENSION / DATE_RANGE / CHART_TYPE /
  MATCH_TYPE / APPLIES_TO choice value, and the colour-only badge maps (a semantic
  ``badge-success`` renders completely unstyled in this theme - L33);
* the guarded verb ladder - ``acknowledge`` / ``justify`` / ``remediate`` / ``dismiss`` - each of
  which re-checks its own guard INSIDE the method, returns a bool, and no-ops on a double submit
  rather than re-stamping who signed;
* and the invariant the whole sub-module lives on (L29): **nothing is stored that can be
  derived**. ``SpendClassificationRule.preview()`` aggregates from the source lines on EVERY call
  and has no cached value column; ``MaverickSpendFinding.leakage_amount`` and ``dedupe_key`` are
  recomputed in ``save()`` and are ``editable=False``; ``SpendReport`` stores only the QUESTION
  (it carries no result column at all); and ``SpendReportSnapshot`` is the ONLY place a computed
  result is ever persisted.

Determinism (L16): every date basis here is ``timezone.localdate()`` and every datetime basis is
``timezone.now()`` - the same bases the model code uses. ``datetime.date.today()`` never appears,
or the exact-window assertions flake for the hours after local midnight.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q
from django.utils import timezone

from apps.procurement.models import (
    MaverickSpendFinding,
    SpendClassificationRule,
    SpendReport,
    SpendReportSnapshot,
    committed_line_window,
    invoiced_line_window,
)
from apps.procurement.models.SpendAnalyticsReporting import SpendClassificationRules as _spend_rules_mod

pytestmark = pytest.mark.django_db


# -- local helpers ------------------------------------------------------------------------------
# Named _spend_* so the next sub-module appending near this file cannot shadow them, and so a
# failure names its own lane. The conftest factories of the same shape are private to conftest
# (the 6.11/6.12 precedent), so the extra rows this module needs are minted here.

#: theme.css ships exactly these modifier classes. Anything else renders completely unstyled (L33).
_SPEND_BADGE_COLOURS = {
    "badge-green", "badge-red", "badge-amber", "badge-info", "badge-muted", "badge-slate",
}

#: The middot MaverickSpendFinding.__str__ folds into its label.
_SPEND_DOT = "·"


def _spend_today():
    """The SAME date basis the models use (L16) - never ``datetime.date.today()``."""
    return timezone.localdate()


def _spend_window(before=1, after=1):
    """``(start, end)`` around today, ``end`` EXCLUSIVE - the shape every 6.14 window uses."""
    today = _spend_today()
    return today - datetime.timedelta(days=before), today + datetime.timedelta(days=after)


def _spend_rule_row(tenant, category, **overrides):
    """A saved SpendClassificationRule; defaults mirror the conftest factory."""
    fields = dict(tenant=tenant, name="Local rule", match_type="vendor", category=category,
                  priority=100, applies_to="both", is_active=True)
    fields.update(overrides)
    return SpendClassificationRule.objects.create(**fields)


def _spend_finding_row(tenant, vendor, **overrides):
    """A saved MaverickSpendFinding. ``dedupe_key`` and ``leakage_amount`` are DERIVED in save()
    - never pass either, and vary reason/pointer because ``(tenant, dedupe_key)`` is unique."""
    fields = dict(tenant=tenant, vendor=vendor, reason="no_contract",
                  document_date=_spend_today(), amount=Decimal("250.00"))
    fields.update(overrides)
    return MaverickSpendFinding.objects.create(**fields)


def _spend_report_row(tenant, **overrides):
    fields = dict(tenant=tenant, name="Local report")
    fields.update(overrides)
    return SpendReport.objects.create(**fields)


def _spend_invoice_line_row(invoice, **overrides):
    from apps.procurement.models import SupplierInvoiceLine
    fields = dict(invoice=invoice, description="Extra line", sku_hint="EXT-1",
                  quantity=Decimal("1"), unit_price=Decimal("10.00"))
    fields.update(overrides)
    return SupplierInvoiceLine.objects.create(**fields)


def _spend_field(model, name):
    return model._meta.get_field(name)


def _spend_field_names(model):
    return {f.name for f in model._meta.get_fields()}


# =================================================================================================
# SpendClassificationRule - shape, defaults, __str__
# =================================================================================================

def test_spend_rule_defaults_are_the_documented_ones(tenant_a, spend_category_a):
    rule = SpendClassificationRule.objects.create(
        tenant=tenant_a, name="Bare rule", category=spend_category_a,
        vendor=None, match_type="keyword", keyword="paper")
    rule.refresh_from_db()
    assert rule.applies_to == "both"
    assert rule.priority == 100
    assert rule.is_active is True
    assert rule.invoice_type == ""
    assert rule.notes == ""
    assert rule.match_count == 0
    assert rule.last_matched_at is None
    assert rule.created_at is not None and rule.updated_at is not None


def test_spend_rule_match_type_default_is_vendor():
    assert _spend_field(SpendClassificationRule, "match_type").default == "vendor"
    assert _spend_field(SpendClassificationRule, "applies_to").default == "both"
    assert _spend_field(SpendClassificationRule, "priority").default == 100
    assert _spend_field(SpendClassificationRule, "is_active").default is True


def test_spend_rule_str_folds_the_category(spend_rule_vendor_a, spend_category_a):
    assert str(spend_rule_vendor_a) == f"{spend_rule_vendor_a.name} -> {spend_category_a}"


def test_spend_rule_str_falls_back_to_name_without_a_category():
    """An unsaved instance (a ModelForm rendering its own errors) must never 500 on __str__."""
    assert str(SpendClassificationRule(name="Half-built rule")) == "Half-built rule"


def test_spend_rule_is_a_configuration_master_not_a_document():
    names = _spend_field_names(SpendClassificationRule)
    assert "number" not in names
    assert "status" not in names
    assert "owner" not in names
    # TenantOwned, not TenantNumbered.
    assert {"tenant", "created_at", "updated_at"} <= names


def test_spend_rule_declares_no_unique_together():
    """Two same-shaped rules at different priorities are legal configuration, not a mistake."""
    assert SpendClassificationRule._meta.unique_together == ()
    assert SpendClassificationRule._meta.ordering == ["priority", "id"]


def test_spend_rule_two_same_shaped_rules_coexist(tenant_a, spend_vendor_a, spend_category_a,
                                                  spend_category_other_a):
    first = _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_a, priority=10)
    second = _spend_rule_row(tenant_a, spend_category_other_a, vendor=spend_vendor_a, priority=50)
    assert list(SpendClassificationRule.objects.filter(tenant=tenant_a)) == [first, second]


def test_spend_rule_usage_stamps_are_not_editable():
    """match_count / last_matched_at are written ONLY by the preview verb (L22)."""
    assert _spend_field(SpendClassificationRule, "match_count").editable is False
    assert _spend_field(SpendClassificationRule, "last_matched_at").editable is False


def test_spend_rule_has_no_cached_classified_value_column():
    """L29 - preview() aggregates every call; there is nothing to go stale."""
    names = _spend_field_names(SpendClassificationRule)
    assert not ({"matched_value", "classified_value", "total_value", "cached_value"} & names)


def test_spend_rule_category_is_protected(tenant_a, spend_category_a, spend_vendor_a):
    _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_a)
    with pytest.raises(ProtectedError):
        spend_category_a.delete()


def test_spend_rule_optional_subjects_survive_their_subject(tenant_a, spend_vendor_a,
                                                            spend_category_a):
    """SET_NULL, not CASCADE: a rule whose supplier vanished must stay VISIBLE for audit."""
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_a)
    from apps.core.models import PartyRole
    PartyRole.objects.filter(party=spend_vendor_a).delete()
    spend_vendor_a.delete()
    rule.refresh_from_db()
    assert rule.pk is not None and rule.vendor_id is None


# =================================================================================================
# SpendClassificationRule - vocabulary
# =================================================================================================

def test_spend_rule_match_type_choices_are_the_five_documented():
    assert SpendClassificationRule.MATCH_TYPE_CHOICES == [
        ("vendor", "Supplier"),
        ("gl_account", "GL Account"),
        ("keyword", "Description / SKU keyword"),
        ("invoice_type", "Invoice Type"),
        ("org_unit", "Department / Cost Centre"),
    ]


def test_spend_rule_applies_to_choices_are_the_three_documented():
    assert SpendClassificationRule.APPLIES_TO_CHOICES == [
        ("both", "Invoiced + Committed"),
        ("invoiced", "Invoiced only"),
        ("committed", "Committed (PO) only"),
    ]


def test_spend_rule_required_field_map_covers_every_match_type():
    assert SpendClassificationRule.REQUIRED_FIELD_BY_MATCH_TYPE == {
        "vendor": "vendor",
        "gl_account": "gl_account",
        "keyword": "keyword",
        "invoice_type": "invoice_type",
        "org_unit": "org_unit",
    }
    assert set(SpendClassificationRule.REQUIRED_FIELD_BY_MATCH_TYPE) == {
        key for key, _label in SpendClassificationRule.MATCH_TYPE_CHOICES}


def test_spend_rule_spend_population_constants():
    assert SpendClassificationRule.RECOGNISED_INVOICE_STATUSES == (
        "approved", "scheduled", "paid")
    assert SpendClassificationRule.SPEND_PO_STATUSES == (
        "approved", "sent", "acknowledged", "partially_received", "received", "closed")


def test_spend_rule_active_badge_map_is_colour_named():
    assert SpendClassificationRule.ACTIVE_CSS == {True: "badge-green", False: "badge-muted"}
    assert set(SpendClassificationRule.ACTIVE_CSS.values()) <= _SPEND_BADGE_COLOURS


def test_spend_rule_status_css_and_label_follow_is_active(tenant_a, spend_category_a,
                                                          spend_vendor_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_a)
    assert (rule.status_css, rule.status_label) == ("badge-green", "Active")
    rule.is_active = False
    assert (rule.status_css, rule.status_label) == ("badge-muted", "Inactive")


@pytest.mark.parametrize("match_type", [key for key, _l in SpendClassificationRule.MATCH_TYPE_CHOICES])
def test_spend_rule_every_match_type_value_validates(match_type, tenant_a, spend_category_a,
                                                     spend_vendor_a, gl_expense_a, org_unit_a):
    subject = {
        "vendor": {"vendor": spend_vendor_a},
        "gl_account": {"gl_account": gl_expense_a},
        "keyword": {"keyword": "paper"},
        "invoice_type": {"invoice_type": "standard"},
        "org_unit": {"org_unit": org_unit_a},
    }[match_type]
    rule = SpendClassificationRule(tenant=tenant_a, name=f"{match_type} rule",
                                   category=spend_category_a, match_type=match_type, **subject)
    rule.full_clean()  # must not raise


@pytest.mark.parametrize("applies_to", [key for key, _l in SpendClassificationRule.APPLIES_TO_CHOICES])
def test_spend_rule_every_applies_to_value_validates(applies_to, tenant_a, spend_category_a,
                                                     spend_vendor_a):
    rule = SpendClassificationRule(tenant=tenant_a, name="A", category=spend_category_a,
                                   match_type="vendor", vendor=spend_vendor_a,
                                   applies_to=applies_to)
    rule.full_clean()


def test_spend_rule_subject_label_per_match_type(tenant_a, spend_category_a, spend_vendor_a,
                                                 gl_expense_a, org_unit_a):
    make = lambda **kw: SpendClassificationRule(tenant=tenant_a, name="n",
                                                category=spend_category_a, **kw)
    assert make(match_type="vendor", vendor=spend_vendor_a).subject_label == str(spend_vendor_a)
    assert make(match_type="gl_account", gl_account=gl_expense_a).subject_label == str(gl_expense_a)
    assert make(match_type="org_unit", org_unit=org_unit_a).subject_label == str(org_unit_a)
    assert make(match_type="keyword", keyword="toner").subject_label == "toner"
    assert make(match_type="invoice_type",
                invoice_type="service").subject_label == "Service Invoice (PO-less)"
    assert make(match_type="vendor").subject_label == "—"


# =================================================================================================
# SpendClassificationRule - clean()
# =================================================================================================

@pytest.mark.parametrize("match_type,field", sorted(
    SpendClassificationRule.REQUIRED_FIELD_BY_MATCH_TYPE.items()))
def test_spend_rule_clean_demands_the_field_its_match_type_reads(match_type, field, tenant_a,
                                                                 spend_category_a):
    """A vendor rule with no vendor would swallow the whole cube into one category."""
    rule = SpendClassificationRule(tenant=tenant_a, name="Empty subject",
                                   category=spend_category_a, match_type=match_type)
    with pytest.raises(ValidationError) as exc:
        rule.full_clean()
    assert field in exc.value.message_dict


def test_spend_rule_clean_rejects_an_unknown_match_type(tenant_a, spend_category_a):
    rule = SpendClassificationRule(tenant=tenant_a, name="Junk", category=spend_category_a,
                                   match_type="telepathy")
    with pytest.raises(ValidationError) as exc:
        rule.clean()
    assert exc.value.message_dict["match_type"] == ["Unknown match type."]


def test_spend_rule_clean_rejects_an_unknown_invoice_type(tenant_a, spend_category_a):
    rule = SpendClassificationRule(tenant=tenant_a, name="Bad type", category=spend_category_a,
                                   match_type="invoice_type", invoice_type="pigeon")
    with pytest.raises(ValidationError) as exc:
        rule.full_clean()
    assert "invoice_type" in exc.value.message_dict


def test_spend_rule_clean_refuses_an_invoice_type_rule_on_committed_spend(tenant_a,
                                                                         spend_category_a):
    """A purchase order has no invoice type at all - the error lands on applies_to."""
    rule = SpendClassificationRule(tenant=tenant_a, name="PO invoice type",
                                   category=spend_category_a, match_type="invoice_type",
                                   invoice_type="standard", applies_to="committed")
    with pytest.raises(ValidationError) as exc:
        rule.full_clean()
    assert "applies_to" in exc.value.message_dict


def test_spend_rule_clean_accepts_an_invoice_type_rule_on_the_invoiced_basis(tenant_a,
                                                                            spend_category_a):
    SpendClassificationRule(tenant=tenant_a, name="Service invoices", category=spend_category_a,
                            match_type="invoice_type", invoice_type="service",
                            applies_to="invoiced").full_clean()


@pytest.mark.parametrize("field", ["vendor", "gl_account", "org_unit", "category"])
def test_spend_rule_clean_rejects_a_cross_tenant_subject(field, tenant_a, spend_category_a,
                                                         spend_vendor_a, spend_vendor_b,
                                                         gl_expense_b, org_unit_b,
                                                         spend_category_b):
    foreign = {"vendor": spend_vendor_b, "gl_account": gl_expense_b, "org_unit": org_unit_b,
               "category": spend_category_b}[field]
    rule = SpendClassificationRule(tenant=tenant_a, name="Crafted", category=spend_category_a,
                                   match_type="vendor", vendor=spend_vendor_a)
    setattr(rule, field, foreign)
    with pytest.raises(ValidationError) as exc:
        rule.clean()
    assert exc.value.message_dict[field] == ["That record belongs to another workspace."]


# =================================================================================================
# SpendClassificationRule - matches() (the pure row-level authority)
# =================================================================================================

def test_spend_rule_vendor_matches_an_invoiced_line(spend_rule_vendor_a, spend_invoice_line_a):
    assert spend_rule_vendor_a.matches(spend_invoice_line_a, "invoiced") is True


def test_spend_rule_vendor_matches_a_committed_line(spend_rule_vendor_a, spend_po_line_a):
    assert spend_rule_vendor_a.matches(spend_po_line_a, "committed") is True


def test_spend_rule_vendor_ignores_another_suppliers_line(tenant_a, spend_category_a,
                                                          spend_vendor_other_a,
                                                          spend_invoice_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_other_a)
    assert rule.matches(spend_invoice_line_a, "invoiced") is False


def test_spend_rule_gl_account_matches_the_line_coding(tenant_a, spend_category_a, gl_expense_a,
                                                       spend_invoice_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="gl_account",
                           gl_account=gl_expense_a)
    assert rule.matches(spend_invoice_line_a, "invoiced") is True


def test_spend_rule_keyword_reads_the_committed_item_description(spend_rule_keyword_a,
                                                                 spend_po_line_a):
    assert spend_rule_keyword_a.matches(spend_po_line_a, "committed") is True


def test_spend_rule_keyword_reads_the_invoiced_sku_hint(tenant_a, spend_category_a,
                                                        spend_invoice_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="keyword",
                           keyword="ppr-a4")
    assert rule.matches(spend_invoice_line_a, "invoiced") is True


def test_spend_rule_keyword_is_case_insensitive(tenant_a, spend_category_a, spend_invoice_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="keyword",
                           keyword="COPY PAPER")
    assert rule.matches(spend_invoice_line_a, "invoiced") is True


def test_spend_rule_keyword_misses_an_unrelated_line(spend_rule_keyword_a, spend_invoice_line_a):
    assert spend_rule_keyword_a.matches(spend_invoice_line_a, "invoiced") is False


def test_spend_rule_invoice_type_never_matches_a_purchase_order_line(tenant_a, spend_category_a,
                                                                     spend_po_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="invoice_type",
                           invoice_type="standard")
    assert rule.matches(spend_po_line_a, "committed") is False


def test_spend_rule_invoice_type_matches_the_header_type(tenant_a, spend_category_a,
                                                         spend_invoice_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="invoice_type",
                           invoice_type="standard")
    assert rule.matches(spend_invoice_line_a, "invoiced") is True


def test_spend_rule_org_unit_matches_through_the_ship_to_fallback(tenant_a, spend_category_a,
                                                                  org_unit_a, spend_po_line_a):
    """The department axis is requisition.org_unit falling back to the order's ship-to."""
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="org_unit",
                           org_unit=org_unit_a)
    assert rule.matches(spend_po_line_a, "committed") is True


def test_spend_rule_org_unit_is_null_for_a_po_less_invoice(tenant_a, spend_category_a, org_unit_a,
                                                           spend_invoice_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="org_unit",
                           org_unit=org_unit_a)
    assert rule.matches(spend_invoice_line_a, "invoiced") is False


def test_spend_rule_inactive_matches_nothing(spend_rule_inactive_a, spend_invoice_line_a):
    assert spend_rule_inactive_a.matches(spend_invoice_line_a, "invoiced") is False


def test_spend_rule_applies_to_narrows_the_basis(tenant_a, spend_category_a, spend_vendor_a,
                                                 spend_invoice_line_a, spend_po_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_a,
                           applies_to="invoiced")
    assert rule.matches(spend_invoice_line_a, "invoiced") is True
    assert rule.matches(spend_po_line_a, "committed") is False


def test_spend_rule_matches_is_false_for_a_none_line_or_junk_basis(spend_rule_vendor_a,
                                                                   spend_invoice_line_a):
    assert spend_rule_vendor_a.matches(None, "invoiced") is False
    assert spend_rule_vendor_a.matches(spend_invoice_line_a, "sideways") is False


# =================================================================================================
# SpendClassificationRule - line_filter() (the SQL mirror)
# =================================================================================================

def test_spend_rule_line_filter_returns_a_q_for_each_basis(spend_rule_vendor_a, spend_vendor_a):
    assert spend_rule_vendor_a.line_filter("invoiced") == Q(invoice__vendor_id=spend_vendor_a.pk)
    assert spend_rule_vendor_a.line_filter("committed") == Q(
        purchase_order__vendor_id=spend_vendor_a.pk)


def test_spend_rule_line_filter_is_none_when_inactive(spend_rule_inactive_a):
    """None means 'can match nothing on this basis' - never 'no filter' (that would report the
    whole workspace's spend as matched)."""
    assert spend_rule_inactive_a.line_filter("invoiced") is None
    assert spend_rule_inactive_a.line_filter("committed") is None


def test_spend_rule_line_filter_is_none_off_its_basis(tenant_a, spend_category_a, spend_vendor_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_a,
                           applies_to="committed")
    assert rule.line_filter("invoiced") is None
    assert rule.line_filter("committed") is not None


def test_spend_rule_line_filter_is_none_for_invoice_type_on_committed(tenant_a, spend_category_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="invoice_type",
                           invoice_type="standard")
    assert rule.line_filter("committed") is None
    assert rule.line_filter("invoiced") == Q(invoice__invoice_type="standard")


def test_spend_rule_line_filter_is_none_when_the_subject_is_unset():
    unsaved = SpendClassificationRule(match_type="vendor", applies_to="both", is_active=True)
    assert unsaved.line_filter("invoiced") is None
    assert SpendClassificationRule(match_type="keyword", keyword="   ", applies_to="both",
                                   is_active=True).line_filter("invoiced") is None


def test_spend_rule_line_filter_is_none_for_a_junk_basis(spend_rule_vendor_a):
    assert spend_rule_vendor_a.line_filter("sideways") is None


def test_spend_rule_keyword_filter_targets_the_right_text_column(tenant_a, spend_category_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=None, match_type="keyword",
                           keyword="toner")
    assert rule.line_filter("invoiced") == (Q(description__icontains="toner")
                                            | Q(sku_hint__icontains="toner"))
    assert rule.line_filter("committed") == (Q(item_description__icontains="toner")
                                             | Q(sku_hint__icontains="toner"))


# =================================================================================================
# SpendClassificationRule - matching_lines() / preview() are DERIVED, never stored (L29)
# =================================================================================================

def test_spend_rule_matching_lines_finds_the_recognised_invoice_line(spend_rule_vendor_a,
                                                                     spend_invoice_line_a):
    start, end = _spend_window()
    assert list(spend_rule_vendor_a.matching_lines(start, end, "invoiced")) == [
        spend_invoice_line_a]


def test_spend_rule_matching_lines_skips_a_draft_invoice(spend_rule_vendor_a, spend_invoice_line_a,
                                                         spend_invoice_draft_a):
    """RECOGNISED_INVOICE_STATUSES is ('approved', 'scheduled', 'paid') - a draft is not spend."""
    draft_line = _spend_invoice_line_row(spend_invoice_draft_a)
    start, end = _spend_window()
    matched = list(spend_rule_vendor_a.matching_lines(start, end, "invoiced"))
    assert spend_invoice_line_a in matched
    assert draft_line not in matched


def test_spend_rule_matching_lines_finds_the_committed_line(spend_rule_vendor_a, spend_po_line_a):
    start, end = _spend_window()
    assert list(spend_rule_vendor_a.matching_lines(start, end, "committed")) == [spend_po_line_a]


def test_spend_rule_matching_lines_is_none_for_a_reversed_window(spend_rule_vendor_a):
    today = _spend_today()
    assert spend_rule_vendor_a.matching_lines(today, today, "invoiced") is None
    assert spend_rule_vendor_a.matching_lines(today + datetime.timedelta(days=5), today,
                                              "invoiced") is None
    assert spend_rule_vendor_a.matching_lines(None, None, "invoiced") is None


def test_spend_rule_matching_lines_excludes_a_window_the_document_misses(spend_rule_vendor_a,
                                                                        spend_invoice_line_a):
    today = _spend_today()
    old_start = today - datetime.timedelta(days=400)
    old_end = today - datetime.timedelta(days=300)
    assert spend_rule_vendor_a.matching_lines(old_start, old_end, "invoiced").count() == 0


def test_spend_rule_preview_aggregates_both_bases(spend_rule_vendor_a, spend_invoice_line_a,
                                                  spend_po_line_a):
    start, end = _spend_window()
    result = spend_rule_vendor_a.preview(start, end)
    assert result["count"] == 2
    assert result["value"] == Decimal("490.00")  # 250.00 invoiced + 240.00 committed


def test_spend_rule_preview_recomputes_after_the_source_line_changes(spend_rule_vendor_a,
                                                                     spend_invoice_line_a,
                                                                     spend_po_line_a):
    """L29 - there is no cached value column, so a repriced line moves the preview immediately."""
    start, end = _spend_window()
    assert spend_rule_vendor_a.preview(start, end)["value"] == Decimal("490.00")
    spend_invoice_line_a.unit_price = Decimal("30.00")
    spend_invoice_line_a.save()
    assert spend_rule_vendor_a.preview(start, end)["value"] == Decimal("540.00")


def test_spend_rule_preview_does_not_stamp_the_usage_counters(spend_rule_vendor_a,
                                                              spend_invoice_line_a):
    """Only the spendrule_preview POST moves match_count / last_matched_at."""
    start, end = _spend_window()
    spend_rule_vendor_a.preview(start, end)
    spend_rule_vendor_a.refresh_from_db()
    assert spend_rule_vendor_a.match_count == 0
    assert spend_rule_vendor_a.last_matched_at is None


def test_spend_rule_preview_is_zero_when_nothing_matches(spend_rule_keyword_a):
    start, end = _spend_window()
    assert spend_rule_keyword_a.preview(start, end) == {"count": 0, "value": Decimal("0.00")}


def test_spend_rule_preview_value_is_quantized_to_two_places(spend_rule_vendor_a,
                                                             spend_invoice_line_a):
    start, end = _spend_window()
    assert spend_rule_vendor_a.preview(start, end)["value"].as_tuple().exponent == -2


# =================================================================================================
# SpendClassificationRule - resolve()
# =================================================================================================

def test_spend_rule_resolve_returns_the_lowest_priority_match(tenant_a, spend_category_a,
                                                              spend_category_other_a,
                                                              spend_vendor_a,
                                                              spend_invoice_line_a):
    _spend_rule_row(tenant_a, spend_category_a, name="Vendor rule", vendor=spend_vendor_a,
                    priority=50)
    _spend_rule_row(tenant_a, spend_category_other_a, name="Paper keyword", vendor=None,
                    match_type="keyword", keyword="paper", priority=5)
    assert SpendClassificationRule.resolve(spend_invoice_line_a,
                                           "invoiced") == spend_category_other_a


def test_spend_rule_resolve_breaks_a_priority_tie_on_id(tenant_a, spend_category_a,
                                                        spend_category_other_a, spend_vendor_a,
                                                        spend_invoice_line_a):
    first = _spend_rule_row(tenant_a, spend_category_a, name="First", vendor=spend_vendor_a,
                            priority=20)
    _spend_rule_row(tenant_a, spend_category_other_a, name="Second", vendor=spend_vendor_a,
                    priority=20)
    assert SpendClassificationRule.resolve(spend_invoice_line_a, "invoiced") == first.category


def test_spend_rule_resolve_returns_none_when_nothing_matches(spend_rule_keyword_a,
                                                              spend_invoice_line_a):
    assert SpendClassificationRule.resolve(spend_invoice_line_a, "invoiced") is None


def test_spend_rule_resolve_refilters_a_supplied_list_by_the_lines_own_tenant(
        tenant_b, spend_category_b, spend_invoice_line_a):
    """Trusting a caller's list for TENANCY is how one workspace's rules would classify another's
    spend. The list is trusted for ORDER only."""
    foreign = _spend_rule_row(tenant_b, spend_category_b, name="Globex paper", vendor=None,
                              match_type="keyword", keyword="paper")
    assert foreign.matches(spend_invoice_line_a, "invoiced") is True   # content DOES match
    assert SpendClassificationRule.resolve(spend_invoice_line_a, "invoiced",
                                           rules=[foreign]) is None   # tenancy refuses it


def test_spend_rule_resolve_uses_a_supplied_list_without_requerying(
        django_assert_max_num_queries, tenant_a, spend_category_a, spend_vendor_a,
        spend_invoice_line_a):
    rule = _spend_rule_row(tenant_a, spend_category_a, vendor=spend_vendor_a)
    line = type(spend_invoice_line_a).objects.select_related("invoice").get(
        pk=spend_invoice_line_a.pk)
    with django_assert_max_num_queries(0):
        assert SpendClassificationRule.resolve(line, "invoiced", rules=[rule]) == spend_category_a


def test_spend_rule_resolve_is_none_for_a_none_line():
    assert SpendClassificationRule.resolve(None, "invoiced") is None


def test_spend_rule_resolve_is_none_for_an_unparented_line():
    from apps.procurement.models import SupplierInvoiceLine
    assert SpendClassificationRule.resolve(SupplierInvoiceLine(), "invoiced") is None


# =================================================================================================
# SpendClassificationRule module helpers
# =================================================================================================

def test_spend_default_preview_window_is_ninety_days_ending_tomorrow():
    start, end = _spend_rules_mod.default_preview_window()
    today = _spend_today()
    assert end == today + datetime.timedelta(days=1)
    assert start == end - datetime.timedelta(days=_spend_rules_mod.DEFAULT_PREVIEW_DAYS)
    assert _spend_rules_mod.DEFAULT_PREVIEW_DAYS == 90
    assert start <= today < end   # today's documents are INSIDE the window


def test_spend_recent_match_limit_is_ten():
    assert _spend_rules_mod.RECENT_MATCH_LIMIT == 10


def test_spend_money_quantizes_to_two_places_without_clamping():
    assert _spend_rules_mod.money(None) == Decimal("0.00")
    assert _spend_rules_mod.money(Decimal("1.005")) == Decimal("1.00")
    # Deliberately NOT q2: a big aggregate over DecimalField(18, 2) lines must not be clamped.
    assert _spend_rules_mod.money(Decimal("99999999999.99")) == Decimal("99999999999.99")


def test_spend_line_windows_are_empty_without_a_tenant():
    start, end = _spend_window()
    assert invoiced_line_window(None, start, end).count() == 0
    assert committed_line_window(None, start, end).count() == 0


def test_spend_invoiced_window_excludes_unrecognised_statuses(tenant_a, spend_invoice_line_a,
                                                              spend_invoice_draft_a):
    draft_line = _spend_invoice_line_row(spend_invoice_draft_a)
    start, end = _spend_window()
    ids = set(invoiced_line_window(tenant_a, start, end).values_list("pk", flat=True))
    assert spend_invoice_line_a.pk in ids
    assert draft_line.pk not in ids


def test_spend_committed_window_dates_an_unstamped_order_by_creation(tenant_a, spend_po_a,
                                                                     spend_po_line_a):
    """order_date is NULLABLE - Coalesce(order_date, created_at) keeps the order in the window."""
    spend_po_a.order_date = None
    spend_po_a.save(update_fields=["order_date"])
    start, end = _spend_window()
    assert list(committed_line_window(tenant_a, start, end)) == [spend_po_line_a]


def test_spend_committed_window_honours_the_po_status_list(tenant_a, spend_po_a, spend_po_line_a):
    spend_po_a.status = "draft"
    spend_po_a.save(update_fields=["status"])
    start, end = _spend_window()
    assert committed_line_window(tenant_a, start, end).count() == 0


# =================================================================================================
# MaverickSpendFinding - numbering, defaults, __str__
# =================================================================================================

def test_spend_finding_auto_number_is_msf_five_wide(tenant_a, spend_vendor_a, spend_invoice_a):
    finding = _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a)
    assert finding.number == "MSF-00001"


def test_spend_finding_numbers_run_in_sequence(tenant_a, spend_vendor_a, spend_invoice_a,
                                               spend_po_a):
    first = _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a)
    second = _spend_finding_row(tenant_a, spend_vendor_a, purchase_order=spend_po_a,
                                reason="no_requisition")
    assert [first.number, second.number] == ["MSF-00001", "MSF-00002"]


def test_spend_finding_numbers_do_not_collide_across_tenants(tenant_a, tenant_b, spend_vendor_a,
                                                             spend_vendor_b, spend_invoice_a,
                                                             spend_invoice_b):
    a = _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a)
    b = _spend_finding_row(tenant_b, spend_vendor_b, supplier_invoice=spend_invoice_b)
    assert a.number == b.number == "MSF-00001"
    assert a.tenant_id != b.tenant_id


def test_spend_finding_number_prefix_and_uniqueness():
    assert MaverickSpendFinding.NUMBER_PREFIX == "MSF"
    assert set(MaverickSpendFinding._meta.unique_together) == {
        ("tenant", "number"), ("tenant", "dedupe_key")}
    assert MaverickSpendFinding._meta.ordering == ["-document_date", "-id"]


def test_spend_finding_defaults_are_the_documented_ones(tenant_a, spend_vendor_a,
                                                        spend_invoice_a):
    finding = MaverickSpendFinding.objects.create(
        tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract",
        document_date=_spend_today(), supplier_invoice=spend_invoice_a)
    finding.refresh_from_db()
    assert finding.severity == "medium"
    assert finding.status == "open"
    assert finding.amount == Decimal("0")
    assert finding.benchmark_amount is None
    assert finding.leakage_amount == Decimal("0")
    assert finding.is_addressable is True
    assert finding.detail == ""
    assert finding.resolution_note == ""
    assert finding.resolved_by_id is None and finding.resolved_at is None
    assert finding.detected_at is not None
    assert finding.dedupe_key


def test_spend_finding_str_folds_number_and_reason(spend_finding_open_a):
    assert str(spend_finding_open_a) == (
        f"{spend_finding_open_a.number} {_SPEND_DOT} No active contract")


def test_spend_finding_str_survives_an_unsaved_row():
    assert str(MaverickSpendFinding(reason="off_catalog")).startswith("MSF ")


# =================================================================================================
# MaverickSpendFinding - vocabulary
# =================================================================================================

def test_spend_finding_reason_choices_are_the_eight_documented():
    assert MaverickSpendFinding.REASON_CHOICES == [
        ("no_contract", "No active contract"),
        ("po_less_invoice", "Invoice with no purchase order"),
        ("no_requisition", "PO raised with no requisition"),
        ("off_catalog", "Item not on an approved catalogue"),
        ("non_preferred_vendor", "Bought from a non-preferred supplier"),
        ("price_above_contract", "Price above the contracted/catalogue price"),
        ("suspended_vendor", "Supplier was blocked or suspended"),
        ("split_purchase", "Orders split below an approval threshold"),
    ]


def test_spend_finding_severity_choices():
    assert MaverickSpendFinding.SEVERITY_CHOICES == [
        ("low", "Low"), ("medium", "Medium"), ("high", "High")]


def test_spend_finding_status_choices_are_the_five_documented():
    assert MaverickSpendFinding.STATUS_CHOICES == [
        ("open", "Open"),
        ("acknowledged", "Acknowledged"),
        ("justified", "Justified - accepted"),
        ("remediated", "Remediated"),
        ("dismissed", "Dismissed - false positive"),
    ]


def test_spend_finding_open_and_terminal_statuses_partition_the_lifecycle():
    assert MaverickSpendFinding.OPEN_STATUSES == ("open", "acknowledged")
    assert MaverickSpendFinding.TERMINAL_STATUSES == ("justified", "remediated", "dismissed")
    every = {key for key, _l in MaverickSpendFinding.STATUS_CHOICES}
    assert set(MaverickSpendFinding.OPEN_STATUSES) | set(
        MaverickSpendFinding.TERMINAL_STATUSES) == every
    assert not (set(MaverickSpendFinding.OPEN_STATUSES)
                & set(MaverickSpendFinding.TERMINAL_STATUSES))


def test_spend_finding_severity_by_reason_covers_every_reason():
    assert MaverickSpendFinding.SEVERITY_BY_REASON == {
        "no_contract": "medium",
        "po_less_invoice": "medium",
        "no_requisition": "medium",
        "off_catalog": "low",
        "non_preferred_vendor": "low",
        "price_above_contract": "high",
        "suspended_vendor": "high",
        "split_purchase": "high",
    }
    assert set(MaverickSpendFinding.SEVERITY_BY_REASON) == {
        key for key, _l in MaverickSpendFinding.REASON_CHOICES}
    assert set(MaverickSpendFinding.SEVERITY_BY_REASON.values()) <= {
        key for key, _l in MaverickSpendFinding.SEVERITY_CHOICES}


@pytest.mark.parametrize("reason,expected",
                         sorted(MaverickSpendFinding.SEVERITY_BY_REASON.items()))
def test_spend_finding_default_severity_per_reason(reason, expected):
    assert MaverickSpendFinding.default_severity(reason) == expected


def test_spend_finding_default_severity_of_an_unknown_reason_is_medium():
    assert MaverickSpendFinding.default_severity("telepathy") == "medium"


def test_spend_finding_badge_maps_are_colour_named():
    assert MaverickSpendFinding.STATUS_CSS == {
        "open": "badge-red", "acknowledged": "badge-amber", "justified": "badge-info",
        "remediated": "badge-green", "dismissed": "badge-muted"}
    assert MaverickSpendFinding.SEVERITY_CSS == {
        "low": "badge-slate", "medium": "badge-amber", "high": "badge-red"}
    assert set(MaverickSpendFinding.STATUS_CSS.values()) <= _SPEND_BADGE_COLOURS
    assert set(MaverickSpendFinding.SEVERITY_CSS.values()) <= _SPEND_BADGE_COLOURS
    assert set(MaverickSpendFinding.STATUS_CSS) == {
        key for key, _l in MaverickSpendFinding.STATUS_CHOICES}


def test_spend_finding_detection_constants():
    assert MaverickSpendFinding.PRICE_TOLERANCE_PCT == Decimal("5.00")
    assert MaverickSpendFinding.SPLIT_WINDOW_DAYS == 30
    assert MaverickSpendFinding.SPLIT_MIN_ORDERS == 3
    assert MaverickSpendFinding.SCAN_LINE_LIMIT == 20000
    assert MaverickSpendFinding.NON_ADDRESSABLE_GL_CODES == (
        "2300", "2310", "2320", "6900", "7100", "7200", "8000")
    assert MaverickSpendFinding.RECOGNISED_INVOICE_STATUSES == ("approved", "scheduled", "paid")
    assert MaverickSpendFinding.COVERING_CONTRACT_STATUSES == ("active", "expiring")


def test_spend_finding_money_ceiling_matches_the_column():
    from apps.procurement.models.SpendAnalyticsReporting.MaverickFindings import MAX_MSF_MONEY
    assert MAX_MSF_MONEY == Decimal("9999999999999999.99")
    field = _spend_field(MaverickSpendFinding, "amount")
    assert (field.max_digits, field.decimal_places) == (18, 2)


def test_spend_finding_status_and_severity_css_properties(spend_finding_open_a,
                                                          spend_finding_dismissed_a,
                                                          spend_finding_leakage_a):
    assert spend_finding_open_a.status_css == "badge-red"
    assert spend_finding_open_a.severity_css == "badge-amber"
    assert spend_finding_dismissed_a.status_css == "badge-muted"
    assert spend_finding_dismissed_a.severity_css == "badge-slate"
    assert spend_finding_leakage_a.severity_css == "badge-red"


# =================================================================================================
# MaverickSpendFinding - derived columns (L29)
# =================================================================================================

def test_spend_finding_leakage_is_derived_from_the_benchmark_gap(spend_finding_leakage_a):
    assert spend_finding_leakage_a.leakage_amount == Decimal("50.00")


def test_spend_finding_leakage_floors_at_zero_below_the_benchmark(tenant_a, spend_vendor_a,
                                                                  spend_invoice_a):
    """Buying BELOW the contracted price is not leakage."""
    finding = _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a,
                                 amount=Decimal("100.00"), benchmark_amount=Decimal("250.00"))
    finding.refresh_from_db()
    assert finding.leakage_amount == Decimal("0.00")


def test_spend_finding_leakage_is_zero_without_a_benchmark(spend_finding_open_a):
    assert spend_finding_open_a.benchmark_amount is None
    assert spend_finding_open_a.leakage_amount == Decimal("0.00")


def test_spend_finding_leakage_recomputes_on_an_update_fields_save(spend_finding_leakage_a):
    """The verbs save with update_fields; the derived column must still be written."""
    spend_finding_leakage_a.amount = Decimal("400.00")
    spend_finding_leakage_a.save(update_fields=["amount"])
    spend_finding_leakage_a.refresh_from_db()
    assert spend_finding_leakage_a.leakage_amount == Decimal("200.00")


def test_spend_finding_derived_columns_are_not_editable():
    for name in ("leakage_amount", "dedupe_key", "status", "resolution_note", "resolved_by",
                 "resolved_at", "number"):
        assert _spend_field(MaverickSpendFinding, name).editable is False, name


def test_spend_finding_detected_at_is_a_system_stamp():
    assert _spend_field(MaverickSpendFinding, "detected_at").auto_now_add is True


def test_spend_finding_dedupe_key_shapes(tenant_a, spend_vendor_a, spend_invoice_a,
                                         spend_invoice_line_a, spend_po_a):
    line_keyed = _spend_finding_row(tenant_a, spend_vendor_a, reason="off_catalog",
                                    supplier_invoice=spend_invoice_a,
                                    invoice_line=spend_invoice_line_a)
    inv_keyed = _spend_finding_row(tenant_a, spend_vendor_a, reason="no_contract",
                                   supplier_invoice=spend_invoice_a)
    po_keyed = _spend_finding_row(tenant_a, spend_vendor_a, reason="no_requisition",
                                  purchase_order=spend_po_a)
    assert line_keyed.dedupe_key == f"off_catalog:line:{spend_invoice_line_a.pk}"
    assert inv_keyed.dedupe_key == f"no_contract:inv:{spend_invoice_a.pk}"
    assert po_keyed.dedupe_key == f"no_requisition:po:{spend_po_a.pk}"


def test_spend_finding_split_purchase_keys_on_supplier_and_window_start(tenant_a, spend_vendor_a,
                                                                        spend_po_a):
    today = _spend_today()
    finding = _spend_finding_row(tenant_a, spend_vendor_a, reason="split_purchase",
                                 purchase_order=spend_po_a, document_date=today)
    assert finding.dedupe_key == f"split:{spend_vendor_a.pk}:{today:%Y%m%d}"


def test_spend_finding_pointerless_rows_get_a_random_key(tenant_a, spend_vendor_a):
    """clean() refuses this shape, so it is only reachable by a direct create - and two such rows
    must not collide into an IntegrityError 500."""
    first = _spend_finding_row(tenant_a, spend_vendor_a)
    second = _spend_finding_row(tenant_a, spend_vendor_a)
    assert first.dedupe_key.startswith("no_contract:manual:")
    assert first.dedupe_key != second.dedupe_key


def test_spend_finding_dedupe_key_is_unique_within_a_tenant(tenant_a, spend_vendor_a,
                                                            spend_invoice_a):
    _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a)


def test_spend_finding_dedupe_key_is_scoped_to_the_tenant(tenant_a, tenant_b, spend_vendor_a,
                                                          spend_vendor_b):
    """The same fact in two workspaces is two rows - the constraint is (tenant, dedupe_key)."""
    key = "no_contract:inv:1"
    a = _spend_finding_row(tenant_a, spend_vendor_a, dedupe_key=key)
    b = _spend_finding_row(tenant_b, spend_vendor_b, dedupe_key=key)
    assert a.dedupe_key == b.dedupe_key == key
    assert a.pk != b.pk


def test_spend_finding_variance_pct_is_the_gap_over_the_benchmark(spend_finding_leakage_a):
    assert spend_finding_leakage_a.variance_pct == Decimal("25.00")


def test_spend_finding_variance_pct_is_none_without_a_benchmark(spend_finding_open_a):
    assert spend_finding_open_a.variance_pct is None


def test_spend_finding_variance_pct_is_none_on_a_zero_benchmark(tenant_a, spend_vendor_a,
                                                                spend_invoice_a):
    """Dividing by zero would be a fabricated infinity, not a variance."""
    finding = _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a,
                                 benchmark_amount=Decimal("0.00"))
    assert finding.variance_pct is None


def test_spend_finding_age_days_is_zero_on_a_fresh_row(spend_finding_open_a):
    assert spend_finding_open_a.age_days == 0


def test_spend_finding_age_days_counts_from_detection_not_the_document(spend_finding_open_a):
    type(spend_finding_open_a).objects.filter(pk=spend_finding_open_a.pk).update(
        detected_at=timezone.now() - datetime.timedelta(days=9, hours=1))
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.age_days == 9


def test_spend_finding_age_days_never_goes_negative(spend_finding_open_a):
    type(spend_finding_open_a).objects.filter(pk=spend_finding_open_a.pk).update(
        detected_at=timezone.now() + datetime.timedelta(days=3))
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.age_days == 0


def test_spend_finding_open_and_resolved_properties(spend_finding_open_a, spend_finding_ack_a,
                                                    spend_finding_dismissed_a):
    assert (spend_finding_open_a.is_open, spend_finding_open_a.is_resolved) == (True, False)
    assert (spend_finding_ack_a.is_open, spend_finding_ack_a.is_resolved) == (True, False)
    assert (spend_finding_dismissed_a.is_open,
            spend_finding_dismissed_a.is_resolved) == (False, True)


# =================================================================================================
# MaverickSpendFinding - the guarded verb ladder
# =================================================================================================

def test_spend_finding_acknowledge_moves_open_to_acknowledged(spend_finding_open_a, admin_user):
    assert spend_finding_open_a.acknowledge(admin_user) is True
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "acknowledged"


def test_spend_finding_acknowledge_is_a_no_op_on_a_double_submit(spend_finding_open_a,
                                                                 admin_user):
    spend_finding_open_a.acknowledge(admin_user)
    assert spend_finding_open_a.acknowledge(admin_user) is False


def test_spend_finding_acknowledge_is_refused_once_resolved(spend_finding_dismissed_a,
                                                            admin_user):
    assert spend_finding_dismissed_a.acknowledge(admin_user) is False
    spend_finding_dismissed_a.refresh_from_db()
    assert spend_finding_dismissed_a.status == "dismissed"


@pytest.mark.parametrize("verb,expected", [("justify", "justified"),
                                           ("remediate", "remediated"),
                                           ("dismiss", "dismissed")])
def test_spend_finding_terminal_verbs_stamp_the_disposition(verb, expected, spend_finding_open_a,
                                                            admin_user):
    before = timezone.now()
    assert getattr(spend_finding_open_a, verb)(admin_user, "Signed off by procurement.") is True
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == expected
    assert spend_finding_open_a.resolution_note == "Signed off by procurement."
    assert spend_finding_open_a.resolved_by_id == admin_user.pk
    assert spend_finding_open_a.resolved_at >= before
    assert spend_finding_open_a.is_resolved is True


@pytest.mark.parametrize("verb", ["justify", "remediate", "dismiss"])
def test_spend_finding_terminal_verbs_work_from_acknowledged(verb, spend_finding_ack_a,
                                                             admin_user):
    assert getattr(spend_finding_ack_a, verb)(admin_user, "note") is True


@pytest.mark.parametrize("verb", ["justify", "remediate", "dismiss"])
def test_spend_finding_terminal_verbs_are_refused_once_resolved(verb, spend_finding_dismissed_a,
                                                                admin_user):
    assert getattr(spend_finding_dismissed_a, verb)(admin_user, "second opinion") is False
    spend_finding_dismissed_a.refresh_from_db()
    assert spend_finding_dismissed_a.status == "dismissed"
    assert spend_finding_dismissed_a.resolution_note == (
        "Catalogue entry was added the same week.")


def test_spend_finding_a_disposition_does_not_reassign_who_signed(spend_finding_open_a,
                                                                  admin_user, member_user):
    spend_finding_open_a.justify(admin_user, "first")
    signed_at = spend_finding_open_a.resolved_at
    assert spend_finding_open_a.remediate(member_user, "second") is False
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.resolved_by_id == admin_user.pk
    assert spend_finding_open_a.resolved_at == signed_at


def test_spend_finding_an_anonymous_disposition_leaves_resolved_by_null(spend_finding_open_a):
    assert spend_finding_open_a.dismiss(None, "system") is True
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.resolved_by_id is None
    assert spend_finding_open_a.resolved_at is not None


def test_spend_finding_a_disposition_note_defaults_to_empty(spend_finding_open_a, admin_user):
    assert spend_finding_open_a.justify(admin_user) is True
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.resolution_note == ""


# =================================================================================================
# MaverickSpendFinding - clean()
# =================================================================================================

def test_spend_finding_clean_demands_a_source_pointer(tenant_a, spend_vendor_a):
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract",
                                   document_date=_spend_today(), amount=Decimal("10.00"))
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert "supplier_invoice" in exc.value.message_dict


def test_spend_finding_clean_accepts_any_one_pointer(tenant_a, spend_vendor_a, spend_po_a):
    MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="no_requisition",
                         document_date=_spend_today(), amount=Decimal("10.00"),
                         purchase_order=spend_po_a).clean()


def test_spend_finding_clean_rejects_an_unknown_reason(tenant_a, spend_vendor_a, spend_invoice_a):
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="telepathy",
                                   document_date=_spend_today(), supplier_invoice=spend_invoice_a)
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert "reason" in exc.value.message_dict


@pytest.mark.parametrize("field,message", [
    ("supplier_invoice", "That invoice belongs to another workspace."),
    ("purchase_order", "That purchase order belongs to another workspace."),
    ("vendor", "That supplier belongs to another workspace."),
    ("category", "That category belongs to another workspace."),
    ("org_unit", "That department belongs to another workspace."),
    ("contract", "That contract belongs to another workspace."),
])
def test_spend_finding_clean_rejects_a_cross_tenant_fk(field, message, tenant_a, spend_vendor_a,
                                                       spend_invoice_a, spend_vendor_b,
                                                       spend_invoice_b, spend_po_b,
                                                       spend_category_b, org_unit_b,
                                                       spend_contract_b):
    foreign = {"supplier_invoice": spend_invoice_b, "purchase_order": spend_po_b,
               "vendor": spend_vendor_b, "category": spend_category_b, "org_unit": org_unit_b,
               "contract": spend_contract_b}[field]
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract",
                                   document_date=_spend_today(), supplier_invoice=spend_invoice_a)
    setattr(finding, field, foreign)
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert exc.value.message_dict[field] == [message]


def test_spend_finding_clean_rejects_a_cross_tenant_invoice_line(tenant_a, spend_vendor_a,
                                                                 spend_invoice_line_b):
    """SupplierInvoiceLine has NO tenant column - it is scoped through its header."""
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="off_catalog",
                                   document_date=_spend_today(),
                                   invoice_line=spend_invoice_line_b)
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert "invoice_line" in exc.value.message_dict


def test_spend_finding_clean_rejects_a_line_from_a_different_invoice(tenant_a, spend_vendor_a,
                                                                     spend_invoice_a,
                                                                     spend_invoice_draft_a):
    stray = _spend_invoice_line_row(spend_invoice_draft_a)
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="off_catalog",
                                   document_date=_spend_today(),
                                   supplier_invoice=spend_invoice_a, invoice_line=stray)
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert exc.value.message_dict["invoice_line"] == ["That line belongs to a different invoice."]


def test_spend_finding_clean_rejects_an_out_of_range_document_date(tenant_a, spend_vendor_a,
                                                                   spend_invoice_a):
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract",
                                   document_date=datetime.date(1800, 1, 1),
                                   supplier_invoice=spend_invoice_a)
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert "document_date" in exc.value.message_dict


@pytest.mark.parametrize("raw", [Decimal("NaN"), Decimal("Infinity"),
                                 Decimal("99999999999999999.99")])
def test_spend_finding_clean_rejects_a_non_finite_or_oversized_amount(raw, tenant_a,
                                                                      spend_vendor_a,
                                                                      spend_invoice_a):
    """L35 - 'NaN' / 'Infinity' / an over-max_digits figure is a friendly field error, never a
    driver 500."""
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract",
                                   document_date=_spend_today(), amount=raw,
                                   supplier_invoice=spend_invoice_a)
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert "amount" in exc.value.message_dict


def test_spend_finding_clean_rejects_a_non_finite_benchmark(tenant_a, spend_vendor_a,
                                                            spend_invoice_a):
    finding = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract",
                                   document_date=_spend_today(), amount=Decimal("10.00"),
                                   benchmark_amount=Decimal("NaN"),
                                   supplier_invoice=spend_invoice_a)
    with pytest.raises(ValidationError) as exc:
        finding.clean()
    assert "benchmark_amount" in exc.value.message_dict


def test_spend_finding_clean_pre_checks_the_dedupe_collision(tenant_a, spend_vendor_a,
                                                             spend_invoice_a):
    """A hand-raised duplicate is a friendly field error, not a unique-constraint 500."""
    _spend_finding_row(tenant_a, spend_vendor_a, supplier_invoice=spend_invoice_a)
    twin = MaverickSpendFinding(tenant=tenant_a, vendor=spend_vendor_a, reason="no_contract",
                                document_date=_spend_today(), amount=Decimal("1.00"),
                                supplier_invoice=spend_invoice_a)
    with pytest.raises(ValidationError) as exc:
        twin.clean()
    assert "already exists" in exc.value.message_dict["reason"][0]


def test_spend_finding_clean_does_not_flag_the_row_against_itself(spend_finding_open_a):
    spend_finding_open_a.clean()   # must not raise on a re-save of an existing row


# =================================================================================================
# MaverickSpendFinding - scan() is idempotent
# =================================================================================================

def test_spend_scan_raises_a_finding_for_a_po_less_invoice(tenant_a, spend_invoice_a,
                                                           spend_invoice_line_a):
    start, end = _spend_window()
    counts = MaverickSpendFinding.scan(tenant_a, start, end, reasons=["po_less_invoice"])
    assert counts == {"po_less_invoice": 1}
    raised = MaverickSpendFinding.objects.get(tenant=tenant_a, reason="po_less_invoice")
    assert raised.supplier_invoice_id == spend_invoice_a.pk
    assert raised.vendor_id == spend_invoice_a.vendor_id
    assert raised.severity == MaverickSpendFinding.default_severity("po_less_invoice")


def test_spend_scan_is_idempotent_over_an_unchanged_window(tenant_a, spend_invoice_a,
                                                           spend_invoice_line_a):
    start, end = _spend_window()
    MaverickSpendFinding.scan(tenant_a, start, end, reasons=["po_less_invoice"])
    again = MaverickSpendFinding.scan(tenant_a, start, end, reasons=["po_less_invoice"])
    assert again == {"po_less_invoice": 0}
    assert MaverickSpendFinding.objects.filter(tenant=tenant_a,
                                               reason="po_less_invoice").count() == 1


def test_spend_scan_never_reopens_a_disposed_finding(tenant_a, admin_user, spend_invoice_a,
                                                     spend_invoice_line_a):
    start, end = _spend_window()
    MaverickSpendFinding.scan(tenant_a, start, end, reasons=["po_less_invoice"])
    raised = MaverickSpendFinding.objects.get(tenant=tenant_a, reason="po_less_invoice")
    raised.dismiss(admin_user, "Service invoice, no PO expected.")
    MaverickSpendFinding.scan(tenant_a, start, end, reasons=["po_less_invoice"])
    raised.refresh_from_db()
    assert raised.status == "dismissed"
    assert raised.resolution_note == "Service invoice, no PO expected."
    assert raised.resolved_by_id == admin_user.pk


def test_spend_scan_ignores_an_unknown_reason(tenant_a, spend_invoice_a, spend_invoice_line_a):
    """A hand-edited checkbox value must NARROW the scan, never 500 it (L11)."""
    start, end = _spend_window()
    assert MaverickSpendFinding.scan(tenant_a, start, end, reasons=["telepathy"]) == {}
    counts = MaverickSpendFinding.scan(tenant_a, start, end,
                                       reasons=["po_less_invoice", "telepathy"])
    assert set(counts) == {"po_less_invoice"}


def test_spend_scan_refuses_a_missing_tenant_or_reversed_window(tenant_a, spend_invoice_a):
    start, end = _spend_window()
    today = _spend_today()
    assert MaverickSpendFinding.scan(None, start, end) == {}
    assert MaverickSpendFinding.scan(tenant_a, None, end) == {}
    assert MaverickSpendFinding.scan(tenant_a, start, None) == {}
    assert MaverickSpendFinding.scan(tenant_a, today, today) == {}
    assert MaverickSpendFinding.scan(tenant_a, end, start) == {}
    assert MaverickSpendFinding.scan(tenant_a, start, end, reasons=[]) == {}


def test_spend_scan_skips_a_draft_invoice(tenant_a, spend_invoice_draft_a):
    """Only RECOGNISED_INVOICE_STATUSES is spend - a draft can never be maverick."""
    _spend_invoice_line_row(spend_invoice_draft_a)
    start, end = _spend_window()
    assert MaverickSpendFinding.scan(tenant_a, start, end,
                                     reasons=["po_less_invoice"]) == {"po_less_invoice": 0}
    assert MaverickSpendFinding.objects.filter(tenant=tenant_a).count() == 0


def test_spend_scan_stays_inside_its_own_workspace(tenant_a, tenant_b, spend_invoice_a,
                                                   spend_invoice_b, spend_invoice_line_b):
    start, end = _spend_window()
    MaverickSpendFinding.scan(tenant_a, start, end, reasons=["po_less_invoice"])
    assert MaverickSpendFinding.objects.filter(tenant=tenant_b).count() == 0


def test_spend_scan_writes_no_ledger_rows(tenant_a, admin_user, spend_invoice_a,
                                          spend_invoice_line_a):
    """L29 - 6.14 is a read-only analytics pass: no Bill, no JournalEntry, no Payment."""
    from apps.accounting.models import Bill, JournalEntry
    before = (Bill.objects.count(), JournalEntry.objects.count())
    start, end = _spend_window()
    MaverickSpendFinding.scan(tenant_a, start, end, reasons=["po_less_invoice", "no_contract"])
    assert (Bill.objects.count(), JournalEntry.objects.count()) == before


# =================================================================================================
# SpendReport - numbering, defaults, __str__
# =================================================================================================

def test_spend_report_auto_number_is_spr_five_wide(tenant_a):
    assert _spend_report_row(tenant_a).number == "SPR-00001"


def test_spend_report_numbers_run_in_sequence_and_never_collide_across_tenants(tenant_a,
                                                                               tenant_b):
    first = _spend_report_row(tenant_a)
    second = _spend_report_row(tenant_a, name="Second")
    other = _spend_report_row(tenant_b, name="Globex")
    assert [first.number, second.number] == ["SPR-00001", "SPR-00002"]
    assert other.number == "SPR-00001"


def test_spend_report_number_prefix_and_unique_together():
    assert SpendReport.NUMBER_PREFIX == "SPR"
    assert SpendReport._meta.unique_together == (("tenant", "number"),)
    assert SpendReport._meta.ordering == ["-is_favorite", "name"]


def test_spend_report_defaults_are_the_documented_ones(tenant_a):
    report = SpendReport.objects.create(tenant=tenant_a, name="Bare report")
    report.refresh_from_db()
    assert report.basis == "invoiced"
    assert report.measure == "net_spend"
    assert report.dimension_1 == "supplier"
    assert report.dimension_2 == "none"
    assert report.date_range == "last_90"
    assert report.date_from is None and report.date_to is None
    assert report.chart_type == "bar"
    assert report.top_n == 20
    assert report.is_favorite is False
    assert report.is_shared is True
    assert report.owner_id is None
    assert report.last_run_at is None
    assert report.min_amount is None
    assert report.description == ""


def test_spend_report_str_folds_number_and_name(spend_report_a):
    assert str(spend_report_a) == f"{spend_report_a.number} - {spend_report_a.name}"


def test_spend_report_favourites_sort_first(tenant_a, spend_report_a, spend_report_favorite_a):
    ordered = list(SpendReport.objects.filter(tenant=tenant_a))
    assert ordered[0] == spend_report_favorite_a


def test_spend_report_last_run_at_is_a_system_stamp():
    assert _spend_field(SpendReport, "last_run_at").editable is False
    assert _spend_field(SpendReport, "number").editable is False


def test_spend_report_stores_only_the_question_not_a_result():
    """L29 - every figure comes from analytics.compute_report(); nothing is cached on the row."""
    names = _spend_field_names(SpendReport)
    assert not ({"summary", "data", "rows", "columns", "result", "row_count", "chart_data",
                 "net_spend", "total_value"} & names)


def test_spend_report_top_n_validators_are_one_to_a_hundred(tenant_a):
    for value in (0, 101):
        report = SpendReport(tenant=tenant_a, name="Bad top n", top_n=value)
        with pytest.raises(ValidationError) as exc:
            report.full_clean()
        assert "top_n" in exc.value.message_dict
    SpendReport(tenant=tenant_a, name="Fine", top_n=100).full_clean()


# =================================================================================================
# SpendReport - vocabulary
# =================================================================================================

def test_spend_report_basis_choices():
    assert SpendReport.BASIS_CHOICES == [
        ("invoiced", "Invoiced (recognised) spend"),
        ("committed", "Committed (PO) spend"),
    ]


def test_spend_report_measure_choices_are_the_eight_documented():
    assert SpendReport.MEASURE_CHOICES == [
        ("net_spend", "Net spend"),
        ("transaction_count", "Transactions"),
        ("avg_transaction", "Average transaction value"),
        ("supplier_count", "Distinct suppliers"),
        ("maverick_spend", "Maverick spend"),
        ("maverick_pct", "Maverick spend %"),
        ("classified_pct", "Classified spend %"),
        ("leakage", "Contract leakage value"),
    ]


def test_spend_report_dimension_choices_are_the_nine_documented():
    assert SpendReport.DIMENSION_CHOICES == [
        ("supplier", "Supplier"),
        ("category", "Category"),
        ("department", "Department / cost centre"),
        ("gl_account", "GL account"),
        ("currency", "Currency"),
        ("month", "Month"),
        ("quarter", "Quarter"),
        ("invoice_type", "Invoice type"),
        ("none", "- none -"),
    ]


def test_spend_report_date_range_and_chart_choices():
    assert SpendReport.DATE_RANGE_CHOICES == [
        ("last_30", "Last 30 days"), ("last_90", "Last 90 days"), ("quarter", "This quarter"),
        ("year", "This year"), ("all", "All time"), ("custom", "Custom range")]
    assert SpendReport.CHART_TYPE_CHOICES == [
        ("bar", "Bar"), ("line", "Line"), ("pie", "Pie"), ("table", "Table only")]


def test_spend_report_basis_badge_map_is_colour_named(tenant_a):
    assert SpendReport.BASIS_CSS == {"invoiced": "badge-info", "committed": "badge-slate"}
    assert set(SpendReport.BASIS_CSS.values()) <= _SPEND_BADGE_COLOURS
    assert _spend_report_row(tenant_a).basis_css == "badge-info"
    assert _spend_report_row(tenant_a, name="Committed",
                             basis="committed").basis_css == "badge-slate"
    assert SpendReport(basis="sideways").basis_css == "badge-muted"


@pytest.mark.parametrize("measure", [key for key, _l in SpendReport.MEASURE_CHOICES])
def test_spend_report_every_measure_value_validates(measure, tenant_a):
    SpendReport(tenant=tenant_a, name="M", measure=measure).full_clean()


@pytest.mark.parametrize("dimension", [key for key, _l in SpendReport.DIMENSION_CHOICES])
def test_spend_report_every_dimension_value_validates(dimension, tenant_a):
    SpendReport(tenant=tenant_a, name="D", dimension_1=dimension, dimension_2="none").full_clean()


@pytest.mark.parametrize("date_range", ["last_30", "last_90", "quarter", "year", "all"])
def test_spend_report_every_preset_range_validates(date_range, tenant_a):
    SpendReport(tenant=tenant_a, name="R", date_range=date_range).full_clean()


@pytest.mark.parametrize("chart_type", [key for key, _l in SpendReport.CHART_TYPE_CHOICES])
def test_spend_report_every_chart_type_validates(chart_type, tenant_a):
    SpendReport(tenant=tenant_a, name="C", chart_type=chart_type).full_clean()


def test_spend_report_uses_department_axis(tenant_a):
    assert _spend_report_row(tenant_a).uses_department_axis is False
    assert _spend_report_row(tenant_a, name="Dept 1",
                             dimension_1="department").uses_department_axis is True
    assert _spend_report_row(tenant_a, name="Dept 2",
                             dimension_2="department").uses_department_axis is True


def test_spend_report_is_custom_range(tenant_a):
    today = _spend_today()
    assert _spend_report_row(tenant_a).is_custom_range is False
    custom = _spend_report_row(tenant_a, name="Custom", date_range="custom",
                               date_from=today - datetime.timedelta(days=7), date_to=today)
    assert custom.is_custom_range is True


# =================================================================================================
# SpendReport - clean()
# =================================================================================================

def test_spend_report_clean_rejects_two_identical_axes(tenant_a):
    report = SpendReport(tenant=tenant_a, name="Doubled", dimension_1="supplier",
                         dimension_2="supplier")
    with pytest.raises(ValidationError) as exc:
        report.full_clean()
    assert "dimension_2" in exc.value.message_dict


def test_spend_report_clean_allows_none_on_both_axes(tenant_a):
    SpendReport(tenant=tenant_a, name="Single figure", dimension_1="none",
                dimension_2="none").full_clean()


@pytest.mark.parametrize("bound,other", [("date_from", "date_to"), ("date_to", "date_from")])
def test_spend_report_clean_demands_both_bounds_of_a_custom_range(bound, other, tenant_a):
    report = SpendReport(tenant=tenant_a, name="Half range", date_range="custom",
                         **{other: _spend_today()})
    with pytest.raises(ValidationError) as exc:
        report.full_clean()
    assert bound in exc.value.message_dict


def test_spend_report_clean_rejects_a_date_outside_the_supported_span(tenant_a):
    report = SpendReport(tenant=tenant_a, name="Ancient", date_range="custom",
                         date_from=datetime.date(1800, 1, 1), date_to=_spend_today())
    with pytest.raises(ValidationError) as exc:
        report.clean()
    assert exc.value.message_dict["date_from"] == ["Enter a date between 1900 and 9999."]


def test_spend_report_clean_rejects_a_reversed_custom_range(tenant_a):
    today = _spend_today()
    report = SpendReport(tenant=tenant_a, name="Backwards", date_range="custom",
                         date_from=today, date_to=today - datetime.timedelta(days=10))
    with pytest.raises(ValidationError) as exc:
        report.full_clean()
    assert "date_from" in exc.value.message_dict


def test_spend_report_clean_accepts_an_equal_day_custom_range(tenant_a):
    today = _spend_today()
    SpendReport(tenant=tenant_a, name="One day", date_range="custom", date_from=today,
                date_to=today).full_clean()


@pytest.mark.parametrize("raw", [Decimal("NaN"), Decimal("Infinity"),
                                 Decimal("10000000000000000.00"), Decimal("-1.00")])
def test_spend_report_clean_rejects_a_bad_min_amount(raw, tenant_a):
    """L35 - NaN / Infinity / over-range / negative are friendly field errors, never a 500."""
    report = SpendReport(tenant=tenant_a, name="Bad floor", min_amount=raw)
    with pytest.raises(ValidationError) as exc:
        report.clean()
    assert "min_amount" in exc.value.message_dict


def test_spend_report_clean_accepts_a_zero_min_amount(tenant_a):
    SpendReport(tenant=tenant_a, name="Zero floor", min_amount=Decimal("0.00")).full_clean()


@pytest.mark.parametrize("field,label", [("vendor", "supplier"), ("category", "category"),
                                         ("org_unit", "department"),
                                         ("gl_account", "GL account")])
def test_spend_report_clean_rejects_a_cross_tenant_filter(field, label, tenant_a, spend_vendor_b,
                                                          spend_category_b, org_unit_b,
                                                          gl_expense_b):
    foreign = {"vendor": spend_vendor_b, "category": spend_category_b, "org_unit": org_unit_b,
               "gl_account": gl_expense_b}[field]
    report = SpendReport(tenant=tenant_a, name="Crafted", **{field: foreign})
    with pytest.raises(ValidationError) as exc:
        report.clean()
    assert exc.value.message_dict[field] == [f"That {label} belongs to another workspace."]


def test_spend_report_clean_accepts_its_own_workspaces_filters(tenant_a, spend_vendor_a,
                                                               spend_category_a, org_unit_a,
                                                               gl_expense_a):
    SpendReport(tenant=tenant_a, name="Narrowed", vendor=spend_vendor_a,
                category=spend_category_a, org_unit=org_unit_a,
                gl_account=gl_expense_a).full_clean()


def test_spend_report_optional_filters_survive_their_subject(tenant_a, spend_category_a):
    """SET_NULL - deleting a cost centre must not delete the report that once looked at it."""
    report = _spend_report_row(tenant_a, category=spend_category_a)
    spend_category_a.delete()
    report.refresh_from_db()
    assert report.pk is not None and report.category_id is None


# =================================================================================================
# SpendReportSnapshot - the ONLY place a result is persisted
# =================================================================================================

def test_spend_snapshot_is_a_plain_model_not_tenant_owned():
    from apps.procurement.models._base import TenantOwned
    assert not issubclass(SpendReportSnapshot, TenantOwned)
    names = _spend_field_names(SpendReportSnapshot)
    assert "tenant" in names and "generated_at" in names
    for absent in ("created_at", "updated_at", "number"):
        with pytest.raises(FieldDoesNotExist):
            SpendReportSnapshot._meta.get_field(absent)


def test_spend_snapshot_defaults_are_empty(tenant_a, spend_report_a):
    snap = SpendReportSnapshot.objects.create(tenant=tenant_a, report=spend_report_a,
                                              title="Empty run")
    snap.refresh_from_db()
    assert snap.summary == []
    assert snap.data == {}
    assert snap.row_count == 0
    assert snap.generated_by_id is None
    assert snap.generated_at is not None


def test_spend_snapshot_str_folds_title_and_stamp(spend_snapshot_a):
    assert str(spend_snapshot_a) == (
        f"{spend_snapshot_a.title} ({spend_snapshot_a.generated_at:%Y-%m-%d %H:%M})")


def test_spend_snapshot_ordering_is_newest_first(tenant_a, spend_report_a, spend_snapshot_a):
    later = SpendReportSnapshot.objects.create(tenant=tenant_a, report=spend_report_a,
                                               title="Later run")
    assert SpendReportSnapshot._meta.ordering == ["-generated_at"]
    assert list(SpendReportSnapshot.objects.filter(tenant=tenant_a))[0] == later


def test_spend_snapshot_freezes_the_payload_verbatim(spend_snapshot_a):
    """A snapshot is re-rendered AS-IS and never recomputed."""
    stored = dict(spend_snapshot_a.data)
    spend_snapshot_a.refresh_from_db()
    assert spend_snapshot_a.data == stored
    assert spend_snapshot_a.data["columns"] == ["Supplier", "Net spend", "Share", "Lines"]
    assert spend_snapshot_a.summary == [{"label": "Net spend", "value": "250.00"}]


def test_spend_snapshot_survives_a_malformed_payload(tenant_a, spend_report_a):
    """The detail page falls back to a table - the model must accept whatever was frozen."""
    snap = SpendReportSnapshot.objects.create(tenant=tenant_a, report=spend_report_a,
                                              title="Odd run", summary="not-a-list",
                                              data={"chart_type": 7, "rows": None})
    snap.refresh_from_db()
    assert snap.data["chart_type"] == 7


def test_spend_snapshot_dies_with_its_parent_report(tenant_a, spend_report_a, spend_snapshot_a):
    spend_report_a.delete()
    assert SpendReportSnapshot.objects.filter(pk=spend_snapshot_a.pk).count() == 0


def test_spend_snapshot_carries_its_own_tenant_column(spend_snapshot_a, tenant_a,
                                                      spend_report_a):
    """Fetched get_object_or_404(..., tenant=request.tenant) without walking the parent."""
    assert spend_snapshot_a.tenant_id == tenant_a.pk == spend_report_a.tenant_id
    assert _spend_field(SpendReportSnapshot, "tenant").remote_field.related_name == "+"


def test_spend_snapshot_is_the_only_persisted_result_in_the_sub_module():
    """L29 - the rule table caches nothing, the report stores only the question."""
    assert {"summary", "data", "row_count"} <= _spend_field_names(SpendReportSnapshot)
    assert not ({"summary", "data", "row_count"} & _spend_field_names(SpendReport))
    assert not ({"summary", "data", "row_count"} & _spend_field_names(SpendClassificationRule))
