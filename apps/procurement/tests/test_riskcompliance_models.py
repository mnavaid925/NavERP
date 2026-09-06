"""Procurement 6.17 - Risk & Compliance Management MODEL tests.

The invariants this lane owns - the claims the sub-module would be worthless without, not the
getters:

* ``ComplianceScreening.clear()`` refuses while ANY child hit is undisposed, and it refuses on a
  LIVE query rather than on ``open_hit_count``. The counters render a badge; a stale badge must
  never unlock the disposition gate, which is what the stale-counter test pins.
* ``block()`` STAMPS an existing 6.4 ``VendorSuspension`` and mints none - 6.17 records a decision
  and never invents a second block flag. A terminal screening has no way back: no un-clear, no
  re-open.
* ``ScreeningHit`` is TENANT-LESS by design; its only scope is ``screening__tenant``.
* ``SupplierRiskSignal`` - the inversion IS the model. FHR 100 is the safest reading and FHR 1 the
  riskiest, while SER 1 is safest and SER 9 riskiest, and both collapse to one comparable 0-100
  ``risk_position`` where 0 is always safest. ``trend`` is judged on that position and never on the
  raw value, which is the one place a falling number can mean either thing. ``metric="other"``
  bands ``unrated`` rather than fabricating an all-clear, out-of-scale values CLAMP, and a
  ``NaN`` / ``Infinity`` degrades instead of raising ``InvalidOperation`` from an ordering
  comparison (L35).
* ``FraudAlert.scan()`` is idempotent by dedupe key, writes ONLY its own table, refuses an
  over-long window in O(1) arithmetic without materialising the range it is guarding (L40 1), and
  each of the six rules fires on data crafted to trigger it - including the four the seeded
  workspace never exercises. ``duplicate_vendor`` FLAGS and never merges.
* ``PolicyAttestation`` - ``requires_acknowledgment=False`` genuinely governs the ledger, raising
  is idempotent and cannot disturb a signature already on file, only a PUBLISHED policy raises a
  roster, a v2 roster cannot reach v1's rows, and ``acknowledge()`` is OWNER-ONLY at the model
  layer: a tenant admin and a superuser are both refused.
* ``AuditSeal`` - ranges are ID-keyed and never time-keyed, ``verify()`` NAMES the entry that was
  modified or deleted, seals chain, an empty seal is refused, and one workspace's seal never
  covers another's interleaved rows.

Determinism (L16): every date basis here is ``timezone.localdate()`` / ``timezone.now()`` - the
same basis the model code uses. ``datetime.date.today()`` never appears, or the window-boundary
and days-late assertions flake for the hours after local midnight.

Naming (L41 2 / L47): every test is ``test_riskcompliance_*`` and every module-level helper is
``_riskcompliance_*``, so a sibling lane appending near this file cannot silently rebind either.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.procurement.models import (
    AuditSeal,
    ComplianceScreening,
    FraudAlert,
    PolicyAttestation,
    ScreeningHit,
    SupplierRiskSignal,
)
from apps.procurement.models.RiskComplianceManagement.AuditSeals import GENESIS_DIGEST
from apps.procurement.models.RiskComplianceManagement.FraudAlerts import (
    MAX_SCAN_WINDOW_DAYS,
)
from apps.procurement.models.RiskComplianceManagement.FraudAlerts import (
    RULE_CHOICES as _RISKCOMPLIANCE_RULE_CHOICES,
)
from apps.procurement.models.RiskComplianceManagement.Policies import (
    DEFAULT_ATTESTATION_DUE_DAYS,
    raise_attestations,
    resolve_audience,
)
from apps.procurement.models.RiskComplianceManagement.Screenings import DEFAULT_RESCREEN_DAYS

pytestmark = pytest.mark.django_db


# -- local helpers ---------------------------------------------------------------------------------
# Named _riskcompliance_* for the same reason the tests are: Python binds the LAST module-level
# definition, so an unprefixed helper here would silently rebind another lane's (L41 2 / L47).
# These mint the SUPPORTING rows the conftest deliberately does not carry - the vendor/employee
# parties, roles, addresses, contacts, orders, invoices and approvals the four fraud rules the
# seeded workspace never exercises actually need. Every 6.17 row itself comes from the shared
# riskcompliance_* fixtures wherever one exists.

#: The six rule names, in the order the model declares them.
_RISKCOMPLIANCE_RULES = tuple(name for name, _label in _RISKCOMPLIANCE_RULE_CHOICES)


def _riskcompliance_today():
    """The date basis the model code uses. Never ``date.today()`` (L16)."""
    return timezone.localdate()


def _riskcompliance_days(count):
    return datetime.timedelta(days=count)


def _riskcompliance_mk_party(tenant, name, kind="organization", tax_id=""):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind=kind, tax_id=tax_id)


def _riskcompliance_mk_role(tenant, party, role):
    """The row that makes a party a supplier / an employee to the fraud scan."""
    from apps.core.models import PartyRole
    return PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")


def _riskcompliance_mk_address(tenant, party, line1, city=""):
    from apps.core.models import Address
    return Address.objects.create(tenant=tenant, party=party, line1=line1, city=city)


def _riskcompliance_mk_contact(tenant, party, value, kind="email"):
    from apps.core.models import ContactMethod
    return ContactMethod.objects.create(tenant=tenant, party=party, kind=kind, value=value)


def _riskcompliance_mk_po(tenant, vendor, order_date, total="1000.00", status="approved"):
    from apps.scm.models import PurchaseOrder
    return PurchaseOrder.objects.create(
        tenant=tenant, vendor=vendor, status=status, order_date=order_date,
        subtotal=Decimal(total), total=Decimal(total))


def _riskcompliance_mk_invoice(tenant, vendor, invoice_date, total="1000.00",
                               invoice_number="INV-1", purchase_order=None, status="approved"):
    from apps.procurement.models import SupplierInvoice
    return SupplierInvoice.objects.create(
        tenant=tenant, vendor=vendor, purchase_order=purchase_order,
        invoice_number=invoice_number, invoice_date=invoice_date,
        invoice_type="standard", status=status,
        subtotal=Decimal(total), total=Decimal(total))


def _riskcompliance_mk_requisition(tenant, requester, title="Bench laptops"):
    from apps.scm.models import PurchaseRequisition
    return PurchaseRequisition.objects.create(tenant=tenant, title=title, requester=requester)


def _riskcompliance_mk_approval(tenant, requisition, approver, tier=1, tier_count=1):
    """One sign-off. ``decided_at`` is ``auto_now_add`` - it lands NOW, inside any window whose
    end is tomorrow, so no test has to rewrite it."""
    from apps.procurement.models import RequisitionApproval
    return RequisitionApproval.objects.create(
        tenant=tenant, requisition=requisition, tier=tier, tier_count=tier_count,
        decision="approved", approver=approver)


def _riskcompliance_mk_screening(tenant, party, **overrides):
    """A bare ``pending_review`` screening. ``status`` is editable=False - the verbs own it."""
    fields = dict(tenant=tenant, party=party, list_source="csl_consolidated",
                  checkpoint="onboarding", method="manual_lookup",
                  screened_on=_riskcompliance_today(), result="clear", match_threshold=85)
    fields.update(overrides)
    return ComplianceScreening.objects.create(**fields)


def _riskcompliance_mk_hit(screening, matched_name="LISTED ENTITY", score=95, **overrides):
    fields = dict(screening=screening, matched_name=matched_name, matched_list="ofac_sdn",
                  match_score=score, match_type="name")
    fields.update(overrides)
    return ScreeningHit.objects.create(**fields)


def _riskcompliance_mk_signal(tenant, party, metric, value, days_ago=0, provider="dnb"):
    """One observation. Only the INPUTS are set - every derived column is stamped by save()."""
    return SupplierRiskSignal.objects.create(
        tenant=tenant, party=party, provider=provider, metric=metric, value=Decimal(value),
        observed_on=_riskcompliance_today() - _riskcompliance_days(days_ago))


def _riskcompliance_mk_audit_rows(tenant, user, count=1, target="Supplier record"):
    from apps.core.models import AuditLog
    return [AuditLog.objects.create(tenant=tenant, user=user, action="update",
                                    target=f"{target} {index + 1}",
                                    changes={"name": ["before", f"after {index + 1}"]})
            for index in range(count)]


def _riskcompliance_mk_suspension(tenant, supplier, user):
    """An EXISTING 6.4 block, so a screening has something real to stamp."""
    from apps.procurement.models import VendorSuspension
    return VendorSuspension.objects.create(
        tenant=tenant, supplier=supplier, kind="suspension", reason_category="other",
        reason="Sanctions match confirmed by compliance.", status="active",
        starts_on=_riskcompliance_today(), requested_by=user)


def _riskcompliance_sealed_log_ids(seal):
    from apps.core.models import AuditLog
    return list(AuditLog.objects
                .filter(tenant_id=seal.tenant_id, id__gte=seal.from_log_id,
                        id__lte=seal.to_log_id)
                .order_by("id").values_list("id", flat=True))


def _riskcompliance_mk_superuser():
    from apps.accounts.models import User
    return User.objects.create_superuser(
        email="root@naverp.test", username="root_naverp", password="TestPass123!")


# =================================================================================================
# ComplianceScreening + ScreeningHit - the disposition gate
# =================================================================================================


def test_riskcompliance_clear_refuses_while_any_hit_is_open(riskcompliance_screening_open,
                                                            admin_user):
    """The gate's whole purpose: two undisposed sanctions matches, so no clearance."""
    screening = riskcompliance_screening_open
    assert screening.hits.filter(disposition="open").count() == 2
    assert screening.has_open_hits is True

    assert screening.clear(admin_user, "Looks fine to me.") is False

    screening.refresh_from_db()
    assert screening.status == "pending_review"
    assert screening.decided_by_id is None
    assert screening.decided_at is None
    assert screening.decision_note == ""
    assert screening.next_rescreen_on is None


def test_riskcompliance_clear_asks_the_database_not_the_cached_counter(
        riskcompliance_screening_open, admin_user):
    """A stale badge must not unlock the gate.

    Both display counters are forced to 0 with a raw ``.update()`` - the exact drift a seeder or a
    half-finished view can leave behind - while two hits are still ``open``. ``clear()`` re-asks
    the database and refuses anyway. This is the single most important assertion in this file.
    """
    screening = riskcompliance_screening_open
    ComplianceScreening.objects.filter(pk=screening.pk).update(hit_count=0, open_hit_count=0)
    screening.refresh_from_db()
    assert (screening.hit_count, screening.open_hit_count) == (0, 0)  # the badge now lies

    assert screening.clear(admin_user, "The counter says zero.") is False

    screening.refresh_from_db()
    assert screening.status == "pending_review"
    assert screening.hits.filter(disposition="open").count() == 2
    assert screening.has_open_hits is True


