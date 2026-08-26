"""Procurement 6.9 - Catalog Management view flows.

Every surface exercised through rendered bytes and real redirects: the four registers
(search/filters/pagination/pinned context keys), guarded edit gates, the item/tier/upload
lifecycle verbs (admin authority post-fix-wave-I2 - members get PermissionDenied -> 403
while proposing stays open), the write-only punch-out secret that never reaches HTML,
delete semantics (POST deletes, GET preserves), cross-tenant pk -> 404, and the audit
trail every verb leaves behind.
"""
import shutil
import tempfile
from decimal import Decimal

import pytest

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from apps.core.models import AuditLog, Party
from apps.procurement.models import (CatalogItem, CatalogPriceTier,
                                     CatalogUploadBatch, PunchOutEndpoint)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _catalogmgmt_messages(response):
    """Rendered flash messages after a followed redirect."""
    return [str(m) for m in response.context["messages"]]


def _catalogmgmt_audit(model, obj, action):
    """AuditLog rows written about ``obj`` (house pattern: ContentType + id)."""
    ct = ContentType.objects.get_for_model(model)
    return AuditLog.objects.filter(content_type=ct, object_id=obj.pk, action=action)


def _catalogmgmt_item(tenant, **overrides):
    fields = dict(tenant=tenant, source_type="supplier_product",
                  name="View-flow catalog entry", base_price=Decimal("19.90"),
                  status="draft")
    fields.update(overrides)
    return CatalogItem.objects.create(**fields)


def _catalogmgmt_tier(catalog_item, **overrides):
    fields = dict(tenant=catalog_item.tenant, catalog_item=catalog_item,
                  min_quantity=Decimal("25"), unit_price=Decimal("17.50"),
                  status="draft")
    fields.update(overrides)
    return CatalogPriceTier.objects.create(**fields)


_CATALOGMGMT_CSV = (
    "name,supplier_part_no,unit_price,uom_code,category_text\n"
    "Safety goggles,NW-GOG-1,12.50,EA,Safety wear\n"
    ",NW-BAD-1,5.00,,\n"
    "Mystery part,NW-X-1,3.00,ZZ,\n"
    "Latex gloves medium,NW-TWO-1,7.25,EA,Safety wear\n"
)


def _catalogmgmt_batch(tenant, party, *, status="received",
                       csv_text=_CATALOGMGMT_CSV, filename="northwind.csv"):
    """A batch with a REAL stored file (the fixture batch carries none)."""
    batch = CatalogUploadBatch(tenant=tenant, party=party)
    batch.file.save(filename, ContentFile(csv_text.encode("utf-8")), save=False)
    batch.status = status
    if status == "validated":
        batch.rows_parsed = 4
        batch.rows_accepted = 2
        batch.rows_rejected = 2
        batch.error_log = "row 2: name is required\nrow 3: unknown UOM code 'ZZ'"
        batch.validated_at = __import__("django.utils.timezone", fromlist=["now"]).now()
    batch.save()
    return batch


@pytest.fixture
def _catalogmgmt_media():
    """MEDIA_ROOT pointed at a throwaway dir so uploads never touch the repo."""
    tmp = tempfile.mkdtemp(prefix="naverp-catalog-media-")
    with override_settings(MEDIA_ROOT=str(tmp)):
        yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ lists


def test_catalogmgmt_item_list_context_and_seed_rows(client_a, catalog_item_approved_a,
                                                     catalog_item_pending_a,
                                                     catalog_item_blocked_a):
    r = client_a.get(reverse("procurement:catalog_item_list"))
    body = r.content.decode()
    assert r.status_code == 200
    assert "object_list" in r.context and "page_obj" in r.context and "q" in r.context
    assert "status_choices" in r.context and "source_choices" in r.context
    assert "supplier_choices" in r.context and "stats" in r.context
    stats = r.context["stats"]
    assert stats["total"] == 3 and stats["pending"] == 1
    assert stats["approved"] == 1 and stats["blocked"] == 1
    for obj in (catalog_item_approved_a, catalog_item_pending_a, catalog_item_blocked_a):
        assert obj.number in body


