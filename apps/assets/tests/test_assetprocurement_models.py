"""Asset Procurement & Acquisition (11.1) — MODEL Invariants Test Suite.

Covers the 4 core models:
- AssetRequisition [AREQ-]
- AssetAcquisitionReceipt [ARCV-]
- AssetCapitalization [ACAP-]
- AssetTag [ATAG-]

Invariants pinned:
1. String representations (__str__) for all 4 models.
2. Default field values, status choices, categories, and colour-named badge CSS.
3. Auto-number generation and prefixing (AREQ, ARCV, ACAP, ATAG).
4. Tenant isolation and unique constraints ((tenant, number) and (tenant, tag_code)).
5. Total cost basis calculation on AssetCapitalization.calculate_total_cost_basis() and save().
6. Lifecycle methods: can_execute_capitalization(), can_reverse_capitalization(), can_affix_tag(), can_verify_tag().
"""
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import (
    AssetRequisition,
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetTag,
)


def _assetprocurement_allowed_badge_classes():
    """Return the set of valid theme.css badge classes."""
    return {
        "badge-green",
        "badge-red",
        "badge-amber",
        "badge-info",
        "badge-muted",
        "badge-slate",
    }


def _assetprocurement_to_date(val):
    """Normalize date or datetime to date."""
    if hasattr(val, "date"):
        return val.date()
    return val


# ==============================================================================
# 1. String Representations (__str__)
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_requisition_str(requisition_a):
    """AssetRequisition __str__ returns '<number> - <title>'."""
    assert str(requisition_a) == f"{requisition_a.number} - Automated Laser Cutting System"


@pytest.mark.django_db
def test_assetprocurement_receipt_str(receipt_a):
    """AssetAcquisitionReceipt __str__ returns '<number> - <title>'."""
    assert str(receipt_a) == f"{receipt_a.number} - Dock Receipt for Laser Cutter"


@pytest.mark.django_db
def test_assetprocurement_capitalization_str(capitalization_a):
    """AssetCapitalization __str__ returns '<number> - <asset_name>'."""
    assert str(capitalization_a) == f"{capitalization_a.number} - Capitalized Trumpf Laser Cutter"


@pytest.mark.django_db
def test_assetprocurement_tag_str(asset_tag_a):
    """AssetTag __str__ returns '<tag_code> (<number>)'."""
    assert str(asset_tag_a) == f"{asset_tag_a.tag_code} ({asset_tag_a.number})"


# ==============================================================================
# 2. Defaults, Choices, and CSS Badges
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_requisition_defaults_and_choices(tenant_a):
    """AssetRequisition field defaults, choices, and badge properties."""
    req = AssetRequisition.objects.create(
        tenant=tenant_a,
        title="CNC Lathe Machine",
        business_justification="Expand turning shop production capacity.",
    )
    assert req.status == "draft"
    assert req.asset_category == "machinery"
    assert req.priority == "medium"
    assert req.estimated_cost == Decimal("0.00")
    assert req.budget_code == ""
    assert req.proposed_manufacturer == ""
    assert req.proposed_model == ""
    assert req.rejection_reason == ""

    # Status choices presence
    status_keys = [c[0] for c in AssetRequisition.STATUS_CHOICES]
    for expected in ["draft", "pending_approval", "approved", "rejected", "ordered", "received", "cancelled"]:
        assert expected in status_keys

    # Category choices presence
    cat_keys = [c[0] for c in AssetRequisition.CATEGORY_CHOICES]
    for expected in ["machinery", "vehicle", "it_hardware", "tooling", "facility", "office_furniture", "other"]:
        assert expected in cat_keys

    # Priority choices presence
    prio_keys = [c[0] for c in AssetRequisition.PRIORITY_CHOICES]
    for expected in ["low", "medium", "high", "urgent"]:
        assert expected in prio_keys

    # Status CSS badges
    assert req.status_css == "badge-slate"
    req.status = "approved"
    assert req.status_css == "badge-green"
    req.status = "pending_approval"
    assert req.status_css == "badge-amber"
    req.status = "rejected"
    assert req.status_css == "badge-red"

    # Priority CSS badges
    assert req.priority_css == "badge-info"
    req.priority = "urgent"
    assert req.priority_css == "badge-red"
    req.priority = "high"
    assert req.priority_css == "badge-amber"
    req.priority = "low"
    assert req.priority_css == "badge-muted"


