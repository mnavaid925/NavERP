"""Procurement 6.16 - Supplier Performance & Evaluation MODEL tests.

The invariants this lane owns:

* **Auto-numbering** - ``SKP-#####`` / ``SFB-#####`` / ``SIP-#####``, allocated once in
  ``TenantNumbered.save()`` and counted PER TENANT, so two workspaces both start at 00001;
  ``SupplierKpiScore`` deliberately carries no number at all (a child fact row).
* **``SupplierKpi.score_and_band()`` - the ONE scale.** Generate, the manual score edit and every
  board band through it, so a figure cannot mean one thing on a scorecard and another on a page.
  Bands are checked in BOTH directions and at their exact boundaries; ``direct`` and ``linear``
  are checked including their clamps and ``linear``'s documented fall-back to the band table; and
  a KPI with NO thresholds bands ``"unknown"`` rather than a flattering ``"ok"``.
* **``clean()`` on all four models** - band ordering read against ``direction``, the
  derived/tier conjunctions, the outcome/closed pairing, the escalation pointer's
  same-tenant-AND-same-supplier rule, and every cross-tenant FK guard.
* **``SupplierFeedback``'s one-response-per-(supplier, scorecard, kpi, respondent) rule**, which
  lives in ``clean()`` and NOT in ``unique_together`` because three of those four columns are
  nullable and SQL compares NULLs as distinct - the all-NULL duplicate is the case a database
  constraint would have waved straight through.
* **``performance.generate_scorecard_lines()``** - idempotent, refuses a closed period, refuses an
  EMPTY run (the C2 regression: a one-way door firing on a no-op destroyed a derivable score and
  reported success), freezes the KPI definition onto every line it writes, and answers a KPI with
  no data ``measured_value=None`` - never a phantom ``0``.
* **``survey_aggregate()``** and ``SupplierFeedback.score_value()`` - the 1-5 -> 0/25/50/75/100
  conversion the aggregate stands on, importance as a WEIGHT that never gates the respondent
  count, and ``None`` (never 0) when nothing qualifies.
* **Tenant isolation at the model layer** - every model carries a real ``tenant`` FK and two
  tenants' rows never collide on any unique constraint.

Determinism (L16): every date basis here is ``timezone.localdate()`` / ``timezone.now()`` - the
same basis the model code uses. ``datetime.date.today()`` never appears, or the ``is_overdue`` and
window-boundary assertions flake for the hours after local midnight.

``Model.objects.create()`` does NOT call ``clean()``, so every rule below is driven through
``full_clean()`` (or through the real function), never by reading a row back.
"""
import datetime
import itertools
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.procurement import performance
from apps.procurement.models import (
    ProcurementAlert,
    SupplierFeedback,
    SupplierImprovementPlan,
    SupplierKpi,
    SupplierKpiScore,
    VendorSuspension,
)

pytestmark = pytest.mark.django_db


# -- local helpers ------------------------------------------------------------------------------
# Named _supplierperf_* so a sibling lane appending near this file cannot shadow them, and so a
# failure names its own lane. Rows are minted HERE wherever a test pins an exact catalogue:
# ``performance.applicable_kpis`` sweeps up EVERY active KPI in the tenant, so a generate test
# that leaned on the shared conftest's KPI fixtures would silently count somebody else's rows.

#: The separators the four ``__str__`` implementations fold into their labels.
_SUPPLIERPERF_DOT = "·"
_SUPPLIERPERF_DASH = "—"

#: L33 - theme.css ships COLOUR-NAMED badge classes only. Every *_CSS map is checked against this.
_SUPPLIERPERF_THEME_BADGES = {"badge-green", "badge-red", "badge-amber", "badge-info",
                              "badge-muted", "badge-slate"}

#: KPI codes only need to be locally distinct - ``unique_together ("tenant", "code")``.
_SUPPLIERPERF_CODE_SEQ = itertools.count(1)


def _supplierperf_today():
    """The SAME date basis the models use (L16) - never ``datetime.date.today()``."""
    return timezone.localdate()


def _supplierperf_field(model, name):
    return model._meta.get_field(name)


def _supplierperf_party(tenant, name="Northwind Precision Castings", role="supplier"):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


def _supplierperf_card(tenant, party, **overrides):
    from apps.scm.models import SupplierScorecard
    end = _supplierperf_today()
    fields = dict(tenant=tenant, party=party, period_start=end - datetime.timedelta(days=89),
                  period_end=end, status="draft")
    fields.update(overrides)
    return SupplierScorecard.objects.create(**fields)


def _supplierperf_make_kpi(tenant, **overrides):
    """A VALID, band-scored, higher-is-better KPI with a locally unique ``code``.

    The band triple is ordered for ``higher_is_better``; flip ``direction`` and the triple has to
    be flipped too or ``clean()`` refuses it (which ``objects.create()`` will never tell you).
    """
    fields = dict(
        tenant=tenant, code=f"KPI-{next(_SUPPLIERPERF_CODE_SEQ):04d}",
        name="On-time delivery", category="delivery", unit="pct",
        direction="higher_is_better", source="manual", derived_metric="", weight=20,
        target_value=Decimal("95"), warning_threshold=Decimal("90"),
        critical_threshold=Decimal("85"), scoring_method="band",
        maps_to_dimension="delivery", applies_to="all", applies_to_tier="",
        review_frequency="quarterly", display_order=10, is_active=True)
    fields.update(overrides)
    return SupplierKpi.objects.create(**fields)


def _supplierperf_unsaved_kpi(tenant, **overrides):
    """A KPI INSTANCE that has never been saved - for the pure ``clean()`` / banding rules."""
    fields = dict(
        tenant=tenant, code="UNSAVED-01", name="Unsaved definition", direction="higher_is_better",
        source="manual", scoring_method="band", applies_to="all")
    fields.update(overrides)
    return SupplierKpi(**fields)


def _supplierperf_line(tenant, scorecard, kpi, **overrides):
    fields = dict(
        tenant=tenant, scorecard=scorecard, kpi=kpi, measured_value=Decimal("92.0000"),
        score=Decimal("70.00"), band="warning", weight_applied=kpi.weight,
        target_at_time=kpi.target_value, direction_at_time=kpi.direction,
        source_at_time=kpi.source, unit_at_time=kpi.unit, kpi_name=kpi.name,
        kpi_category=kpi.category, breakdown={"source": "test"})
    fields.update(overrides)
    return SupplierKpiScore.objects.create(**fields)


def _supplierperf_response(tenant, supplier, **overrides):
    end = _supplierperf_today()
    fields = dict(tenant=tenant, supplier=supplier,
                  period_start=end - datetime.timedelta(days=89), period_end=end,
                  respondent_kind="internal", respondent_function="procurement",
                  importance=5, status="requested")
    fields.update(overrides)
    return SupplierFeedback.objects.create(**fields)


def _supplierperf_unsaved_response(tenant, supplier, **overrides):
    end = _supplierperf_today()
    fields = dict(tenant=tenant, supplier=supplier,
                  period_start=end - datetime.timedelta(days=89), period_end=end,
                  respondent_kind="internal", respondent_function="procurement",
                  importance=5, status="requested")
    fields.update(overrides)
    return SupplierFeedback(**fields)


def _supplierperf_unsaved_plan(tenant, supplier, **overrides):
    today = _supplierperf_today()
    fields = dict(tenant=tenant, supplier=supplier, title="Late deliveries",
                  severity="major", finding="Four of six shipments arrived late.",
                  start_date=today, target_close_date=today + datetime.timedelta(days=30),
                  status="draft")
    fields.update(overrides)
    return SupplierImprovementPlan(**fields)


def _supplierperf_band(kpi, value):
    """``score_and_band`` on a plain Decimal - the shape most banding assertions want."""
    return kpi.score_and_band(Decimal(value))


# =================================================================================================
# SupplierKpi - shape, defaults, __str__, the closed registries
# =================================================================================================

def test_supplierperf_kpi_defaults_are_the_documented_ones(tenant_a):
    kpi = SupplierKpi.objects.create(tenant=tenant_a, code="DEF-01", name="Defaults")
    kpi.refresh_from_db()
    assert kpi.category == "delivery"
    assert kpi.unit == "pct"
    assert kpi.direction == "higher_is_better"
    assert kpi.source == "manual"
    assert kpi.derived_metric == ""
    assert kpi.weight == 10
    assert kpi.scoring_method == "band"
    assert kpi.maps_to_dimension == ""
    assert kpi.applies_to == "all"
    assert kpi.applies_to_tier == ""
    assert kpi.review_frequency == "quarterly"
    assert kpi.display_order == 100
    assert kpi.is_active is True
    assert kpi.target_value is None
    assert kpi.warning_threshold is None
    assert kpi.critical_threshold is None
    assert kpi.industry_benchmark_value is None
    assert kpi.owner_id is None
    assert kpi.notes == "" and kpi.description == ""
    assert kpi.created_at is not None and kpi.updated_at is not None


def test_supplierperf_kpi_str_leads_with_the_code(tenant_a):
    """``code`` is the master identifier a score line is rolled up by, so it leads."""
    kpi = _supplierperf_make_kpi(tenant_a, code="OTD-01", name="On-time delivery")
    assert str(kpi) == f"OTD-01 {_SUPPLIERPERF_DOT} On-time delivery"


def test_supplierperf_kpi_meta_is_the_pinned_shape():
    meta = SupplierKpi._meta
    assert meta.ordering == ["display_order", "code"]
    assert set(meta.unique_together) == {("tenant", "code"), ("tenant", "number")}
    assert meta.verbose_name == "Supplier KPI"
    assert meta.verbose_name_plural == "Supplier KPIs"
    assert {i.name for i in meta.indexes} >= {"prc_skp_tnt_active_idx", "prc_skp_tnt_cat_idx",
                                              "prc_skp_tnt_source_idx"}


def test_supplierperf_kpi_ordering_is_display_order_then_code(tenant_a):
    last = _supplierperf_make_kpi(tenant_a, code="AAA-01", display_order=90)
    first = _supplierperf_make_kpi(tenant_a, code="ZZZ-01", display_order=10)
    middle = _supplierperf_make_kpi(tenant_a, code="MMM-01", display_order=10)
    assert list(SupplierKpi.objects.filter(tenant=tenant_a)) == [middle, first, last]


def test_supplierperf_kpi_derived_registry_is_closed_and_has_a_resolver_each():
    """A key in ``DERIVED_METRIC_CHOICES`` is a PROMISE that a reviewed resolver exists."""
    metric_keys = {key for key, _ in SupplierKpi.DERIVED_METRIC_CHOICES}
    assert len(metric_keys) == 14
    assert metric_keys == set(performance.DERIVED_RESOLVERS)


def test_supplierperf_kpi_choice_values_are_the_contract_ones():
    assert [v for v, _ in SupplierKpi.SOURCE_CHOICES] == ["derived", "survey", "manual"]
    assert [v for v, _ in SupplierKpi.DIRECTION_CHOICES] == ["higher_is_better", "lower_is_better"]
    assert [v for v, _ in SupplierKpi.SCORING_CHOICES] == ["band", "linear", "direct"]
    assert [v for v, _ in SupplierKpi.APPLIES_CHOICES] == ["all", "tier"]
    assert [v for v, _ in SupplierKpi.DIMENSION_CHOICES] == ["delivery", "quality", "price",
                                                             "responsiveness"]


def test_supplierperf_kpi_tier_mirror_matches_the_scm_source_of_truth():
    """``TIER_CHOICES`` is a LOCAL mirror; ``scm.SupplierProfile`` stays the source of truth."""
    from apps.scm.models import SupplierProfile
    assert ([v for v, _ in SupplierKpi.TIER_CHOICES]
            == [v for v, _ in SupplierProfile.TIER_CHOICES])


def test_supplierperf_kpi_dimensions_match_the_generate_field_map():
    assert set(performance.DIMENSION_FIELDS) == {v for v, _ in SupplierKpi.DIMENSION_CHOICES}


def test_supplierperf_kpi_weight_is_validated_one_to_a_hundred(tenant_a):
    over = _supplierperf_unsaved_kpi(tenant_a, weight=101)
    with pytest.raises(ValidationError) as excinfo:
        over.full_clean()
    assert "weight" in excinfo.value.error_dict
    under = _supplierperf_unsaved_kpi(tenant_a, weight=0)
    with pytest.raises(ValidationError) as excinfo:
        under.full_clean()
    assert "weight" in excinfo.value.error_dict


# =================================================================================================
# SupplierKpi - auto-numbering
# =================================================================================================

def test_supplierperf_kpi_numbers_run_skp_per_tenant(tenant_a):
    first = _supplierperf_make_kpi(tenant_a)
    second = _supplierperf_make_kpi(tenant_a)
    assert (first.number, second.number) == ("SKP-00001", "SKP-00002")


def test_supplierperf_kpi_numbering_is_independent_per_tenant(tenant_a, tenant_b):
    """Two workspaces both start at 00001 - the counter is per (tenant, prefix)."""
    _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_a)
    theirs = _supplierperf_make_kpi(tenant_b, code="MAN-01")
    assert theirs.number == "SKP-00001"


def test_supplierperf_kpi_number_is_allocated_once_and_survives_an_edit(tenant_a):
    kpi = _supplierperf_make_kpi(tenant_a)
    original = kpi.number
    kpi.name = "Renamed"
    kpi.save()
    kpi.refresh_from_db()
    assert kpi.number == original


def test_supplierperf_kpi_number_is_not_user_input():
    assert _supplierperf_field(SupplierKpi, "number").editable is False


def test_supplierperf_feedback_numbers_run_sfb_per_tenant(tenant_a, tenant_b):
    party_a = _supplierperf_party(tenant_a)
    party_b = _supplierperf_party(tenant_b, "Globex Alloys")
    first = _supplierperf_response(tenant_a, party_a)
    second = _supplierperf_response(tenant_a, party_a, respondent_function="quality")
    theirs = _supplierperf_response(tenant_b, party_b)
    assert (first.number, second.number) == ("SFB-00001", "SFB-00002")
    assert theirs.number == "SFB-00001"


def test_supplierperf_plan_numbers_run_sip_per_tenant(tenant_a, tenant_b):
    party_a = _supplierperf_party(tenant_a)
    party_b = _supplierperf_party(tenant_b, "Globex Alloys")
    first = _supplierperf_unsaved_plan(tenant_a, party_a)
    first.save()
    second = _supplierperf_unsaved_plan(tenant_a, party_a, title="Second plan")
    second.save()
    theirs = _supplierperf_unsaved_plan(tenant_b, party_b)
    theirs.save()
    assert (first.number, second.number) == ("SIP-00001", "SIP-00002")
    assert theirs.number == "SIP-00001"


