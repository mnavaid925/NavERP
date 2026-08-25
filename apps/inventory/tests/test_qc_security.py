"""Inventory 5.15 Quality Control (QC) & Inspection — security.

Adversarial multi-tenancy around the four QC entities: cross-tenant IDOR on every route
shape (GET pages, destructive POSTs, lifecycle verb POSTs), the privilege matrix (config
masters and fate-deciding verbs are admin-gated; operators read everything, draft their
own holds and log defects), anonymous walls, crafted-POST FK injection against every
tenant-scoped pointer, POST-only verbs, tenant-less superuser isolation, and ledger
integrity — no foreign session may ever grow Acme's QRD-/DEF- StockMove book.
"""
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import (
    DefectReport,
    QcChecklist,
    QcRoutingRule,
    QuarantineOrder,
)
from apps.scm.models import StockMove

pytestmark = pytest.mark.django_db

#: Strings minted exclusively for ONE workspace. Both tenants' first documents read
#: QRD-00001 / DEF-00001 (per-tenant numbering), so isolation is asserted ONLY on
#: markers these fixtures mint for one side — never on numbers.
_MARKERS_A = ["Dock Check A", "Catch-all inspect", "Item-tier inspect"]


# ---- module helpers ------------------------------------------------------------------------------


def _qc_assert_login_redirect(response):
    assert response.status_code == 302
    assert "/login" in response.url or response.url.endswith("login")


def _qc_quarantine_payload(item_pk, source_pk, zone_pk, **overrides):
    """A minimal VALID quarantine POST body; overrides carry the adversarial bits."""
    data = {"item": str(item_pk), "lot_serial": "",
            "source_location": str(source_pk), "quarantine_location": str(zone_pk),
            "quantity": "3", "reason": "qc_hold", "reference": "", "notes": ""}
    data.update(overrides)
    return data


def _qc_defect_payload(item_pk, location_pk, **overrides):
    """A minimal VALID defect-report POST body."""
    data = {"item": str(item_pk), "location": str(location_pk), "lot_serial": "",
            "quantity": "1", "defect_type": "packaging", "severity": "major",
            "discovered_during": "receiving", "description": "", "photo": "",
            "photo_url": "", "reported_by": "", "ncr": ""}
    data.update(overrides)
    return data


def _qc_routing_rule_payload(zone_pk, **overrides):
    data = {"name": "Probe gate", "item": "", "category": "", "vendor": "",
            "verdict": "inspect", "qc_location": str(zone_pk), "priority": "10",
            "is_active": "on", "notes": ""}
    data.update(overrides)
    return data


def _qc_checklist_payload(**overrides):
    data = {"name": "Probe checklist", "item": "", "vendor": "",
            "description": "", "is_active": "on"}
    data.update(overrides)
    return data


def _qc_assert_form_refusal(response, field_name):
    """The shared refusal shape: re-rendered form, THAT field errored. The scoped
    <select> usually refuses first ("valid choice"); _reject_foreign's wording is the
    fallback when a stale pk still parses."""
    assert response.status_code == 200
    assert field_name in response.context["form"].errors
    html = response.content.decode()
    assert ("valid choice" in html
            or "That record belongs to another workspace." in html)


# ---- local fixtures ------------------------------------------------------------------------------


@pytest.fixture
def _qc_foreign_ncr(db, tenant_b):
    """A Globex non-conformance — the foreign escalation pointer for the defect form."""
    from apps.scm.models import NonConformance
    return NonConformance.objects.create(
        tenant=tenant_b, title="Foreign finding", description="Foreign workspace control.",
        detected_on=timezone.localdate())