@pytest.mark.django_db
def test_assetprocurement_receipt_defaults_and_choices(tenant_a):
    """AssetAcquisitionReceipt field defaults, choices, and badge properties."""
    rcv = AssetAcquisitionReceipt.objects.create(
        tenant=tenant_a,
        title="Forklift Intake",
    )
    assert rcv.status == "pending_inspection"
    assert rcv.condition_on_arrival == "good"
    assert rcv.quantity_received == 1
    assert rcv.carrier_name == ""
    assert rcv.tracking_number == ""
    assert rcv.bill_of_lading == ""
    assert rcv.inspection_notes == ""
    assert _assetprocurement_to_date(rcv.received_date) == timezone.now().date()

    # Status choices
    status_keys = [c[0] for c in AssetAcquisitionReceipt.STATUS_CHOICES]
    for expected in ["pending_inspection", "accepted", "quarantined", "rejected", "capitalized"]:
        assert expected in status_keys

    # Condition choices
    cond_keys = [c[0] for c in AssetAcquisitionReceipt.CONDITION_CHOICES]
    for expected in ["excellent", "good", "fair", "damaged", "defective"]:
        assert expected in cond_keys

    # CSS properties
    assert rcv.status_css == "badge-amber"
    assert rcv.condition_css == "badge-info"

    rcv.status = "accepted"
    assert rcv.status_css == "badge-green"
    rcv.condition_on_arrival = "excellent"
    assert rcv.condition_css == "badge-green"


@pytest.mark.django_db
def test_assetprocurement_capitalization_defaults_and_choices(tenant_a):
    """AssetCapitalization field defaults, choices, and badge properties."""
    cap = AssetCapitalization.objects.create(
        tenant=tenant_a,
        title="Laser Cutter Capitalization Event",
        asset_name="Trumpf TruLaser 3030 Fiber",
    )
    assert cap.status == "draft"
    assert cap.depreciation_method == "straight_line"
    assert cap.useful_life_months == 60
    assert cap.purchase_cost == Decimal("0.00")
    assert cap.freight_cost == Decimal("0.00")
    assert cap.installation_cost == Decimal("0.00")
    assert cap.customs_duties_cost == Decimal("0.00")
    assert cap.other_initial_costs == Decimal("0.00")
    assert cap.salvage_value == Decimal("0.00")
    assert cap.total_cost_basis == Decimal("0.00")
    assert cap.is_cip_conversion is False
    assert _assetprocurement_to_date(cap.in_service_date) == timezone.now().date()

    # Depreciation choices
    meth_keys = [c[0] for c in AssetCapitalization.DEPRECIATION_METHOD_CHOICES]
    for expected in ["straight_line", "declining_balance", "units_of_production"]:
        assert expected in meth_keys

    # Status choices
    status_keys = [c[0] for c in AssetCapitalization.STATUS_CHOICES]
    for expected in ["draft", "approved", "capitalized", "reversed"]:
        assert expected in status_keys

    # CSS badges
    assert cap.status_css == "badge-slate"
    cap.status = "capitalized"
    assert cap.status_css == "badge-green"
    cap.status = "approved"
    assert cap.status_css == "badge-amber"
    cap.status = "reversed"
    assert cap.status_css == "badge-red"