def test_riskcompliance_clear_succeeds_once_every_hit_is_disposed(
        riskcompliance_screening_disposed, admin_user):
    """Both hits adjudicated -> the gate opens, and clearing stamps the three evidence columns."""
    screening = riskcompliance_screening_disposed
    assert (screening.hit_count, screening.open_hit_count) == (2, 0)
    before = timezone.now()

    assert screening.clear(admin_user, "  Both matches adjudicated as false positives.  ") is True

    screening.refresh_from_db()
    assert screening.status == "cleared"
    assert screening.is_terminal is True
    assert screening.decided_by_id == admin_user.pk
    assert screening.decided_at is not None and screening.decided_at >= before
    assert screening.decision_note == "Both matches adjudicated as false positives."
    assert screening.next_rescreen_on == (screening.screened_on
                                          + _riskcompliance_days(DEFAULT_RESCREEN_DAYS))


def test_riskcompliance_clear_never_moves_a_rescreen_date_somebody_already_set(
        riskcompliance_screening_disposed, admin_user):
    """``next_rescreen_on`` is back-filled only when it is blank."""
    screening = riskcompliance_screening_disposed
    chosen = _riskcompliance_today() + _riskcompliance_days(90)
    screening.next_rescreen_on = chosen
    screening.save(update_fields=["next_rescreen_on", "updated_at"])

    assert screening.clear(admin_user, "Cleared; keep the 90-day cycle.") is True

    screening.refresh_from_db()
    assert screening.next_rescreen_on == chosen


def test_riskcompliance_block_stamps_an_existing_suspension_and_mints_none(
        tenant_a, riskcompliance_party_a, admin_user):
    """6.17 RECORDS the block; the 6.4 register is the only place one is raised."""
    from apps.procurement.models import VendorSuspension

    suspension = _riskcompliance_mk_suspension(tenant_a, riskcompliance_party_a, admin_user)
    screening = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a,
                                             result="confirmed_match")
    before = VendorSuspension.objects.count()
    assert before == 1

    assert screening.block(admin_user, "Confirmed SDN match.", suspension=suspension) is True

    screening.refresh_from_db()
    assert screening.status == "blocked"
    assert screening.suspension_id == suspension.pk
    assert screening.decided_by_id == admin_user.pk
    assert screening.decision_note == "Confirmed SDN match."
    assert VendorSuspension.objects.count() == 1  # nothing minted, nothing duplicated


def test_riskcompliance_block_without_a_suspension_creates_no_block_row(
        riskcompliance_screening_blocked):
    """The fixture blocked a screening with no 6.4 row picked - so no 6.4 row may exist."""
    from apps.procurement.models import VendorSuspension

    screening = riskcompliance_screening_blocked
    assert screening.status == "blocked"
    assert screening.suspension_id is None
    assert VendorSuspension.objects.count() == 0


def test_riskcompliance_block_requires_a_note(tenant_a, riskcompliance_party_a, admin_user):
    screening = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a)

    assert screening.block(admin_user, "   ") is False

    screening.refresh_from_db()
    assert screening.status == "pending_review"


def test_riskcompliance_a_terminal_screening_cannot_be_reopened(riskcompliance_screening_cleared,
                                                                riskcompliance_screening_blocked,
                                                                admin_user):
    """No un-clear and no re-open: a correction is a NEW screening, which is the honest trail."""
    cleared = riskcompliance_screening_cleared
    blocked = riskcompliance_screening_blocked
    assert cleared.status == "cleared" and blocked.status == "blocked"

    assert cleared.escalate(admin_user, "On reflection this needs review.") is False
    assert blocked.escalate(admin_user, "Reconsider the block.") is False
    assert cleared.block(admin_user, "Actually block them.") is False
    assert blocked.clear(admin_user, "Actually clear them.") is False

    cleared.refresh_from_db()
    blocked.refresh_from_db()
    assert cleared.status == "cleared"
    assert blocked.status == "blocked"


def test_riskcompliance_escalate_moves_only_from_pending_review_and_needs_a_reason(
        riskcompliance_screening_open, admin_user):
    screening = riskcompliance_screening_open

    assert screening.escalate(admin_user, "  ") is False
    screening.refresh_from_db()
    assert screening.status == "pending_review"

    assert screening.escalate(admin_user, "Two matches above threshold.") is True
    screening.refresh_from_db()
    assert screening.status == "escalated"
    assert screening.is_open is True
    assert screening.decision_note == "Two matches above threshold."

    # Escalating twice is not a second escalation.
    assert screening.escalate(admin_user, "Again.") is False


def test_riskcompliance_recount_hits_recomputes_both_counters_from_live_rows(
        riskcompliance_screening_open, admin_user):
    """The counters are DERIVED from the child rows and re-derived on demand."""
    screening = riskcompliance_screening_open
    ComplianceScreening.objects.filter(pk=screening.pk).update(hit_count=99, open_hit_count=99)
    screening.refresh_from_db()

    screening.recount_hits()
    screening.refresh_from_db()
    assert (screening.hit_count, screening.open_hit_count) == (2, 2)

    top = screening.hits.order_by("-match_score", "id").first()
    assert top.dispose(admin_user, "false_positive", "Different registered address.") is True
    screening.recount_hits()
    screening.refresh_from_db()
    assert (screening.hit_count, screening.open_hit_count) == (2, 1)

    _riskcompliance_mk_hit(screening, "THIRD ENTRY", 70)
    screening.recount_hits()
    screening.refresh_from_db()
    assert (screening.hit_count, screening.open_hit_count) == (3, 2)


def test_riskcompliance_dispose_refuses_a_second_adjudication(riskcompliance_hit_disposed,
                                                              admin_user):
    """There is no re-open on a hit either - a hit that can be re-adjudicated is not evidence."""
    hit = riskcompliance_hit_disposed
    assert hit.disposition == "false_positive"
    note_before = hit.disposition_note
    at_before = hit.disposed_at

    assert hit.dispose(admin_user, "true_match", "Second thoughts.") is False

    hit.refresh_from_db()
    assert hit.disposition == "false_positive"
    assert hit.disposition_note == note_before
    assert hit.disposed_at == at_before


def test_riskcompliance_dispose_requires_a_terminal_disposition_and_a_note(
        riskcompliance_hit_open, admin_user):
    hit = riskcompliance_hit_open
    assert hit.is_open is True

    assert hit.dispose(admin_user, "open", "Leaving it open.") is False
    assert hit.dispose(admin_user, "not_a_disposition", "Nonsense.") is False
    assert hit.dispose(admin_user, "false_positive", "   ") is False
    hit.refresh_from_db()
    assert hit.disposition == "open"

    assert hit.dispose(admin_user, "cleared_with_licence", "BIS licence 2026-114 on file.") is True
    hit.refresh_from_db()
    assert hit.disposition == "cleared_with_licence"
    assert hit.disposed_by_id == admin_user.pk
    assert hit.disposed_at is not None


def test_riskcompliance_screening_hit_is_tenant_less(riskcompliance_screening_open,
                                                     riskcompliance_screening_b, tenant_a,
                                                     tenant_b):
    """The parent FK IS the scope. A second tenant column would be a second answer."""
    field_names = {field.name for field in ScreeningHit._meta.get_fields()}
    assert "tenant" not in field_names
    with pytest.raises(FieldDoesNotExist):
        ScreeningHit._meta.get_field("tenant")

    _riskcompliance_mk_hit(riskcompliance_screening_b, "GLOBEX OFFSHORE SA", 93)

    assert ScreeningHit.objects.filter(screening__tenant=tenant_a).count() == 2
    assert ScreeningHit.objects.filter(screening__tenant=tenant_b).count() == 1
    a_ids = set(ScreeningHit.objects.filter(screening__tenant=tenant_a)
                .values_list("id", flat=True))
    b_ids = set(ScreeningHit.objects.filter(screening__tenant=tenant_b)
                .values_list("id", flat=True))
    assert a_ids.isdisjoint(b_ids)


def test_riskcompliance_hit_is_above_threshold_reads_its_parents_threshold(
        tenant_a, riskcompliance_party_a):
    screening = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a, match_threshold=90)
    above = _riskcompliance_mk_hit(screening, "EXACT MATCH", 90)
    below = _riskcompliance_mk_hit(screening, "WEAK MATCH", 89)

    assert above.is_above_threshold is True
    assert below.is_above_threshold is False
    assert ScreeningHit(matched_name="unsaved", match_score=100).is_above_threshold is False


def test_riskcompliance_hit_clean_requires_a_matched_name(riskcompliance_screening_open):
    hit = ScreeningHit(screening=riskcompliance_screening_open, matched_name="   ",
                       matched_list="ofac_sdn", match_score=80)

    with pytest.raises(ValidationError) as caught:
        hit.full_clean()
    assert "matched_name" in caught.value.error_dict


def test_riskcompliance_screening_clean_rejects_a_cross_tenant_party(tenant_a,
                                                                    riskcompliance_party_b):
    """``objects.create()`` does NOT call ``clean()`` - the guard is asserted through the model."""
    screening = ComplianceScreening(tenant=tenant_a, party=riskcompliance_party_b,
                                    screened_on=_riskcompliance_today())

    with pytest.raises(ValidationError) as caught:
        screening.full_clean()
    assert "party" in caught.value.error_dict
    assert "another workspace" in str(caught.value.error_dict["party"][0])


def test_riskcompliance_screening_clean_rejects_a_list_dated_after_the_search(
        tenant_a, riskcompliance_party_a):
    today = _riskcompliance_today()
    screening = ComplianceScreening(tenant=tenant_a, party=riskcompliance_party_a,
                                    screened_on=today, list_as_of=today + _riskcompliance_days(1))

    with pytest.raises(ValidationError) as caught:
        screening.full_clean()
    assert "list_as_of" in caught.value.error_dict


def test_riskcompliance_screening_retention_is_ten_years_from_the_search(
        riskcompliance_screening_cleared):
    screening = riskcompliance_screening_cleared
    screened_on = screening.screened_on

    assert screening.RETENTION_YEARS == 10
    assert screening.retention_until.year == screened_on.year + 10
    assert screening.retention_until.month == screened_on.month
    assert ComplianceScreening(screened_on=None).retention_until is None


def test_riskcompliance_screening_workflow_columns_are_not_operator_writable():
    """``status`` and every decision stamp belong to the three verbs, never to a form."""
    for name in ("status", "hit_count", "open_hit_count", "suspension", "screened_by",
                 "decided_by", "decided_at", "decision_note"):
        assert ComplianceScreening._meta.get_field(name).editable is False, name
    for name in ("disposition", "disposition_note", "disposed_by", "disposed_at"):
        assert ScreeningHit._meta.get_field(name).editable is False, name
    assert ComplianceScreening._meta.get_field("notes").editable is True


def test_riskcompliance_screening_status_and_disposition_choices_are_pinned():
    assert [value for value, _label in ComplianceScreening.STATUS_CHOICES] == [
        "pending_review", "cleared", "escalated", "blocked"]
    assert ComplianceScreening.OPEN_STATUSES == ("pending_review", "escalated")
    assert ComplianceScreening.TERMINAL_STATUSES == ("cleared", "blocked")
    assert [value for value, _label in ScreeningHit.DISPOSITION_CHOICES] == [
        "open", "false_positive", "true_match", "cleared_with_licence"]
    assert ScreeningHit.TERMINAL_DISPOSITIONS == (
        "false_positive", "true_match", "cleared_with_licence")