def test_supplierperf_score_carries_no_number_at_all():
    """A child fact row: nobody quotes a score line by reference, they quote its scorecard."""
    names = {f.name for f in SupplierKpiScore._meta.get_fields()}
    assert "number" not in names
    assert {"tenant", "created_at", "updated_at"} <= names
    assert not hasattr(SupplierKpiScore, "NUMBER_PREFIX") or SupplierKpiScore.NUMBER_PREFIX == ""


# =================================================================================================
# SupplierKpi.score_and_band - the ONE scale
# =================================================================================================

def test_supplierperf_score_and_band_is_none_and_unknown_without_a_measurement(tenant_a):
    """A missing measurement is not a zero - writing one punishes a supplier for OUR data gap."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, target_value=Decimal("95"),
                                    warning_threshold=Decimal("90"),
                                    critical_threshold=Decimal("85"))
    assert kpi.score_and_band(None) == (None, "unknown")


def test_supplierperf_score_and_band_higher_is_better_boundaries(tenant_a):
    """Exactly ON a threshold is the BETTER band - ``<`` not ``<=``."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, warning_threshold=Decimal("90"),
                                    critical_threshold=Decimal("85"))
    assert _supplierperf_band(kpi, "84.99")[1] == "critical"
    assert _supplierperf_band(kpi, "85")[1] == "warning"
    assert _supplierperf_band(kpi, "89.99")[1] == "warning"
    assert _supplierperf_band(kpi, "90")[1] == "ok"
    assert _supplierperf_band(kpi, "100")[1] == "ok"


def test_supplierperf_score_and_band_lower_is_better_boundaries(tenant_a):
    """The mirror image: worse is HIGHER, and exactly on the line is still the better band."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, direction="lower_is_better",
                                    target_value=Decimal("1"), warning_threshold=Decimal("2"),
                                    critical_threshold=Decimal("5"))
    assert _supplierperf_band(kpi, "5.01")[1] == "critical"
    assert _supplierperf_band(kpi, "5")[1] == "warning"
    assert _supplierperf_band(kpi, "2.01")[1] == "warning"
    assert _supplierperf_band(kpi, "2")[1] == "ok"
    assert _supplierperf_band(kpi, "0")[1] == "ok"


def test_supplierperf_score_and_band_with_no_thresholds_is_unknown_not_ok(tenant_a):
    """With no line to fall either side of, ``unknown`` is honest and ``ok`` would be a lie."""
    kpi = _supplierperf_unsaved_kpi(tenant_a)
    assert kpi.target_value is None and kpi.warning_threshold is None
    assert kpi.score_and_band(Decimal("99")) == (None, "unknown")
    assert kpi.score_and_band(Decimal("0")) == (None, "unknown")


def test_supplierperf_score_and_band_uses_a_lone_critical_threshold(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, critical_threshold=Decimal("85"))
    assert _supplierperf_band(kpi, "80")[1] == "critical"
    assert _supplierperf_band(kpi, "88")[1] == "ok"


def test_supplierperf_score_and_band_uses_a_lone_warning_threshold(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, warning_threshold=Decimal("90"))
    assert _supplierperf_band(kpi, "80")[1] == "warning"
    assert _supplierperf_band(kpi, "95")[1] == "ok"


def test_supplierperf_score_and_band_band_method_reads_the_band_table(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="band",
                                    warning_threshold=Decimal("90"),
                                    critical_threshold=Decimal("85"))
    assert _supplierperf_band(kpi, "95") == (Decimal("100.00"), "ok")
    assert _supplierperf_band(kpi, "87") == (Decimal("70.00"), "warning")
    assert _supplierperf_band(kpi, "10") == (Decimal("30.00"), "critical")


def test_supplierperf_score_and_band_band_method_scores_none_when_unbanded(tenant_a):
    """No thresholds -> band ``unknown`` -> NO score. The band table has no ``unknown`` entry."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="band")
    assert kpi.score_and_band(Decimal("77")) == (None, "unknown")


def test_supplierperf_score_and_band_direct_is_the_value_clamped(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="direct", unit="score",
                                    warning_threshold=Decimal("65"),
                                    critical_threshold=Decimal("50"))
    assert _supplierperf_band(kpi, "42.5")[0] == Decimal("42.50")
    assert _supplierperf_band(kpi, "150")[0] == Decimal("100.00")
    assert _supplierperf_band(kpi, "-10")[0] == Decimal("0.00")


def test_supplierperf_score_and_band_direct_scores_even_when_unbanded(tenant_a):
    """``direct`` does not need thresholds - the value IS the score; the band stays honest."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="direct")
    assert kpi.score_and_band(Decimal("64")) == (Decimal("64.00"), "unknown")


def test_supplierperf_score_and_band_linear_higher_is_better_interpolates(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="linear",
                                    target_value=Decimal("100"),
                                    critical_threshold=Decimal("50"))
    assert _supplierperf_band(kpi, "100")[0] == Decimal("100.00")
    assert _supplierperf_band(kpi, "75")[0] == Decimal("50.00")
    assert _supplierperf_band(kpi, "60")[0] == Decimal("20.00")


def test_supplierperf_score_and_band_linear_higher_is_better_clamps_both_ends(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="linear",
                                    target_value=Decimal("100"),
                                    critical_threshold=Decimal("50"))
    assert _supplierperf_band(kpi, "140") == (Decimal("100.00"), "ok")
    assert _supplierperf_band(kpi, "10") == (Decimal("0.00"), "critical")


def test_supplierperf_score_and_band_linear_lower_is_better_interpolates(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, direction="lower_is_better",
                                    scoring_method="linear", target_value=Decimal("2"),
                                    critical_threshold=Decimal("10"))
    assert _supplierperf_band(kpi, "2")[0] == Decimal("100.00")
    assert _supplierperf_band(kpi, "6")[0] == Decimal("50.00")
    assert _supplierperf_band(kpi, "10")[0] == Decimal("0.00")


def test_supplierperf_score_and_band_linear_lower_is_better_clamps_both_ends(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, direction="lower_is_better",
                                    scoring_method="linear", target_value=Decimal("2"),
                                    critical_threshold=Decimal("10"))
    assert _supplierperf_band(kpi, "0")[0] == Decimal("100.00")
    assert _supplierperf_band(kpi, "40")[0] == Decimal("0.00")


def test_supplierperf_score_and_band_linear_falls_back_to_the_band_table_without_a_span(tenant_a):
    """A half-configured KPI must still band. The fallback is documented, not an error."""
    no_critical = _supplierperf_unsaved_kpi(tenant_a, scoring_method="linear",
                                            target_value=Decimal("95"),
                                            warning_threshold=Decimal("90"))
    assert no_critical.score_and_band(Decimal("80")) == (Decimal("70.00"), "warning")
    no_target = _supplierperf_unsaved_kpi(tenant_a, scoring_method="linear",
                                          warning_threshold=Decimal("90"),
                                          critical_threshold=Decimal("85"))
    assert no_target.score_and_band(Decimal("99")) == (Decimal("100.00"), "ok")


def test_supplierperf_score_and_band_linear_falls_back_when_the_span_points_the_wrong_way(
        tenant_a):
    """target <= critical on a higher-is-better KPI has no usable span - band table, no raise."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="linear",
                                    target_value=Decimal("50"),
                                    critical_threshold=Decimal("100"))
    assert kpi.score_and_band(Decimal("75")) == (Decimal("30.00"), "critical")


def test_supplierperf_score_and_band_linear_zero_span_does_not_divide_by_zero(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="linear",
                                    target_value=Decimal("90"),
                                    critical_threshold=Decimal("90"))
    score, band = kpi.score_and_band(Decimal("90"))
    assert band == "ok"
    assert score == Decimal("100.00")


def test_supplierperf_score_and_band_quantizes_to_two_places(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="linear",
                                    target_value=Decimal("100"),
                                    critical_threshold=Decimal("0"))
    score, _ = kpi.score_and_band(Decimal("33.333"))
    assert score == Decimal("33.33")
    assert score.as_tuple().exponent == -2


def test_supplierperf_score_and_band_accepts_a_plain_number(tenant_a):
    """Resolvers hand back Decimals, but the manual edit path can hand an int straight in."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, scoring_method="direct")
    assert kpi.score_and_band(64)[0] == Decimal("64.00")


def test_supplierperf_score_and_band_is_pure(tenant_a):
    """No queries, no writes, no clock - generate calls it once per KPI per supplier."""
    kpi = _supplierperf_make_kpi(tenant_a)
    before = (kpi.target_value, kpi.warning_threshold, kpi.updated_at)
    kpi.score_and_band(Decimal("91"))
    kpi.refresh_from_db()
    assert (kpi.target_value, kpi.warning_threshold, kpi.updated_at) == before


# =================================================================================================
# SupplierKpi.clean - band ordering, the derived conjunction, the tier conjunction
# =================================================================================================

def test_supplierperf_kpi_clean_accepts_a_well_ordered_definition(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, target_value=Decimal("95"),
                                    warning_threshold=Decimal("90"),
                                    critical_threshold=Decimal("85"))
    kpi.full_clean()


def test_supplierperf_kpi_clean_rejects_a_warning_above_the_target_when_higher_is_better(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, target_value=Decimal("90"),
                                    warning_threshold=Decimal("95"))
    with pytest.raises(ValidationError) as excinfo:
        kpi.full_clean()
    assert "warning_threshold" in excinfo.value.error_dict
    assert "higher-is-better" in str(excinfo.value)


def test_supplierperf_kpi_clean_rejects_a_critical_above_the_warning_when_higher_is_better(
        tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, target_value=Decimal("95"),
                                    warning_threshold=Decimal("90"),
                                    critical_threshold=Decimal("92"))
    with pytest.raises(ValidationError) as excinfo:
        kpi.full_clean()
    assert "critical_threshold" in excinfo.value.error_dict


def test_supplierperf_kpi_clean_rejects_a_warning_below_the_target_when_lower_is_better(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, direction="lower_is_better",
                                    target_value=Decimal("2"), warning_threshold=Decimal("1"))
    with pytest.raises(ValidationError) as excinfo:
        kpi.full_clean()
    assert "warning_threshold" in excinfo.value.error_dict
    assert "lower-is-better" in str(excinfo.value)


def test_supplierperf_kpi_clean_accepts_an_ascending_triple_when_lower_is_better(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, direction="lower_is_better",
                                    target_value=Decimal("1"), warning_threshold=Decimal("2"),
                                    critical_threshold=Decimal("5"))
    kpi.full_clean()


def test_supplierperf_kpi_clean_only_orders_the_thresholds_that_are_set(tenant_a):
    """A target and a critical line with no warning between them is still checked, both ways."""
    ok = _supplierperf_unsaved_kpi(tenant_a, target_value=Decimal("95"),
                                   critical_threshold=Decimal("85"))
    ok.full_clean()
    bad = _supplierperf_unsaved_kpi(tenant_a, target_value=Decimal("95"),
                                    critical_threshold=Decimal("99"))
    with pytest.raises(ValidationError) as excinfo:
        bad.full_clean()
    assert "critical_threshold" in excinfo.value.error_dict


def test_supplierperf_kpi_clean_accepts_no_thresholds_at_all(tenant_a):
    _supplierperf_unsaved_kpi(tenant_a).full_clean()


def test_supplierperf_kpi_clean_requires_a_metric_on_a_derived_kpi(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, source="derived", derived_metric="")
    with pytest.raises(ValidationError) as excinfo:
        kpi.full_clean()
    assert "derived_metric" in excinfo.value.error_dict


def test_supplierperf_kpi_clean_forbids_a_metric_on_a_manual_or_survey_kpi(tenant_a):
    """A stale metric key reads like a computation that is not happening."""
    for source in ("manual", "survey"):
        kpi = _supplierperf_unsaved_kpi(tenant_a, source=source, derived_metric="otd")
        with pytest.raises(ValidationError) as excinfo:
            kpi.full_clean()
        assert "derived_metric" in excinfo.value.error_dict


def test_supplierperf_kpi_clean_accepts_the_derived_conjunction(tenant_a):
    _supplierperf_unsaved_kpi(tenant_a, source="derived", derived_metric="otd").full_clean()


def test_supplierperf_kpi_clean_requires_a_tier_when_it_applies_to_one(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, applies_to="tier", applies_to_tier="")
    with pytest.raises(ValidationError) as excinfo:
        kpi.full_clean()
    assert "applies_to_tier" in excinfo.value.error_dict


def test_supplierperf_kpi_clean_forbids_a_tier_when_it_applies_to_all(tenant_a):
    kpi = _supplierperf_unsaved_kpi(tenant_a, applies_to="all", applies_to_tier="strategic")
    with pytest.raises(ValidationError) as excinfo:
        kpi.full_clean()
    assert "applies_to_tier" in excinfo.value.error_dict


def test_supplierperf_kpi_clean_accepts_the_tier_conjunction(tenant_a):
    _supplierperf_unsaved_kpi(tenant_a, applies_to="tier",
                              applies_to_tier="strategic").full_clean()


def test_supplierperf_kpi_clean_collects_every_problem_at_once(tenant_a):
    """A form must show all three, not the first - errors are collected into one dict."""
    kpi = _supplierperf_unsaved_kpi(tenant_a, source="derived", derived_metric="",
                                    applies_to="tier", applies_to_tier="",
                                    target_value=Decimal("90"),
                                    warning_threshold=Decimal("95"))
    with pytest.raises(ValidationError) as excinfo:
        kpi.full_clean()
    assert set(excinfo.value.error_dict) >= {"derived_metric", "applies_to_tier",
                                             "warning_threshold"}


# =================================================================================================
# SupplierKpi - uniqueness and tenant isolation
# =================================================================================================

def test_supplierperf_kpi_code_is_unique_inside_one_tenant(tenant_a):
    _supplierperf_make_kpi(tenant_a, code="OTD-01")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _supplierperf_make_kpi(tenant_a, code="OTD-01")


def test_supplierperf_kpi_two_tenants_may_both_own_the_same_code(tenant_a, tenant_b):
    mine = _supplierperf_make_kpi(tenant_a, code="OTD-01")
    theirs = _supplierperf_make_kpi(tenant_b, code="OTD-01")
    assert mine.pk != theirs.pk
    assert SupplierKpi.objects.filter(tenant=tenant_a, code="OTD-01").count() == 1
    assert SupplierKpi.objects.filter(tenant=tenant_b, code="OTD-01").count() == 1


def test_supplierperf_every_model_carries_a_real_tenant_fk():
    for model in (SupplierKpi, SupplierKpiScore, SupplierFeedback, SupplierImprovementPlan):
        field = _supplierperf_field(model, "tenant")
        assert field.many_to_one
        assert field.related_model._meta.label == "core.Tenant"
        assert field.null is False


# =================================================================================================
# SupplierKpiScore - shape, __str__, derived properties
# =================================================================================================

def test_supplierperf_line_defaults_are_the_documented_ones(
        tenant_a, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a)
    line = SupplierKpiScore.objects.create(
        tenant=tenant_a, scorecard=supplierperf_scorecard_draft_a, kpi=kpi)
    line.refresh_from_db()
    assert line.measured_value is None
    assert line.score is None
    assert line.band == "unknown"
    assert line.weight_applied == 0
    assert line.breakdown == {}
    assert line.respondent_count == 0
    assert line.comment == ""
    assert line.computed_at is not None
    assert line.computed_by_id is None


def test_supplierperf_line_computed_at_restamps_rather_than_freezing():
    """``default=timezone.now``, NOT ``auto_now_add`` - a re-run must re-stamp freshness."""
    field = _supplierperf_field(SupplierKpiScore, "computed_at")
    assert field.auto_now_add is False
    assert field.default is timezone.now
    assert field.editable is False


def test_supplierperf_line_frozen_columns_are_not_editable():
    frozen = ("target_at_time", "direction_at_time", "source_at_time", "unit_at_time",
              "kpi_name", "kpi_category", "breakdown", "respondent_count", "computed_at",
              "computed_by")
    for name in frozen:
        assert _supplierperf_field(SupplierKpiScore, name).editable is False, name


def test_supplierperf_line_str_uses_the_frozen_name_not_a_join(
        tenant_a, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a, name="On-time delivery")
    line = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                              kpi_name="On-time delivery", score=Decimal("70.00"))
    assert str(line) == f"On-time delivery {_SUPPLIERPERF_DOT} 70.00"
    kpi.name = "Renamed since"
    kpi.save(update_fields=["name"])
    line.refresh_from_db()
    assert str(line) == f"On-time delivery {_SUPPLIERPERF_DOT} 70.00"


def test_supplierperf_line_str_renders_an_em_dash_for_an_unscored_line(
        tenant_a, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a)
    line = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                              score=None, measured_value=None, band="unknown")
    assert str(line).endswith(f"{_SUPPLIERPERF_DOT} {_SUPPLIERPERF_DASH}")


def test_supplierperf_line_str_survives_an_unsaved_instance():
    assert str(SupplierKpiScore()) == f"KPI {_SUPPLIERPERF_DOT} {_SUPPLIERPERF_DASH}"


def test_supplierperf_line_band_css_is_colour_named_for_every_band():
    assert set(SupplierKpiScore.BAND_CSS) == {v for v, _ in SupplierKpiScore.BAND_CHOICES}
    assert set(SupplierKpiScore.BAND_CSS.values()) <= _SUPPLIERPERF_THEME_BADGES


def test_supplierperf_line_band_css_falls_back_to_slate():
    assert SupplierKpiScore(band="ok").band_css == "badge-green"
    assert SupplierKpiScore(band="critical").band_css == "badge-red"
    assert SupplierKpiScore(band="not-a-band").band_css == "badge-slate"


def test_supplierperf_line_contribution_is_score_times_frozen_weight(
        tenant_a, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a, weight=20)
    line = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                              score=Decimal("70.00"), weight_applied=20)
    assert line.contribution == Decimal("1400.00")


def test_supplierperf_line_contribution_is_none_when_the_line_never_scored(
        tenant_a, supplierperf_scorecard_draft_a):
    """An unscored line must drop out of BOTH sides of the composite, not drag the top down."""
    kpi = _supplierperf_make_kpi(tenant_a)
    line = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                              score=None, weight_applied=20)
    assert line.contribution is None


def test_supplierperf_line_meta_is_the_pinned_shape():
    meta = SupplierKpiScore._meta
    assert meta.ordering == ["kpi_category", "kpi_name", "id"]
    assert meta.unique_together == (("tenant", "scorecard", "kpi"),)
    assert meta.verbose_name == "Supplier KPI Score"
    assert {i.name for i in meta.indexes} >= {"prc_sks_tnt_scr_idx", "prc_sks_tnt_band_idx",
                                              "prc_sks_tnt_kpi_idx",
                                              "prc_sks_tnt_cat_name_idx"}


def test_supplierperf_line_default_sort_is_covered_by_an_index():
    """C3 - the register's default sort was a filesort over the whole tenant partition."""
    covering = [i for i in SupplierKpiScore._meta.indexes
                if i.fields == ["tenant", "kpi_category", "kpi_name", "id"]]
    assert covering, "no index covers SupplierKpiScore.Meta.ordering"