@pytest.mark.django_db
def test_assetprocurement_tag_defaults_and_choices(tenant_a):
    """AssetTag field defaults, choices, and badge properties."""
    tag = AssetTag.objects.create(
        tenant=tenant_a,
        tag_code="TAG-INSPECT-001",
    )
    assert tag.status == "pending_print"
    assert tag.tag_format == "qr_code"
    assert tag.is_verified is False
    assert tag.physical_placement == ""
    assert tag.scanner_device_id == ""
    assert tag.notes == ""

    # Tag format choices
    fmt_keys = [c[0] for c in AssetTag.TAG_FORMAT_CHOICES]
    for expected in ["qr_code", "barcode_128", "rfid_uhf", "nfc", "metal_plate"]:
        assert expected in fmt_keys

    # Status choices
    status_keys = [c[0] for c in AssetTag.STATUS_CHOICES]
    for expected in ["pending_print", "printed", "affixed", "verified", "damaged_reissued", "retired"]:
        assert expected in status_keys

    # Status CSS badges
    assert tag.status_css == "badge-slate"
    tag.status = "printed"
    assert tag.status_css == "badge-info"
    tag.status = "affixed"
    assert tag.status_css == "badge-amber"
    tag.status = "verified"
    assert tag.status_css == "badge-green"
    tag.status = "damaged_reissued"
    assert tag.status_css == "badge-red"
    tag.status = "retired"
    assert tag.status_css == "badge-muted"


@pytest.mark.django_db
def test_assetprocurement_css_badge_classes():
    """Verify that all STATUS_CSS, PRIORITY_CSS, CONDITION_CSS use valid theme.css classes."""
    valid_badges = _assetprocurement_allowed_badge_classes()

    for status, css in AssetRequisition.STATUS_CSS.items():
        assert css in valid_badges, f"Invalid CSS badge '{css}' in AssetRequisition.STATUS_CSS for '{status}'"

    for prio, css in AssetRequisition.PRIORITY_CSS.items():
        assert css in valid_badges, f"Invalid CSS badge '{css}' in AssetRequisition.PRIORITY_CSS for '{prio}'"

    for status, css in AssetAcquisitionReceipt.STATUS_CSS.items():
        assert css in valid_badges, f"Invalid CSS badge '{css}' in AssetAcquisitionReceipt.STATUS_CSS for '{status}'"

    for cond, css in AssetAcquisitionReceipt.CONDITION_CSS.items():
        assert css in valid_badges, f"Invalid CSS badge '{css}' in AssetAcquisitionReceipt.CONDITION_CSS for '{cond}'"

    for status, css in AssetCapitalization.STATUS_CSS.items():
        assert css in valid_badges, f"Invalid CSS badge '{css}' in AssetCapitalization.STATUS_CSS for '{status}'"

    for status, css in AssetTag.STATUS_CSS.items():
        assert css in valid_badges, f"Invalid CSS badge '{css}' in AssetTag.STATUS_CSS for '{status}'"


# ==============================================================================
# 3. Auto-Number Generation & Prefixes
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_autonumber_prefixes():
    """Verify that each model defines the expected NUMBER_PREFIX."""
    assert AssetRequisition.NUMBER_PREFIX == "AREQ"
    assert AssetAcquisitionReceipt.NUMBER_PREFIX == "ARCV"
    assert AssetCapitalization.NUMBER_PREFIX == "ACAP"
    assert AssetTag.NUMBER_PREFIX == "ATAG"