# =================================================================================================
# Auto-numbering across the four numbered entities
# =================================================================================================


def test_riskcompliance_auto_numbers_use_the_pinned_prefixes(riskcompliance_screening_open,
                                                             riskcompliance_signal_fhr,
                                                             riskcompliance_fraud_open,
                                                             riskcompliance_seal):
    assert riskcompliance_screening_open.number.startswith("SCR-")
    assert riskcompliance_signal_fhr.number.startswith("SRS-")
    assert riskcompliance_fraud_open.number.startswith("FRD-")
    assert riskcompliance_seal.number.startswith("ASL-")
    assert len(riskcompliance_screening_open.number) == len("SCR-00001")
    assert (ComplianceScreening.NUMBER_PREFIX, SupplierRiskSignal.NUMBER_PREFIX,
            FraudAlert.NUMBER_PREFIX, AuditSeal.NUMBER_PREFIX) == ("SCR", "SRS", "FRD", "ASL")


def test_riskcompliance_numbers_are_a_per_tenant_sequence(tenant_a, riskcompliance_party_a):
    first = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a)
    second = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a)
    third = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a)

    assert [first.number, second.number, third.number] == ["SCR-00001", "SCR-00002", "SCR-00003"]


def test_riskcompliance_two_tenants_can_hold_the_same_number(tenant_a, tenant_b,
                                                             riskcompliance_party_a,
                                                             riskcompliance_party_b):
    a_first = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a)
    b_first = _riskcompliance_mk_screening(tenant_b, riskcompliance_party_b)

    assert a_first.number == b_first.number == "SCR-00001"
    assert ComplianceScreening.objects.filter(number="SCR-00001").count() == 2
    assert ComplianceScreening._meta.unique_together == (("tenant", "number"),)


def test_riskcompliance_a_number_is_unique_inside_one_tenant(tenant_a, riskcompliance_party_a):
    first = _riskcompliance_mk_screening(tenant_a, riskcompliance_party_a)
    clash = ComplianceScreening(tenant=tenant_a, party=riskcompliance_party_a,
                                screened_on=_riskcompliance_today(), number=first.number)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            clash.save()


def test_riskcompliance_screening_str_leads_with_its_number(riskcompliance_screening_open):
    text = str(riskcompliance_screening_open)
    assert text.startswith(riskcompliance_screening_open.number)
    assert "Northwind Components Ltd" in text
    # An UNSAVED row (a ModelForm re-rendering its own errors) must not raise.
    assert str(ComplianceScreening()).startswith("SCR")


# =================================================================================================
# SupplierRiskSignal - the inversion is the whole model
# =================================================================================================


def test_riskcompliance_fhr_and_ser_invert_against_each_other(riskcompliance_signal_fhr,
                                                              riskcompliance_signal_ser):
    """The larger raw number bands SAFER, which is the entire reason METRIC_SCALES exists."""
    fhr = riskcompliance_signal_fhr
    ser = riskcompliance_signal_ser

    assert fhr.value == Decimal("82.00")
    assert fhr.risk_position == Decimal("18.18")
    assert fhr.band == "low"
    assert ser.value == Decimal("7.00")
    assert ser.risk_position == Decimal("75.00")
    assert ser.band == "critical"
    assert fhr.risk_position < ser.risk_position
    assert (fhr.scale_min, fhr.scale_max, fhr.higher_is_better) == (
        Decimal("1.00"), Decimal("100.00"), True)
    assert (ser.scale_min, ser.scale_max, ser.higher_is_better) == (
        Decimal("1.00"), Decimal("9.00"), False)


def test_riskcompliance_fhr_100_is_safest_and_fhr_1_is_riskiest(tenant_a, riskcompliance_party_a):
    safest = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "100.00",
                                       provider="rapidratings")
    riskiest = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "1.00",
                                         days_ago=1, provider="rapidratings")

    assert (safest.risk_position, safest.band) == (Decimal("0.00"), "low")
    assert (riskiest.risk_position, riskiest.band) == (Decimal("100.00"), "critical")
    assert safest.is_banded is True  # a position of 0.00 is a value, not a blank


def test_riskcompliance_ser_1_is_safest_and_ser_9_is_riskiest(tenant_a, riskcompliance_party_a):
    safest = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "1.00")
    riskiest = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "9.00",
                                         days_ago=1)

    assert (safest.risk_position, safest.band) == (Decimal("0.00"), "low")
    assert (riskiest.risk_position, riskiest.band) == (Decimal("100.00"), "critical")


def test_riskcompliance_a_high_fhr_bands_safer_than_a_high_ser(tenant_a, riskcompliance_party_a):
    """90 on a higher-is-better scale and 8 on a higher-is-worse one, compared correctly."""
    healthy = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "90.00",
                                        provider="rapidratings")
    dangerous = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "8.00")

    assert healthy.risk_position == Decimal("10.10")
    assert dangerous.risk_position == Decimal("87.50")
    assert healthy.risk_position < dangerous.risk_position
    assert healthy.band == "low"
    assert dangerous.band == "critical"


def test_riskcompliance_band_thresholds_are_read_off_the_risk_position(tenant_a,
                                                                      riskcompliance_party_a):
    """< 25 low, < 50 watch, < 75 elevated, 75 and over critical - on the POSITION."""
    cases = [("1.00", Decimal("0.00"), "low"),
             ("3.00", Decimal("25.00"), "watch"),
             ("5.00", Decimal("50.00"), "elevated"),
             ("7.00", Decimal("75.00"), "critical")]
    for offset, (value, position, band) in enumerate(cases):
        signal = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", value,
                                           days_ago=offset, provider="creditsafe")
        assert (signal.risk_position, signal.band) == (position, band), value


def test_riskcompliance_metric_other_bands_unrated_and_does_not_raise(tenant_a,
                                                                     riskcompliance_party_a):
    """An unregistered metric has no scale - "we do not know" beats a fabricated all-clear."""
    signal = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "other", "42.00")

    assert signal.has_scale is False
    assert signal.risk_position is None
    assert signal.is_banded is False
    assert signal.band == "unrated"
    assert signal.scale_min is None and signal.scale_max is None
    assert signal.band_css == "badge-muted"
    assert signal.breaches_minimum is False


def test_riskcompliance_an_unscaled_metric_never_reports_a_direction(tenant_a,
                                                                    riskcompliance_party_a):
    """Two "other" observations in one series: no scale means no claim about which way is up."""
    _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "other", "10.00", days_ago=10)
    later = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "other", "900.00")

    assert later.previous_value == Decimal("10.00")
    assert later.trend == "stable"
    assert later.band == "unrated"


def test_riskcompliance_a_value_outside_the_scale_clamps_into_the_range(tenant_a,
                                                                       riskcompliance_party_a):
    """A PAYDEX of 140 is a typo or a rescaled feed - not 140% along a 1-100 scale."""
    over_top = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "paydex", "140.00")
    over_bottom = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating",
                                            "-40.00")
    under_zero = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "dso_days", "-5.00")
    way_over = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "dso_days", "5000.00",
                                         days_ago=1)

    assert over_top.risk_position == Decimal("0.00")  # clamped to 100, then flipped
    assert over_bottom.risk_position == Decimal("0.00")  # clamped up to the scale minimum
    assert under_zero.risk_position == Decimal("0.00")
    assert way_over.risk_position == Decimal("100.00")
    for signal in (over_top, over_bottom, under_zero, way_over):
        assert Decimal("0") <= signal.risk_position <= Decimal("100")


def test_riskcompliance_a_falling_ser_is_an_improvement_not_a_deterioration(
        tenant_a, riskcompliance_party_a):
    """The case that matters: lower is BETTER here, so a falling raw number is good news.

    A raw-value comparison would call this a deterioration. The comparison lives on the RISK
    POSITION precisely so it cannot.
    """
    worse = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "7.00",
                                      days_ago=30)
    better = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "4.00")

    assert worse.risk_position == Decimal("75.00")
    assert better.risk_position == Decimal("37.50")
    assert better.value < worse.value  # the RAW number fell ...
    assert better.previous_value == Decimal("7.00")
    assert better.trend == "improved"  # ... and that is an IMPROVEMENT
    assert better.alerts_on_deterioration is False


def test_riskcompliance_a_falling_fhr_is_a_deterioration(tenant_a, riskcompliance_party_a):
    """The mirror image: same direction of raw movement, opposite meaning."""
    healthy = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "70.00",
                                        days_ago=30, provider="rapidratings")
    sick = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "40.00",
                                     provider="rapidratings")

    assert healthy.risk_position == Decimal("30.30")
    assert sick.risk_position == Decimal("60.61")
    assert sick.value < healthy.value  # the RAW number fell ...
    assert sick.previous_value == Decimal("70.00")
    assert sick.trend == "deteriorated"  # ... and here that is BAD
    assert sick.band == "elevated"
    assert sick.alerts_on_deterioration is True


def test_riskcompliance_movement_inside_the_epsilon_reads_as_stable(tenant_a,
                                                                    riskcompliance_party_a):
    first = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "80.00",
                                      days_ago=20, provider="rapidratings")
    second = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "80.50",
                                       provider="rapidratings")

    assert first.risk_position == Decimal("20.20")
    assert second.risk_position == Decimal("19.70")
    assert second.previous_value == Decimal("80.00")
    assert second.trend == "stable"


def test_riskcompliance_previous_value_comes_from_the_same_series(tenant_a, tenant_b,
                                                                  riskcompliance_party_a,
                                                                  riskcompliance_party_b):
    """Same tenant + party + provider + metric, newest first. Nothing else is comparable."""
    other_party = _riskcompliance_mk_party(tenant_a, "Contoso Fasteners")
    _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "2.00", days_ago=40)
    wanted = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "3.00",
                                       days_ago=20)
    # Three near-misses that must NOT be picked: another metric, another provider, another party.
    _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "paydex", "70.00", days_ago=5)
    _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "9.00", days_ago=5,
                              provider="creditsafe")
    _riskcompliance_mk_signal(tenant_a, other_party, "ser_rating", "8.00", days_ago=5)
    _riskcompliance_mk_signal(tenant_b, riskcompliance_party_b, "ser_rating", "8.00", days_ago=5)

    latest = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "6.00")

    assert latest.prior_observation().pk == wanted.pk
    assert latest.previous_value == Decimal("3.00")
    assert latest.trend == "deteriorated"


def test_riskcompliance_the_first_observation_in_a_series_is_new(riskcompliance_signal_series):
    assert riskcompliance_signal_series.previous_value is None
    assert riskcompliance_signal_series.trend == "new"
    assert riskcompliance_signal_series.risk_position == Decimal("37.50")
    assert riskcompliance_signal_series.band == "watch"