# =================================================================================================
# SupplierKpiScore - uniqueness, PROTECT, clean
# =================================================================================================

def test_supplierperf_line_is_unique_per_scorecard_and_kpi(
        tenant_a, supplierperf_scorecard_draft_a):
    """THIS is the safety on the Generate button - a second press updates, never doubles."""
    kpi = _supplierperf_make_kpi(tenant_a)
    _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi)


def test_supplierperf_line_two_tenants_never_collide_on_the_unique_key(
        tenant_a, tenant_b, supplierperf_scorecard_draft_a, supplierperf_scorecard_b):
    mine = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a,
                              _supplierperf_make_kpi(tenant_a))
    theirs = _supplierperf_line(tenant_b, supplierperf_scorecard_b,
                                _supplierperf_make_kpi(tenant_b))
    assert mine.pk != theirs.pk
    assert SupplierKpiScore.objects.filter(tenant=tenant_a).count() == 1
    assert SupplierKpiScore.objects.filter(tenant=tenant_b).count() == 1


def test_supplierperf_line_protects_the_kpi_it_measured(
        tenant_a, supplierperf_scorecard_draft_a):
    """PROTECT: retire a KPI with ``is_active=False``; never delete measured history."""
    kpi = _supplierperf_make_kpi(tenant_a)
    _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi)
    with pytest.raises(ProtectedError):
        kpi.delete()


def test_supplierperf_line_dies_with_its_scorecard(tenant_a, supplierperf_supplier_a):
    """CASCADE: a scorecard IS the period document; its lines have no life without it."""
    card = _supplierperf_card(tenant_a, supplierperf_supplier_a)
    _supplierperf_line(tenant_a, card, _supplierperf_make_kpi(tenant_a))
    card.delete()
    assert SupplierKpiScore.objects.count() == 0


def test_supplierperf_line_clean_accepts_a_same_tenant_pair(
        tenant_a, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a)
    SupplierKpiScore(tenant=tenant_a, scorecard=supplierperf_scorecard_draft_a,
                     kpi=kpi).full_clean()


def test_supplierperf_line_clean_rejects_another_workspaces_scorecard(
        tenant_a, supplierperf_scorecard_b):
    kpi = _supplierperf_make_kpi(tenant_a)
    line = SupplierKpiScore(tenant=tenant_a, scorecard=supplierperf_scorecard_b, kpi=kpi)
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "scorecard" in excinfo.value.error_dict
    assert "another workspace" in str(excinfo.value)


def test_supplierperf_line_clean_rejects_another_workspaces_kpi(
        tenant_a, tenant_b, supplierperf_scorecard_draft_a):
    theirs = _supplierperf_make_kpi(tenant_b)
    line = SupplierKpiScore(tenant=tenant_a, scorecard=supplierperf_scorecard_draft_a, kpi=theirs)
    with pytest.raises(ValidationError) as excinfo:
        line.full_clean()
    assert "kpi" in excinfo.value.error_dict


def test_supplierperf_line_clean_is_skipped_while_the_tenant_is_unset(
        supplierperf_scorecard_draft_a, tenant_a):
    """No tenant yet means nothing to compare against - and no RelatedObjectDoesNotExist."""
    kpi = _supplierperf_make_kpi(tenant_a)
    SupplierKpiScore(scorecard=supplierperf_scorecard_draft_a, kpi=kpi).clean()
    SupplierKpiScore().clean()


# =================================================================================================
# SupplierFeedback - shape, score_value, display properties
# =================================================================================================

def test_supplierperf_feedback_defaults_are_the_documented_ones(tenant_a):
    party = _supplierperf_party(tenant_a)
    row = _supplierperf_response(tenant_a, party)
    row.refresh_from_db()
    assert row.respondent_kind == "internal"
    assert row.respondent_function == "procurement"
    assert row.status == "requested"
    assert row.importance == 5
    assert row.rating is None
    assert row.scorecard_id is None and row.kpi_id is None and row.respondent_id is None
    assert row.due_date is None
    assert row.submitted_at is None
    assert row.requested_at is not None
    assert row.comment == "" and row.respondent_name == ""


def test_supplierperf_feedback_score_value_maps_the_whole_scale(tenant_a):
    party = _supplierperf_party(tenant_a)
    expected = {1: Decimal("0"), 2: Decimal("25"), 3: Decimal("50"),
                4: Decimal("75"), 5: Decimal("100")}
    for rating, value in expected.items():
        row = _supplierperf_unsaved_response(tenant_a, party, rating=rating)
        assert row.score_value() == value


def test_supplierperf_feedback_score_value_is_none_without_a_rating(tenant_a):
    """An unanswered request is not a zero - scoring one punishes a supplier for an inbox."""
    party = _supplierperf_party(tenant_a)
    assert _supplierperf_unsaved_response(tenant_a, party, rating=None).score_value() is None


def test_supplierperf_feedback_rating_score_map_covers_every_rating_choice():
    assert (set(SupplierFeedback.RATING_SCORE_MAP)
            == {v for v, _ in SupplierFeedback.RATING_CHOICES})
    assert sorted(SupplierFeedback.RATING_SCORE_MAP.values()) == [0, 25, 50, 75, 100]


def test_supplierperf_feedback_str_folds_the_number_and_supplier(tenant_a):
    party = _supplierperf_party(tenant_a, "Northwind Precision Castings")
    row = _supplierperf_response(tenant_a, party)
    assert str(row) == (f"{row.number} {_SUPPLIERPERF_DOT} Northwind Precision Castings")


def test_supplierperf_feedback_str_survives_an_unsaved_instance():
    """An unsaved instance rendered its supplier as the literal word 'None' once already."""
    assert str(SupplierFeedback()) == f"SFB {_SUPPLIERPERF_DOT} {_SUPPLIERPERF_DASH}"


def test_supplierperf_feedback_css_maps_are_colour_named_only():
    for mapping in (SupplierFeedback.STATUS_CSS, SupplierFeedback.RATING_CSS,
                    SupplierFeedback.KIND_CSS):
        assert set(mapping.values()) <= _SUPPLIERPERF_THEME_BADGES
    assert set(SupplierFeedback.STATUS_CSS) == {v for v, _ in SupplierFeedback.STATUS_CHOICES}
    assert set(SupplierFeedback.KIND_CSS) == {
        v for v, _ in SupplierFeedback.RESPONDENT_KIND_CHOICES}


def test_supplierperf_feedback_css_properties_fall_back_to_slate():
    assert SupplierFeedback(status="submitted").status_css == "badge-green"
    assert SupplierFeedback(status="nonsense").status_css == "badge-slate"
    assert SupplierFeedback(rating=5).rating_css == "badge-green"
    assert SupplierFeedback(rating=None).rating_css == "badge-slate"
    assert SupplierFeedback(respondent_kind="supplier_self").kind_css == "badge-info"
    assert SupplierFeedback(respondent_kind="nonsense").kind_css == "badge-slate"


def test_supplierperf_feedback_is_overdue_only_while_still_requested(tenant_a):
    party = _supplierperf_party(tenant_a)
    yesterday = _supplierperf_today() - datetime.timedelta(days=1)
    overdue = _supplierperf_unsaved_response(tenant_a, party, due_date=yesterday,
                                             status="requested")
    assert overdue.is_overdue is True
    for status in ("submitted", "declined", "expired"):
        answered = _supplierperf_unsaved_response(tenant_a, party, due_date=yesterday,
                                                  status=status, rating=3)
        assert answered.is_overdue is False, status


def test_supplierperf_feedback_is_not_overdue_on_its_due_date(tenant_a):
    """Strictly BEFORE today - a response due today is not late yet."""
    party = _supplierperf_party(tenant_a)
    row = _supplierperf_unsaved_response(tenant_a, party, due_date=_supplierperf_today())
    assert row.is_overdue is False


def test_supplierperf_feedback_without_a_due_date_is_never_overdue(tenant_a):
    party = _supplierperf_party(tenant_a)
    assert _supplierperf_unsaved_response(tenant_a, party, due_date=None).is_overdue is False


def test_supplierperf_feedback_meta_is_the_pinned_shape():
    meta = SupplierFeedback._meta
    assert meta.ordering == ["-period_end", "-id"]
    assert meta.unique_together == (("tenant", "number"),)
    assert meta.verbose_name_plural == "Supplier Feedback"


def test_supplierperf_feedback_uniqueness_is_not_a_database_constraint():
    """The natural key holds three NULLABLE columns, so a constraint would let duplicates
    through. The rule lives in ``clean()`` - see the duplicate tests below."""
    constrained = {tuple(rule) for rule in SupplierFeedback._meta.unique_together}
    assert ("tenant", "supplier", "scorecard", "kpi", "respondent") not in constrained


# =================================================================================================
# SupplierFeedback.clean - the five rules
# =================================================================================================