@pytest.mark.django_db
def test_assetprocurement_autonumber_generation_and_sequencing(tenant_a):
    """Verify sequential numbering per model in tenant_a."""
    # AssetRequisition sequence
    req1 = AssetRequisition.objects.create(
        tenant=tenant_a,
        title="Requisition Sequence Test 1",
        business_justification="Test sequence 1",
    )
    req2 = AssetRequisition.objects.create(
        tenant=tenant_a,
        title="Requisition Sequence Test 2",
        business_justification="Test sequence 2",
    )
    assert req1.number.startswith("AREQ-")
    assert req2.number.startswith("AREQ-")
    assert req1.number != req2.number

    num1 = int(req1.number.replace("AREQ-", ""))
    num2 = int(req2.number.replace("AREQ-", ""))
    assert num2 == num1 + 1

    # AssetAcquisitionReceipt sequence
    rcv1 = AssetAcquisitionReceipt.objects.create(tenant=tenant_a, title="Receipt 1")
    rcv2 = AssetAcquisitionReceipt.objects.create(tenant=tenant_a, title="Receipt 2")
    assert rcv1.number.startswith("ARCV-")
    assert rcv2.number.startswith("ARCV-")
    rcv_num1 = int(rcv1.number.replace("ARCV-", ""))
    rcv_num2 = int(rcv2.number.replace("ARCV-", ""))
    assert rcv_num2 == rcv_num1 + 1

    # AssetCapitalization sequence
    cap1 = AssetCapitalization.objects.create(tenant=tenant_a, title="Cap 1", asset_name="Machine A")
    cap2 = AssetCapitalization.objects.create(tenant=tenant_a, title="Cap 2", asset_name="Machine B")
    assert cap1.number.startswith("ACAP-")
    assert cap2.number.startswith("ACAP-")
    cap_num1 = int(cap1.number.replace("ACAP-", ""))
    cap_num2 = int(cap2.number.replace("ACAP-", ""))
    assert cap_num2 == cap_num1 + 1

    # AssetTag sequence
    tag1 = AssetTag.objects.create(tenant=tenant_a, tag_code="SEQ-TAG-001")
    tag2 = AssetTag.objects.create(tenant=tenant_a, tag_code="SEQ-TAG-002")
    assert tag1.number.startswith("ATAG-")
    assert tag2.number.startswith("ATAG-")
    tag_num1 = int(tag1.number.replace("ATAG-", ""))
    tag_num2 = int(tag2.number.replace("ATAG-", ""))
    assert tag_num2 == tag_num1 + 1


# ==============================================================================
# 4. Tenant Isolation & Unique Constraints
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_tenant_isolation_and_scoping(
    requisition_a,
    requisition_b,
    receipt_a,
    receipt_b,
    capitalization_a,
    capitalization_b,
    asset_tag_a,
    asset_tag_b,
    tenant_a,
    tenant_b,
):
    """Querysets filtered by tenant isolate objects completely between workspaces."""
    # Requisition scoping
    reqs_a = AssetRequisition.objects.filter(tenant=tenant_a)
    reqs_b = AssetRequisition.objects.filter(tenant=tenant_b)
    assert requisition_a in reqs_a
    assert requisition_a not in reqs_b
    assert requisition_b in reqs_b
    assert requisition_b not in reqs_a

    # Receipt scoping
    rcvs_a = AssetAcquisitionReceipt.objects.filter(tenant=tenant_a)
    rcvs_b = AssetAcquisitionReceipt.objects.filter(tenant=tenant_b)
    assert receipt_a in rcvs_a
    assert receipt_a not in rcvs_b
    assert receipt_b in rcvs_b
    assert receipt_b not in rcvs_a

    # Capitalization scoping
    caps_a = AssetCapitalization.objects.filter(tenant=tenant_a)
    caps_b = AssetCapitalization.objects.filter(tenant=tenant_b)
    assert capitalization_a in caps_a
    assert capitalization_a not in caps_b
    assert capitalization_b in caps_b
    assert capitalization_b not in caps_a

    # Tag scoping
    tags_a = AssetTag.objects.filter(tenant=tenant_a)
    tags_b = AssetTag.objects.filter(tenant=tenant_b)
    assert asset_tag_a in tags_a
    assert asset_tag_a not in tags_b
    assert asset_tag_b in tags_b
    assert asset_tag_b not in tags_a