def test_riskcompliance_a_nan_value_never_raises_from_an_ordering_comparison(
        tenant_a, riskcompliance_party_a):
    """L35 in full: ``Decimal("NaN")`` parses cleanly and then raises on the first ``<``.

    ``_finite`` refuses it BEFORE any comparison, so the row degrades to unrated/stable rather
    than 500ing out of ``derive()``. Asserted on an unsaved instance because ``clean()`` is what
    refuses the value on the way in - this is the guard behind that guard.
    """
    prior = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "82.00",
                                      days_ago=10, provider="rapidratings")
    assert prior.risk_position == Decimal("18.18")

    for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        signal = SupplierRiskSignal(tenant=tenant_a, party=riskcompliance_party_a,
                                    provider="rapidratings", metric="fhr",
                                    observed_on=_riskcompliance_today(), value=bad)
        signal.derive()  # must not raise InvalidOperation

        assert signal.risk_position is None, bad
        assert signal.band == "unrated", bad
        assert signal.previous_value == Decimal("82.00"), bad
        assert signal.trend == "stable", bad  # no direction can be claimed from a non-number
        assert signal.breaches_minimum is False, bad


def test_riskcompliance_clean_refuses_a_non_finite_value(tenant_a, riskcompliance_party_a):
    for bad in (Decimal("NaN"), Decimal("Infinity")):
        signal = SupplierRiskSignal(tenant=tenant_a, party=riskcompliance_party_a,
                                    provider="dnb", metric="ser_rating",
                                    observed_on=_riskcompliance_today(), value=bad)

        with pytest.raises(ValidationError) as caught:
            signal.clean()
        assert "value" in caught.value.error_dict, bad
        assert "real number" in str(caught.value.error_dict["value"][0]), bad

    assert SupplierRiskSignal.objects.count() == 0


def test_riskcompliance_an_over_wide_value_is_a_friendly_error_not_a_driver_failure(
        tenant_a, riskcompliance_party_a):
    """Bound-checked in ``clean()`` so an oversized number never reaches the column."""
    signal = SupplierRiskSignal(tenant=tenant_a, party=riskcompliance_party_a, provider="dnb",
                                metric="fhr", observed_on=_riskcompliance_today(),
                                value=Decimal("99999999999.99"))

    with pytest.raises(ValidationError) as caught:
        signal.clean()
    assert "value" in caught.value.error_dict
    assert "outside the range" in str(caught.value.error_dict["value"][0])

    with pytest.raises(ValidationError) as full:
        signal.full_clean()
    assert "value" in full.value.error_dict
    assert SupplierRiskSignal.objects.count() == 0


def test_riskcompliance_clean_refuses_a_future_observation_and_a_backwards_refresh(
        tenant_a, riskcompliance_party_a):
    today = _riskcompliance_today()
    future = SupplierRiskSignal(tenant=tenant_a, party=riskcompliance_party_a, provider="dnb",
                                metric="fhr", value=Decimal("55.00"),
                                observed_on=today + _riskcompliance_days(1))
    with pytest.raises(ValidationError) as caught:
        future.clean()
    assert "observed_on" in caught.value.error_dict

    backwards = SupplierRiskSignal(tenant=tenant_a, party=riskcompliance_party_a, provider="dnb",
                                   metric="fhr", value=Decimal("55.00"), observed_on=today,
                                   next_refresh_on=today - _riskcompliance_days(1))
    with pytest.raises(ValidationError) as caught:
        backwards.clean()
    assert "next_refresh_on" in caught.value.error_dict


def test_riskcompliance_signal_clean_rejects_a_cross_tenant_party(tenant_a,
                                                                  riskcompliance_party_b):
    signal = SupplierRiskSignal(tenant=tenant_a, party=riskcompliance_party_b, provider="dnb",
                                metric="fhr", value=Decimal("60.00"),
                                observed_on=_riskcompliance_today())

    with pytest.raises(ValidationError) as caught:
        signal.full_clean()
    assert "party" in caught.value.error_dict


def test_riskcompliance_breaches_minimum_reads_the_direction_from_the_scale(
        tenant_a, riskcompliance_party_a):
    """A floor of 40 on FHR means "below is bad"; a floor of 5 on SER means "above is bad"."""
    weak_fhr = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "30.00",
                                         provider="rapidratings")
    strong_fhr = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "82.00",
                                           days_ago=1, provider="rapidratings")
    bad_ser = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "7.00")
    good_ser = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "ser_rating", "4.00",
                                         days_ago=1)

    assert weak_fhr.breaches_minimum is True
    assert strong_fhr.breaches_minimum is False
    assert bad_ser.breaches_minimum is True
    assert good_ser.breaches_minimum is False
    assert weak_fhr.minimum_acceptable == Decimal("40")
    assert bad_ser.minimum_acceptable == Decimal("5")


def test_riskcompliance_review_verbs_move_only_from_their_own_state(riskcompliance_signal_fhr,
                                                                    admin_user):
    signal = riskcompliance_signal_fhr
    assert signal.review_status == "new"
    assert signal.is_open is True

    assert signal.mark_reviewed(admin_user, "  Noted.  ") is True
    signal.refresh_from_db()
    assert signal.review_status == "reviewed"
    assert signal.review_note == "Noted."
    assert signal.reviewed_by_id == admin_user.pk
    assert signal.mark_reviewed(admin_user, "Again.") is False

    assert signal.mark_actioned(admin_user, "  ") is False
    assert signal.mark_actioned(admin_user, "Requested a fresh report.") is True
    signal.refresh_from_db()
    assert signal.review_status == "actioned"
    assert signal.is_terminal is True
    assert signal.dismiss(admin_user, "Changed my mind.") is False


def test_riskcompliance_a_review_verb_does_not_redrive_the_derivation(riskcompliance_signal_ser,
                                                                      admin_user):
    """The verbs save with ``update_fields`` that touch no derivation input, so nothing moves."""
    signal = riskcompliance_signal_ser
    before = (signal.risk_position, signal.band, signal.previous_value, signal.trend)

    assert signal.dismiss(admin_user, "Known; mitigation already agreed.") is True

    signal.refresh_from_db()
    assert (signal.risk_position, signal.band, signal.previous_value, signal.trend) == before
    assert signal.review_status == "dismissed"


def test_riskcompliance_signal_derived_columns_are_not_operator_writable():
    for name in ("scale_min", "scale_max", "higher_is_better", "risk_position", "band",
                 "previous_value", "trend", "review_status", "review_note", "reviewed_by",
                 "reviewed_at", "captured_by", "alert"):
        assert SupplierRiskSignal._meta.get_field(name).editable is False, name
    for name in ("value", "observed_on", "provider", "metric", "next_refresh_on", "source_ref"):
        assert SupplierRiskSignal._meta.get_field(name).editable is True, name


def test_riskcompliance_is_stale_reads_the_observation_date(tenant_a, riskcompliance_party_a):
    fresh = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "70.00",
                                      days_ago=SupplierRiskSignal.STALE_AFTER_DAYS,
                                      provider="rapidratings")
    stale = _riskcompliance_mk_signal(tenant_a, riskcompliance_party_a, "fhr", "70.00",
                                      days_ago=SupplierRiskSignal.STALE_AFTER_DAYS + 1,
                                      provider="rapidratings")

    assert fresh.is_stale is False
    assert stale.is_stale is True


# =================================================================================================
# FraudAlert - deterministic rules, idempotent detection
# =================================================================================================


def test_riskcompliance_an_over_long_window_is_refused_without_a_single_query(
        tenant_a, django_assert_num_queries):
    """L40 1: a cap that had to build the range to measure it IS the payload it refuses.

    ``(end - start).days`` is O(1) arithmetic, so an over-long window costs exactly ZERO queries.
    """
    today = _riskcompliance_today()
    start = today - _riskcompliance_days(MAX_SCAN_WINDOW_DAYS + 1)

    with django_assert_num_queries(0):
        assert FraudAlert.scan(tenant_a, start, today) == {}

    with django_assert_num_queries(0):
        assert FraudAlert.scan(tenant_a, today, today) == {}  # end <= start
        assert FraudAlert.scan(tenant_a, today, today - _riskcompliance_days(5)) == {}
        assert FraudAlert.scan(None, start, today) == {}
        assert FraudAlert.scan(tenant_a, None, today) == {}

    assert FraudAlert.objects.count() == 0


def test_riskcompliance_the_window_cap_is_not_off_by_one(tenant_a):
    """Exactly ``MAX_SCAN_WINDOW_DAYS`` is still allowed - the refusal starts one day later."""
    today = _riskcompliance_today()
    allowed = FraudAlert.scan(tenant_a, today - _riskcompliance_days(MAX_SCAN_WINDOW_DAYS), today)

    assert set(allowed) == set(_RISKCOMPLIANCE_RULES)
    assert set(allowed.values()) == {0}  # an empty workspace raises nothing


def test_riskcompliance_an_unknown_rule_name_narrows_the_scan_and_never_raises(tenant_a):
    """The rule list arrives from a POST checkbox group - junk must narrow, never 500 (L11)."""
    today = _riskcompliance_today()

    assert FraudAlert.scan(tenant_a, today - _riskcompliance_days(7), today,
                           rules=["not_a_rule"]) == {}
    assert FraudAlert.scan(tenant_a, today - _riskcompliance_days(7), today, rules=[]) == {}
    mixed = FraudAlert.scan(tenant_a, today - _riskcompliance_days(7), today,
                            rules=["backdated_po", "not_a_rule"])
    assert mixed == {"backdated_po": 0}


def test_riskcompliance_build_dedupe_key_orders_a_party_pair_stably():
    """Same overlap, whichever side the detector walked first - one row, not a mirror image."""
    forward = FraudAlert(rule="vendor_employee_match", vendor_id=7, related_party_id=3)
    backward = FraudAlert(rule="vendor_employee_match", vendor_id=3, related_party_id=7)

    assert forward.build_dedupe_key() == "vem:3:7:manual"
    assert backward.build_dedupe_key() == "vem:3:7:manual"
    assert forward.build_dedupe_key() == forward.build_dedupe_key()

    dup_forward = FraudAlert(rule="duplicate_vendor", vendor_id=12, related_party_id=4)
    dup_backward = FraudAlert(rule="duplicate_vendor", vendor_id=4, related_party_id=12)
    assert dup_forward.build_dedupe_key() == dup_backward.build_dedupe_key() == "dupven:4:12:manual"


def test_riskcompliance_build_dedupe_key_is_deterministic_per_rule():
    assert FraudAlert(rule="self_approval", approval_id=9).build_dedupe_key() == "selfapp:9"
    assert FraudAlert(rule="backdated_po", supplier_invoice_id=5).build_dedupe_key() == "bdpo:5"
    assert (FraudAlert(rule="screening_unresolved", purchase_order_id=41).build_dedupe_key()
            == "scrunres:41")
    assert FraudAlert(rule="new_vendor_rush", vendor_id=2).build_dedupe_key() == "nvrush:2"

    # No usable pointer -> a random token, so a data-entry mistake cannot IntegrityError a POST.
    orphan = FraudAlert(rule="new_vendor_rush")
    first, second = orphan.build_dedupe_key(), orphan.build_dedupe_key()
    assert first.startswith("new_vendor_rush:manual:")
    assert first != second