def test_supplierperf_feedback_clean_accepts_a_plain_internal_response(
        tenant_a, admin_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    row = _supplierperf_unsaved_response(
        tenant_a, supplierperf_supplier_a, scorecard=supplierperf_scorecard_draft_a,
        kpi=supplierperf_kpi_survey_a, respondent=admin_user, rating=4, status="submitted")
    row.full_clean()


def test_supplierperf_feedback_clean_rejects_a_genuine_duplicate(
        tenant_a, admin_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    """One response per (supplier, scorecard, kpi, respondent)."""
    _supplierperf_response(tenant_a, supplierperf_supplier_a,
                           scorecard=supplierperf_scorecard_draft_a,
                           kpi=supplierperf_kpi_survey_a, respondent=admin_user)
    second = _supplierperf_unsaved_response(
        tenant_a, supplierperf_supplier_a, scorecard=supplierperf_scorecard_draft_a,
        kpi=supplierperf_kpi_survey_a, respondent=admin_user)
    with pytest.raises(ValidationError) as excinfo:
        second.full_clean()
    assert "respondent" in excinfo.value.error_dict
    assert "already answered" in str(excinfo.value)


def test_supplierperf_feedback_clean_rejects_an_all_null_duplicate(
        tenant_a, supplierperf_supplier_a):
    """THE trap a ``unique_together`` would have waved through: SQL compares NULLs as distinct,
    so two ad-hoc rows (no scorecard, no kpi, no respondent) would both have been accepted."""
    _supplierperf_response(tenant_a, supplierperf_supplier_a)
    second = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a)
    with pytest.raises(ValidationError) as excinfo:
        second.full_clean()
    assert "respondent" in excinfo.value.error_dict


def test_supplierperf_feedback_clean_lets_a_different_kpi_through(
        tenant_a, admin_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    """Same respondent, same period document, DIFFERENT question - a legitimate second answer."""
    other = _supplierperf_make_kpi(tenant_a, code="SRV-02", source="survey",
                                   scoring_method="direct")
    _supplierperf_response(tenant_a, supplierperf_supplier_a,
                           scorecard=supplierperf_scorecard_draft_a,
                           kpi=supplierperf_kpi_survey_a, respondent=admin_user)
    second = _supplierperf_unsaved_response(
        tenant_a, supplierperf_supplier_a, scorecard=supplierperf_scorecard_draft_a,
        kpi=other, respondent=admin_user)
    second.full_clean()


def test_supplierperf_feedback_clean_lets_a_different_respondent_through(
        tenant_a, admin_user, member_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    _supplierperf_response(tenant_a, supplierperf_supplier_a,
                           scorecard=supplierperf_scorecard_draft_a,
                           kpi=supplierperf_kpi_survey_a, respondent=admin_user)
    second = _supplierperf_unsaved_response(
        tenant_a, supplierperf_supplier_a, scorecard=supplierperf_scorecard_draft_a,
        kpi=supplierperf_kpi_survey_a, respondent=member_user)
    second.full_clean()


def test_supplierperf_feedback_clean_does_not_flag_a_row_against_itself(
        tenant_a, admin_user, supplierperf_supplier_a, supplierperf_kpi_survey_a):
    """Re-cleaning an existing row on edit must not read it as its own duplicate."""
    row = _supplierperf_response(tenant_a, supplierperf_supplier_a,
                                 kpi=supplierperf_kpi_survey_a, respondent=admin_user)
    row.comment = "Edited."
    row.full_clean()


def test_supplierperf_feedback_clean_refuses_a_derived_kpi(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_derived_a):
    """Filing an opinion against a derived KPI files it where nothing will ever read it."""
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a,
                                         kpi=supplierperf_kpi_derived_a)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "kpi" in excinfo.value.error_dict
    assert "not a survey question" in str(excinfo.value)


def test_supplierperf_feedback_clean_refuses_a_manual_kpi_too(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_manual_a):
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a,
                                         kpi=supplierperf_kpi_manual_a)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "kpi" in excinfo.value.error_dict


def test_supplierperf_feedback_clean_rejects_a_backwards_period(
        tenant_a, supplierperf_supplier_a):
    today = _supplierperf_today()
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a,
                                         period_start=today,
                                         period_end=today - datetime.timedelta(days=1))
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "period_end" in excinfo.value.error_dict


def test_supplierperf_feedback_clean_allows_a_single_day_period(
        tenant_a, supplierperf_supplier_a):
    today = _supplierperf_today()
    _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a, period_start=today,
                                   period_end=today).full_clean()


def test_supplierperf_feedback_clean_requires_a_rating_once_submitted(
        tenant_a, supplierperf_supplier_a):
    """'Submitted, unrated' is not an answer."""
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a, status="submitted",
                                         rating=None)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "rating" in excinfo.value.error_dict


def test_supplierperf_feedback_clean_forbids_an_internal_user_on_a_self_assessment(
        tenant_a, admin_user, supplierperf_supplier_a):
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a,
                                         respondent_kind="supplier_self",
                                         respondent=admin_user,
                                         respondent_name="D. Whitlock")
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "respondent" in excinfo.value.error_dict
    assert "not filed by an internal user" in str(excinfo.value)


def test_supplierperf_feedback_clean_requires_a_name_on_a_self_assessment(
        tenant_a, supplierperf_supplier_a):
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a,
                                         respondent_kind="supplier_self", respondent_name="")
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "respondent_name" in excinfo.value.error_dict


def test_supplierperf_feedback_clean_accepts_a_well_formed_self_assessment(
        tenant_a, supplierperf_supplier_a):
    _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a,
                                   respondent_kind="supplier_self",
                                   respondent_name="D. Whitlock", rating=5,
                                   status="submitted").full_clean()


def test_supplierperf_feedback_clean_rejects_another_workspaces_supplier(
        tenant_a, supplierperf_supplier_b):
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_b)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "supplier" in excinfo.value.error_dict


def test_supplierperf_feedback_clean_rejects_another_workspaces_scorecard(
        tenant_a, supplierperf_supplier_a, supplierperf_scorecard_b):
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a,
                                         scorecard=supplierperf_scorecard_b)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "scorecard" in excinfo.value.error_dict


def test_supplierperf_feedback_clean_rejects_another_workspaces_kpi(
        tenant_a, tenant_b, supplierperf_supplier_a):
    theirs = _supplierperf_make_kpi(tenant_b, source="survey")
    row = _supplierperf_unsaved_response(tenant_a, supplierperf_supplier_a, kpi=theirs)
    with pytest.raises(ValidationError) as excinfo:
        row.full_clean()
    assert "kpi" in excinfo.value.error_dict
    assert "another workspace" in str(excinfo.value)


def test_supplierperf_feedback_clean_is_skipped_while_the_tenant_is_unset(
        supplierperf_supplier_a):
    SupplierFeedback(supplier=supplierperf_supplier_a).clean()


# =================================================================================================
# SupplierImprovementPlan - shape, __str__, derived properties
# =================================================================================================

def test_supplierperf_plan_defaults_are_the_documented_ones(tenant_a, supplierperf_supplier_a):
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a)
    plan.save()
    plan.refresh_from_db()
    assert plan.status == "draft"
    assert plan.severity == "major"
    assert plan.outcome == ""
    assert plan.scorecard_id is None and plan.kpi_id is None
    assert plan.escalated_suspension_id is None
    assert plan.actual_close_date is None
    assert plan.extended_close_date is None
    assert plan.acknowledged_at is None and plan.acknowledged_by_id is None
    assert plan.verified_at is None and plan.verified_by_id is None
    assert plan.closure_note == ""
    assert not plan.evidence and plan.evidence_url == ""


def test_supplierperf_plan_stamps_are_not_editable():
    for name in ("actual_close_date", "acknowledged_by", "acknowledged_at", "verified_by",
                 "verified_at", "closure_note"):
        assert _supplierperf_field(SupplierImprovementPlan, name).editable is False, name


def test_supplierperf_plan_str_folds_the_number_and_title(tenant_a, supplierperf_supplier_a):
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a, title="Late deliveries")
    plan.save()
    assert str(plan) == f"{plan.number} {_SUPPLIERPERF_DOT} Late deliveries"


def test_supplierperf_plan_str_survives_an_unsaved_instance():
    assert str(SupplierImprovementPlan(title="Draft")) == f"SIP {_SUPPLIERPERF_DOT} Draft"


def test_supplierperf_plan_has_evidence_accepts_either_proof(tenant_a, supplierperf_supplier_a):
    bare = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a)
    assert bare.has_evidence is False
    linked = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                                        evidence_url="https://qms.example/capa/1")
    assert linked.has_evidence is True


def test_supplierperf_plan_effective_close_date_prefers_the_extension(
        tenant_a, supplierperf_supplier_a):
    today = _supplierperf_today()
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                                      target_close_date=today + datetime.timedelta(days=10))
    assert plan.effective_close_date == today + datetime.timedelta(days=10)
    plan.extended_close_date = today + datetime.timedelta(days=25)
    assert plan.effective_close_date == today + datetime.timedelta(days=25)


def test_supplierperf_plan_is_overdue_reads_the_effective_date(
        tenant_a, supplierperf_supplier_a):
    today = _supplierperf_today()
    plan = _supplierperf_unsaved_plan(
        tenant_a, supplierperf_supplier_a, status="active",
        start_date=today - datetime.timedelta(days=40),
        target_close_date=today - datetime.timedelta(days=5))
    assert plan.is_overdue is True
    plan.extended_close_date = today + datetime.timedelta(days=5)
    assert plan.is_overdue is False


def test_supplierperf_plan_is_overdue_only_while_open(tenant_a, supplierperf_supplier_a):
    today = _supplierperf_today()
    for status in SupplierImprovementPlan.OPEN_STATUSES:
        plan = _supplierperf_unsaved_plan(
            tenant_a, supplierperf_supplier_a, status=status,
            start_date=today - datetime.timedelta(days=40),
            target_close_date=today - datetime.timedelta(days=5))
        assert plan.is_overdue is True, status
    for status in ("closed", "cancelled"):
        plan = _supplierperf_unsaved_plan(
            tenant_a, supplierperf_supplier_a, status=status,
            start_date=today - datetime.timedelta(days=40),
            target_close_date=today - datetime.timedelta(days=5))
        assert plan.is_overdue is False, status


def test_supplierperf_plan_open_statuses_are_a_subset_of_the_status_choices():
    assert (set(SupplierImprovementPlan.OPEN_STATUSES)
            < {v for v, _ in SupplierImprovementPlan.STATUS_CHOICES})


def test_supplierperf_plan_css_maps_are_colour_named_only():
    for mapping in (SupplierImprovementPlan.SEVERITY_CSS, SupplierImprovementPlan.STATUS_CSS,
                    SupplierImprovementPlan.OUTCOME_CSS):
        assert set(mapping.values()) <= _SUPPLIERPERF_THEME_BADGES
    assert set(SupplierImprovementPlan.STATUS_CSS) == {
        v for v, _ in SupplierImprovementPlan.STATUS_CHOICES}
    assert set(SupplierImprovementPlan.OUTCOME_CSS) == {
        v for v, _ in SupplierImprovementPlan.OUTCOME_CHOICES}


def test_supplierperf_plan_css_properties_fall_back_to_slate():
    assert SupplierImprovementPlan(severity="critical").severity_css == "badge-red"
    assert SupplierImprovementPlan(status="closed").status_css == "badge-green"
    assert SupplierImprovementPlan(outcome="failed").outcome_css == "badge-red"
    assert SupplierImprovementPlan(outcome="").outcome_css == "badge-slate"
    assert SupplierImprovementPlan(status="nonsense").status_css == "badge-slate"


def test_supplierperf_plan_meta_is_the_pinned_shape():
    meta = SupplierImprovementPlan._meta
    assert meta.ordering == ["-start_date", "-id"]
    assert meta.unique_together == (("tenant", "number"),)
    assert meta.verbose_name == "Supplier Improvement Plan"


def test_supplierperf_plan_protects_the_supplier_it_names(tenant_a, supplierperf_supplier_a):
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a)
    plan.save()
    with pytest.raises(ProtectedError):
        supplierperf_supplier_a.delete()


# =================================================================================================
# SupplierImprovementPlan.clean - the five rules
# =================================================================================================

def test_supplierperf_plan_clean_accepts_a_well_formed_draft(tenant_a, supplierperf_supplier_a):
    _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a).full_clean()


def test_supplierperf_plan_clean_rejects_a_close_before_the_start(
        tenant_a, supplierperf_supplier_a):
    today = _supplierperf_today()
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a, start_date=today,
                                      target_close_date=today - datetime.timedelta(days=1))
    with pytest.raises(ValidationError) as excinfo:
        plan.full_clean()
    assert "target_close_date" in excinfo.value.error_dict


def test_supplierperf_plan_clean_allows_a_same_day_close(tenant_a, supplierperf_supplier_a):
    today = _supplierperf_today()
    _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a, start_date=today,
                               target_close_date=today).full_clean()


def test_supplierperf_plan_clean_requires_an_extension_strictly_after_the_target(
        tenant_a, supplierperf_supplier_a):
    """An extension granted on or before the agreed date quietly re-writes what was agreed."""
    today = _supplierperf_today()
    target = today + datetime.timedelta(days=30)
    same_day = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                                          target_close_date=target,
                                          extended_close_date=target)
    with pytest.raises(ValidationError) as excinfo:
        same_day.full_clean()
    assert "extended_close_date" in excinfo.value.error_dict
    earlier = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                                         target_close_date=target,
                                         extended_close_date=target
                                         - datetime.timedelta(days=1))
    with pytest.raises(ValidationError):
        earlier.full_clean()
    later = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                                       target_close_date=target,
                                       extended_close_date=target + datetime.timedelta(days=1))
    later.full_clean()


def test_supplierperf_plan_clean_requires_an_outcome_once_closed(
        tenant_a, supplierperf_supplier_a):
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a, status="closed",
                                      outcome="")
    with pytest.raises(ValidationError) as excinfo:
        plan.full_clean()
    assert "outcome" in excinfo.value.error_dict


def test_supplierperf_plan_clean_forbids_an_outcome_while_still_open(
        tenant_a, supplierperf_supplier_a):
    """An outcome on an active plan is a result nobody signed off."""
    for status in ("draft", "active", "monitoring", "cancelled"):
        plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a, status=status,
                                          outcome="successful")
        with pytest.raises(ValidationError) as excinfo:
            plan.full_clean()
        assert "outcome" in excinfo.value.error_dict, status


def test_supplierperf_plan_clean_accepts_a_closed_plan_with_its_outcome(
        tenant_a, supplierperf_supplier_a):
    _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a, status="closed",
                               outcome="escalated").full_clean()


def test_supplierperf_plan_clean_accepts_an_escalation_against_the_same_supplier(
        tenant_a, supplierperf_supplier_a, supplierperf_suspension_a):
    _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                               escalated_suspension=supplierperf_suspension_a).full_clean()


def test_supplierperf_plan_clean_rejects_an_escalation_against_another_supplier(
        tenant_a, supplierperf_supplier2_a, supplierperf_suspension_a):
    """A pointer at somebody else's block shows a block on this page that blocks nobody here."""
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier2_a,
                                      escalated_suspension=supplierperf_suspension_a)
    with pytest.raises(ValidationError) as excinfo:
        plan.full_clean()
    assert "escalated_suspension" in excinfo.value.error_dict
    assert "different supplier" in str(excinfo.value)


def test_supplierperf_plan_clean_rejects_another_workspaces_suspension(
        tenant_a, tenant_b, admin_b, supplierperf_supplier_a, supplierperf_supplier_b):
    theirs = VendorSuspension.objects.create(
        tenant=tenant_b, supplier=supplierperf_supplier_b, reason="Globex only.",
        status="active", requested_by=admin_b)
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                                      escalated_suspension=theirs)
    with pytest.raises(ValidationError) as excinfo:
        plan.full_clean()
    assert "escalated_suspension" in excinfo.value.error_dict
    assert "another workspace" in str(excinfo.value)


def test_supplierperf_plan_clean_rejects_another_workspaces_supplier(
        tenant_a, supplierperf_supplier_b):
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_b)
    with pytest.raises(ValidationError) as excinfo:
        plan.full_clean()
    assert "supplier" in excinfo.value.error_dict


def test_supplierperf_plan_clean_rejects_another_workspaces_scorecard(
        tenant_a, supplierperf_supplier_a, supplierperf_scorecard_b):
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a,
                                      scorecard=supplierperf_scorecard_b)
    with pytest.raises(ValidationError) as excinfo:
        plan.full_clean()
    assert "scorecard" in excinfo.value.error_dict