def test_catalogmgmt_item_list_search_narrows(client_a, catalog_item_pending_a,
                                              catalog_item_approved_a):
    url = reverse("procurement:catalog_item_list")
    # by name
    r = client_a.get(url, {"q": "safety gloves"})
    nums = {o.pk for o in r.context["object_list"]}
    assert nums == {catalog_item_pending_a.pk}
    # by number
    r = client_a.get(url, {"q": catalog_item_pending_a.number})
    assert [o.pk for o in r.context["object_list"]] == [catalog_item_pending_a.pk]
    # by supplier part no - all three seeded rows share NW-GLOVE-D1, so assert membership
    r = client_a.get(url, {"q": "NW-GLOVE-D1"})
    assert catalog_item_pending_a.pk in {o.pk for o in r.context["object_list"]}
    # q present in context verbatim for the filter form
    assert r.context["q"] == "NW-GLOVE-D1"


def test_catalogmgmt_item_list_status_source_supplier_filters(client_a, tenant_a,
                                                              catalog_item_pending_a,
                                                              catalog_item_approved_a,
                                                              supplier_a):
    _, party = supplier_a
    catalog_item_pending_a.supplier = party
    catalog_item_pending_a.save(update_fields=["supplier"])
    url = reverse("procurement:catalog_item_list")

    r = client_a.get(url, {"status": "pending_approval"})
    assert [o.pk for o in r.context["object_list"]] == [catalog_item_pending_a.pk]

    r = client_a.get(url, {"source_type": "internal"})
    assert [o.pk for o in r.context["object_list"]] == [catalog_item_approved_a.pk]

    r = client_a.get(url, {"supplier": str(party.pk)})
    assert [o.pk for o in r.context["object_list"]] == [catalog_item_pending_a.pk]


def test_catalogmgmt_item_list_boolean_preferred_filter(client_a, catalog_item_approved_a,
                                                        catalog_item_pending_a):
    url = reverse("procurement:catalog_item_list")
    r = client_a.get(url, {"is_preferred": "True"})
    assert [o.pk for o in r.context["object_list"]] == [catalog_item_approved_a.pk]
    r = client_a.get(url, {"is_preferred": "False"})
    assert catalog_item_approved_a.pk not in {o.pk for o in r.context["object_list"]}
    assert catalog_item_pending_a.pk in {o.pk for o in r.context["object_list"]}


def test_catalogmgmt_item_list_pagination_page_two(client_a, tenant_a,
                                                   catalog_item_approved_a):
    for i in range(20):
        _catalogmgmt_item(tenant_a, name=f"Bulk catalog line {i}")
    r = client_a.get(reverse("procurement:catalog_item_list"), {"page": "2"})
    assert r.status_code == 200
    assert r.context["page_obj"].number == 2
    assert 0 < len(r.context["object_list"]) <= 15
    assert r.context["page_obj"].paginator.count >= 21


def test_catalogmgmt_tier_list_context_and_filters(client_a, tier_active_a,
                                                   catalog_item_approved_a):
    _catalogmgmt_tier(catalog_item_approved_a, min_quantity=Decimal("5"),
                      unit_price=Decimal("33.00"))
    r = client_a.get(reverse("procurement:catalog_tier_list"))
    assert r.status_code == 200
    assert "object_list" in r.context and "page_obj" in r.context and "q" in r.context
    assert "status_choices" in r.context and "item_choices" in r.context
    assert set(r.context["stats"]) == {"proposed", "active", "superseded"}
    assert r.context["stats"]["active"] == 1 and r.context["stats"]["proposed"] == 1

    r = client_a.get(reverse("procurement:catalog_tier_list"),
                     {"status": "active", "catalog_item": str(catalog_item_approved_a.pk)})
    assert [o.pk for o in r.context["object_list"]] == [tier_active_a.pk]