@pytest.mark.django_db
def test_assetprocurement_unique_constraint_tenant_number(tenant_a, tenant_b):
    """Unique constraint (tenant, number) forbids duplicate numbers in the same tenant,
    but allows the same number in different tenants."""
    # Create requisition with explicit number in tenant_a
    req1 = AssetRequisition(
        tenant=tenant_a,
        number="AREQ-99999",
        title="Explicit Req 1",
        business_justification="Unique test",
    )
    req1.save()

    # Same number in same tenant should fail
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetRequisition.objects.create(
                tenant=tenant_a,
                number="AREQ-99999",
                title="Duplicate Req in Tenant A",
                business_justification="Should fail",
            )

    # Same number in tenant_b should succeed
    req_b = AssetRequisition.objects.create(
        tenant=tenant_b,
        number="AREQ-99999",
        title="Allowed Req in Tenant B",
        business_justification="Cross-tenant same number allowed",
    )
    assert req_b.number == "AREQ-99999"
    assert req_b.tenant == tenant_b

    # Receipt unique (tenant, number)
    rcv1 = AssetAcquisitionReceipt(tenant=tenant_a, number="ARCV-99999", title="Explicit Receipt 1")
    rcv1.save()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetAcquisitionReceipt.objects.create(
                tenant=tenant_a,
                number="ARCV-99999",
                title="Duplicate Receipt",
            )

    rcv_b = AssetAcquisitionReceipt.objects.create(
        tenant=tenant_b,
        number="ARCV-99999",
        title="Allowed Receipt in B",
    )
    assert rcv_b.number == "ARCV-99999"

    # Capitalization unique (tenant, number)
    cap1 = AssetCapitalization(
        tenant=tenant_a,
        number="ACAP-99999",
        title="Explicit Cap 1",
        asset_name="Test Asset",
    )
    cap1.save()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetCapitalization.objects.create(
                tenant=tenant_a,
                number="ACAP-99999",
                title="Duplicate Cap",
                asset_name="Test Asset Duplicate",
            )

    cap_b = AssetCapitalization.objects.create(
        tenant=tenant_b,
        number="ACAP-99999",
        title="Allowed Cap in B",
        asset_name="Asset B",
    )
    assert cap_b.number == "ACAP-99999"

    # Tag unique (tenant, number)
    tag1 = AssetTag(tenant=tenant_a, number="ATAG-99999", tag_code="TEST-TAG-A1")
    tag1.save()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetTag.objects.create(tenant=tenant_a, number="ATAG-99999", tag_code="TEST-TAG-A2")

    tag_b = AssetTag.objects.create(tenant=tenant_b, number="ATAG-99999", tag_code="TEST-TAG-B1")
    assert tag_b.number == "ATAG-99999"


@pytest.mark.django_db
def test_assetprocurement_tag_unique_constraint_tenant_tag_code(tenant_a, tenant_b):
    """Unique constraint (tenant, tag_code) on AssetTag forbids identical tag_code
    within the same tenant, but allows it across distinct tenants."""
    AssetTag.objects.create(
        tenant=tenant_a,
        tag_code="RFID-EPC-12345",
    )

    # Duplicate tag_code in tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetTag.objects.create(
                tenant=tenant_a,
                tag_code="RFID-EPC-12345",
            )

    # Same tag_code in tenant_b succeeds
    tag_b = AssetTag.objects.create(
        tenant=tenant_b,
        tag_code="RFID-EPC-12345",
    )
    assert tag_b.tag_code == "RFID-EPC-12345"
    assert tag_b.tenant == tenant_b


# ==============================================================================
# 5. Total Cost Basis Calculation on AssetCapitalization
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_capitalization_calculate_total_cost_basis(tenant_a):
    """AssetCapitalization.calculate_total_cost_basis() correctly sums all 5 cost components."""
    cap = AssetCapitalization(
        tenant=tenant_a,
        title="Test Buildup",
        asset_name="Mazak 5-Axis Mill",
        purchase_cost=Decimal("75000.00"),
        freight_cost=Decimal("2500.50"),
        installation_cost=Decimal("1200.25"),
        customs_duties_cost=Decimal("3800.75"),
        other_initial_costs=Decimal("499.50"),
    )
    expected_total = (
        Decimal("75000.00")
        + Decimal("2500.50")
        + Decimal("1200.25")
        + Decimal("3800.75")
        + Decimal("499.50")
    )
    assert expected_total == Decimal("83001.00")
    assert cap.calculate_total_cost_basis() == expected_total


