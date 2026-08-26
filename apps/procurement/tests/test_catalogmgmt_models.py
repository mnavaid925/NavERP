"""Procurement 6.9 - Catalog Management model tests.

Load-bearing contracts: per-tenant PCI-/POE-/CUB- auto-numbering, the guarded
CatalogItem lifecycle verbs (submit/approve/reject/block/archive) that stamp their
audit columns exactly once and touch nothing else via save(update_fields),
is_purchasable = approved AND active, the single-occupancy (item, min_quantity)
price-break invariant enforced on BOTH clean() and the tier approval path, the
q2-clamped effective-price math, and CatalogUploadBatch.validate_and_stage()'s
parse/count/error-log split with CSV-injection escaping.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.procurement.models import (
    CatalogItem,
    CatalogPriceTier,
    CatalogUploadBatch,
    PunchOutEndpoint,
)

pytestmark = pytest.mark.django_db


# -- local factories ----------------------------------------------------------------------------------

def _catalogmgmt_item(tenant, **overrides):
    fields = dict(
        tenant=tenant,
        source_type="supplier_product",
        name="Industrial safety gloves",
        supplier_part_no="NW-GLOVE-D1",
        base_price=Decimal("34.90"),
        status="draft",
    )
    fields.update(overrides)
    return CatalogItem.objects.create(**fields)


def _catalogmgmt_tier(catalog_item, **overrides):
    fields = dict(
        tenant=catalog_item.tenant,
        catalog_item=catalog_item,
        min_quantity=Decimal("10"),
        unit_price=Decimal("31.50"),
        status="draft",
    )
    fields.update(overrides)
    return CatalogPriceTier.objects.create(**fields)


_CSV_HEADER = "name,supplier_part_no,unit_price,uom_code,category_text"


def _catalogmgmt_csv(*data_lines):
    """A real UTF-8 CSV payload (header first) ready for a FileField."""
    return "\n".join((_CSV_HEADER,) + data_lines).encode("utf-8")


def _catalogmgmt_attach_csv(batch, content):
    batch.file = SimpleUploadedFile("catalog.csv", content)
    batch.save()
    return batch


# -- 1. auto-numbering ---------------------------------------------------------------------------------

def test_catalogmgmt_pci_number_empty_before_save_then_increments_stably(tenant_a, tenant_b):
    unsaved = CatalogItem(tenant=tenant_a, source_type="supplier_product",
                          name="Unsaved numbering probe")
    assert unsaved.number == ""
    unsaved.save()
    assert unsaved.number == "PCI-00001"

    assert _catalogmgmt_item(tenant_a).number == "PCI-00002"
    assert _catalogmgmt_item(tenant_b).number == "PCI-00001"  # per-tenant sequence

    unsaved.name = "Renamed probe"
    unsaved.save()
    unsaved.refresh_from_db()
    assert unsaved.number == "PCI-00001"  # stable across re-save


def test_catalogmgmt_poe_number_sequence_per_tenant_stable_on_resave(tenant_a, supplier_a):
    _, party = supplier_a
    endpoint = PunchOutEndpoint(tenant=tenant_a, party=party, name="First endpoint",
                                punchout_url="https://punch.example.com/cxml")
    assert endpoint.number == ""
    endpoint.save()
    assert endpoint.number == "POE-00001"

    PunchOutEndpoint.objects.create(tenant=tenant_a, party=party, name="Second endpoint",
                                    punchout_url="https://punch.example.com/oci")
    endpoint.notes = "handshake deferred by design"
    endpoint.save()
    endpoint.refresh_from_db()
    assert endpoint.number == "POE-00001"


def test_catalogmgmt_cub_numbers_increment_and_survive_resave(tenant_a, upload_batch_received_a):
    assert upload_batch_received_a.number == "CUB-00001"
    second = CatalogUploadBatch.objects.create(tenant=tenant_a, status="received")
    assert second.number == "CUB-00002"

    upload_batch_received_a.notes = "supplier autumn price list"
    upload_batch_received_a.save()
    upload_batch_received_a.refresh_from_db()
    assert upload_batch_received_a.number == "CUB-00001"


# -- 2. CatalogItem state machine ----------------------------------------------------------------------

def test_catalogmgmt_item_submit_from_draft_and_again_from_rejected(tenant_a, admin_user,
                                                                   member_user):
    ci = _catalogmgmt_item(tenant_a)
    assert ci.submit(admin_user) is True
    ci.refresh_from_db()
    assert ci.status == "pending_approval"
    assert ci.submitted_by == admin_user
    assert ci.submitted_at is not None

    assert ci.reject(admin_user, "Price off contract") is True  # pending -> rejected
    ci.refresh_from_db()
    assert ci.status == "rejected"
    assert ci.rejection_reason == "Price off contract"

    first_stamp = ci.submitted_at
    assert ci.submit(member_user) is True  # a rejected entry returns to the maintainer
    ci.refresh_from_db()
    assert ci.status == "pending_approval"
    assert ci.submitted_by == member_user  # re-stamped with the new submitter
    assert ci.submitted_at is not None and ci.submitted_at >= first_stamp


def test_catalogmgmt_item_submit_refused_when_not_submittable(tenant_a, admin_user,
                                                              catalog_item_approved_a,
                                                              catalog_item_pending_a,
                                                              catalog_item_blocked_a):
    for ci in (catalog_item_approved_a, catalog_item_pending_a, catalog_item_blocked_a):
        before_status = ci.status
        assert ci.submit(admin_user) is False
        ci.refresh_from_db()
        assert ci.status == before_status
        assert ci.submitted_at is None and ci.submitted_by is None  # no timestamp overwrite


def test_catalogmgmt_item_approve_stamps_once_and_skips_unrelated_fields(tenant_a, admin_user,
                                                                        member_user,
                                                                        catalog_item_pending_a):
    ci = catalog_item_pending_a
    ci.name = "TAMPERED IN MEMORY"
    ci.rejection_reason = "must not persist through approve()"
    assert ci.approve(admin_user) is True
    ci.refresh_from_db()
    assert ci.status == "approved"
    assert ci.approved_by == admin_user
    assert ci.approved_at is not None
    assert ci.name == "Industrial safety gloves"  # update_fields left the name alone
    assert ci.rejection_reason == ""

    stamp = ci.approved_at
    assert ci.approve(member_user) is False
    ci.refresh_from_db()
    assert ci.approved_by == admin_user  # stamped exactly once, never overwritten
    assert ci.approved_at == stamp


def test_catalogmgmt_item_reject_records_reason_exactly_once(tenant_a, admin_user,
                                                             catalog_item_pending_a):
    ci = catalog_item_pending_a
    assert ci.reject(admin_user, "Spec mismatch") is True
    ci.refresh_from_db()
    assert ci.status == "rejected"
    assert ci.rejection_reason == "Spec mismatch"

    assert ci.reject(admin_user, "Changed mind") is False
    ci.refresh_from_db()
    assert ci.status == "rejected"
    assert ci.rejection_reason == "Spec mismatch"


def test_catalogmgmt_item_block_only_from_approved(tenant_a, catalog_item_approved_a,
                                                   catalog_item_pending_a):
    assert catalog_item_pending_a.block() is False
    catalog_item_pending_a.refresh_from_db()
    assert catalog_item_pending_a.status == "pending_approval"

    assert catalog_item_approved_a.block() is True
    catalog_item_approved_a.refresh_from_db()
    assert catalog_item_approved_a.status == "blocked"
    assert catalog_item_approved_a.block() is False  # idempotence refused
    catalog_item_approved_a.refresh_from_db()
    assert catalog_item_approved_a.status == "blocked"


def test_catalogmgmt_item_archive_from_terminal_states_only(tenant_a, admin_user,
                                                            catalog_item_approved_a,
                                                            catalog_item_pending_a,
                                                            catalog_item_blocked_a):
    rejected = _catalogmgmt_item(tenant_a, status="pending_approval")
    assert rejected.reject(admin_user, "obsolete") is True
    assert rejected.archive() is True

    assert catalog_item_approved_a.archive() is True
    assert catalog_item_blocked_a.archive() is True
    catalog_item_approved_a.refresh_from_db()
    catalog_item_blocked_a.refresh_from_db()
    assert catalog_item_approved_a.status == "archived"
    assert catalog_item_blocked_a.status == "archived"

    fresh = _catalogmgmt_item(tenant_a)
    assert fresh.archive() is False
    fresh.refresh_from_db()
    assert fresh.status == "draft"
    assert catalog_item_pending_a.archive() is False
    catalog_item_pending_a.refresh_from_db()
    assert catalog_item_pending_a.status == "pending_approval"


def test_catalogmgmt_is_purchasable_requires_approved_and_active(tenant_a,
                                                                 catalog_item_approved_a,
                                                                 catalog_item_pending_a,
                                                                 catalog_item_blocked_a):
    assert catalog_item_approved_a.is_purchasable is True

    catalog_item_approved_a.is_active = False
    assert catalog_item_approved_a.is_purchasable is False
    catalog_item_approved_a.is_active = True

    assert catalog_item_pending_a.is_purchasable is False
    assert catalog_item_blocked_a.is_purchasable is False

    catalog_item_approved_a.block()
    assert catalog_item_approved_a.is_purchasable is False


# -- 3. CatalogPriceTier machine -----------------------------------------------------------------------

def test_catalogmgmt_tier_approve_stamps_approver_once(catalog_item_approved_a, admin_user,
                                                       member_user):
    tier = _catalogmgmt_tier(catalog_item_approved_a)  # proposed/draft
    assert tier.approve(admin_user) is True
    tier.refresh_from_db()
    assert tier.status == "active"
    assert tier.approved_by == admin_user
    assert tier.approved_at is not None

    stamp = tier.approved_at
    assert tier.approve(member_user) is False
    tier.refresh_from_db()
    assert tier.approved_by == admin_user
    assert tier.approved_at == stamp


def test_catalogmgmt_second_draft_tier_same_break_cannot_go_active(catalog_item_approved_a,
                                                                   tier_active_a, admin_user):
    """C1 regression guard: two drafts may share a break, but only ONE may activate."""
    rival = _catalogmgmt_tier(catalog_item_approved_a, min_quantity=Decimal("10"),
                              unit_price=Decimal("28.00"))
    assert rival.status == "draft"
    assert rival.approve(admin_user) is False
    rival.refresh_from_db()
    assert rival.status == "draft"
    assert rival.approved_by is None and rival.approved_at is None


def test_catalogmgmt_retire_supersedes_and_frees_the_break(catalog_item_approved_a,
                                                           tier_active_a, admin_user):
    assert tier_active_a.retire() is True
    tier_active_a.refresh_from_db()
    assert tier_active_a.status == "superseded"
    assert tier_active_a.retire() is False  # already superseded

    successor = _catalogmgmt_tier(catalog_item_approved_a, min_quantity=Decimal("10"),
                                  unit_price=Decimal("29.90"))
    assert successor.approve(admin_user) is True  # freed break accepts a fresh propose+approve
    successor.refresh_from_db()
    assert successor.status == "active"


def test_catalogmgmt_tier_cancel_from_draft_and_superseded_not_active(catalog_item_approved_a,
                                                                      tier_active_a):
    draft = _catalogmgmt_tier(catalog_item_approved_a, min_quantity=Decimal("50"))
    assert draft.cancel() is True
    draft.refresh_from_db()
    assert draft.status == "cancelled"

    assert tier_active_a.cancel() is False  # an active break must retire instead
    tier_active_a.refresh_from_db()
    assert tier_active_a.status == "active"

    assert tier_active_a.retire() is True
    assert tier_active_a.cancel() is True
    tier_active_a.refresh_from_db()
    assert tier_active_a.status == "cancelled"


def test_catalogmgmt_effective_price_unit_and_discount_paths(catalog_item_approved_a):
    flat = CatalogPriceTier(tenant=catalog_item_approved_a.tenant,
                            catalog_item=catalog_item_approved_a,
                            min_quantity=Decimal("1"), unit_price=Decimal("31.50"))
    assert flat.effective_price(Decimal("34.90")) == Decimal("31.50")  # unit_price verbatim

    discounted = CatalogPriceTier(tenant=catalog_item_approved_a.tenant,
                                  catalog_item=catalog_item_approved_a,
                                  min_quantity=Decimal("1"), unit_price=Decimal("0"),
                                  discount_pct=Decimal("15.00"))
    assert discounted.effective_price(Decimal("100.00")) == Decimal("85.00")


def test_catalogmgmt_effective_price_clamps_huge_base_to_max_q2(catalog_item_approved_a):
    runaway = CatalogPriceTier(tenant=catalog_item_approved_a.tenant,
                               catalog_item=catalog_item_approved_a,
                               min_quantity=Decimal("1"), unit_price=Decimal("0"),
                               discount_pct=Decimal("0.00"))
    assert runaway.effective_price(Decimal("99999999999999999999")) \
        == Decimal("9999999999.99")


# -- 4. tier overlap clean() ---------------------------------------------------------------------------

def test_catalogmgmt_overlap_clean_rejects_duplicate_active_break(tier_active_a):
    dupe = CatalogPriceTier(tenant=tier_active_a.tenant,
                            catalog_item=tier_active_a.catalog_item,
                            min_quantity=tier_active_a.min_quantity,
                            unit_price=Decimal("30.00"), status="active")
    with pytest.raises(ValidationError) as err:
        dupe.full_clean()
    assert "min_quantity" in err.value.message_dict


def test_catalogmgmt_overlap_clean_permits_other_break_self_and_other_tenant(tier_active_a,
                                                                             catalog_item_b):
    other_break = CatalogPriceTier(tenant=tier_active_a.tenant,
                                   catalog_item=tier_active_a.catalog_item,
                                   min_quantity=Decimal("25"), unit_price=Decimal("28.00"),
                                   status="active")
    other_break.full_clean()  # a DIFFERENT min_quantity never clashes

    tier_active_a.full_clean()  # excluding self: re-saving the live tier is fine

    foreign = CatalogPriceTier(tenant=catalog_item_b.tenant, catalog_item=catalog_item_b,
                               min_quantity=Decimal("10"), unit_price=Decimal("40.00"),
                               status="active")
    foreign.full_clean()  # tenant B's break is invisible to tenant A's occupancy guard


# -- 5. PunchOutEndpoint -------------------------------------------------------------------------------

def test_catalogmgmt_record_session_stamps_last_session_only(punchout_endpoint_a):
    endpoint = punchout_endpoint_a
    assert endpoint.last_session_at is None

    endpoint.name = "RENAMED IN MEMORY"
    endpoint.enabled = False
    endpoint.record_session()
    endpoint.refresh_from_db()
    assert endpoint.last_session_at is not None
    assert endpoint.name == "Amazon Business (sandbox)"  # update_fields touched the stamp only
    assert endpoint.enabled is True


# -- 6. CatalogUploadBatch.validate_and_stage ----------------------------------------------------------

def test_catalogmgmt_validate_and_stage_mixed_rows(upload_batch_received_a, admin_user, uom_a):
    batch = _catalogmgmt_attach_csv(upload_batch_received_a, _catalogmgmt_csv(
        "Safety gloves L,NW-GLOVE-L,34.90,EA,Safety wear",      # row 1: good
        "Gloves no price,NW-GLOVE-NP,,EA,Safety wear",          # row 2: missing unit_price
        "Mystery gloves,NW-GLOVE-U,19.00,XX,Safety wear",       # row 3: unknown uom_code
    ))
    ok, staged = batch.validate_and_stage(admin_user)
    assert (ok, staged) == (True, 1)

    batch.refresh_from_db()
    assert batch.status == "validated"
    assert batch.rows_parsed == 3
    assert batch.rows_accepted == 1
    assert batch.rows_rejected == 2
    assert batch.validated_by == admin_user
    assert batch.validated_at is not None
    assert "row 2" in batch.error_log
    assert "row 3" in batch.error_log

    item = CatalogItem.objects.get(tenant=batch.tenant, name="Safety gloves L")
    assert item.source_type == "supplier_product"
    assert item.status == "pending_approval"
    assert item.number.startswith("PCI-")
    assert item.uom == uom_a  # matched by uom_code when valid
    assert item.supplier_id == batch.party_id
    assert item.base_price == Decimal("34.90")


def test_catalogmgmt_validate_refused_off_received(upload_batch_received_a, admin_user):
    batch = upload_batch_received_a
    for state in ("published", "rejected"):
        batch.status = state
        batch.save(update_fields=["status"])
        ok, why = batch.validate_and_stage(admin_user)
        assert ok is False
        assert state in why
        batch.refresh_from_db()
        assert batch.status == state  # nothing moved


def test_catalogmgmt_publish_only_from_validated_and_reject_paths(upload_batch_received_a):
    batch = upload_batch_received_a
    assert batch.publish() is False  # received cannot publish straight away
    assert batch.reject() is True    # received -> rejected
    batch.refresh_from_db()
    assert batch.status == "rejected"
    assert batch.reject() is False
    assert batch.publish() is False

    live = CatalogUploadBatch.objects.create(tenant=batch.tenant, status="validated")
    assert live.reject() is True     # validated -> rejected is legal too
    published = CatalogUploadBatch.objects.create(tenant=batch.tenant, status="validated")
    assert published.publish() is True
    published.refresh_from_db()
    assert published.status == "published"
    assert published.reject() is False  # terminal


def test_catalogmgmt_header_only_file_stays_received(upload_batch_received_a, admin_user):
    batch = _catalogmgmt_attach_csv(upload_batch_received_a, _catalogmgmt_csv())
    ok, why = batch.validate_and_stage(admin_user)
    assert (ok, why) == (False, "no data rows")
    batch.refresh_from_db()
    assert batch.status == "received"
    assert batch.rows_parsed == 0 and batch.rows_accepted == 0 and batch.rows_rejected == 0


def test_catalogmgmt_exe_upload_rejected_by_full_clean(upload_batch_received_a):
    batch = upload_batch_received_a
    batch.file = SimpleUploadedFile("payload.exe", b"MZ-not-a-csv")
    with pytest.raises(ValidationError) as err:
        batch.full_clean()
    assert "file" in err.value.message_dict

    batch.file = SimpleUploadedFile("catalog.CSV", b"name\nx")
    batch.clean()  # allowlist is case-insensitive on the extension


def test_catalogmgmt_formula_cell_name_prefix_escaped_at_staging(upload_batch_received_a,
                                                                 admin_user, uom_a):
    batch = _catalogmgmt_attach_csv(upload_batch_received_a, _catalogmgmt_csv(
        "=SUM(A1),FW-1,12.50,EA,",
    ))
    ok, staged = batch.validate_and_stage(admin_user)
    assert (ok, staged) == (True, 1)
    item = CatalogItem.objects.get(supplier_part_no="FW-1")
    assert item.name == "'=SUM(A1)"  # spreadsheet-operator cell neutralized with a prefix


# -- 7. str / Meta ordering ----------------------------------------------------------------------------

def test_catalogmgmt_str_representations_carry_number_and_name(catalog_item_approved_a,
                                                               tier_active_a,
                                                               punchout_endpoint_a,
                                                               upload_batch_received_a):
    assert catalog_item_approved_a.number in str(catalog_item_approved_a)
    assert catalog_item_approved_a.name in str(catalog_item_approved_a)
    assert "active" in str(tier_active_a)
    assert punchout_endpoint_a.number in str(punchout_endpoint_a)
    assert punchout_endpoint_a.name in str(punchout_endpoint_a)
    assert upload_batch_received_a.number in str(upload_batch_received_a)
    assert upload_batch_received_a.original_filename in str(upload_batch_received_a)


def test_catalogmgmt_meta_ordering_items_newest_first_tiers_by_break(tenant_a,
                                                                     catalog_item_approved_a):
    older = _catalogmgmt_item(tenant_a, name="Older catalogue line")
    newer = _catalogmgmt_item(tenant_a, name="Newer catalogue line")
    pks = list(CatalogItem.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
    assert pks == sorted(pks, reverse=True)  # -created_at, -id -> newest first
    assert pks.index(newer.pk) < pks.index(older.pk)

    _catalogmgmt_tier(catalog_item_approved_a, min_quantity=Decimal("100"))
    _catalogmgmt_tier(catalog_item_approved_a, min_quantity=Decimal("5"))
    _catalogmgmt_tier(catalog_item_approved_a, min_quantity=Decimal("25"))
    assert [t.min_quantity for t in catalog_item_approved_a.price_tiers.all()] \
        == [Decimal("5"), Decimal("25"), Decimal("100")]