def test_catalogmgmt_punchout_list_context_and_enabled_filter(client_a, tenant_a,
                                                              supplier_a,
                                                              punchout_endpoint_a):
    _, party = supplier_a
    PunchOutEndpoint.objects.create(
        tenant=tenant_a, party=party, name="Grainger public catalogue",
        protocol="manual_link", punchout_url="https://grainger.example/link",
        enabled=False)
    r = client_a.get(reverse("procurement:punchout_endpoint_list"))
    assert r.status_code == 200
    assert "object_list" in r.context and "page_obj" in r.context and "q" in r.context
    assert "protocol_choices" in r.context
    assert set(r.context["stats"]) == {"total", "enabled", "cxml"}
    assert r.context["stats"] == {"total": 2, "enabled": 1, "cxml": 1}

    r = client_a.get(reverse("procurement:punchout_endpoint_list"), {"enabled": "False"})
    assert [o.enabled for o in r.context["object_list"]] == [False]
    r = client_a.get(reverse("procurement:punchout_endpoint_list"), {"enabled": "True"})
    assert [o.enabled for o in r.context["object_list"]] == [True]
    r = client_a.get(reverse("procurement:punchout_endpoint_list"), {"protocol": "cxml"})
    assert [o.pk for o in r.context["object_list"]] == [punchout_endpoint_a.pk]


def test_catalogmgmt_upload_list_context_and_filters(client_a, tenant_a, supplier_a,
                                                     _catalogmgmt_media):
    _, party = supplier_a
    received = _catalogmgmt_batch(tenant_a, party, status="received")
    validated = _catalogmgmt_batch(tenant_a, party, status="validated")
    r = client_a.get(reverse("procurement:catalog_upload_list"))
    assert r.status_code == 200
    assert "object_list" in r.context and "page_obj" in r.context and "q" in r.context
    assert "status_choices" in r.context and "party_choices" in r.context
    assert set(r.context["stats"]) == {"received", "validated", "published"}
    assert received.original_filename in r.content.decode()

    r = client_a.get(reverse("procurement:catalog_upload_list"), {"status": "validated"})
    assert [o.pk for o in r.context["object_list"]] == [validated.pk]
    r = client_a.get(reverse("procurement:catalog_upload_list"),
                     {"party": str(party.pk)})
    assert r.context["page_obj"].paginator.count == 2


# ------------------------------------------------------------------ details


def test_catalogmgmt_item_detail_includes_tiers_queryset(client_a, catalog_item_approved_a,
                                                         tier_active_a):
    r = client_a.get(reverse("procurement:catalog_item_detail",
                             kwargs={"pk": catalog_item_approved_a.pk}))
    assert r.status_code == 200
    assert r.context["obj"].pk == catalog_item_approved_a.pk
    assert tier_active_a in r.context["tiers"]
    assert str(tier_active_a.min_quantity) in r.content.decode()


def test_catalogmgmt_tier_detail_effective_price_keys(client_a, tier_active_a):
    r = client_a.get(reverse("procurement:catalog_tier_detail",
                             kwargs={"pk": tier_active_a.pk}))
    assert r.status_code == 200
    assert r.context["obj"].pk == tier_active_a.pk
    assert r.context["base_price"] == tier_active_a.catalog_item.base_price
    # No discount_pct -> effective price IS the stored unit price.
    assert r.context["effective_price"] == tier_active_a.unit_price
    assert "item_tiers" in r.context


def test_catalogmgmt_batch_detail_counters_and_error_log(client_a, tenant_a, supplier_a,
                                                         _catalogmgmt_media):
    _, party = supplier_a
    batch = _catalogmgmt_batch(tenant_a, party, status="validated")
    r = client_a.get(reverse("procurement:catalog_upload_detail",
                             kwargs={"pk": batch.pk}))
    body = r.content.decode()
    assert r.status_code == 200 and r.context["obj"].pk == batch.pk
    assert "row 2: name is required" in body          # error_log surfaced
    assert ">4<" in body and ">2<" in body            # parsed / accepted / rejected trio