def test_supplierperf_plan_clean_rejects_another_workspaces_kpi(
        tenant_a, tenant_b, supplierperf_supplier_a):
    theirs = _supplierperf_make_kpi(tenant_b)
    plan = _supplierperf_unsaved_plan(tenant_a, supplierperf_supplier_a, kpi=theirs)
    with pytest.raises(ValidationError) as excinfo:
        plan.full_clean()
    assert "kpi" in excinfo.value.error_dict


def test_supplierperf_plan_clean_is_skipped_while_the_tenant_is_unset(
        supplierperf_supplier_a, supplierperf_suspension_a):
    SupplierImprovementPlan(supplier=supplierperf_supplier_a,
                            escalated_suspension=supplierperf_suspension_a).clean()


# =================================================================================================
# performance.applicable_kpis
# =================================================================================================

def test_supplierperf_applicable_kpis_returns_every_all_kpi_in_display_order(
        tenant_a, supplierperf_supplier_a):
    late = _supplierperf_make_kpi(tenant_a, code="ZZZ-01", display_order=90)
    early = _supplierperf_make_kpi(tenant_a, code="AAA-01", display_order=10)
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier_a) == [early, late]


def test_supplierperf_applicable_kpis_skips_retired_definitions(
        tenant_a, supplierperf_supplier_a):
    live = _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_a, is_active=False)
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier_a) == [live]


def test_supplierperf_applicable_kpis_adds_the_matching_tier(
        tenant_a, supplierperf_supplier_a, supplierperf_profile_a):
    everyone = _supplierperf_make_kpi(tenant_a, display_order=10)
    strategic = _supplierperf_make_kpi(tenant_a, applies_to="tier",
                                       applies_to_tier="strategic", display_order=20)
    _supplierperf_make_kpi(tenant_a, applies_to="tier", applies_to_tier="transactional",
                           display_order=30)
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier_a) == [everyone, strategic]


def test_supplierperf_applicable_kpis_gives_an_unprofiled_supplier_only_the_all_kpis(
        tenant_a, supplierperf_supplier2_a):
    """Guessing a tier would measure a supplier against a standard nobody agreed to."""
    everyone = _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_a, applies_to="tier", applies_to_tier="strategic")
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier2_a) == [everyone]


def test_supplierperf_applicable_kpis_never_reaches_into_another_workspace(
        tenant_a, tenant_b, supplierperf_supplier_a):
    mine = _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_b)
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier_a) == [mine]


# =================================================================================================
# performance.survey_aggregate
# =================================================================================================

def test_supplierperf_survey_aggregate_is_none_with_nothing_to_average(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    """Never a phantom zero - no responses is a gap in OUR data, not a bad supplier."""
    start, end = (supplierperf_scorecard_draft_a.period_start,
                  supplierperf_scorecard_draft_a.period_end)
    value, count, breakdown = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a, start, end)
    assert value is None
    assert count == 0
    assert breakdown["respondents"] == 0


def test_supplierperf_survey_aggregate_weights_by_importance(
        tenant_a, admin_user, member_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    """rating 4 -> 75 at weight 8 and rating 2 -> 25 at weight 2 == 65.00."""
    card = supplierperf_scorecard_draft_a
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=admin_user, rating=4, importance=8, status="submitted")
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=member_user, rating=2, importance=2, status="submitted")
    value, count, breakdown = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        card.period_start, card.period_end)
    assert value == Decimal("65.00")
    assert count == 2
    assert breakdown["weight_total"] == 10


def test_supplierperf_survey_aggregate_counts_a_zero_weight_respondent(
        tenant_a, admin_user, member_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    """"Eight people answered, six moved the number" has to be sayable honestly."""
    card = supplierperf_scorecard_draft_a
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=admin_user, rating=4, importance=8, status="submitted")
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=member_user, rating=1, importance=0, status="submitted")
    value, count, breakdown = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        card.period_start, card.period_end)
    assert value == Decimal("75.00")
    assert count == 2
    assert breakdown["weighted_respondents"] == 2
    assert breakdown["weight_total"] == 8


def test_supplierperf_survey_aggregate_refuses_to_invent_a_weighting(
        tenant_a, admin_user, member_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    """Everybody at importance 0: there is no weighted mean, and an unweighted one is a fiction."""
    card = supplierperf_scorecard_draft_a
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=admin_user, rating=4, importance=0, status="submitted")
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=member_user, rating=2, importance=0, status="submitted")
    value, count, breakdown = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        card.period_start, card.period_end)
    assert value is None
    assert count == 2
    assert "importance 0" in breakdown["note"]


def test_supplierperf_survey_aggregate_reads_only_submitted_internal_responses(
        tenant_a, admin_user, member_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a, supplierperf_feedback_self_a):
    """A supplier's own self-assessment sits BESIDE our score, never folded into it."""
    card = supplierperf_scorecard_draft_a
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=admin_user, rating=4, importance=5, status="submitted")
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=member_user, rating=1, importance=5, status="declined")
    value, count, _ = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        card.period_start, card.period_end)
    assert value == Decimal("75.00")
    assert count == 1


def test_supplierperf_survey_aggregate_ignores_responses_outside_the_window(
        tenant_a, admin_user, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a):
    card = supplierperf_scorecard_draft_a
    old = card.period_start - datetime.timedelta(days=10)
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=supplierperf_kpi_survey_a,
                           respondent=admin_user, rating=5, importance=5, status="submitted",
                           period_start=old - datetime.timedelta(days=30), period_end=old)
    value, count, _ = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        card.period_start, card.period_end)
    assert value is None and count == 0


# =================================================================================================
# performance.generate_scorecard_lines - the heart of the sub-module
# =================================================================================================

def test_supplierperf_generate_writes_one_line_per_applicable_kpi(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    first = _supplierperf_make_kpi(tenant_a, display_order=10)
    second = _supplierperf_make_kpi(tenant_a, display_order=20, source="derived",
                                    derived_metric="otd", scoring_method="linear")
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    assert result["refused"] is False
    assert result["written"] == 2
    lines = SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a)
    assert set(lines.values_list("kpi_id", flat=True)) == {first.pk, second.pk}
    assert all(line.tenant_id == tenant_a.pk for line in lines)
    assert all(line.computed_by_id == admin_user.pk for line in lines)


def test_supplierperf_generate_is_idempotent(tenant_a, admin_user,
                                             supplierperf_scorecard_draft_a):
    """Pressing it twice REFRESHES each line in place - ``unique_together`` is the safety."""
    _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_a, display_order=20)
    first = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    ids_after_first = set(SupplierKpiScore.objects
                          .filter(scorecard=supplierperf_scorecard_draft_a)
                          .values_list("pk", flat=True))
    stamp = SupplierKpiScore.objects.filter(
        scorecard=supplierperf_scorecard_draft_a).first().computed_at

    second = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    lines = SupplierKpiScore.objects.filter(scorecard=supplierperf_scorecard_draft_a)
    assert first["written"] == second["written"] == 2
    assert lines.count() == 2
    assert set(lines.values_list("pk", flat=True)) == ids_after_first
    assert lines.first().computed_at >= stamp


def test_supplierperf_generate_refuses_a_published_scorecard(
        tenant_a, admin_user, supplierperf_scorecard_published_a):
    """A closed period must never be silently rewritten under somebody who has acted on it."""
    _supplierperf_make_kpi(tenant_a)
    result = performance.generate_scorecard_lines(supplierperf_scorecard_published_a, admin_user)
    supplierperf_scorecard_published_a.refresh_from_db()
    assert result["refused"] is True
    assert result["written"] == 0
    assert "closed" in result["refusal_reason"]
    assert SupplierKpiScore.objects.count() == 0
    assert supplierperf_scorecard_published_a.manual_override is False


def test_supplierperf_generate_refuses_an_archived_scorecard(
        tenant_a, admin_user, supplierperf_scorecard_archived_a):
    _supplierperf_make_kpi(tenant_a)
    result = performance.generate_scorecard_lines(supplierperf_scorecard_archived_a, admin_user)
    supplierperf_scorecard_archived_a.refresh_from_db()
    assert result["refused"] is True
    assert SupplierKpiScore.objects.count() == 0
    assert supplierperf_scorecard_archived_a.manual_override is False