@pytest.mark.django_db
def test_assetprocurement_capitalization_save_updates_total_cost_basis(tenant_a):
    """AssetCapitalization.save() automatically recalculates total_cost_basis upon save."""
    cap = AssetCapitalization.objects.create(
        tenant=tenant_a,
        title="Automated Cost Save",
        asset_name="Fanuc Welding Robot",
        purchase_cost=Decimal("45000.00"),
        freight_cost=Decimal("1500.00"),
        installation_cost=Decimal("2000.00"),
    )
    assert cap.total_cost_basis == Decimal("48500.00")

    # Update freight and other costs, save and verify
    cap.freight_cost = Decimal("2500.00")
    cap.customs_duties_cost = Decimal("1000.00")
    cap.other_initial_costs = Decimal("500.00")
    cap.save()

    cap.refresh_from_db()
    assert cap.total_cost_basis == Decimal("51000.00")


@pytest.mark.django_db
def test_assetprocurement_capitalization_calculate_total_cost_basis_with_zeroes_and_nones(tenant_a):
    """AssetCapitalization.calculate_total_cost_basis() handles zeroes and None gracefully."""
    cap = AssetCapitalization(
        tenant=tenant_a,
        title="Zero Test",
        asset_name="Manual Drill Press",
        purchase_cost=None,
        freight_cost=Decimal("0.00"),
        installation_cost=None,
        customs_duties_cost=None,
        other_initial_costs=Decimal("150.00"),
    )
    assert cap.calculate_total_cost_basis() == Decimal("150.00")


# ==============================================================================
# 6. Lifecycle & Workflow Methods
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_capitalization_can_execute_capitalization(tenant_a):
    """AssetCapitalization.can_execute_capitalization() is True for draft/approved, False otherwise."""
    cap = AssetCapitalization.objects.create(
        tenant=tenant_a,
        title="Cap Execution Test",
        asset_name="Test Machine",
        status="draft",
    )
    assert cap.can_execute_capitalization() is True

    cap.status = "approved"
    assert cap.can_execute_capitalization() is True

    cap.status = "capitalized"
    assert cap.can_execute_capitalization() is False

    cap.status = "reversed"
    assert cap.can_execute_capitalization() is False


@pytest.mark.django_db
def test_assetprocurement_capitalization_can_reverse_capitalization(tenant_a):
    """AssetCapitalization.can_reverse() and can_reverse_capitalization() are True only when capitalized."""
    cap = AssetCapitalization.objects.create(
        tenant=tenant_a,
        title="Cap Reverse Test",
        asset_name="Test Machine",
        status="draft",
    )
    assert cap.can_reverse() is False
    assert cap.can_reverse_capitalization() is False

    cap.status = "approved"
    assert cap.can_reverse() is False
    assert cap.can_reverse_capitalization() is False

    cap.status = "capitalized"
    assert cap.can_reverse() is True
    assert cap.can_reverse_capitalization() is True

    cap.status = "reversed"
    assert cap.can_reverse() is False
    assert cap.can_reverse_capitalization() is False


@pytest.mark.django_db
def test_assetprocurement_tag_can_affix_tag(tenant_a):
    """AssetTag.can_affix() and can_affix_tag() are True for pending_print and printed."""
    tag = AssetTag.objects.create(
        tenant=tenant_a,
        tag_code="TAG-AFFIX-001",
        status="pending_print",
    )
    assert tag.can_affix() is True
    assert tag.can_affix_tag() is True

    tag.status = "printed"
    assert tag.can_affix() is True
    assert tag.can_affix_tag() is True

    tag.status = "affixed"
    assert tag.can_affix() is False
    assert tag.can_affix_tag() is False

    tag.status = "verified"
    assert tag.can_affix() is False
    assert tag.can_affix_tag() is False

    tag.status = "damaged_reissued"
    assert tag.can_affix() is False
    assert tag.can_affix_tag() is False

    tag.status = "retired"
    assert tag.can_affix() is False
    assert tag.can_affix_tag() is False