def test_catalogmgmt_punchout_detail_never_renders_secret(client_a, punchout_endpoint_a):
    punchout_endpoint_a.shared_secret = "hunter2-super-secret"
    punchout_endpoint_a.save(update_fields=["shared_secret"])
    r = client_a.get(reverse("procurement:punchout_endpoint_detail",
                             kwargs={"pk": punchout_endpoint_a.pk}))
    body = r.content.decode()
    assert r.status_code == 200
    assert "hunter2-super-secret" not in body
    assert "write-only" in body                        # placeholder note instead


# ------------------------------------------------------------------ create / edit flows


def test_catalogmgmt_item_create_via_post_stamps_created_by(client_a, admin_user,
                                                            supplier_a):
    _, party = supplier_a
    payload = {
        "source_type": "supplier_product",
        "name": "Posted nitrile gloves",
        "supplier": str(party.pk),
        "supplier_part_no": "NW-NIT-M",
        "base_price": "9.45",
        "category_text": "Safety wear",
        "is_active": "on",
    }
    r = client_a.post(reverse("procurement:catalog_item_create"), payload)
    assert r.status_code == 302
    obj = CatalogItem.objects.get(name="Posted nitrile gloves", tenant_id=party.tenant_id)
    assert obj.created_by == admin_user
    assert obj.status == "draft" and obj.number.startswith("PCI-")
    assert r.url == reverse("procurement:catalog_item_detail", kwargs={"pk": obj.pk})


def test_catalogmgmt_item_edit_gated_when_blocked(client_a, catalog_item_blocked_a):
    url = reverse("procurement:catalog_item_edit", kwargs={"pk": catalog_item_blocked_a.pk})
    r = client_a.get(url, follow=True)
    assert r.status_code == 200
    assert any("only draft or rejected" in m.lower() for m in _catalogmgmt_messages(r))
    # Even a crafted POST cannot mutate a blocked header.
    r = client_a.post(url, {"source_type": "supplier_product",
                            "name": "Renamed while blocked", "base_price": "1.00"})
    assert r.status_code == 302
    catalog_item_blocked_a.refresh_from_db()
    assert catalog_item_blocked_a.name == "Generic toner cartridge"
    assert catalog_item_blocked_a.status == "blocked"


def test_catalogmgmt_item_edit_draft_roundtrip(client_a, tenant_a):
    obj = _catalogmgmt_item(tenant_a)
    r = client_a.get(reverse("procurement:catalog_item_edit", kwargs={"pk": obj.pk}))
    assert r.status_code == 200 and r.context["is_edit"] is True
    r = client_a.post(reverse("procurement:catalog_item_edit", kwargs={"pk": obj.pk}),
                      {"source_type": "supplier_product", "name": "Renamed draft line",
                       "base_price": "24.00"})
    assert r.status_code == 302
    obj.refresh_from_db()
    assert obj.name == "Renamed draft line" and obj.base_price == Decimal("24.00")


def test_catalogmgmt_tier_create_stamps_submitted_by(client_a, admin_user,
                                                     catalog_item_approved_a):
    payload = {"catalog_item": str(catalog_item_approved_a.pk),
               "min_quantity": "50", "unit_price": "28.75"}
    r = client_a.post(reverse("procurement:catalog_tier_create"), payload)
    assert r.status_code == 302
    tier = CatalogPriceTier.objects.get(catalog_item=catalog_item_approved_a,
                                        min_quantity=Decimal("50"))
    assert tier.status == "draft" and tier.submitted_by == admin_user
    assert r.url == reverse("procurement:catalog_tier_detail", kwargs={"pk": tier.pk})


def test_catalogmgmt_tier_edit_refused_while_active(client_a, tier_active_a):
    tier_active_a.unit_price = Decimal("31.50")
    tier_active_a.save(update_fields=["unit_price"])
    url = reverse("procurement:catalog_tier_edit", kwargs={"pk": tier_active_a.pk})
    r = client_a.get(url, follow=True)
    assert any("only proposed tiers can be edited" in m.lower()
               for m in _catalogmgmt_messages(r))
    r = client_a.post(url, {"catalog_item": str(tier_active_a.catalog_item_id),
                            "min_quantity": "10", "unit_price": "0.01"})
    assert r.status_code == 302
    tier_active_a.refresh_from_db()
    assert tier_active_a.unit_price == Decimal("31.50")
    assert tier_active_a.status == "active"