def test_riskcompliance_scan_raises_vendor_employee_match(tenant_a):
    """R1 - the conflict of interest. The seeded workspace never exercises this rule."""
    vendor = _riskcompliance_mk_party(tenant_a, "Harrogate Tooling Ltd", tax_id="GB-99-1234")
    employee = _riskcompliance_mk_party(tenant_a, "J. Marsden", kind="person",
                                        tax_id="gb991234")
    _riskcompliance_mk_role(tenant_a, vendor, "vendor")
    _riskcompliance_mk_role(tenant_a, employee, "employee")
    today = _riskcompliance_today()

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(30), today,
                             rules=["vendor_employee_match"])

    assert counts == {"vendor_employee_match": 1}
    alert = FraudAlert.objects.get(tenant=tenant_a, rule="vendor_employee_match")
    assert alert.vendor_id == vendor.pk
    assert alert.related_party_id == employee.pk
    assert alert.dedupe_key == f"vem:{min(vendor.pk, employee.pk)}:{max(vendor.pk, employee.pk)}:tax_id"
    assert alert.severity == "high"
    assert alert.status == "open"
    assert alert.amount is None  # an overlap is not a transaction
    assert alert.matched_on.startswith("tax_id")
    assert "GB991234" not in alert.matched_on  # masked, never the raw identifier (L20)
    assert alert.is_pair_rule is True
    assert alert.number.startswith("FRD-")


def test_riskcompliance_scan_raises_vendor_employee_match_on_address_and_contact(tenant_a):
    """The same rule joins on three attributes; each one is its own finding."""
    vendor = _riskcompliance_mk_party(tenant_a, "Calder Print Services")
    employee = _riskcompliance_mk_party(tenant_a, "P. Ahmed", kind="person")
    _riskcompliance_mk_role(tenant_a, vendor, "vendor")
    _riskcompliance_mk_role(tenant_a, employee, "employee")
    _riskcompliance_mk_address(tenant_a, vendor, "12 Mill Lane", "Leeds")
    _riskcompliance_mk_address(tenant_a, employee, "12  MILL LANE", "leeds")
    _riskcompliance_mk_contact(tenant_a, vendor, "p.ahmed@calder.test")
    _riskcompliance_mk_contact(tenant_a, employee, "P.Ahmed@Calder.test")
    today = _riskcompliance_today()

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(30), today,
                             rules=["vendor_employee_match"])

    assert counts == {"vendor_employee_match": 2}
    keys = set(FraudAlert.objects.filter(tenant=tenant_a).values_list("dedupe_key", flat=True))
    low, high = min(vendor.pk, employee.pk), max(vendor.pk, employee.pk)
    assert keys == {f"vem:{low}:{high}:address", f"vem:{low}:{high}:contact"}
    contact_alert = FraudAlert.objects.get(dedupe_key=f"vem:{low}:{high}:contact")
    assert "p.ahmed@calder.test" not in contact_alert.matched_on  # masked local part
    assert "@calder.test" in contact_alert.matched_on


def test_riskcompliance_scan_raises_self_approval(tenant_a, admin_user):
    """R2 - segregation of duties, and the rule with zero false positives in it."""
    requisition = _riskcompliance_mk_requisition(tenant_a, admin_user)
    approval = _riskcompliance_mk_approval(tenant_a, requisition, admin_user)
    today = _riskcompliance_today()

    counts = FraudAlert.scan(tenant_a, today, today + _riskcompliance_days(1),
                             rules=["self_approval"])

    assert counts == {"self_approval": 1}
    alert = FraudAlert.objects.get(tenant=tenant_a, rule="self_approval")
    assert alert.approval_id == approval.pk
    assert alert.requisition_id == requisition.pk
    assert alert.dedupe_key == f"selfapp:{approval.pk}"
    assert alert.severity == "high"
    assert alert.document_date == today
    assert alert.amount == Decimal("0.00")
    assert requisition.number in alert.detail


def test_riskcompliance_scan_leaves_a_properly_segregated_approval_alone(tenant_a, admin_user,
                                                                        riskcompliance_member_a):
    """The negative case that proves the rule is not simply "any approval"."""
    requisition = _riskcompliance_mk_requisition(tenant_a, riskcompliance_member_a)
    _riskcompliance_mk_approval(tenant_a, requisition, admin_user)
    today = _riskcompliance_today()

    counts = FraudAlert.scan(tenant_a, today, today + _riskcompliance_days(1),
                             rules=["self_approval"])

    assert counts == {"self_approval": 0}
    assert FraudAlert.objects.count() == 0


def test_riskcompliance_scan_raises_duplicate_vendor(tenant_a):
    """R3 - two supplier records that reduce to the same company name."""
    first = _riskcompliance_mk_party(tenant_a, "Acme Supplies Ltd")
    second = _riskcompliance_mk_party(tenant_a, "ACME  SUPPLIES LIMITED")
    _riskcompliance_mk_role(tenant_a, first, "vendor")
    _riskcompliance_mk_role(tenant_a, second, "supplier")
    today = _riskcompliance_today()

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(30), today,
                             rules=["duplicate_vendor"])

    assert counts == {"duplicate_vendor": 1}
    alert = FraudAlert.objects.get(tenant=tenant_a, rule="duplicate_vendor")
    low, high = min(first.pk, second.pk), max(first.pk, second.pk)
    assert alert.vendor_id == low  # deterministically the LOWER pk
    assert alert.related_party_id == high
    assert alert.dedupe_key == f"dupven:{low}:{high}:name"
    assert alert.severity == "medium"
    assert alert.amount is None
    assert "FLAGGED ONLY" in alert.detail


def test_riskcompliance_duplicate_vendor_flags_and_never_merges(tenant_a):
    """Supplier-master dedup belongs to 6.4 - a rule that merged would eventually merge two real
    companies. Nothing here may delete, deactivate or rewrite a ``core.Party``."""
    from apps.core.models import Party, PartyRole

    first = _riskcompliance_mk_party(tenant_a, "Acme Supplies Ltd")
    second = _riskcompliance_mk_party(tenant_a, "Acme Supplies Co")
    _riskcompliance_mk_role(tenant_a, first, "vendor")
    _riskcompliance_mk_role(tenant_a, second, "vendor")
    before_parties = sorted(Party.objects.filter(tenant=tenant_a)
                            .values_list("id", "name", "kind", "tax_id"))
    before_roles = sorted(PartyRole.objects.filter(tenant=tenant_a)
                          .values_list("id", "party_id", "role", "status"))
    today = _riskcompliance_today()

    assert FraudAlert.scan(tenant_a, today - _riskcompliance_days(30), today,
                           rules=["duplicate_vendor"]) == {"duplicate_vendor": 1}

    assert sorted(Party.objects.filter(tenant=tenant_a)
                  .values_list("id", "name", "kind", "tax_id")) == before_parties
    assert sorted(PartyRole.objects.filter(tenant=tenant_a)
                  .values_list("id", "party_id", "role", "status")) == before_roles
    assert Party.objects.filter(pk__in=[first.pk, second.pk]).count() == 2


def test_riskcompliance_scan_raises_backdated_po(tenant_a):
    """R4 - the order was written AFTER the invoice it is supposed to authorise."""
    vendor = _riskcompliance_mk_party(tenant_a, "Pennine Logistics")
    today = _riskcompliance_today()
    invoice_date = today - _riskcompliance_days(6)
    order = _riskcompliance_mk_po(tenant_a, vendor, order_date=today, total="5000.00")
    invoice = _riskcompliance_mk_invoice(tenant_a, vendor, invoice_date, total="5000.00",
                                         invoice_number="PL-8891", purchase_order=order)

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(10),
                             today + _riskcompliance_days(1), rules=["backdated_po"])

    assert counts == {"backdated_po": 1}
    alert = FraudAlert.objects.get(tenant=tenant_a, rule="backdated_po")
    assert alert.supplier_invoice_id == invoice.pk
    assert alert.purchase_order_id == order.pk
    assert alert.vendor_id == vendor.pk
    assert alert.document_date == invoice_date  # the date of the FACT, not of detection
    assert alert.amount == Decimal("5000.00")
    assert alert.dedupe_key == f"bdpo:{invoice.pk}"
    assert alert.severity == "medium"


def test_riskcompliance_a_days_clerical_lag_is_not_a_backdated_order(tenant_a):
    """BACKDATE_GRACE_DAYS is 1: a day later is paperwork, a fortnight is a story."""
    vendor = _riskcompliance_mk_party(tenant_a, "Wharfe Instruments")
    today = _riskcompliance_today()
    invoice_date = today - _riskcompliance_days(3)
    order = _riskcompliance_mk_po(tenant_a, vendor,
                                  order_date=invoice_date + _riskcompliance_days(1))
    _riskcompliance_mk_invoice(tenant_a, vendor, invoice_date, invoice_number="WI-2",
                              purchase_order=order)

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(10),
                             today + _riskcompliance_days(1), rules=["backdated_po"])

    assert counts == {"backdated_po": 0}
    assert FraudAlert.objects.count() == 0


def test_riskcompliance_scan_raises_screening_unresolved(tenant_a):
    """R5 - the cross-link: new spend against a sanctions match nobody adjudicated."""
    vendor = _riskcompliance_mk_party(tenant_a, "Kestrel Marine Supply")
    today = _riskcompliance_today()
    screening = _riskcompliance_mk_screening(tenant_a, vendor, result="potential_match",
                                             screened_on=today - _riskcompliance_days(4))
    _riskcompliance_mk_hit(screening, "KESTREL MARINE LLC", 94)  # disposition stays open
    order = _riskcompliance_mk_po(tenant_a, vendor, order_date=today - _riskcompliance_days(1),
                                  total="9000.00")

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(10),
                             today + _riskcompliance_days(1), rules=["screening_unresolved"])

    assert counts == {"screening_unresolved": 1}
    alert = FraudAlert.objects.get(tenant=tenant_a, rule="screening_unresolved")
    assert alert.purchase_order_id == order.pk
    assert alert.screening_id == screening.pk
    assert alert.vendor_id == vendor.pk
    assert alert.amount == Decimal("9000.00")
    assert alert.dedupe_key == f"scrunres:{order.pk}"
    assert alert.severity == "high"
    assert "nobody has adjudicated" in alert.detail


def test_riskcompliance_a_screening_found_after_the_order_is_not_the_buyers_fault(tenant_a):
    """Only a screening dated ON OR BEFORE the order counts - anything else is hindsight."""
    vendor = _riskcompliance_mk_party(tenant_a, "Ouse Valley Castings")
    today = _riskcompliance_today()
    screening = _riskcompliance_mk_screening(tenant_a, vendor, result="potential_match",
                                             screened_on=today)
    _riskcompliance_mk_hit(screening, "OUSE VALLEY OOO", 91)
    _riskcompliance_mk_po(tenant_a, vendor, order_date=today - _riskcompliance_days(5))

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(10),
                             today + _riskcompliance_days(1), rules=["screening_unresolved"])

    assert counts == {"screening_unresolved": 0}
    assert FraudAlert.objects.count() == 0