@pytest.mark.django_db
def test_assetprocurement_tag_can_verify_tag(tenant_a):
    """AssetTag.can_verify() and can_verify_tag() require status == 'affixed' and not is_verified."""
    tag = AssetTag.objects.create(
        tenant=tenant_a,
        tag_code="TAG-VERIFY-001",
        status="pending_print",
        is_verified=False,
    )
    assert tag.can_verify() is False
    assert tag.can_verify_tag() is False

    tag.status = "printed"
    assert tag.can_verify() is False
    assert tag.can_verify_tag() is False

    tag.status = "affixed"
    assert tag.can_verify() is True
    assert tag.can_verify_tag() is True

    # If already verified, should be False
    tag.is_verified = True
    assert tag.can_verify() is False
    assert tag.can_verify_tag() is False

    # Other statuses
    tag.is_verified = False
    tag.status = "retired"
    assert tag.can_verify() is False
    assert tag.can_verify_tag() is False


@pytest.mark.django_db
def test_assetprocurement_tag_can_mark_printed(tenant_a):
    """AssetTag.can_mark_printed() is True only when status is pending_print."""
    tag = AssetTag.objects.create(
        tenant=tenant_a,
        tag_code="TAG-PRINT-001",
        status="pending_print",
    )
    assert tag.can_mark_printed() is True

    tag.status = "printed"
    assert tag.can_mark_printed() is False

    tag.status = "affixed"
    assert tag.can_mark_printed() is False


@pytest.mark.django_db
def test_assetprocurement_receipt_lifecycle_methods(tenant_a):
    """AssetAcquisitionReceipt inspection, quarantine, and rejection transition checks."""
    rcv = AssetAcquisitionReceipt.objects.create(
        tenant=tenant_a,
        title="Receipt Workflow Test",
        status="pending_inspection",
    )
    # When pending_inspection:
    assert rcv.can_inspect_accept() is True
    assert rcv.can_quarantine() is True
    assert rcv.can_reject() is True

    # When accepted:
    rcv.status = "accepted"
    assert rcv.can_inspect_accept() is False
    assert rcv.can_quarantine() is True
    assert rcv.can_reject() is False

    # When quarantined:
    rcv.status = "quarantined"
    assert rcv.can_inspect_accept() is True
    assert rcv.can_quarantine() is False
    assert rcv.can_reject() is True

    # When capitalized:
    rcv.status = "capitalized"
    assert rcv.can_inspect_accept() is False
    assert rcv.can_quarantine() is False
    assert rcv.can_reject() is False

    # When rejected:
    rcv.status = "rejected"
    assert rcv.can_inspect_accept() is False
    assert rcv.can_quarantine() is False
    assert rcv.can_reject() is False


# ==============================================================================
# 7. Relationships, Related Names & Foreign Keys
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_foreign_key_relationships(
    requisition_a,
    receipt_a,
    capitalization_a,
    asset_tag_a,
):
    """Verify related names across all 4 procurement models and core spine."""
    # Requisition -> Receipts
    assert receipt_a in requisition_a.acquisition_receipts.all()

    # Requisition -> Capitalizations
    capitalization_a.requisition = requisition_a
    capitalization_a.acquisition_receipt = receipt_a
    capitalization_a.save()
    assert capitalization_a in requisition_a.capitalization_events.all()
    assert capitalization_a in receipt_a.capitalization_events.all()

    # Capitalization -> AssetTags
    assert asset_tag_a in capitalization_a.asset_tags.all()


@pytest.mark.django_db
def test_assetprocurement_cascade_and_set_null_behavior(
    tenant_a,
    currency_usd,
    vendor_party_a,
    location_a,
):
    """SET_NULL behavior on optional foreign keys preserves records when linked entities are deleted."""
    req = AssetRequisition.objects.create(
        tenant=tenant_a,
        title="Preservation Check",
        business_justification="Verify SET_NULL on vendor deletion",
        proposed_vendor=vendor_party_a,
        currency=currency_usd,
        target_location=location_a,
    )
    assert req.proposed_vendor == vendor_party_a
    assert req.currency == currency_usd

    # Delete currency - should set null, not cascade delete requisition
    currency_usd.delete()
    req.refresh_from_db()
    assert req.currency is None
    assert AssetRequisition.objects.filter(pk=req.pk).exists()