def test_catalogmgmt_endpoint_create_stores_secret_and_edit_keeps_it(
        client_a, supplier_a, _catalogmgmt_media):
    _, party = supplier_a
    secret = "create-only-hunter2"
    payload = {"party": str(party.pk), "name": "Grainger OCI gateway",
               "protocol": "oci", "punchout_url": "https://grainger.example/oci",
               "username": "acme-buyer", "shared_secret": secret, "enabled": "on"}
    r = client_a.post(reverse("procurement:punchout_endpoint_create"), payload)
    assert r.status_code == 302
    ep = PunchOutEndpoint.objects.get(name="Grainger OCI gateway")
    assert ep.shared_secret == secret and ep.number.startswith("POE-")

    # The EDIT form never renders nor re-demands the stored secret...
    r = client_a.get(reverse("procurement:punchout_endpoint_edit", kwargs={"pk": ep.pk}))
    assert r.status_code == 200
    assert secret not in r.content.decode()
    # ...and a POST without the secret field keeps the old value.
    r = client_a.post(reverse("procurement:punchout_endpoint_edit", kwargs={"pk": ep.pk}),
                      {"party": str(party.pk), "name": "Grainger OCI gateway v2",
                       "protocol": "oci", "punchout_url": "https://grainger.example/oci",
                       "username": "acme-buyer", "enabled": "on"})
    assert r.status_code == 302
    ep.refresh_from_db()
    assert ep.shared_secret == secret and ep.name == "Grainger OCI gateway v2"


def test_catalogmgmt_batch_create_with_real_csv(client_a, supplier_a,
                                                _catalogmgmt_media):
    _, party = supplier_a
    upload = SimpleUploadedFile("price-list.csv", _CATALOGMGMT_CSV.encode("utf-8"),
                                content_type="text/csv")
    r = client_a.post(reverse("procurement:catalog_upload_create"),
                      {"party": str(party.pk), "file": upload,
                       "notes": "Weekly drop"}, format="multipart")
    assert r.status_code == 302
    batch = CatalogUploadBatch.objects.get(notes="Weekly drop")
    assert batch.status == "received"
    assert batch.original_filename == "price-list.csv"
    assert batch.file.name.endswith(".csv")


# ------------------------------------------------------------------ lifecycle verbs (admin)


def test_catalogmgmt_item_lifecycle_submit_approve_block(client_a, admin_user, tenant_a):
    obj = _catalogmgmt_item(tenant_a)
    detail_url = reverse("procurement:catalog_item_detail", kwargs={"pk": obj.pk})

    r = client_a.post(reverse("procurement:catalog_item_submit", kwargs={"pk": obj.pk}),
                      follow=True)
    obj.refresh_from_db()
    assert obj.status == "pending_approval" and obj.submitted_by == admin_user
    assert obj.submitted_at is not None

    r = client_a.post(reverse("procurement:catalog_item_approve", kwargs={"pk": obj.pk}),
                      follow=True)
    obj.refresh_from_db()
    assert obj.status == "approved"
    assert obj.approved_by == admin_user and obj.approved_at is not None

    r = client_a.post(reverse("procurement:catalog_item_block", kwargs={"pk": obj.pk}),
                      follow=True)
    obj.refresh_from_db()
    assert obj.status == "blocked"

    # Illegal transition: blocking again / approving a blocked row flashes an error, no change.
    r = client_a.post(reverse("procurement:catalog_item_approve", kwargs={"pk": obj.pk}),
                      follow=True)
    assert any("pending approval" in m.lower() for m in _catalogmgmt_messages(r))
    obj.refresh_from_db()
    assert obj.status == "blocked"