def test_riskcompliance_scan_raises_new_vendor_rush(tenant_a):
    """R6 - a brand-new supplier taking high-value spend before it has any history."""
    vendor = _riskcompliance_mk_party(tenant_a, "Swift Components Trading")
    _riskcompliance_mk_role(tenant_a, vendor, "vendor")
    today = _riskcompliance_today()
    biggest = _riskcompliance_mk_invoice(tenant_a, vendor, today, total="30000.00",
                                         invoice_number="SCT-1")
    _riskcompliance_mk_invoice(tenant_a, vendor, today, total="18000.00", invoice_number="SCT-2")

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(2),
                             today + _riskcompliance_days(1), rules=["new_vendor_rush"])

    assert counts == {"new_vendor_rush": 1}
    alert = FraudAlert.objects.get(tenant=tenant_a, rule="new_vendor_rush")
    assert alert.vendor_id == vendor.pk
    assert alert.supplier_invoice_id == biggest.pk  # the LARGEST single invoice in the run
    assert alert.amount == Decimal("48000.00")
    assert alert.document_date == today
    assert alert.dedupe_key == f"nvrush:{vendor.pk}"
    assert alert.severity == "medium"
    assert "2 invoices" in alert.matched_on


def test_riskcompliance_a_new_vendor_under_the_threshold_is_not_a_rush(tenant_a):
    vendor = _riskcompliance_mk_party(tenant_a, "Quiet Start Supplies")
    _riskcompliance_mk_role(tenant_a, vendor, "vendor")
    today = _riskcompliance_today()
    _riskcompliance_mk_invoice(tenant_a, vendor, today, total="24999.99", invoice_number="QSS-1")

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(2),
                             today + _riskcompliance_days(1), rules=["new_vendor_rush"])

    assert counts == {"new_vendor_rush": 0}
    assert FraudAlert.objects.count() == 0


def test_riskcompliance_scan_is_idempotent(tenant_a):
    """A second pass over the same window raises NOTHING and re-opens NOTHING."""
    vendor = _riskcompliance_mk_party(tenant_a, "Ribble Fabrication")
    today = _riskcompliance_today()
    invoice_date = today - _riskcompliance_days(6)
    order = _riskcompliance_mk_po(tenant_a, vendor, order_date=today, total="7500.00")
    _riskcompliance_mk_invoice(tenant_a, vendor, invoice_date, total="7500.00",
                               invoice_number="RF-4410", purchase_order=order)
    window = (today - _riskcompliance_days(10), today + _riskcompliance_days(1))

    assert FraudAlert.scan(tenant_a, *window, rules=["backdated_po"]) == {"backdated_po": 1}
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 1
    assert FraudAlert.scan(tenant_a, *window, rules=["backdated_po"]) == {"backdated_po": 0}
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 1


def test_riskcompliance_a_rescan_never_reopens_a_disposed_alert(tenant_a, admin_user):
    """An alert somebody already dispositioned keeps its disposition; only its facts refresh."""
    vendor = _riskcompliance_mk_party(tenant_a, "Aire Valley Plastics")
    today = _riskcompliance_today()
    invoice_date = today - _riskcompliance_days(8)
    order = _riskcompliance_mk_po(tenant_a, vendor, order_date=today, total="3300.00")
    _riskcompliance_mk_invoice(tenant_a, vendor, invoice_date, total="3300.00",
                               invoice_number="AVP-77", purchase_order=order)
    window = (today - _riskcompliance_days(20), today + _riskcompliance_days(1))
    FraudAlert.scan(tenant_a, *window, rules=["backdated_po"])
    alert = FraudAlert.objects.get(tenant=tenant_a, rule="backdated_po")
    assert alert.unsubstantiate(admin_user, "Order was raised late by the buyer; goods predate.") \
        is True
    alert.refresh_from_db()
    resolved_at = alert.resolved_at

    assert FraudAlert.scan(tenant_a, *window, rules=["backdated_po"]) == {"backdated_po": 0}

    alert.refresh_from_db()
    assert alert.status == "unsubstantiated"
    assert alert.resolution_note == "Order was raised late by the buyer; goods predate."
    assert alert.resolved_by_id == admin_user.pk
    assert alert.resolved_at == resolved_at
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 1


def test_riskcompliance_scan_writes_only_fraud_alert_rows(tenant_a, admin_user):
    """Detection SUGGESTS. Nothing on the spine, in core, or in the screening register moves."""
    from apps.core.models import Address, Party
    from apps.scm.models import PurchaseOrder

    today = _riskcompliance_today()
    vendor = _riskcompliance_mk_party(tenant_a, "Trent Bearing Company", tax_id="GB-55-7788")
    insider = _riskcompliance_mk_party(tenant_a, "L. Grover", kind="person", tax_id="gb557788")
    _riskcompliance_mk_role(tenant_a, vendor, "vendor")
    _riskcompliance_mk_role(tenant_a, insider, "employee")
    _riskcompliance_mk_address(tenant_a, vendor, "4 Canal Wharf", "Nottingham")
    screening = _riskcompliance_mk_screening(tenant_a, vendor, result="potential_match",
                                             screened_on=today - _riskcompliance_days(5))
    _riskcompliance_mk_hit(screening, "TRENT BEARING CO", 92)
    _riskcompliance_mk_po(tenant_a, vendor, order_date=today - _riskcompliance_days(1),
                          total="4100.00")
    counts_before = {
        "party": Party.objects.count(),
        "address": Address.objects.count(),
        "order": PurchaseOrder.objects.count(),
        "screening": ComplianceScreening.objects.count(),
        "hit": ScreeningHit.objects.count(),
    }
    party_rows_before = sorted(Party.objects.values_list("id", "name", "tax_id"))
    screening_rows_before = sorted(ComplianceScreening.objects.values_list("id", "status",
                                                                          "result"))

    raised = FraudAlert.scan(tenant_a, today - _riskcompliance_days(30),
                             today + _riskcompliance_days(1), user=admin_user)

    assert sum(raised.values()) == 2  # vendor_employee_match + screening_unresolved
    assert FraudAlert.objects.count() == 2
    assert Party.objects.count() == counts_before["party"]
    assert Address.objects.count() == counts_before["address"]
    assert PurchaseOrder.objects.count() == counts_before["order"]
    assert ComplianceScreening.objects.count() == counts_before["screening"]
    assert ScreeningHit.objects.count() == counts_before["hit"]
    assert sorted(Party.objects.values_list("id", "name", "tax_id")) == party_rows_before
    assert sorted(ComplianceScreening.objects.values_list("id", "status", "result")) \
        == screening_rows_before


def test_riskcompliance_scan_never_reaches_another_workspace(tenant_a, tenant_b):
    """Every source queryset is tenant-scoped; B's identical overlap is B's business."""
    for tenant, prefix in ((tenant_a, "A"), (tenant_b, "B")):
        vendor = _riskcompliance_mk_party(tenant, f"{prefix} Ridings Cabling",
                                          tax_id="GB-13-9000")
        person = _riskcompliance_mk_party(tenant, f"{prefix} K. Doyle", kind="person",
                                          tax_id="gb139000")
        _riskcompliance_mk_role(tenant, vendor, "vendor")
        _riskcompliance_mk_role(tenant, person, "employee")
    today = _riskcompliance_today()

    counts = FraudAlert.scan(tenant_a, today - _riskcompliance_days(30), today,
                             rules=["vendor_employee_match"])

    assert counts == {"vendor_employee_match": 1}
    assert FraudAlert.objects.filter(tenant=tenant_a).count() == 1
    assert FraudAlert.objects.filter(tenant=tenant_b).count() == 0
    alert = FraudAlert.objects.get(tenant=tenant_a)
    assert alert.vendor.tenant_id == tenant_a.pk
    assert alert.related_party.tenant_id == tenant_a.pk


def test_riskcompliance_fraud_clean_requires_a_pointer_and_refuses_a_foreign_one(
        tenant_a, riskcompliance_party_b):
    pointerless = FraudAlert(tenant=tenant_a, rule="new_vendor_rush",
                             document_date=_riskcompliance_today())
    with pytest.raises(ValidationError) as caught:
        pointerless.clean()
    assert "vendor" in caught.value.error_dict

    foreign = FraudAlert(tenant=tenant_a, rule="new_vendor_rush", vendor=riskcompliance_party_b,
                         document_date=_riskcompliance_today())
    with pytest.raises(ValidationError) as caught:
        foreign.clean()
    assert "vendor" in caught.value.error_dict
    assert "another workspace" in str(caught.value.error_dict["vendor"][0])


def test_riskcompliance_fraud_clean_refuses_a_duplicate_evidence_key(riskcompliance_fraud_open,
                                                                     tenant_a,
                                                                     riskcompliance_party_a):
    """A hand-raised second alert for the same evidence is a friendly error, not a 500."""
    twin = FraudAlert(tenant=tenant_a, vendor=riskcompliance_party_a, rule="new_vendor_rush",
                      document_date=_riskcompliance_today(), amount=Decimal("100.00"))

    with pytest.raises(ValidationError) as caught:
        twin.clean()
    assert "rule" in caught.value.error_dict
    assert "already exists" in str(caught.value.error_dict["rule"][0])


def test_riskcompliance_fraud_clean_refuses_a_non_finite_amount(tenant_a,
                                                                riskcompliance_party_a):
    alert = FraudAlert(tenant=tenant_a, vendor=riskcompliance_party_a, rule="new_vendor_rush",
                       document_date=_riskcompliance_today(), amount=Decimal("NaN"))

    with pytest.raises(ValidationError) as caught:
        alert.clean()
    assert "amount" in caught.value.error_dict


def test_riskcompliance_fraud_disposition_verbs_require_a_note(riskcompliance_fraud_open,
                                                               admin_user):
    alert = riskcompliance_fraud_open
    assert alert.status == "open"

    assert alert.unsubstantiate(admin_user, "  ") is False
    assert alert.substantiate(admin_user, "") is False
    assert alert.refer(admin_user, None) is False
    alert.refresh_from_db()
    assert alert.status == "open"

    assert alert.investigate(admin_user) is True
    alert.refresh_from_db()
    assert alert.status == "investigating"
    assert alert.refer(admin_user, "Handed to internal audit.") is True
    alert.refresh_from_db()
    assert alert.status == "referred"
    assert alert.is_terminal is True
    assert alert.investigate(admin_user) is False


def test_riskcompliance_a_substantiated_alert_is_terminal(riskcompliance_fraud_resolved,
                                                          admin_user):
    alert = riskcompliance_fraud_resolved
    assert alert.status == "substantiated"
    assert alert.resolved_by_id == admin_user.pk
    assert alert.resolved_at is not None
    assert alert.is_open is False

    assert alert.unsubstantiate(admin_user, "Actually a false positive.") is False
    alert.refresh_from_db()
    assert alert.status == "substantiated"


def test_riskcompliance_fraud_governance_columns_are_not_operator_writable():
    for name in ("dedupe_key", "status", "resolution_note", "resolved_by", "resolved_at",
                 "suspension"):
        assert FraudAlert._meta.get_field(name).editable is False, name
    # severity stays writable on purpose: a reviewer re-grades a row the engine over-called.
    assert FraudAlert._meta.get_field("severity").editable is True
    assert FraudAlert._meta.unique_together == (("tenant", "number"), ("tenant", "dedupe_key"))