@pytest.fixture
def _qc_tenantless_superuser(db):
    """The platform superuser: tenant=None BY DESIGN — it owns no workspace at all."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="qc-super@naverp.test", username="admin_x",
        password="TestPass123!", tenant=None, is_superuser=True, is_staff=True)


@pytest.fixture
def _qc_super_client(_qc_tenantless_superuser):
    c = Client()
    c.force_login(_qc_tenantless_superuser)
    return c


# ---- 1. IDOR: GET pages -------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_name,prefix", [
    ("qc_checklist_a", "qcchecklist"),
    ("qc_rule_item_a", "qcroutingrule"),
    ("qrd_quarantined_a", "quarantineorder"),
    ("defect_open_a", "defectreport"),
])
def test_qc_idor_gets_on_foreign_pks_return_404(client_b, fixture_name, prefix, request):
    """Globex's admin pointing detail/edit URLs at Acme's rows must read nonexistent —
    even for a document whose lifecycle already posted ledger legs."""
    obj = request.getfixturevalue(fixture_name)
    for action in ("detail", "edit"):
        url = reverse(f"inventory:{prefix}_{action}", args=[obj.pk])
        assert client_b.get(url).status_code == 404


# ---- 2. IDOR: destructive writes + ledger integrity ----------------------------------------------


def test_qc_idor_destructive_posts_leave_acme_rows_and_ledger_intact(
        client_b, tenant_a, qc_checklist_a, qc_rule_item_a, qrd_draft_a,
        qrd_quarantined_a, defect_open_a):
    """Every hostile POST Globex can aim at Acme's QC documents, fired as one battery:
    deletes and lifecycle verbs must 404 AND leave each row exactly where it was AND
    never grow the StockMove book keyed to Acme's QRD- numbers."""
    qrd_legs_before = StockMove.objects.filter(
        tenant=tenant_a, reference__startswith="QRD-").count()
    acme_legs_before = StockMove.objects.filter(tenant=tenant_a).count()
    rows_before = (QcChecklist.objects.count(), QcRoutingRule.objects.count(),
                   QuarantineOrder.objects.count(), DefectReport.objects.count())

    delete_cases = [("qcchecklist_delete", qc_checklist_a),
                    ("qcroutingrule_delete", qc_rule_item_a),
                    ("quarantineorder_delete", qrd_draft_a),
                    ("defectreport_delete", defect_open_a)]
    for name, obj in delete_cases:
        assert client_b.post(reverse(f"inventory:{name}", args=[obj.pk])).status_code == 404

    # qrd_draft_a is BORN quarantined here — the qrd_quarantined_a fixture walks THAT
    # SAME row through quarantine() — so its hold pair is already on the books.
    verb_cases = [("quarantineorder_quarantine", qrd_draft_a, "quarantined"),
                  ("quarantineorder_release", qrd_quarantined_a, "quarantined"),
                  ("quarantineorder_scrap", qrd_quarantined_a, "quarantined"),
                  ("quarantineorder_cancel", qrd_quarantined_a, "quarantined"),
                  ("defectreport_writeoff", defect_open_a, "open"),
                  ("defectreport_close", defect_open_a, "open")]
    for name, obj, expected_status in verb_cases:
        assert client_b.post(reverse(f"inventory:{name}", args=[obj.pk])).status_code == 404
        obj.refresh_from_db()
        assert obj.status == expected_status

    for obj in (qc_checklist_a, qc_rule_item_a, qrd_draft_a, defect_open_a):
        obj.refresh_from_db()  # raises if deleted — the real assertion
    assert (QcChecklist.objects.count(), QcRoutingRule.objects.count(),
            QuarantineOrder.objects.count(), DefectReport.objects.count()) == rows_before
    assert StockMove.objects.filter(
        tenant=tenant_a, reference__startswith="QRD-").count() == qrd_legs_before == 2
    assert StockMove.objects.filter(tenant=tenant_a).count() == acme_legs_before


# ---- 3. Privilege matrix ------------------------------------------------------------------------


def test_qc_member_writes_are_admin_gated(member_client, qc_checklist_a,
                                          qc_rule_item_a, qrd_draft_a, defect_open_a):
    """Config-master CRUD and every fate-deciding verb are @tenant_admin_required: a
    plain member gets 403 (the role is checked BEFORE require_POST) and the targeted
    rows' lifecycle state does not move."""
    forbidden = [
        ("get", "qcchecklist_create", None),
        ("post", "qcchecklist_create", None),
        ("get", "qcchecklist_edit", qc_checklist_a.pk),
        ("post", "qcchecklist_delete", qc_checklist_a.pk),
        ("get", "qcroutingrule_create", None),
        ("post", "qcroutingrule_create", None),
        ("get", "qcroutingrule_edit", qc_rule_item_a.pk),
        ("post", "qcroutingrule_delete", qc_rule_item_a.pk),
        ("post", "quarantineorder_delete", qrd_draft_a.pk),
        ("post", "quarantineorder_release", qrd_draft_a.pk),
        ("post", "quarantineorder_scrap", qrd_draft_a.pk),
        ("post", "quarantineorder_cancel", qrd_draft_a.pk),
        ("post", "defectreport_delete", defect_open_a.pk),
        ("post", "defectreport_writeoff", defect_open_a.pk),
        ("post", "defectreport_close", defect_open_a.pk),
    ]
    for method, name, pk in forbidden:
        url = reverse(f"inventory:{name}") if pk is None else reverse(
            f"inventory:{name}", args=[pk])
        response = getattr(member_client, method)(url)
        assert response.status_code == 403, f"{method.upper()} {name} must be 403"

    qrd_draft_a.refresh_from_db()
    assert qrd_draft_a.status == "draft"
    defect_open_a.refresh_from_db()
    assert defect_open_a.status == "open"