def test_catalogmgmt_item_reject_carries_reason_then_resubmits(client_a, admin_user,
                                                               catalog_item_pending_a):
    obj = catalog_item_pending_a
    r = client_a.post(reverse("procurement:catalog_item_reject", kwargs={"pk": obj.pk}),
                      {"reason": "Quote does not match contract pricing."}, follow=True)
    obj.refresh_from_db()
    assert obj.status == "rejected"
    assert obj.rejection_reason == "Quote does not match contract pricing."
    # A rejected entry returns to the maintainer: editable AND resubmittable.
    assert client_a.get(reverse("procurement:catalog_item_edit",
                                kwargs={"pk": obj.pk})).status_code == 200
    client_a.post(reverse("procurement:catalog_item_submit", kwargs={"pk": obj.pk}))
    obj.refresh_from_db()
    assert obj.status == "pending_approval"


def test_catalogmgmt_tier_approve_retire_lifecycle(client_a, admin_user,
                                                   catalog_item_approved_a):
    tier = _catalogmgmt_tier(catalog_item_approved_a)
    client_a.post(reverse("procurement:catalog_tier_approve", kwargs={"pk": tier.pk}))
    tier.refresh_from_db()
    assert tier.status == "active" and tier.approved_by == admin_user
    assert tier.approved_at is not None

    client_a.post(reverse("procurement:catalog_tier_retire", kwargs={"pk": tier.pk}))
    tier.refresh_from_db()
    assert tier.status == "superseded"

    # Retiring a superseded tier is refused and leaves the state alone.
    r = client_a.post(reverse("procurement:catalog_tier_retire", kwargs={"pk": tier.pk}),
                      follow=True)
    assert any("only active tiers can be retired" in m.lower()
               for m in _catalogmgmt_messages(r))
    tier.refresh_from_db()
    assert tier.status == "superseded"


def test_catalogmgmt_upload_validate_counters_then_publish_and_reject(
        client_a, admin_user, tenant_a, supplier_a, uom_a, _catalogmgmt_media):
    _, party = supplier_a

    # validate: 4 parsed rows -> 2 staged pending_approval items + 2 rejects logged.
    batch = _catalogmgmt_batch(tenant_a, party, status="received")
    r = client_a.post(reverse("procurement:catalog_upload_validate",
                              kwargs={"pk": batch.pk}), follow=True)
    batch.refresh_from_db()
    assert batch.status == "validated"
    assert (batch.rows_parsed, batch.rows_accepted, batch.rows_rejected) == (4, 2, 2)
    assert batch.validated_by == admin_user
    assert "row 2" in batch.error_log
    staged = CatalogItem.objects.filter(supplier=party,
                                        source_type="supplier_product",
                                        status="pending_approval")
    assert staged.count() == 2
    assert any("staged" in m.lower() for m in _catalogmgmt_messages(r))

    # publish: validated -> published; validating again is refused.
    client_a.post(reverse("procurement:catalog_upload_publish", kwargs={"pk": batch.pk}))
    batch.refresh_from_db()
    assert batch.status == "published"
    r = client_a.post(reverse("procurement:catalog_upload_validate",
                              kwargs={"pk": batch.pk}), follow=True)
    assert any("validation failed" in m.lower() for m in _catalogmgmt_messages(r))
    assert batch.status == "published"

    # reject straight from received; publishing a rejected batch is refused.
    other = _catalogmgmt_batch(tenant_a, party, status="received")
    client_a.post(reverse("procurement:catalog_upload_reject", kwargs={"pk": other.pk}))
    other.refresh_from_db()
    assert other.status == "rejected"
    r = client_a.post(reverse("procurement:catalog_upload_publish",
                              kwargs={"pk": other.pk}), follow=True)
    assert any("only validated batches" in m.lower() for m in _catalogmgmt_messages(r))
    other.refresh_from_db()
    assert other.status == "rejected"