# =================================================================================================
# PolicyAttestation - the sign-off ledger
# =================================================================================================


def test_riskcompliance_a_policy_that_needs_no_acknowledgment_raises_no_rows(
        riskcompliance_policy_no_ack, admin_user, riskcompliance_member_a):
    """6.19's flag is the workspace's statement of intent - a ledger that ignored it would be
    decorative. The refusal is a SENTENCE, never a silent zero."""
    result = raise_attestations(riskcompliance_policy_no_ack, user=admin_user)

    assert (result.created, result.existing, result.audience) == (0, 0, 0)
    assert "not marked as requiring acknowledgment" in result.refusal
    assert PolicyAttestation.objects.filter(policy=riskcompliance_policy_no_ack).count() == 0
    assert PolicyAttestation.objects.count() == 0


def test_riskcompliance_only_a_published_policy_raises_a_roster(riskcompliance_policy_draft,
                                                                riskcompliance_policy_published,
                                                                admin_user):
    """A draft is not yet the rule; an archived one is no longer it."""
    draft_result = raise_attestations(riskcompliance_policy_draft, user=admin_user)
    assert (draft_result.created, draft_result.existing) == (0, 0)
    assert "published policy" in draft_result.refusal
    assert PolicyAttestation.objects.filter(policy=riskcompliance_policy_draft).count() == 0

    archived = riskcompliance_policy_published
    archived.status = "archived"
    archived.save(update_fields=["status", "updated_at"])
    archived_result = raise_attestations(archived, user=admin_user)
    assert (archived_result.created, archived_result.existing) == (0, 0)
    assert "published policy" in archived_result.refusal
    assert PolicyAttestation.objects.count() == 0


def test_riskcompliance_raising_a_roster_creates_one_row_per_active_person(
        riskcompliance_policy_published, admin_user, riskcompliance_member_a):
    policy = riskcompliance_policy_published
    audience = list(resolve_audience(policy))
    assert {person.pk for person in audience} == {admin_user.pk, riskcompliance_member_a.pk}

    result = raise_attestations(policy, user=admin_user)

    assert (result.created, result.existing, result.audience) == (2, 0, 2)
    assert result.refusal is None
    rows = PolicyAttestation.objects.filter(policy=policy)
    assert rows.count() == 2
    assert set(rows.values_list("user_id", flat=True)) == {admin_user.pk,
                                                           riskcompliance_member_a.pk}
    assert set(rows.values_list("status", flat=True)) == {"pending"}
    assert set(rows.values_list("due_on", flat=True)) == {
        _riskcompliance_today() + _riskcompliance_days(DEFAULT_ATTESTATION_DUE_DAYS)}


def test_riskcompliance_raising_is_idempotent_and_leaves_a_signature_byte_identical(
        riskcompliance_attestation_signed, riskcompliance_member_a, admin_user):
    """The repair button: pressing it again adds nobody and disturbs nothing already on file."""
    signed = riskcompliance_attestation_signed
    policy = signed.policy
    before = (signed.status, signed.acknowledged_at, signed.acknowledgement_note, signed.due_on)

    first = raise_attestations(policy, user=admin_user)
    assert (first.created, first.existing, first.audience) == (1, 1, 2)

    second = raise_attestations(policy, user=admin_user)
    assert (second.created, second.existing, second.audience) == (0, 2, 2)
    assert second.refusal is None

    assert PolicyAttestation.objects.filter(policy=policy).count() == 2
    signed.refresh_from_db()
    assert (signed.status, signed.acknowledged_at, signed.acknowledgement_note,
            signed.due_on) == before


def test_riskcompliance_a_repair_run_never_moves_a_deadline(riskcompliance_attestation_pending,
                                                            admin_user):
    """``due_on`` is stamped only in ``defaults`` - nobody's clock is reset by a second press."""
    pending = riskcompliance_attestation_pending
    original_due = pending.due_on

    raise_attestations(pending.policy, user=admin_user, due_days=1)

    pending.refresh_from_db()
    assert pending.due_on == original_due
    assert pending.status == "pending"


def test_riskcompliance_raising_on_v2_leaves_v1_rows_untouched(riskcompliance_policy_published,
                                                               riskcompliance_member_a,
                                                               admin_user, tenant_a):
    """A row keys on ONE policy row, so v1's signatures stay true statements about v1."""
    from apps.procurement.models import ProcurementPolicy

    v1 = riskcompliance_policy_published
    raise_attestations(v1, user=admin_user)
    v1_rows = sorted(PolicyAttestation.objects.filter(policy=v1)
                     .values_list("id", "user_id", "status", "due_on"))
    assert len(v1_rows) == 2

    v2 = ProcurementPolicy.objects.create(
        tenant=tenant_a, title=v1.title, policy_type=v1.policy_type, version_number="2.0",
        previous_version=v1, status="published", published_at=timezone.now(),
        summary="Second version.", body="Read it again.", requires_acknowledgment=True,
        effective_from=_riskcompliance_today(), owner=admin_user, created_by=admin_user)

    result = raise_attestations(v2, user=admin_user)

    assert (result.created, result.existing) == (2, 0)
    assert sorted(PolicyAttestation.objects.filter(policy=v1)
                  .values_list("id", "user_id", "status", "due_on")) == v1_rows
    assert PolicyAttestation.objects.filter(policy=v2).count() == 2
    v1_ids = {row[0] for row in v1_rows}
    v2_ids = set(PolicyAttestation.objects.filter(policy=v2).values_list("id", flat=True))
    assert v1_ids.isdisjoint(v2_ids)


def test_riskcompliance_acknowledge_is_owner_only_at_the_model_layer(
        riskcompliance_attestation_pending, riskcompliance_member_a, admin_user):
    """A signature an administrator could apply on somebody's behalf records nothing.

    The guard is in the MODEL, not only in the view: a tenant admin and a superuser are BOTH
    refused, and the only honest administrative answer is ``mark_exempt``.
    """
    attestation = riskcompliance_attestation_pending
    assert attestation.user_id == riskcompliance_member_a.pk

    assert attestation.acknowledge(admin_user, "Signing for them.") is False
    assert attestation.acknowledge(_riskcompliance_mk_superuser(), "Root override.") is False
    assert attestation.acknowledge(None, "Anonymous.") is False
    attestation.refresh_from_db()
    assert attestation.status == "pending"
    assert attestation.acknowledged_at is None
    assert attestation.acknowledgement_note == ""

    assert attestation.acknowledge(riskcompliance_member_a, "  Read in full.  ") is True
    attestation.refresh_from_db()
    assert attestation.status == "acknowledged"
    assert attestation.is_terminal is True
    assert attestation.acknowledged_at is not None
    assert attestation.acknowledgement_note == "Read in full."

    # No un-sign: a withdrawn signature is a second, contradictory claim about the same day.
    assert attestation.acknowledge(riskcompliance_member_a, "Actually, no.") is False


def test_riskcompliance_mark_exempt_requires_a_reason_and_names_the_grantor(
        riskcompliance_attestation_pending, admin_user):
    attestation = riskcompliance_attestation_pending

    assert attestation.mark_exempt(admin_user, "   ") is False
    attestation.refresh_from_db()
    assert attestation.status == "pending"

    assert attestation.mark_exempt(admin_user, "Contractor; covered by the agency's own code.") \
        is True
    attestation.refresh_from_db()
    assert attestation.status == "exempt"
    assert attestation.exempt_reason == "Contractor; covered by the agency's own code."
    assert attestation.exempted_by_id == admin_user.pk
    assert attestation.exempted_at is not None
    assert attestation.mark_exempt(admin_user, "Again.") is False


def test_riskcompliance_overdue_derives_from_localdate_never_a_stored_flag(
        riskcompliance_attestation_overdue, riskcompliance_attestation_pending):
    overdue = riskcompliance_attestation_overdue
    pending = riskcompliance_attestation_pending

    assert overdue.due_on == _riskcompliance_today() - _riskcompliance_days(21)
    assert overdue.is_overdue is True
    assert overdue.days_late == 21
    assert overdue.status == "pending"
    assert pending.is_overdue is False
    assert pending.days_late == -10
    assert "is_overdue" not in {field.name for field in PolicyAttestation._meta.get_fields()}

    # A settled row is never overdue, whatever its date says.
    assert overdue.mark_exempt(overdue.user, "Left the company.") is True
    overdue.refresh_from_db()
    assert overdue.is_overdue is False


def test_riskcompliance_one_person_owes_one_policy_once(riskcompliance_attestation_pending,
                                                        riskcompliance_member_a):
    duplicate = PolicyAttestation(tenant=riskcompliance_attestation_pending.tenant,
                                  policy=riskcompliance_attestation_pending.policy,
                                  user=riskcompliance_member_a,
                                  due_on=_riskcompliance_today())

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            duplicate.save()

    assert PolicyAttestation._meta.unique_together == (("tenant", "policy", "user"),)


def test_riskcompliance_attestation_clean_refuses_an_unpublished_policy_and_a_foreign_user(
        riskcompliance_policy_draft, riskcompliance_member_a, tenant_a, admin_b):
    against_draft = PolicyAttestation(tenant=tenant_a, policy=riskcompliance_policy_draft,
                                      user=riskcompliance_member_a)
    with pytest.raises(ValidationError) as caught:
        against_draft.clean()
    assert "policy" in caught.value.error_dict

    foreign_signer = PolicyAttestation(tenant=tenant_a, policy=riskcompliance_policy_draft,
                                       user=admin_b)
    with pytest.raises(ValidationError) as caught:
        foreign_signer.clean()
    assert "user" in caught.value.error_dict


def test_riskcompliance_attestation_evidence_columns_are_not_operator_writable():
    for name in ("status", "acknowledged_at", "acknowledgement_note", "exempt_reason",
                 "exempted_by", "exempted_at", "alert"):
        assert PolicyAttestation._meta.get_field(name).editable is False, name
    assert PolicyAttestation._meta.get_field("due_on").editable is True


# =================================================================================================
# AuditSeal - tamper EVIDENCE
# =================================================================================================


def test_riskcompliance_a_seal_is_valid_immediately_after_sealing(riskcompliance_seal,
                                                                  admin_user):
    seal = riskcompliance_seal
    assert seal.row_count == 3
    assert seal.prev_seal_id is None
    assert seal.prev_digest == GENESIS_DIGEST
    assert seal.algorithm == "sha256"
    assert len(seal.digest) == 64
    assert len(seal.row_fingerprints) == 3

    ok, detail = seal.verify(user=admin_user)

    assert ok is True
    assert "Verified" in detail
    assert str(seal.row_count) in detail
    seal.refresh_from_db()
    assert seal.last_verify_ok is True
    assert seal.last_verified_at is not None
    assert seal.last_verified_by_id == admin_user.pk
    assert seal.verify_state == "verified"