def test_supplierperf_generate_rereads_the_status_it_was_handed(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """The caller's instance is a SNAPSHOT - a card published since must still be refused."""
    _supplierperf_make_kpi(tenant_a)
    stale = supplierperf_scorecard_draft_a
    type(stale).objects.filter(pk=stale.pk).update(status="published")
    assert stale.status == "draft"                      # the in-memory snapshot is still stale
    result = performance.generate_scorecard_lines(stale, admin_user)
    assert result["refused"] is True
    assert SupplierKpiScore.objects.count() == 0


def test_supplierperf_generate_refuses_an_empty_run_and_leaves_manual_override_alone(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """C2 REGRESSION. A one-way door fired on a no-op: with no applicable KPI, generate used to
    set ``manual_override``, which stops ``recompute_from_signals()`` for good - destroying a
    derivable score AND reporting success. Refusing must write NOTHING."""
    assert SupplierKpi.objects.filter(tenant=tenant_a).count() == 0
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    supplierperf_scorecard_draft_a.refresh_from_db()
    assert result["refused"] is True
    assert result["written"] == 0
    assert result["dimensions"] == {}
    assert result["alerts"] == 0
    assert "nothing to generate" in result["refusal_reason"]
    assert supplierperf_scorecard_draft_a.manual_override is False
    assert supplierperf_scorecard_draft_a.overall_score is None
    assert SupplierKpiScore.objects.count() == 0


def test_supplierperf_generate_refuses_when_every_kpi_is_retired(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """Reachable path 1 of the C2 regression: a library mid-retune."""
    _supplierperf_make_kpi(tenant_a, is_active=False)
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    supplierperf_scorecard_draft_a.refresh_from_db()
    assert result["refused"] is True
    assert supplierperf_scorecard_draft_a.manual_override is False
    assert SupplierKpiScore.objects.count() == 0


def test_supplierperf_generate_refuses_a_tier_only_library_for_an_unprofiled_supplier(
        tenant_a, admin_user, supplierperf_supplier2_a):
    """Reachable path 2 of the C2 regression: tier-scoped KPIs and no ``scm.SupplierProfile``."""
    card = _supplierperf_card(tenant_a, supplierperf_supplier2_a)
    _supplierperf_make_kpi(tenant_a, applies_to="tier", applies_to_tier="strategic")
    result = performance.generate_scorecard_lines(card, admin_user)
    card.refresh_from_db()
    assert result["refused"] is True
    assert card.manual_override is False
    assert SupplierKpiScore.objects.count() == 0


def test_supplierperf_generate_does_not_destroy_a_signal_derived_score_on_an_empty_run(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """The C2 damage, stated as the user saw it: a card grading B/78.00 stayed scoreable."""
    card = supplierperf_scorecard_draft_a
    card.delivery_score = Decimal("78.00")
    card.save(update_fields=["delivery_score"])
    card.recompute_overall()
    card.refresh_from_db()
    graded_before = (card.overall_score, card.grade)

    performance.generate_scorecard_lines(card, admin_user)
    card.refresh_from_db()
    assert (card.overall_score, card.grade) == graded_before
    assert card.manual_override is False
    card.recompute_from_signals(save=False)             # the SCM engine is still allowed in


def test_supplierperf_generate_freezes_the_definition_onto_every_line(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """Re-tune a KPI afterwards and a closed period still reads exactly as it was shown."""
    kpi = _supplierperf_make_kpi(tenant_a, name="On-time delivery", category="delivery",
                                 unit="pct", weight=20, target_value=Decimal("95"),
                                 direction="higher_is_better", source="manual")
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    line = SupplierKpiScore.objects.get(scorecard=supplierperf_scorecard_draft_a, kpi=kpi)
    assert line.weight_applied == 20
    assert line.target_at_time == Decimal("95.0000")
    assert line.direction_at_time == "higher_is_better"
    assert line.source_at_time == "manual"
    assert line.unit_at_time == "pct"
    assert line.kpi_name == "On-time delivery"
    assert line.kpi_category == "delivery"

    kpi.weight = 55
    kpi.target_value = Decimal("70")
    kpi.direction = "lower_is_better"
    kpi.source = "survey"
    kpi.unit = "days"
    kpi.name = "Renamed after the period closed"
    kpi.category = "quality"
    kpi.save()

    line.refresh_from_db()
    assert line.weight_applied == 20
    assert line.target_at_time == Decimal("95.0000")
    assert line.direction_at_time == "higher_is_better"
    assert line.source_at_time == "manual"
    assert line.unit_at_time == "pct"
    assert line.kpi_name == "On-time delivery"
    assert line.kpi_category == "delivery"


def test_supplierperf_generate_leaves_a_kpi_with_no_data_unmeasured(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """A phantom zero would silently tank a supplier for a gap in OUR data."""
    kpi = _supplierperf_make_kpi(tenant_a, source="derived", derived_metric="otd",
                                 scoring_method="linear")
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    line = SupplierKpiScore.objects.get(scorecard=supplierperf_scorecard_draft_a, kpi=kpi)
    assert line.measured_value is None
    assert line.measured_value != Decimal("0")
    assert line.score is None
    assert line.band == "unknown"
    assert result["skipped"] == 1


def test_supplierperf_generate_never_overwrites_a_hand_entered_figure(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """The manual figure is a human's - a re-run must carry it forward, not blank it."""
    kpi = _supplierperf_make_kpi(tenant_a, source="manual")
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    line = SupplierKpiScore.objects.get(scorecard=supplierperf_scorecard_draft_a, kpi=kpi)
    assert line.measured_value is None

    line.measured_value = Decimal("93.0000")
    line.save(update_fields=["measured_value"])
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    line.refresh_from_db()
    assert line.measured_value == Decimal("93.0000")
    assert line.band == "ok"
    assert line.score == Decimal("100.00")


def test_supplierperf_generate_writes_the_mapped_dimension_and_takes_the_card_over(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a, source="manual", maps_to_dimension="delivery")
    _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                       measured_value=Decimal("93.0000"), score=None, band="unknown")
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    supplierperf_scorecard_draft_a.refresh_from_db()
    assert result["dimensions"]["delivery"] == Decimal("100.00")
    assert supplierperf_scorecard_draft_a.delivery_score == Decimal("100.00")
    assert supplierperf_scorecard_draft_a.manual_override is True
    assert supplierperf_scorecard_draft_a.overall_score == Decimal("100.00")


def test_supplierperf_generate_blends_two_kpis_by_their_frozen_weight(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """(100 x 30 + 30 x 10) / 40 = 82.50."""
    high = _supplierperf_make_kpi(tenant_a, weight=30, maps_to_dimension="quality",
                                  display_order=10)
    low = _supplierperf_make_kpi(tenant_a, weight=10, maps_to_dimension="quality",
                                 display_order=20)
    _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, high,
                       measured_value=Decimal("99.0000"), score=None)
    _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, low,
                       measured_value=Decimal("10.0000"), score=None)
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    assert result["dimensions"]["quality"] == Decimal("82.50")


def test_supplierperf_generate_leaves_an_unscored_dimension_untouched(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """Never overwritten with a phantom zero - the same rule recompute_from_signals follows."""
    card = supplierperf_scorecard_draft_a
    card.quality_score = Decimal("64.00")
    card.save(update_fields=["quality_score"])
    _supplierperf_make_kpi(tenant_a, source="derived", derived_metric="otd",
                           maps_to_dimension="quality", scoring_method="linear")
    result = performance.generate_scorecard_lines(card, admin_user)
    card.refresh_from_db()
    assert result["dimensions"]["quality"] is None
    assert card.quality_score == Decimal("64.00")


def test_supplierperf_generate_aggregates_a_survey_kpi_onto_its_line(
        tenant_a, admin_user, member_user, supplierperf_supplier_a,
        supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a, source="survey", scoring_method="direct",
                                 unit="score", target_value=Decimal("80"),
                                 warning_threshold=Decimal("65"),
                                 critical_threshold=Decimal("50"))
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=kpi, respondent=admin_user,
                           rating=4, importance=8, status="submitted")
    _supplierperf_response(tenant_a, supplierperf_supplier_a, kpi=kpi, respondent=member_user,
                           rating=2, importance=2, status="submitted")
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    line = SupplierKpiScore.objects.get(scorecard=supplierperf_scorecard_draft_a, kpi=kpi)
    assert line.measured_value == Decimal("65.0000")
    assert line.score == Decimal("65.00")
    assert line.band == "ok"
    assert line.respondent_count == 2
    assert line.source_at_time == "survey"


def test_supplierperf_generate_ignores_a_retired_kpi(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    live = _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_a, is_active=False)
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    assert result["written"] == 1
    assert list(SupplierKpiScore.objects.values_list("kpi_id", flat=True)) == [live.pk]


def test_supplierperf_generate_never_reaches_into_another_workspace(
        tenant_a, tenant_b, admin_user, supplierperf_scorecard_draft_a):
    mine = _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_b)
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    lines = SupplierKpiScore.objects.all()
    assert [line.kpi_id for line in lines] == [mine.pk]
    assert {line.tenant_id for line in lines} == {tenant_a.pk}


def test_supplierperf_generate_raises_one_alert_per_new_critical_crossing(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """Assigned to the KPI's owner, and never re-raised for a band that was already critical."""
    kpi = _supplierperf_make_kpi(tenant_a, source="manual", owner=admin_user)
    _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                       measured_value=Decimal("40.0000"), score=None, band="unknown")
    first = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    assert first["alerts"] == 1
    alert = ProcurementAlert.objects.get()
    assert alert.tenant_id == tenant_a.pk
    assert alert.kind == "task" and alert.severity == "critical"
    assert alert.assigned_to_id == admin_user.pk
    assert alert.link_url.startswith("/")

    second = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    assert second["alerts"] == 0
    assert ProcurementAlert.objects.count() == 1


def test_supplierperf_generate_writes_an_auditable_breakdown_on_every_line(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """``breakdown`` is JSON with the DEFAULT encoder - a raw Decimal in it would 500 the run."""
    import json
    _supplierperf_make_kpi(tenant_a, source="derived", derived_metric="otd",
                           scoring_method="linear")
    _supplierperf_make_kpi(tenant_a, source="manual", display_order=20)
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    for line in SupplierKpiScore.objects.all():
        assert isinstance(line.breakdown, dict) and line.breakdown
        json.dumps(line.breakdown)


def test_supplierperf_generate_keeps_its_query_count_flat(
        tenant_a, admin_user, supplierperf_scorecard_draft_a, django_assert_max_num_queries):
    """Two write round-trips for the WHOLE run, not four per line."""
    for index in range(8):
        _supplierperf_make_kpi(tenant_a, display_order=10 + index)
    with django_assert_max_num_queries(14):
        performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    assert SupplierKpiScore.objects.count() == 8


def test_supplierperf_generate_tolerates_an_anonymous_caller(
        tenant_a, supplierperf_scorecard_draft_a):
    from django.contrib.auth.models import AnonymousUser
    _supplierperf_make_kpi(tenant_a)
    result = performance.generate_scorecard_lines(supplierperf_scorecard_draft_a,
                                                  AnonymousUser())
    assert result["refused"] is False
    assert SupplierKpiScore.objects.get().computed_by_id is None


def test_supplierperf_generate_refuses_a_scorecard_that_no_longer_exists(
        tenant_a, admin_user, supplierperf_supplier_a):
    card = _supplierperf_card(tenant_a, supplierperf_supplier_a)
    _supplierperf_make_kpi(tenant_a)
    type(card).objects.filter(pk=card.pk).delete()
    result = performance.generate_scorecard_lines(card, admin_user)
    assert result["refused"] is True
    assert "no longer exists" in result["refusal_reason"]
    assert SupplierKpiScore.objects.count() == 0


def test_supplierperf_generate_bands_through_the_one_scale(
        tenant_a, admin_user, supplierperf_scorecard_draft_a):
    """Whatever the line says, ``kpi.score_and_band(measured)`` must say the same."""
    kpi = _supplierperf_make_kpi(tenant_a, source="manual")
    _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                       measured_value=Decimal("87.0000"), score=None, band="unknown")
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    line = SupplierKpiScore.objects.get(kpi=kpi)
    assert (line.score, line.band) == kpi.score_and_band(line.measured_value)


# =================================================================================================
# Cross-model tenant isolation
# =================================================================================================

def test_supplierperf_two_tenants_generate_side_by_side_without_touching_each_other(
        tenant_a, tenant_b, admin_user, admin_b, supplierperf_scorecard_draft_a,
        supplierperf_scorecard_b):
    _supplierperf_make_kpi(tenant_a)
    _supplierperf_make_kpi(tenant_b)
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    performance.generate_scorecard_lines(supplierperf_scorecard_b, admin_b)
    assert SupplierKpiScore.objects.filter(tenant=tenant_a).count() == 1
    assert SupplierKpiScore.objects.filter(tenant=tenant_b).count() == 1
    assert (SupplierKpiScore.objects.filter(tenant=tenant_a)
            .filter(scorecard=supplierperf_scorecard_b).count() == 0)


def test_supplierperf_a_tenants_registers_never_contain_the_others_rows(
        tenant_a, tenant_b, supplierperf_kpi_manual_a, supplierperf_kpi_b,
        supplierperf_feedback_submitted_a, supplierperf_feedback_b,
        supplierperf_plan_draft_a, supplierperf_plan_b, supplierperf_score_manual_a,
        supplierperf_score_b):
    for model in (SupplierKpi, SupplierKpiScore, SupplierFeedback, SupplierImprovementPlan):
        mine = set(model.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
        theirs = set(model.objects.filter(tenant=tenant_b).values_list("pk", flat=True))
        assert mine and theirs
        assert not (mine & theirs), model.__name__


# =================================================================================================
# The shared conftest's 6.16 fixture contract
#
# The forms, views and security lanes build on these rows. A fixture that silently drifts - or one
# that would fail ``full_clean()`` - breaks THEIR edit tests, not this file's, and the failure
# surfaces three lanes away from its cause. Every 6.16 fixture is therefore driven at least once
# here, and every one that a form will later re-validate is put through ``full_clean()``.
# =================================================================================================

def test_supplierperf_fixture_kpi_library_all_validate(
        supplierperf_kpi_manual_a, supplierperf_kpi_derived_a, supplierperf_kpi_survey_a,
        supplierperf_kpi_tier_a, supplierperf_kpi_inactive_a, supplierperf_kpi_b):
    """Every seeded KPI is a definition a form could legitimately have produced."""
    for kpi in (supplierperf_kpi_manual_a, supplierperf_kpi_derived_a, supplierperf_kpi_survey_a,
                supplierperf_kpi_tier_a, supplierperf_kpi_inactive_a, supplierperf_kpi_b):
        kpi.full_clean()
        assert kpi.number.startswith("SKP-")


def test_supplierperf_fixture_kpi_sources_span_all_three(
        supplierperf_kpi_manual_a, supplierperf_kpi_derived_a, supplierperf_kpi_survey_a):
    assert supplierperf_kpi_manual_a.source == "manual"
    assert supplierperf_kpi_derived_a.source == "derived"
    assert supplierperf_kpi_derived_a.derived_metric in performance.DERIVED_RESOLVERS
    assert supplierperf_kpi_survey_a.source == "survey"


def test_supplierperf_fixture_kpi_tier_only_applies_with_a_profile(
        tenant_a, supplierperf_kpi_tier_a, supplierperf_supplier_a, supplierperf_supplier2_a):
    """The tier KPI is invisible until ``supplierperf_profile_a`` is requested."""
    assert supplierperf_kpi_tier_a.applies_to == "tier"
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier_a) == []
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier2_a) == []


def test_supplierperf_fixture_profile_turns_the_tier_kpi_on(
        tenant_a, supplierperf_profile_a, supplierperf_kpi_tier_a, supplierperf_supplier_a):
    assert supplierperf_profile_a.tier == "strategic"
    assert performance.applicable_kpis(tenant_a,
                                       supplierperf_supplier_a) == [supplierperf_kpi_tier_a]


def test_supplierperf_fixture_kpi_inactive_is_retired_not_deleted(
        tenant_a, supplierperf_kpi_inactive_a, supplierperf_supplier_a):
    assert supplierperf_kpi_inactive_a.is_active is False
    assert supplierperf_kpi_inactive_a.pk is not None
    assert performance.applicable_kpis(tenant_a, supplierperf_supplier_a) == []


def test_supplierperf_fixture_scorecards_are_the_three_statuses(
        supplierperf_scorecard_draft_a, supplierperf_scorecard_published_a,
        supplierperf_scorecard_archived_a, supplierperf_scorecard_b):
    assert supplierperf_scorecard_draft_a.status == "draft"
    assert supplierperf_scorecard_published_a.status == "published"
    assert supplierperf_scorecard_archived_a.status == "archived"
    assert supplierperf_scorecard_b.status == "draft"
    for card in (supplierperf_scorecard_draft_a, supplierperf_scorecard_published_a,
                 supplierperf_scorecard_archived_a, supplierperf_scorecard_b):
        assert card.manual_override is False
        assert card.period_start <= card.period_end


def test_supplierperf_fixture_score_manual_is_the_editable_row(supplierperf_score_manual_a):
    """The edit view's gate is ``source_at_time == "manual"``."""
    assert supplierperf_score_manual_a.source_at_time == "manual"
    assert supplierperf_score_manual_a.weight_applied > 0
    assert supplierperf_score_manual_a.kpi_name
    assert supplierperf_score_manual_a.band_css == "badge-amber"
    supplierperf_score_manual_a.full_clean()


def test_supplierperf_fixture_score_derived_is_the_refusal_row(supplierperf_score_derived_a):
    assert supplierperf_score_derived_a.source_at_time == "derived"
    assert supplierperf_score_derived_a.breakdown["metric"] == "otd"
    supplierperf_score_derived_a.full_clean()


def test_supplierperf_fixture_score_b_belongs_to_the_other_workspace(
        tenant_b, supplierperf_score_b):
    assert supplierperf_score_b.tenant_id == tenant_b.pk
    assert supplierperf_score_b.scorecard.tenant_id == tenant_b.pk
    assert supplierperf_score_b.kpi.tenant_id == tenant_b.pk


def test_supplierperf_fixture_feedback_rows_are_four_distinct_natural_keys(
        supplierperf_feedback_requested_a, supplierperf_feedback_submitted_a,
        supplierperf_feedback_self_a, supplierperf_feedback_overdue_a):
    """All four coexist under the one-response-per-respondent rule, which is what lets a lane
    request every one of them in a single test without a spurious ValidationError."""
    rows = (supplierperf_feedback_requested_a, supplierperf_feedback_submitted_a,
            supplierperf_feedback_self_a, supplierperf_feedback_overdue_a)
    keys = {(r.supplier_id, r.scorecard_id, r.kpi_id, r.respondent_id) for r in rows}
    assert len(keys) == 4
    for row in rows:
        row.full_clean()
        assert row.number.startswith("SFB-")


def test_supplierperf_fixture_feedback_requested_is_open_and_not_yet_due(
        supplierperf_feedback_requested_a):
    assert supplierperf_feedback_requested_a.status == "requested"
    assert supplierperf_feedback_requested_a.rating is None
    assert supplierperf_feedback_requested_a.is_overdue is False
    assert supplierperf_feedback_requested_a.status_css == "badge-amber"


def test_supplierperf_fixture_feedback_submitted_is_what_the_aggregate_counts(
        tenant_a, supplierperf_feedback_submitted_a, supplierperf_supplier_a,
        supplierperf_kpi_survey_a, supplierperf_scorecard_draft_a):
    assert supplierperf_feedback_submitted_a.respondent_kind == "internal"
    assert supplierperf_feedback_submitted_a.status == "submitted"
    assert supplierperf_feedback_submitted_a.score_value() == Decimal("75")
    value, count, _ = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a.period_start,
        supplierperf_scorecard_draft_a.period_end)
    assert (value, count) == (Decimal("75.00"), 1)


def test_supplierperf_fixture_feedback_self_is_never_folded_into_our_score(
        tenant_a, supplierperf_feedback_self_a, supplierperf_supplier_a,
        supplierperf_kpi_survey_a, supplierperf_scorecard_draft_a):
    assert supplierperf_feedback_self_a.respondent_kind == "supplier_self"
    assert supplierperf_feedback_self_a.respondent_id is None
    assert supplierperf_feedback_self_a.respondent_name
    value, count, _ = performance.survey_aggregate(
        tenant_a, supplierperf_supplier_a, supplierperf_kpi_survey_a,
        supplierperf_scorecard_draft_a.period_start,
        supplierperf_scorecard_draft_a.period_end)
    assert value is None and count == 0


def test_supplierperf_fixture_feedback_overdue_is_the_ad_hoc_null_key_row(
        supplierperf_feedback_overdue_a):
    assert supplierperf_feedback_overdue_a.scorecard_id is None
    assert supplierperf_feedback_overdue_a.kpi_id is None
    assert supplierperf_feedback_overdue_a.respondent_id is None
    assert supplierperf_feedback_overdue_a.is_overdue is True


def test_supplierperf_fixture_feedback_b_belongs_to_the_other_workspace(
        tenant_b, supplierperf_feedback_b):
    assert supplierperf_feedback_b.tenant_id == tenant_b.pk
    assert supplierperf_feedback_b.supplier.tenant_id == tenant_b.pk
    supplierperf_feedback_b.full_clean()


def test_supplierperf_fixture_plans_all_validate(
        supplierperf_plan_draft_a, supplierperf_plan_overdue_a, supplierperf_plan_closed_a,
        supplierperf_plan_b):
    for plan in (supplierperf_plan_draft_a, supplierperf_plan_overdue_a,
                 supplierperf_plan_closed_a, supplierperf_plan_b):
        plan.full_clean()
        assert plan.number.startswith("SIP-")


def test_supplierperf_fixture_plan_draft_is_the_editable_one(supplierperf_plan_draft_a):
    assert supplierperf_plan_draft_a.status == "draft"
    assert supplierperf_plan_draft_a.outcome == ""
    assert supplierperf_plan_draft_a.is_overdue is False
    assert supplierperf_plan_draft_a.has_evidence is False


def test_supplierperf_fixture_plan_overdue_is_open_and_late(supplierperf_plan_overdue_a):
    assert supplierperf_plan_overdue_a.status == "active"
    assert supplierperf_plan_overdue_a.is_overdue is True
    assert supplierperf_plan_overdue_a.severity_css == "badge-red"


def test_supplierperf_fixture_plan_closed_records_its_outcome(supplierperf_plan_closed_a):
    assert supplierperf_plan_closed_a.status == "closed"
    assert supplierperf_plan_closed_a.outcome == "successful"
    assert supplierperf_plan_closed_a.actual_close_date is not None
    assert supplierperf_plan_closed_a.is_overdue is False
    assert supplierperf_plan_closed_a.has_evidence is True


def test_supplierperf_fixture_suspension_is_the_escalation_target(
        tenant_a, supplierperf_suspension_a, supplierperf_supplier_a):
    assert supplierperf_suspension_a.tenant_id == tenant_a.pk
    assert supplierperf_suspension_a.supplier_id == supplierperf_supplier_a.pk
    assert supplierperf_suspension_a.status == "active"
    assert supplierperf_suspension_a.number.startswith("VSU-")


def test_supplierperf_fixture_suppliers_carry_the_role_every_dropdown_filters_on(
        supplierperf_supplier_a, supplierperf_supplier2_a, supplierperf_supplier_b):
    """A Party with no ``PartyRole`` is invisible to every 6.16 supplier queryset."""
    from apps.core.models import Party
    for party in (supplierperf_supplier_a, supplierperf_supplier2_a, supplierperf_supplier_b):
        assert Party.objects.filter(pk=party.pk,
                                    roles__role__in=("supplier", "vendor")).exists()


# =================================================================================================
# performance.DERIVED_RESOLVERS - the fourteen
#
# Uniform signature ``(tenant, party, start, end) -> (Decimal | None, dict)``. The rule every one
# of them keeps is the one generate depends on: an EMPTY denominator answers ``None``, never 0.
# A phantom zero is a claim about the supplier where the truth is a gap in OUR data, and it would
# tank a composite that nothing measured.
#
# The spine each resolver reads is minted here rather than in the shared conftest - these rows
# exist to pin one ratio each, and a fixture shared with three other lanes would drift the moment
# one of them needed a different denominator.
# =================================================================================================

def _supplierperf_window():
    """The window every resolver test measures over - the same 90 days a scorecard covers."""
    end = _supplierperf_today()
    return end - datetime.timedelta(days=89), end


def _supplierperf_po(tenant, vendor, **overrides):
    from apps.scm.models import PurchaseOrder
    end = _supplierperf_today()
    fields = dict(tenant=tenant, vendor=vendor, status="approved",
                  order_date=end - datetime.timedelta(days=30),
                  expected_date=end - datetime.timedelta(days=10))
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _supplierperf_po_line(po, quantity=Decimal("10"), unit_price=Decimal("25.00")):
    from apps.scm.models import PurchaseOrderLine
    return PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Bearing housing 40mm", quantity=quantity,
        unit_price=unit_price, sku_hint="BRG-40", uom_hint="EA")


def _supplierperf_grn(tenant, po, days_ago=10, **overrides):
    """A BOOKED receipt - ``_received_notes`` counts ``status="received"`` and nothing else."""
    from apps.scm.models import GoodsReceiptNote
    fields = dict(tenant=tenant, purchase_order=po, status="received",
                  receipt_date=_supplierperf_today() - datetime.timedelta(days=days_ago))
    fields.update(overrides)
    return GoodsReceiptNote.objects.create(**fields)


def _supplierperf_grn_line(grn, po_line, received="10", rejected="0"):
    from apps.scm.models import GoodsReceiptLine
    return GoodsReceiptLine.objects.create(
        goods_receipt=grn, po_line=po_line, quantity_received=Decimal(received),
        quantity_rejected=Decimal(rejected))


def _supplierperf_invoice(tenant, vendor, number, **overrides):
    from apps.procurement.models import SupplierInvoice
    fields = dict(tenant=tenant, vendor=vendor, invoice_number=number,
                  invoice_date=_supplierperf_today() - datetime.timedelta(days=20),
                  match_status="not_run")
    fields.update(overrides)
    return SupplierInvoice.objects.create(**fields)


def _supplierperf_dispute(tenant, invoice, supplier, raised_at=None, resolved_at=None,
                          **overrides):
    """One invoice dispute, optionally BACK-DATED.

    ``InvoiceDispute.raised_at`` is ``auto_now_add`` (``InvoiceDisputes.py:158``), so passing it
    to ``create()`` is silently ignored - the column is stamped at INSERT. Back-dating therefore
    goes through a queryset ``.update()``, which does not run ``pre_save`` and is the only way to
    place a dispute anywhere but "now". Left alone, ``raised_at`` is today, which is inside every
    window these tests measure over.
    """
    from apps.procurement.models import InvoiceDispute
    fields = dict(tenant=tenant, invoice=invoice, supplier=supplier, reason_code="price",
                  description="Unit price above the agreed schedule.")
    fields.update(overrides)
    dispute = InvoiceDispute.objects.create(**fields)
    stamps = {}
    if raised_at is not None:
        stamps["raised_at"] = raised_at
    if resolved_at is not None:
        stamps["resolved_at"] = resolved_at
    if stamps:
        InvoiceDispute.objects.filter(pk=dispute.pk).update(**stamps)
        dispute.refresh_from_db()
    return dispute


def _supplierperf_rfq(tenant, issued_days_ago=20, **overrides):
    from apps.scm.models import RFQ
    fields = dict(tenant=tenant, title="Bearings restock",
                  issue_date=_supplierperf_today()
                  - datetime.timedelta(days=issued_days_ago))
    fields.update(overrides)
    return RFQ.objects.create(**fields)


def _supplierperf_quote(tenant, rfq, party, total, received_days_ago=17):
    from apps.scm.models import RFQQuote
    return RFQQuote.objects.create(
        tenant=tenant, rfq=rfq, party=party, total=Decimal(total),
        received_date=_supplierperf_today() - datetime.timedelta(days=received_days_ago))


@pytest.mark.parametrize("metric", sorted(performance.DERIVED_RESOLVERS))
def test_supplierperf_every_derived_resolver_answers_none_without_data(
        metric, tenant_a, supplierperf_supplier_a):
    """No data is NOT a zero. Every one of the fourteen has to say so."""
    start, end = _supplierperf_window()
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a, metric,
                                                   start, end)
    assert value is None, metric
    assert breakdown["metric"] == metric
    assert breakdown["window"] == [str(start), str(end)]
    assert breakdown["rows"] == 0