def test_catalogmgmt_punchout_test_stamps_last_session(client_a, punchout_endpoint_a):
    assert punchout_endpoint_a.last_session_at is None
    r = client_a.post(reverse("procurement:punchout_endpoint_test",
                              kwargs={"pk": punchout_endpoint_a.pk}), follow=True)
    punchout_endpoint_a.refresh_from_db()
    assert punchout_endpoint_a.last_session_at is not None
    assert any("session timestamp recorded" in m.lower()
               for m in _catalogmgmt_messages(r))
    assert _catalogmgmt_audit(PunchOutEndpoint, punchout_endpoint_a,
                              "test").exists()


# ------------------------------------------------------------------ authorization split (post-I2)


def test_catalogmgmt_member_admin_verbs_refused_state_unchanged(
        member_client, catalog_item_pending_a, tier_active_a, upload_batch_received_a):
    cases = [
        ("procurement:catalog_item_approve", catalog_item_pending_a),
        ("procurement:catalog_item_block", catalog_item_pending_a),
        ("procurement:catalog_tier_approve", tier_active_a),
        ("procurement:catalog_upload_validate", upload_batch_received_a),
        ("procurement:catalog_upload_publish", upload_batch_received_a),
    ]
    for url_name, obj in cases:
        r = member_client.post(reverse(url_name, kwargs={"pk": obj.pk}))
        assert r.status_code == 403, url_name   # tenant_admin_required -> PermissionDenied

    catalog_item_pending_a.refresh_from_db()
    assert catalog_item_pending_a.status == "pending_approval"
    tier_active_a.refresh_from_db()
    assert tier_active_a.status == "active"
    upload_batch_received_a.refresh_from_db()
    assert upload_batch_received_a.status == "received"


def test_catalogmgmt_member_can_view_lists_and_details(
        member_client, catalog_item_approved_a, tier_active_a, punchout_endpoint_a,
        upload_batch_received_a):
    urls = [
        reverse("procurement:catalog_item_list"),
        reverse("procurement:catalog_item_detail", kwargs={"pk": catalog_item_approved_a.pk}),
        reverse("procurement:catalog_tier_list"),
        reverse("procurement:catalog_tier_detail", kwargs={"pk": tier_active_a.pk}),
        reverse("procurement:punchout_endpoint_list"),
        reverse("procurement:punchout_endpoint_detail", kwargs={"pk": punchout_endpoint_a.pk}),
        reverse("procurement:catalog_upload_list"),
        reverse("procurement:catalog_upload_detail", kwargs={"pk": upload_batch_received_a.pk}),
    ]
    for url in urls:
        assert member_client.get(url).status_code == 200, url


def test_catalogmgmt_member_can_submit_own_draft(member_client, member_user, tenant_a):
    # Proposing stays open to every member - maker-checker needs makers (view docstring).
    obj = _catalogmgmt_item(tenant_a)
    r = member_client.post(reverse("procurement:catalog_item_submit", kwargs={"pk": obj.pk}))
    assert r.status_code == 302
    obj.refresh_from_db()
    assert obj.status == "pending_approval" and obj.submitted_by == member_user


# ------------------------------------------------------------------ deletes + cross-tenant


def test_catalogmgmt_delete_post_removes_row_and_redirects(
        client_a, tenant_a, supplier_a, _catalogmgmt_media):
    _, party = supplier_a
    item = _catalogmgmt_item(tenant_a)
    # Own parent item: deleting the first row below must not cascade the tier away.
    tier = _catalogmgmt_tier(_catalogmgmt_item(tenant_a, name="Tier host line"))
    endpoint = PunchOutEndpoint.objects.create(
        tenant=tenant_a, party=party, name="Doomed endpoint",
        protocol="cxml", punchout_url="https://doomed.example/cxml")
    batch = _catalogmgmt_batch(tenant_a, party)

    for url_name, obj, list_name in [
        ("procurement:catalog_item_delete", item, "procurement:catalog_item_list"),
        ("procurement:catalog_tier_delete", tier, "procurement:catalog_tier_list"),
        ("procurement:punchout_endpoint_delete", endpoint,
         "procurement:punchout_endpoint_list"),
        ("procurement:catalog_upload_delete", batch, "procurement:catalog_upload_list"),
    ]:
        r = client_a.post(reverse(url_name, kwargs={"pk": obj.pk}))
        assert r.status_code == 302, url_name
        assert r.url == reverse(list_name), url_name
        assert not type(obj).objects.filter(pk=obj.pk).exists(), url_name