def test_riskcompliance_modifying_a_sealed_entry_breaks_verify_and_names_the_row(
        riskcompliance_seal, admin_user):
    """The module's one real claim: not "something changed" but WHICH entry changed."""
    from apps.core.models import AuditLog

    seal = riskcompliance_seal
    log_ids = _riskcompliance_sealed_log_ids(seal)
    assert len(log_ids) == 3
    victim = log_ids[1]
    AuditLog.objects.filter(pk=victim).update(target="Rewritten long after the fact")

    ok, detail = seal.verify(user=admin_user)

    assert ok is False
    assert "MODIFIED" in detail
    assert f"#{victim}" in detail
    assert seal.number in detail
    seal.refresh_from_db()
    assert seal.last_verify_ok is False
    assert seal.verify_state == "broken"


def test_riskcompliance_deleting_a_sealed_entry_breaks_verify_and_names_the_row(
        riskcompliance_seal, admin_user):
    from apps.core.models import AuditLog

    seal = riskcompliance_seal
    log_ids = _riskcompliance_sealed_log_ids(seal)
    victim = log_ids[1]
    AuditLog.objects.filter(pk=victim).delete()

    ok, detail = seal.verify(user=admin_user)

    assert ok is False
    assert "DELETED" in detail
    assert f"#{victim}" in detail
    assert "1 of 3" in detail


def test_riskcompliance_an_entry_inserted_into_a_sealed_range_is_detected(tenant_a, tenant_b,
                                                                          admin_user, admin_b):
    """Ids are monotonic, so a row can only appear INSIDE a sealed range by hand.

    The interior slot is made the way it exists in real life - another workspace's row sat there
    and was removed - and a fresh tenant-A entry is then landed on that id. The seal never covered
    it, and the verifier says so and names it.
    """
    from apps.core.models import AuditLog

    a_first, = _riskcompliance_mk_audit_rows(tenant_a, admin_user, count=1, target="Acme one")
    b_middle, = _riskcompliance_mk_audit_rows(tenant_b, admin_b, count=1, target="Globex one")
    a_last, = _riskcompliance_mk_audit_rows(tenant_a, admin_user, count=1, target="Acme two")
    seal, _message = AuditSeal.seal_now(tenant_a, admin_user, note="Before the insert.")
    assert seal.row_count == 2
    assert (seal.from_log_id, seal.to_log_id) == (a_first.pk, a_last.pk)
    assert seal.verify(stamp=False)[0] is True

    AuditLog.objects.filter(pk=b_middle.pk).delete()  # free the interior id
    smuggled = AuditLog.objects.create(tenant=tenant_a, user=admin_user, action="delete",
                                       target="Smuggled entry", changes={})
    AuditLog.objects.filter(pk=smuggled.pk).update(id=b_middle.pk)

    ok, detail = seal.verify()

    assert ok is False
    assert "INSERTED" in detail
    assert f"#{b_middle.pk}" in detail


def test_riskcompliance_seal_ranges_are_id_keyed_not_time_keyed(riskcompliance_seal, tenant_a,
                                                                admin_user):
    """A row written LATER but stamped OLDER must not be silently swallowed.

    A time-keyed seal would either miss it entirely or claim to cover it; an id-keyed one puts it
    in the NEXT seal, where it belongs, and leaves the first seal's proof intact.
    """
    from apps.core.models import AuditLog

    first = riskcompliance_seal
    latecomer = AuditLog.objects.create(tenant=tenant_a, user=admin_user, action="update",
                                        target="Backdated arrival", changes={})
    older_than_the_seal = first.period_start - _riskcompliance_days(30)
    AuditLog.objects.filter(pk=latecomer.pk).update(at=older_than_the_seal)

    second, message = AuditSeal.seal_now(tenant_a, admin_user, note="Catch-up seal.")

    assert second is not None
    assert second.from_log_id == latecomer.pk
    assert second.to_log_id == latecomer.pk
    assert second.row_count == 1
    assert second.period_start < first.period_start  # metadata is NOT the authority on coverage
    assert latecomer.pk > first.to_log_id  # the id is what decided which seal covers it
    assert first.verify()[0] is True
    assert second.verify()[0] is True
    assert str(second.row_count) in message


def test_riskcompliance_a_second_seal_chains_onto_the_first(riskcompliance_seal, tenant_a,
                                                            admin_user):
    first = riskcompliance_seal
    _riskcompliance_mk_audit_rows(tenant_a, admin_user, count=2, target="Later change")

    second, message = AuditSeal.seal_now(tenant_a, admin_user, note="Second seal.")

    assert second is not None
    assert second.prev_seal_id == first.pk
    assert second.prev_digest == first.chain_digest
    assert second.chain_digest == AuditSeal.chain_value(second.prev_digest, second.digest)
    assert second.from_log_id > first.to_log_id
    assert second.row_count == 2
    assert second.number == "ASL-00002"
    assert second.link_state()[0] is True
    assert first.link_state()[0] is True  # genesis
    assert AuditSeal.verify_chain(tenant_a)[0] is True


def test_riskcompliance_sealing_twice_with_no_new_rows_is_a_no_op(riskcompliance_seal, tenant_a,
                                                                  admin_user):
    """An empty seal is chain spam that proves nothing, so the button refuses with a sentence."""
    seal = riskcompliance_seal

    again, message = AuditSeal.seal_now(tenant_a, admin_user, note="Nothing new.")

    assert again is None
    assert seal.number in message
    assert "empty seal" in message
    assert AuditSeal.objects.filter(tenant=tenant_a).count() == 1


def test_riskcompliance_sealing_an_empty_workspace_is_refused(tenant_b, admin_b):
    seal, message = AuditSeal.seal_now(tenant_b, admin_b)

    assert seal is None
    assert "no audit entries" in message
    assert AuditSeal.objects.filter(tenant=tenant_b).count() == 0
    assert AuditSeal.seal_now(None, admin_b)[0] is None


def test_riskcompliance_a_seal_never_covers_another_workspaces_rows(tenant_a, tenant_b,
                                                                    admin_user, admin_b):
    """Ids interleave in one table; the seal is scoped in both directions."""
    from apps.core.models import AuditLog

    a_rows, b_rows = [], []
    for index in range(3):
        a_rows.extend(_riskcompliance_mk_audit_rows(tenant_a, admin_user, count=1,
                                                    target=f"Acme change {index}"))
        b_rows.extend(_riskcompliance_mk_audit_rows(tenant_b, admin_b, count=1,
                                                    target=f"Globex change {index}"))
    a_ids = [row.pk for row in a_rows]
    b_ids = [row.pk for row in b_rows]
    assert min(b_ids) > min(a_ids) and max(b_ids) > max(a_ids)  # genuinely interleaved

    seal, _message = AuditSeal.seal_now(tenant_a, admin_user, note="Acme month end.")

    assert seal is not None
    assert seal.row_count == 3
    assert set(seal.fingerprint_map) == set(a_ids)
    assert set(seal.fingerprint_map).isdisjoint(b_ids)
    assert seal.from_log_id == min(a_ids) and seal.to_log_id == max(a_ids)
    # B's rows sit INSIDE that id range - changing and deleting them must not touch A's proof.
    AuditLog.objects.filter(pk=b_ids[0]).update(target="Globex rewrote this")
    AuditLog.objects.filter(pk=b_ids[1]).delete()
    ok, detail = seal.verify()
    assert ok is True, detail


def test_riskcompliance_a_seal_number_is_per_tenant(tenant_a, tenant_b, admin_user, admin_b):
    _riskcompliance_mk_audit_rows(tenant_a, admin_user, count=1)
    _riskcompliance_mk_audit_rows(tenant_b, admin_b, count=1)

    a_seal, _a_message = AuditSeal.seal_now(tenant_a, admin_user)
    b_seal, _b_message = AuditSeal.seal_now(tenant_b, admin_b)

    assert a_seal.number == b_seal.number == "ASL-00001"
    assert AuditSeal.objects.filter(number="ASL-00001").count() == 2


def test_riskcompliance_canonical_serialisation_is_pinned(riskcompliance_seal):
    """Changing a separator would read every seal ever taken as broken with no tampering."""
    from apps.core.models import AuditLog

    seal = riskcompliance_seal
    rows = list(AuditLog.objects.filter(tenant_id=seal.tenant_id,
                                        id__gte=seal.from_log_id, id__lte=seal.to_log_id)
                .order_by("id"))
    line = AuditSeal.canonical_line(rows[0])

    assert line.split("|")[0] == str(rows[0].id)
    assert line.count("|") == 7
    assert AuditSeal.compute_digest(rows) == seal.digest
    assert AuditSeal.row_fingerprint(rows[0]) == seal.row_fingerprints[0][1]
    assert len(AuditSeal.row_fingerprint(rows[0])) == AuditSeal.FINGERPRINT_CHARS
    assert AuditSeal.chain_value(GENESIS_DIGEST, seal.digest) == seal.chain_digest


def test_riskcompliance_no_seal_digest_column_is_writable(riskcompliance_seal):
    """No edit route and no delete route: a digest a form could set proves nothing."""
    for name in ("from_log_id", "to_log_id", "period_start", "period_end", "row_count", "digest",
                 "prev_seal", "prev_digest", "chain_digest", "algorithm", "row_fingerprints",
                 "sealed_by", "last_verified_at", "last_verify_ok", "last_verify_detail",
                 "last_verified_by"):
        assert AuditSeal._meta.get_field(name).editable is False, name
    # ``note`` is the ONLY field anybody types on this record.
    assert AuditSeal._meta.get_field("note").editable is True
    assert str(riskcompliance_seal).startswith(riskcompliance_seal.number)


def test_riskcompliance_chain_links_report_state_without_reading_the_log(riskcompliance_seal,
                                                                        tenant_a, admin_user,
                                                                        django_assert_max_num_queries):
    seal = riskcompliance_seal
    seal.verify(user=admin_user)

    with django_assert_max_num_queries(2):
        links = AuditSeal.chain_links(tenant_a)

    assert len(links) == 1
    row = links[0]
    assert row["pk"] == seal.pk
    assert row["number"] == seal.number
    assert row["row_count"] == 3
    assert row["range"] == f"#{seal.from_log_id} - #{seal.to_log_id}"
    assert row["linked"] is True
    assert row["verified"] is True
    assert row["state"] == "verified"
    assert row["state_css"] == "badge-green"
    assert row["digest_short"] == seal.chain_digest[:12]
    assert AuditSeal.chain_links(None) == []


def test_riskcompliance_verify_chain_reports_a_broken_seal(riskcompliance_seal, tenant_a,
                                                           admin_user):
    from apps.core.models import AuditLog

    seal = riskcompliance_seal
    log_ids = _riskcompliance_sealed_log_ids(seal)
    AuditLog.objects.filter(pk=log_ids[0]).update(target="Rewritten by hand")
    seal.verify(user=admin_user)

    ok, first_broken, detail = AuditSeal.verify_chain(tenant_a)

    assert ok is False
    assert first_broken["number"] == seal.number
    assert seal.number in detail
    assert f"#{log_ids[0]}" in detail


def test_riskcompliance_verify_can_run_without_stamping(riskcompliance_seal):
    seal = riskcompliance_seal

    ok, _detail = seal.verify(stamp=False)

    assert ok is True
    seal.refresh_from_db()
    assert seal.last_verify_ok is None
    assert seal.last_verified_at is None
    assert seal.verify_state == "unverified"