def test_supplierperf_resolve_derived_survives_an_unknown_metric_key(
        tenant_a, supplierperf_supplier_a):
    """A definition problem must not take a whole generate run down with it."""
    start, end = _supplierperf_window()
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "not_a_metric", start, end)
    assert value is None
    assert breakdown["error"] == "no resolver"


def test_supplierperf_resolver_otd_counts_only_datable_receipts(
        tenant_a, supplierperf_supplier_a):
    """One on time, one late, and one whose PO carries no expected date (excluded both sides)."""
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    _supplierperf_grn(tenant_a, po, days_ago=12)                      # on time
    _supplierperf_grn(tenant_a, po, days_ago=4)                       # late
    undated = _supplierperf_po(tenant_a, supplierperf_supplier_a, expected_date=None)
    _supplierperf_grn(tenant_a, undated, days_ago=3)
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "otd",
                                                   start, end)
    assert value == Decimal("50.00")
    assert breakdown["datable_receipts"] == 2
    assert breakdown["on_time"] == 1


def test_supplierperf_resolver_otd_ignores_an_unbooked_receipt(
        tenant_a, supplierperf_supplier_a):
    """A draft receipt has not been booked - it says nothing about the supplier yet."""
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    _supplierperf_grn(tenant_a, po, days_ago=12, status="draft")
    value, _ = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "otd", start, end)
    assert value is None


def test_supplierperf_resolver_otif_needs_the_lines_to_add_up(
        tenant_a, supplierperf_supplier_a):
    """On time AND in full - an on-time receipt that arrived short is not OTIF."""
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    line = _supplierperf_po_line(po, quantity=Decimal("10"))
    full = _supplierperf_grn(tenant_a, po, days_ago=12)
    _supplierperf_grn_line(full, line, received="10")
    short = _supplierperf_grn(tenant_a, po, days_ago=11)
    _supplierperf_grn_line(short, line, received="4")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "otif",
                                                   start, end)
    assert value == Decimal("50.00")
    assert breakdown["in_full"] == 1
    assert breakdown["short_receipts"] == 1


def test_supplierperf_resolver_otif_refuses_to_call_a_lineless_receipt_full(
        tenant_a, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    _supplierperf_po_line(po)
    _supplierperf_grn(tenant_a, po, days_ago=12)                      # on time, NO lines
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "otif",
                                                   start, end)
    assert value == Decimal("0.00")
    assert breakdown["on_time"] == 1 and breakdown["in_full"] == 0


def test_supplierperf_resolver_defect_rate_is_rejected_over_inspected(
        tenant_a, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    line = _supplierperf_po_line(po)
    grn = _supplierperf_grn(tenant_a, po)
    _supplierperf_grn_line(grn, line, received="90", rejected="10")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "defect_rate", start, end)
    assert value == Decimal("10.00")
    assert Decimal(breakdown["inspected"]) == Decimal("100")
    assert Decimal(breakdown["rejected"]) == Decimal("10")


def test_supplierperf_resolver_defect_rate_is_none_when_nothing_was_inspected(
        tenant_a, supplierperf_supplier_a):
    """A receipt line of zero is not a clean one - there was nothing to reject."""
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    line = _supplierperf_po_line(po)
    grn = _supplierperf_grn(tenant_a, po)
    _supplierperf_grn_line(grn, line, received="0", rejected="0")
    value, _ = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "defect_rate",
                                           start, end)
    assert value is None


def test_supplierperf_resolver_ncr_rate_is_discrepancies_over_receipts(
        tenant_a, supplierperf_supplier_a):
    from apps.procurement.models import ReceiptDiscrepancy
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    flagged = _supplierperf_grn(tenant_a, po, days_ago=12)
    _supplierperf_grn(tenant_a, po, days_ago=11)
    ReceiptDiscrepancy.objects.create(
        tenant=tenant_a, goods_receipt=flagged, kind="short_shipment",
        description="Three cartons short on the pallet.")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "ncr_rate",
                                                   start, end)
    assert value == Decimal("50.00")
    assert (breakdown["discrepancies"], breakdown["receipts"]) == (1, 2)


def test_supplierperf_resolver_rtv_rate_is_returns_over_receipts(
        tenant_a, supplierperf_supplier_a):
    from apps.procurement.models import ReturnToVendor
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    _supplierperf_grn(tenant_a, po, days_ago=12)
    _supplierperf_grn(tenant_a, po, days_ago=11)
    ReturnToVendor.objects.create(tenant=tenant_a, vendor=supplierperf_supplier_a,
                                  reason="damaged", remedy="credit")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "rtv_rate",
                                                   start, end)
    assert value == Decimal("50.00")
    assert (breakdown["returns"], breakdown["receipts"]) == (1, 2)


def test_supplierperf_resolver_invoice_accuracy_excludes_an_unmatched_invoice(
        tenant_a, supplierperf_supplier_a):
    """An invoice whose match never ran says nothing about the supplier's paperwork."""
    start, end = _supplierperf_window()
    _supplierperf_invoice(tenant_a, supplierperf_supplier_a, "SUP-1", match_status="matched")
    _supplierperf_invoice(tenant_a, supplierperf_supplier_a, "SUP-2",
                          match_status="price_variance")
    _supplierperf_invoice(tenant_a, supplierperf_supplier_a, "SUP-3", match_status="not_run")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "invoice_accuracy", start, end)
    assert value == Decimal("50.00")
    assert breakdown["matched_invoices"] == 2


def test_supplierperf_resolver_invoice_accuracy_counts_within_tolerance_as_clean(
        tenant_a, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    _supplierperf_invoice(tenant_a, supplierperf_supplier_a, "SUP-1",
                          match_status="within_tolerance")
    value, _ = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                           "invoice_accuracy", start, end)
    assert value == Decimal("100.00")


def test_supplierperf_resolver_dispute_rate_is_disputes_over_invoices(
        tenant_a, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    first = _supplierperf_invoice(tenant_a, supplierperf_supplier_a, "SUP-1")
    _supplierperf_invoice(tenant_a, supplierperf_supplier_a, "SUP-2")
    _supplierperf_dispute(tenant_a, first, supplierperf_supplier_a)
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "dispute_rate", start, end)
    assert value == Decimal("50.00")
    assert (breakdown["disputes"], breakdown["invoices"]) == (1, 2)


def test_supplierperf_resolver_dispute_days_averages_only_the_closed_ones(
        tenant_a, supplierperf_supplier_a):
    """An unresolved dispute has no resolution time yet - averaging it in would invent one."""
    start, end = _supplierperf_window()
    invoice = _supplierperf_invoice(tenant_a, supplierperf_supplier_a, "SUP-1")
    raised = timezone.now() - datetime.timedelta(days=20)
    _supplierperf_dispute(tenant_a, invoice, supplierperf_supplier_a, raised_at=raised,
                          resolved_at=raised + datetime.timedelta(days=2))
    _supplierperf_dispute(tenant_a, invoice, supplierperf_supplier_a, raised_at=raised,
                          resolved_at=raised + datetime.timedelta(days=4),
                          reason_code="quantity")
    _supplierperf_dispute(tenant_a, invoice, supplierperf_supplier_a, raised_at=raised,
                          reason_code="tax")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "dispute_days", start, end)
    assert value == Decimal("3.00")
    assert breakdown["resolved_disputes"] == 2