def test_catalogmgmt_delete_get_does_not_delete(client_a, tenant_a, supplier_a,
                                                _catalogmgmt_media):
    _, party = supplier_a
    item = _catalogmgmt_item(tenant_a)
    tier = _catalogmgmt_tier(_catalogmgmt_item(tenant_a, name="Get-guard host line"))
    endpoint = PunchOutEndpoint.objects.create(
        tenant=tenant_a, party=party, name="Survivor endpoint",
        protocol="oci", punchout_url="https://survivor.example/oci")
    batch = _catalogmgmt_batch(tenant_a, party)

    for url_name, obj in [
        ("procurement:catalog_item_delete", item),
        ("procurement:catalog_tier_delete", tier),
        ("procurement:punchout_endpoint_delete", endpoint),
        ("procurement:catalog_upload_delete", batch),
    ]:
        # Every delete view is @require_POST: a GET is refused outright (405) and,
        # a fortiori, deletes nothing.
        r = client_a.get(reverse(url_name, kwargs={"pk": obj.pk}))
        assert r.status_code == 405, url_name
        assert type(obj).objects.filter(pk=obj.pk).exists(), url_name


def test_catalogmgmt_cross_tenant_pk_is_404(client_a, tenant_b, catalog_item_b):
    foreign_party = Party.objects.create(tenant=tenant_b, name="Globex punchout co",
                                         kind="organization")
    foreign_endpoint = PunchOutEndpoint.objects.create(
        tenant=tenant_b, party=foreign_party, name="Globex cXML",
        protocol="cxml", punchout_url="https://globex.example/cxml")
    foreign_tier = _catalogmgmt_tier(catalog_item_b)

    routes = [
        # (url_name, pk, method, expected status). GET on a POST-only delete route is
        # refused with 405 before the tenant lookup ever runs; everything else 404s.
        ("procurement:catalog_item_detail", catalog_item_b.pk, "get", 404),
        ("procurement:catalog_item_edit", catalog_item_b.pk, "get", 404),
        ("procurement:catalog_item_delete", catalog_item_b.pk, "get", 405),
        ("procurement:catalog_item_delete", catalog_item_b.pk, "post", 404),
        ("procurement:catalog_item_submit", catalog_item_b.pk, "post", 404),
        ("procurement:catalog_item_approve", catalog_item_b.pk, "post", 404),
        ("procurement:catalog_tier_detail", foreign_tier.pk, "get", 404),
        ("procurement:catalog_tier_delete", foreign_tier.pk, "get", 405),
        ("procurement:catalog_tier_delete", foreign_tier.pk, "post", 404),
        ("procurement:punchout_endpoint_detail", foreign_endpoint.pk, "get", 404),
        ("procurement:punchout_endpoint_delete", foreign_endpoint.pk, "post", 404),
    ]
    for url_name, pk, method, expected in routes:
        fn = getattr(client_a, method)
        r = fn(reverse(url_name, kwargs={"pk": pk}))
        assert r.status_code == expected, f"{url_name} ({method})"


# ------------------------------------------------------------------ audit trail


def test_catalogmgmt_verbs_write_audit_log(client_a, admin_user, catalog_item_pending_a,
                                           tenant_a):
    obj = catalog_item_pending_a
    client_a.post(reverse("procurement:catalog_item_approve", kwargs={"pk": obj.pk}))
    logs = _catalogmgmt_audit(CatalogItem, obj, "approve")
    assert logs.exists()
    assert logs.first().user == admin_user

    draft = _catalogmgmt_item(tenant_a)
    client_a.post(reverse("procurement:catalog_item_delete", kwargs={"pk": draft.pk}))
    assert _catalogmgmt_audit(CatalogItem, draft, "delete").exists()