def test_qc_member_reads_and_operator_verbs_are_allowed(member_client, item_a,
                                                        qc_warehouse_a, qc_zone_a,
                                                        qc_stocked_a, qc_checklist_a,
                                                        qc_rule_item_a, qrd_draft_a,
                                                        defect_open_a):
    """The other half of the matrix: members READ all four registers, draft-edit a hold,
    START one (an operator verb) and log/edit defects — 200s on pages, 302s on saves."""
    reads = [("qcchecklist_list", None, qc_checklist_a),
             ("qcroutingrule_list", None, qc_rule_item_a),
             ("quarantineorder_list", None, qrd_draft_a),
             ("defectreport_list", None, defect_open_a)]
    for name, _, obj in reads:
        assert member_client.get(reverse(f"inventory:{name}")).status_code == 200
        assert member_client.get(
            reverse(f"inventory:{name.replace('_list', '_detail')}",
                    args=[obj.pk])).status_code == 200

    # Edit a still-draft hold (login_required verb).
    edit_url = reverse("inventory:quarantineorder_edit", args=[qrd_draft_a.pk])
    assert member_client.get(edit_url).status_code == 200
    assert member_client.post(
        edit_url,
        data=_qc_quarantine_payload(item_a.pk, qc_warehouse_a.pk, qc_zone_a.pk),
    ).status_code == 302

    # Start the hold — the operator verb really posts its transfer pair.
    assert member_client.post(
        reverse("inventory:quarantineorder_quarantine", args=[qrd_draft_a.pk])
    ).status_code == 302
    qrd_draft_a.refresh_from_db()
    assert qrd_draft_a.status == "quarantined"
    assert qrd_draft_a.ledger_moves().count() == 2

    # Log and edit defects.
    assert member_client.get(reverse("inventory:defectreport_create")).status_code == 200
    assert member_client.get(
        reverse("inventory:defectreport_edit", args=[defect_open_a.pk])).status_code == 200
    assert member_client.post(
        reverse("inventory:defectreport_edit", args=[defect_open_a.pk]),
        data=_qc_defect_payload(item_a.pk, qc_warehouse_a.pk),
    ).status_code == 302


# ---- 4. Auth walls ------------------------------------------------------------------------------


def test_qc_anonymous_redirected_on_every_route(client, qc_checklist_a, qc_rule_item_a,
                                                qrd_draft_a, defect_open_a):
    """Every list/detail/create route plus one state-changing verb sits behind
    @login_required — unauthenticated traffic lands on the login page, never a page."""
    targets = {"qcchecklist": qc_checklist_a, "qcroutingrule": qc_rule_item_a,
               "quarantineorder": qrd_draft_a, "defectreport": defect_open_a}
    for prefix, obj in targets.items():
        _qc_assert_login_redirect(client.get(reverse(f"inventory:{prefix}_list")))
        _qc_assert_login_redirect(client.get(reverse(f"inventory:{prefix}_create")))
        _qc_assert_login_redirect(
            client.get(reverse(f"inventory:{prefix}_detail", args=[obj.pk])))
    _qc_assert_login_redirect(client.get(
        reverse("inventory:quarantineorder_quarantine", args=[qrd_draft_a.pk])))


# ---- 5. Crafted-FK containment --------------------------------------------------------------------