def test_supplierperf_resolver_promise_adherence_ignores_an_unpromised_instalment(
        tenant_a, supplierperf_supplier_a):
    from apps.procurement.models import DeliverySchedule
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    line = _supplierperf_po_line(po)
    need_by = _supplierperf_today() - datetime.timedelta(days=15)
    DeliverySchedule.objects.create(                       # promised early - kept
        tenant=tenant_a, po_line=line, sequence=1, scheduled_quantity=Decimal("4"),
        need_by_date=need_by, promised_date=need_by - datetime.timedelta(days=2))
    DeliverySchedule.objects.create(                       # promised late - not kept
        tenant=tenant_a, po_line=line, sequence=2, scheduled_quantity=Decimal("3"),
        need_by_date=need_by, promised_date=need_by + datetime.timedelta(days=5))
    DeliverySchedule.objects.create(                       # never promised - excluded
        tenant=tenant_a, po_line=line, sequence=3, scheduled_quantity=Decimal("3"),
        need_by_date=need_by)
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "promise_adherence", start, end)
    assert value == Decimal("50.00")
    assert (breakdown["kept"], breakdown["promised"]) == (1, 2)


def test_supplierperf_resolver_backorder_rate_is_backorders_over_po_lines(
        tenant_a, supplierperf_supplier_a):
    from apps.procurement.models import Backorder
    start, end = _supplierperf_window()
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    first = _supplierperf_po_line(po)
    _supplierperf_po_line(po, quantity=Decimal("4"), unit_price=Decimal("60.00"))
    Backorder.objects.create(
        tenant=tenant_a, po_line=first, quantity_backordered=Decimal("3"),
        reason="out_of_stock",
        original_promise_date=_supplierperf_today() - datetime.timedelta(days=15))
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "backorder_rate", start, end)
    assert value == Decimal("50.00")
    assert (breakdown["backorders"], breakdown["po_lines"]) == (1, 2)


def test_supplierperf_resolver_po_change_rate_rides_the_order_date_on_both_sides(
        tenant_a, supplierperf_supplier_a):
    from apps.procurement.models import PurchaseOrderChange
    start, end = _supplierperf_window()
    amended = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    _supplierperf_po(tenant_a, supplierperf_supplier_a)
    PurchaseOrderChange.objects.create(tenant=tenant_a, purchase_order=amended,
                                       reason="The vendor moved the dispatch date.")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "po_change_rate", start, end)
    assert value == Decimal("50.00")
    assert (breakdown["changes"], breakdown["purchase_orders"]) == (1, 2)


def test_supplierperf_resolver_price_competitiveness_compares_against_the_best_quote(
        tenant_a, supplierperf_supplier_a, supplierperf_supplier2_a):
    """100% would mean this supplier WAS the cheapest; 80/100 quoted is 80%."""
    start, end = _supplierperf_window()
    rfq = _supplierperf_rfq(tenant_a)
    _supplierperf_quote(tenant_a, rfq, supplierperf_supplier_a, "100.00")
    _supplierperf_quote(tenant_a, rfq, supplierperf_supplier2_a, "80.00")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "price_competitiveness", start, end)
    assert value == Decimal("80.00")
    assert breakdown["compared"] == 1


def test_supplierperf_resolver_price_competitiveness_caps_the_cheapest_at_a_hundred(
        tenant_a, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    rfq = _supplierperf_rfq(tenant_a)
    _supplierperf_quote(tenant_a, rfq, supplierperf_supplier_a, "80.00")
    value, _ = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                           "price_competitiveness", start, end)
    assert value == Decimal("100.00")


def test_supplierperf_resolver_price_competitiveness_is_none_with_nothing_to_compare(
        tenant_a, supplierperf_supplier_a):
    """A zero-total quote is not a free one - there is no ratio to take."""
    start, end = _supplierperf_window()
    rfq = _supplierperf_rfq(tenant_a)
    _supplierperf_quote(tenant_a, rfq, supplierperf_supplier_a, "0.00")
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "price_competitiveness", start, end)
    assert value is None
    assert breakdown["compared"] == 0


def test_supplierperf_resolver_quote_turnaround_measures_from_the_rfq_issue_date(
        tenant_a, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    rfq = _supplierperf_rfq(tenant_a, issued_days_ago=20)
    _supplierperf_quote(tenant_a, rfq, supplierperf_supplier_a, "100.00",
                        received_days_ago=17)
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "quote_turnaround", start, end)
    assert value == Decimal("3.00")
    assert breakdown["quotes"] == 1


def test_supplierperf_resolver_quote_turnaround_excludes_an_unissued_rfq(
        tenant_a, supplierperf_supplier_a):
    """There is nothing to measure the turnaround FROM."""
    start, end = _supplierperf_window()
    rfq = _supplierperf_rfq(tenant_a, issue_date=None)
    _supplierperf_quote(tenant_a, rfq, supplierperf_supplier_a, "100.00")
    value, _ = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                           "quote_turnaround", start, end)
    assert value is None


def test_supplierperf_resolver_suspension_incidents_is_none_without_any_trade(
        tenant_a, supplierperf_supplier_a):
    """A supplier we never bought from has no incident RATE - only a supplier we did can
    honestly score a real zero."""
    start, end = _supplierperf_window()
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "suspension_incidents", start, end)
    assert value is None
    assert breakdown["had_activity"] is False


def test_supplierperf_resolver_suspension_incidents_scores_a_real_zero_after_trade(
        tenant_a, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    _supplierperf_po(tenant_a, supplierperf_supplier_a)
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "suspension_incidents", start, end)
    assert value == Decimal("0.00")
    assert breakdown["had_activity"] is True


def test_supplierperf_resolver_suspension_incidents_counts_blocks_in_force(
        tenant_a, admin_user, supplierperf_supplier_a):
    start, end = _supplierperf_window()
    VendorSuspension.objects.create(
        tenant=tenant_a, supplier=supplierperf_supplier_a, reason="Four late shipments.",
        status="active", starts_on=_supplierperf_today() - datetime.timedelta(days=30),
        requested_by=admin_user)
    VendorSuspension.objects.create(                       # requested, never came into force
        tenant=tenant_a, supplier=supplierperf_supplier_a, reason="Under review.",
        status="requested", starts_on=_supplierperf_today() - datetime.timedelta(days=20),
        requested_by=admin_user)
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a,
                                                   "suspension_incidents", start, end)
    assert value == Decimal("1.00")
    assert breakdown["incidents"] == 1


def test_supplierperf_resolvers_never_read_another_workspaces_spine(
        tenant_a, tenant_b, supplierperf_supplier_a, supplierperf_supplier_b):
    """Tenant B's receipts must not show up in tenant A's on-time delivery figure."""
    start, end = _supplierperf_window()
    theirs = _supplierperf_po(tenant_b, supplierperf_supplier_b)
    _supplierperf_grn(tenant_b, theirs, days_ago=12)
    value, breakdown = performance.resolve_derived(tenant_a, supplierperf_supplier_a, "otd",
                                                   start, end)
    assert value is None
    assert breakdown["datable_receipts"] == 0


def test_supplierperf_generate_writes_a_derived_figure_onto_the_line(
        tenant_a, admin_user, supplierperf_supplier_a, supplierperf_scorecard_draft_a):
    """End to end: a resolver's number reaches the score line, banded by the one scale."""
    po = _supplierperf_po(tenant_a, supplierperf_supplier_a)
    _supplierperf_grn(tenant_a, po, days_ago=12)
    kpi = _supplierperf_make_kpi(tenant_a, source="derived", derived_metric="otd",
                                 scoring_method="linear", target_value=Decimal("95"),
                                 warning_threshold=Decimal("90"),
                                 critical_threshold=Decimal("85"))
    performance.generate_scorecard_lines(supplierperf_scorecard_draft_a, admin_user)
    line = SupplierKpiScore.objects.get(kpi=kpi)
    assert line.measured_value == Decimal("100.0000")
    assert line.band == "ok"
    assert line.score == Decimal("100.00")
    assert line.breakdown["metric"] == "otd"
    assert line.source_at_time == "derived"


# =================================================================================================
# performance - the composite arithmetic the boards publish
#
# These are pure (or near-pure) helpers, so they are pinned HERE rather than through a page: the
# views lane asserts that a board renders them; this lane asserts they are RIGHT. The rule they
# share with SupplierScorecard.recompute_overall() is the one that matters - weights re-weight
# over the lines that actually scored, so a KPI with no data in the period never quietly drags a
# supplier down.
# =================================================================================================

def test_supplierperf_composite_reweights_over_the_lines_that_scored(
        tenant_a, supplierperf_scorecard_draft_a):
    """(100 x 30 + 40 x 10) / 40 = 85.00 - the unscored line drops out of BOTH sides."""
    high = _supplierperf_make_kpi(tenant_a, weight=30, display_order=10)
    low = _supplierperf_make_kpi(tenant_a, weight=10, display_order=20)
    dark = _supplierperf_make_kpi(tenant_a, weight=60, display_order=30)
    lines = [
        _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, high,
                           score=Decimal("100.00"), weight_applied=30),
        _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, low,
                           score=Decimal("40.00"), weight_applied=10),
        _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, dark,
                           score=None, weight_applied=60),
    ]
    assert performance._composite(lines) == Decimal("85.00")


def test_supplierperf_composite_is_none_when_nothing_scored(
        tenant_a, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a)
    line = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi, score=None)
    assert performance._composite([line]) is None
    assert performance._composite([]) is None


def test_supplierperf_composite_from_sums_matches_the_row_wise_arithmetic(
        tenant_a, supplierperf_scorecard_draft_a):
    """The cohort board sums in SQL; the trend board averages fetched rows. Same answer."""
    high = _supplierperf_make_kpi(tenant_a, weight=30, display_order=10)
    low = _supplierperf_make_kpi(tenant_a, weight=10, display_order=20)
    lines = [
        _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, high,
                           score=Decimal("100.00"), weight_applied=30),
        _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, low,
                           score=Decimal("40.00"), weight_applied=10),
    ]
    weighted = sum(line.score * line.weight_applied for line in lines)
    assert (performance._composite_from_sums(weighted, 40)
            == performance._composite(lines) == Decimal("85.00"))


def test_supplierperf_composite_from_sums_is_none_on_an_empty_cohort():
    assert performance._composite_from_sums(None, 0) is None
    assert performance._composite_from_sums(Decimal("100"), 0) is None
    assert performance._composite_from_sums(None, 40) is None


def test_supplierperf_meets_target_reads_the_frozen_direction(
        tenant_a, supplierperf_scorecard_draft_a):
    """Flipping a KPI's direction later must not re-judge a period already closed."""
    kpi = _supplierperf_make_kpi(tenant_a)
    higher = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                                measured_value=Decimal("96"), target_at_time=Decimal("95"),
                                direction_at_time="higher_is_better")
    assert performance.meets_target(higher) is True
    higher.measured_value = Decimal("94")
    assert performance.meets_target(higher) is False
    higher.direction_at_time = "lower_is_better"
    assert performance.meets_target(higher) is True


def test_supplierperf_meets_target_is_true_exactly_on_the_target(
        tenant_a, supplierperf_scorecard_draft_a):
    kpi = _supplierperf_make_kpi(tenant_a)
    line = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                              measured_value=Decimal("95"), target_at_time=Decimal("95"),
                              direction_at_time="higher_is_better")
    assert performance.meets_target(line) is True
    line.direction_at_time = "lower_is_better"
    assert performance.meets_target(line) is True


def test_supplierperf_meets_target_is_none_when_either_side_is_missing(
        tenant_a, supplierperf_scorecard_draft_a):
    """A KPI with no target has nothing to meet - "False" would read as a failure nobody asked
    for."""
    kpi = _supplierperf_make_kpi(tenant_a)
    no_target = _supplierperf_line(tenant_a, supplierperf_scorecard_draft_a, kpi,
                                   measured_value=Decimal("96"), target_at_time=None)
    assert performance.meets_target(no_target) is None
    no_target.target_at_time = Decimal("95")
    no_target.measured_value = None
    assert performance.meets_target(no_target) is None


def test_supplierperf_quadrant_for_splits_on_performance_and_risk():
    """70 composite and a 2.5 risk index are the two axes; both boundaries are inclusive."""
    assert performance.quadrant_for(Decimal("80"), Decimal("1.0")) == "strategic"
    assert performance.quadrant_for(Decimal("80"), Decimal("4.0")) == "hidden"
    assert performance.quadrant_for(Decimal("40"), Decimal("1.0")) == "development"
    assert performance.quadrant_for(Decimal("40"), Decimal("4.0")) == "underperforming"
    assert performance.quadrant_for(Decimal("70"), Decimal("2.5")) == "strategic"


def test_supplierperf_quadrant_for_is_blank_without_both_axes():
    assert performance.quadrant_for(None, Decimal("1.0")) == ""
    assert performance.quadrant_for(Decimal("80"), None) == ""
    assert performance.quadrant_for(None, None) == ""


def test_supplierperf_weighted_mean_counts_a_zero_weight_voice():
    """Same contract as survey_aggregate: importance WEIGHTS, it does not gate the count."""
    assert performance._weighted([]) == (None, 0)
    assert performance._weighted([(Decimal("75"), 8), (Decimal("25"), 2)]) == (Decimal("65.00"), 2)
    assert performance._weighted([(Decimal("75"), 0), (Decimal("25"), 0)]) == (None, 2)


def test_supplierperf_delta_css_is_colour_named_only():
    for delta in (None, Decimal("40"), Decimal("20"), Decimal("15"), Decimal("10"),
                  Decimal("0"), Decimal("-10"), Decimal("-40")):
        assert performance._delta_css(delta) in _SUPPLIERPERF_THEME_BADGES, delta
    assert performance._delta_css(None) == "badge-slate"
    assert performance._delta_css(Decimal("20")) == "badge-red"
    assert performance._delta_css(Decimal("10")) == "badge-amber"
    assert performance._delta_css(Decimal("-10")) == "badge-info"
    assert performance._delta_css(Decimal("0")) == "badge-green"


def test_supplierperf_period_choices_are_distinct_and_newest_first(
        tenant_a, tenant_b, supplierperf_supplier_a, supplierperf_supplier_b):
    end = _supplierperf_today()
    older = end - datetime.timedelta(days=90)
    _supplierperf_card(tenant_a, supplierperf_supplier_a, period_end=end)
    _supplierperf_card(tenant_a, supplierperf_supplier_a, period_end=end)   # same period twice
    _supplierperf_card(tenant_a, supplierperf_supplier_a, period_end=older,
                       period_start=older - datetime.timedelta(days=89))
    _supplierperf_card(tenant_b, supplierperf_supplier_b)
    assert performance.period_choices(tenant_a) == [end, older]


def test_supplierperf_period_choices_are_empty_without_a_scorecard(tenant_a):
    assert performance.period_choices(tenant_a) == []


def test_supplierperf_handover_note_names_the_one_way_door():
    """ONE constant - the register, the detail page and the confirm dialog all print it."""
    note = performance.HANDOVER_NOTE
    assert "manual_override" in note
    assert "recompute_from_signals" in note
    assert "cannot be undone" in note


def test_supplierperf_benchmark_note_refuses_to_imply_an_external_feed():
    """There is no industry benchmark feed anywhere in this system and no page may imply one."""
    assert "no external industry feed" in performance.BENCHMARK_NOTE