@pytest.mark.parametrize("field_name,foreign_fixture", [
    ("item", "item_b"),
    ("source_location", "qc_zone_b"),
    ("quarantine_location", "qc_zone_b"),
])
def test_quarantine_create_rejects_each_foreign_fk(client_a, item_a, qc_warehouse_a,
                                                   qc_zone_a, field_name,
                                                   foreign_fixture, request):
    """Each tenant-scoped pointer on the hold form, aimed at Globex one at a time: the
    form re-renders with THAT field's error and no segregation order appears anywhere."""
    foreign = request.getfixturevalue(foreign_fixture)
    data = _qc_quarantine_payload(item_a.pk, qc_warehouse_a.pk, qc_zone_a.pk)
    data[field_name] = foreign.pk

    total_before = QuarantineOrder.objects.count()
    response = client_a.post(reverse("inventory:quarantineorder_create"), data=data)
    _qc_assert_form_refusal(response, field_name)
    assert QuarantineOrder.objects.count() == total_before


@pytest.mark.parametrize("field_name,foreign_fixture", [
    ("item", "item_b"),
    ("location", "qc_zone_b"),
    ("ncr", "_qc_foreign_ncr"),
])
def test_defect_create_rejects_each_foreign_fk(client_a, item_a, qc_warehouse_a,
                                               field_name, foreign_fixture, request):
    """The defect capture refuses foreign item/location AND a foreign SCM escalation
    pointer as field errors — never a leaked row, never a 500."""
    foreign = request.getfixturevalue(foreign_fixture)
    data = _qc_defect_payload(item_a.pk, qc_warehouse_a.pk)
    data[field_name] = foreign.pk

    total_before = DefectReport.objects.count()
    response = client_a.post(reverse("inventory:defectreport_create"), data=data)
    _qc_assert_form_refusal(response, field_name)
    assert DefectReport.objects.count() == total_before


def test_routing_rule_create_rejects_foreign_qc_location(client_a, qc_zone_a, qc_zone_b):
    """A routing rule IS the receiving gate: posting Globex's zone as its destination
    dies as a field error and leaves the gate catalog untouched."""
    total_before = QcRoutingRule.objects.count()
    response = client_a.post(
        reverse("inventory:qcroutingrule_create"),
        data=_qc_routing_rule_payload(qc_zone_a.pk, qc_location=qc_zone_b.pk))
    _qc_assert_form_refusal(response, "qc_location")
    assert QcRoutingRule.objects.count() == total_before


def test_checklist_create_rejects_foreign_vendor(client_a, vendor_party_b):
    """Pinning a checklist to Globex's vendor party from Acme's session is refused as a
    field error; the atomic parent+formset block saves nothing."""
    total_before = QcChecklist.objects.count()
    response = client_a.post(
        reverse("inventory:qcchecklist_create"),
        data=_qc_checklist_payload(vendor=vendor_party_b.pk))
    _qc_assert_form_refusal(response, "vendor")
    assert QcChecklist.objects.count() == total_before


# ---- 6. Verb discipline ---------------------------------------------------------------------------


def test_qc_state_changing_verbs_reject_get(client_a, qc_checklist_a, qc_rule_item_a,
                                            qrd_draft_a, qrd_quarantined_a,
                                            defect_open_a):
    """GET on every @require_POST route — four deletes and six lifecycle/resolution
    verbs — is a 405, never accidental execution."""
    cases = [("qcchecklist_delete", qc_checklist_a),
             ("qcroutingrule_delete", qc_rule_item_a),
             ("quarantineorder_delete", qrd_draft_a),
             ("quarantineorder_quarantine", qrd_draft_a),
             ("quarantineorder_release", qrd_quarantined_a),
             ("quarantineorder_scrap", qrd_quarantined_a),
             ("quarantineorder_cancel", qrd_quarantined_a),
             ("defectreport_delete", defect_open_a),
             ("defectreport_writeoff", defect_open_a),
             ("defectreport_close", defect_open_a)]
    for name, obj in cases:
        assert client_a.get(reverse(f"inventory:{name}", args=[obj.pk])).status_code == 405


# ---- 7. Superuser isolation -------------------------------------------------------------------------


def test_qc_tenantless_superuser_sees_zero_workspace_rows(
        _qc_super_client, qc_checklist_a, qc_rule_item_a, qrd_quarantined_a,
        defect_written_off_a):
    """tenant=None means NO workspace: all four QC registers render empty even though
    Acme's rows — including fully-posted ones — exist in the database."""
    for name in ["qcchecklist_list", "qcroutingrule_list", "quarantineorder_list",
                 "defectreport_list"]:
        response = _qc_super_client.get(reverse(f"inventory:{name}"))
        assert response.status_code == 200
        assert len(response.context["object_list"]) == 0
        html = response.content.decode()
        for marker in _MARKERS_A:
            assert marker not in html
