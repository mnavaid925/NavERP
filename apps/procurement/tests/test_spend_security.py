"""Procurement 6.14 Spend Analytics & Reporting - isolation & hardening tests.

The defensive half of the 6.14 suite. Every test here asks the same question from a different
angle: *can a caller reach a row, a field or a state transition the product never meant to give
them - and does a hand-edited URL or POST ever reach a 500 instead of a message?*

Laid out in eight sections:

1. **Cross-tenant IDOR** - every pk-scoped 6.14 route (rule, finding, report, snapshot) aimed at
   another workspace's pk returns **404**, and every tenant-B row comes back byte-identical.
2. **In-workspace visibility** - ``is_shared`` is an access-control claim, not a label: a
   colleague's private report (and every snapshot of it) is a 404 on all nine routes for another
   member of the SAME workspace, is absent from the register, and is not counted in its stats.
3. **Register & computed-page isolation** - none of the three registers and none of the six
   computed pages ever renders another workspace's rows, and the tenant-less superuser gets an
   empty (or refused) page rather than everybody's spend.
4. **The authz ladder** - anonymous redirects to ``/login/``; a plain member is refused on the
   three ``@tenant_admin_required`` routes and *allowed* everywhere else (6.14 keeps
   ``spendrule_delete`` and ``spendrule_preview`` member-reachable on purpose); CSRF is enforced
   on every POST; a GET on a ``@require_POST`` verb is 405 and mutates nothing.
5. **Mass assignment** - the crafted-POST surface: another workspace's pk in every FK field on
   all three write forms, plus a forged ``tenant`` / ``number`` / ``status`` / ``owner`` /
   ``dedupe_key`` / ``leakage_amount`` / ``match_count`` / ``last_run_at`` block.
6. **Hostile input** - junk FK filter params, junk enum params, junk dates, page junk and page 2,
   the crafted ``spendrule_create`` prefill, the ``favorite`` open-redirect guard, a malformed
   stored snapshot payload, and the decimal family (``NaN`` / ``Infinity`` / garbage / negative /
   over-``max_digits``) on both money forms (L11 / L35).
7. **Absent prerequisites are REJECTED, never fallen through** (L35) - no note, no justification;
   no action, no disposition; a disposed finding cannot be re-disposed, edited or deleted; a rule
   with no subject is refused rather than matching the entire workspace's spend.
8. **N+1** - the three registers hold their query count as rows are added.

Every negative case is paired with the POSITIVE path proving the guard did not simply break the
feature (L44). All dates derive from ``timezone.localdate()`` (never ``date.today()``) so nothing
here flakes in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models import (
    MaverickSpendFinding,
    SpendClassificationRule,
    SpendReport,
    SpendReportSnapshot,
)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers (module-private)
def _spend_iso(offset_days=0):
    """A date string relative to TODAY as the CODE sees it - ``timezone.localdate()`` (L16)."""
    return (timezone.localdate() + datetime.timedelta(days=offset_days)).isoformat()


def _spend_rule_payload(**overrides):
    """A complete, valid ``SpendClassificationRuleForm`` POST body.

    ``category`` is the one required FK and ``vendor`` is what a ``match_type="vendor"`` rule
    demands - the caller supplies both pks, because every crafted-FK case below flips exactly one
    of them to tenant B's row.
    """
    payload = {
        "name": "Crafted rule",
        "match_type": "vendor",
        "vendor": "",
        "gl_account": "",
        "org_unit": "",
        "keyword": "",
        "invoice_type": "",
        "category": "",
        "priority": "100",
        "applies_to": "both",
        "is_active": "on",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _spend_finding_payload(**overrides):
    """A complete, valid ``MaverickSpendFindingForm`` POST body.

    ``vendor`` is a non-nullable PROTECT FK, and ``clean()`` demands at least one of
    ``supplier_invoice`` / ``invoice_line`` / ``purchase_order`` - both are the caller's, for the
    same reason as above.
    """
    payload = {
        "reason": "no_requisition",
        "severity": "medium",
        "supplier_invoice": "",
        "invoice_line": "",
        "purchase_order": "",
        "vendor": "",
        "category": "",
        "org_unit": "",
        "contract": "",
        "catalog_item": "",
        "document_date": _spend_iso(),
        "amount": "250.00",
        "benchmark_amount": "",
        "is_addressable": "on",
        "detail": "Crafted finding.",
    }
    payload.update(overrides)
    return payload


def _spend_report_payload(**overrides):
    """A complete, valid ``SpendReportForm`` POST body - every axis defaulted, no FK chosen."""
    payload = {
        "name": "Crafted report",
        "description": "",
        "basis": "invoiced",
        "measure": "net_spend",
        "dimension_1": "supplier",
        "dimension_2": "none",
        "date_range": "last_90",
        "date_from": "",
        "date_to": "",
        "vendor": "",
        "category": "",
        "org_unit": "",
        "gl_account": "",
        "min_amount": "",
        "chart_type": "bar",
        "top_n": "20",
        "is_favorite": "",
        "is_shared": "on",
    }
    payload.update(overrides)
    return payload


def _spend_rule_state(obj):
    """Every column a crafted request might move on a classification rule - the freeze probe."""
    obj.refresh_from_db()
    return (obj.tenant_id, obj.name, obj.match_type, obj.vendor_id, obj.gl_account_id,
            obj.org_unit_id, obj.keyword, obj.invoice_type, obj.category_id, obj.priority,
            obj.applies_to, obj.is_active, obj.notes, obj.match_count, obj.last_matched_at)


def _spend_finding_state(obj):
    obj.refresh_from_db()
    return (obj.tenant_id, obj.number, obj.status, obj.reason, obj.severity, obj.amount,
            obj.benchmark_amount, obj.leakage_amount, obj.dedupe_key, obj.detail,
            obj.is_addressable, obj.document_date, obj.vendor_id, obj.category_id,
            obj.org_unit_id, obj.supplier_invoice_id, obj.invoice_line_id, obj.purchase_order_id,
            obj.contract_id, obj.catalog_item_id, obj.resolution_note, obj.resolved_by_id,
            obj.resolved_at, obj.detected_at)


def _spend_report_state(obj):
    obj.refresh_from_db()
    return (obj.tenant_id, obj.number, obj.name, obj.description, obj.basis, obj.measure,
            obj.dimension_1, obj.dimension_2, obj.date_range, obj.date_from, obj.date_to,
            obj.vendor_id, obj.category_id, obj.org_unit_id, obj.gl_account_id, obj.min_amount,
            obj.chart_type, obj.top_n, obj.is_favorite, obj.is_shared, obj.owner_id,
            obj.last_run_at)


def _spend_snapshot_state(obj):
    obj.refresh_from_db()
    return (obj.tenant_id, obj.report_id, obj.title, obj.generated_by_id, obj.summary, obj.data,
            obj.row_count)


def _spend_counts():
    """Row counts of every table 6.14 can write - the "nothing was created" probe."""
    return {model.__name__: model.objects.count() for model in
            (SpendClassificationRule, MaverickSpendFinding, SpendReport, SpendReportSnapshot)}


#: Every 6.14 page that RENDERS and needs NO pk.
_SPEND_PAGE_ROUTES = (
    "procurement:spend_dashboard",
    "procurement:category_spend",
    "procurement:spend_export",
    "procurement:spend_export_download",
    "procurement:classification_workbench",
    "procurement:maverick_dashboard",
    "procurement:spendrule_list",
    "procurement:spendrule_create",
    "procurement:maverickfinding_list",
    "procurement:maverickfinding_create",
    "procurement:spendreport_list",
    "procurement:spendreport_create",
)

#: Every 6.14 page that RENDERS off a pk: (url name, fixture kind).
_SPEND_PK_ROUTES = (
    ("procurement:spendrule_detail", "rule"),
    ("procurement:spendrule_edit", "rule"),
    ("procurement:maverickfinding_detail", "finding"),
    ("procurement:maverickfinding_edit", "finding"),
    ("procurement:spendreport_detail", "report"),
    ("procurement:spendreport_edit", "report"),
    ("procurement:spendreport_export", "report"),
    ("procurement:spendreportsnapshot_detail", "snapshot"),
    ("procurement:spendreportsnapshot_export", "snapshot"),
)

#: Every POST-only verb that takes a pk, with a body that would otherwise succeed.
_SPEND_VERB_ROUTES = (
    ("procurement:spendrule_delete", "rule", {}),
    ("procurement:spendrule_preview", "rule", {}),
    ("procurement:maverickfinding_delete", "finding", {}),
    ("procurement:maverickfinding_disposition", "finding",
     {"action": "acknowledge", "resolution_note": "crafted"}),
    ("procurement:spendreport_delete", "report", {}),
    ("procurement:spendreport_run", "report", {}),
    ("procurement:spendreport_snapshot", "report", {}),
    ("procurement:spendreport_favorite", "report", {}),
    ("procurement:spendreportsnapshot_delete", "snapshot", {}),
)

#: The three routes ``@tenant_admin_required`` guards in 6.14. ``maverick_scan`` takes no pk.
_SPEND_ADMIN_ONLY_ROUTES = (
    ("procurement:maverick_scan", None),
    ("procurement:maverickfinding_delete", "finding"),
    ("procurement:maverickfinding_disposition", "finding"),
)

#: Query strings anybody can type into the address bar. Every one must render, never 500 (L11).
_SPEND_JUNK_QUERIES = (
    {"category": "abc"},
    {"category": "999999999999999999999"},
    {"vendor": "-1"},
    {"vendor": "²"},
    {"org_unit": "abc"},
    {"gl_account": "9" * 40},
    {"is_active": "abc"},
    {"addressable": "maybe"},
    {"is_favorite": "yes"},
    {"status": "not-a-status", "reason": "nope", "severity": "extreme", "measure": "zzz"},
    {"basis": "xx", "range": "yy", "dimension": "zz", "group_by": "qq"},
    {"range": "custom", "date_from": "not-a-date", "date_to": "9999-99-99"},
    {"range": "custom", "date_from": "9999-12-31", "date_to": "1899-01-01"},
    {"page": "abc"},
    {"page": "999"},
    {"page": "0"},
    {"page": "-5"},
    {"q": "'; DROP TABLE procurement_spendreport; --"},
)


@pytest.fixture
def _spend_hostile_vendor_a(db, tenant_a, usd, gl_expense_a):
    """A tenant-A supplier whose NAME is a spreadsheet formula, with recognised spend behind it.

    Everything about it is legal input - a supplier really can be called that - which is exactly
    why every exported cell has to be neutralised rather than trusted.
    """
    from apps.core.models import Party, PartyRole
    from apps.procurement.models import SupplierInvoice, SupplierInvoiceLine

    party = Party.objects.create(tenant=tenant_a, name="=cmd|' /C calc'!A0",
                                 kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="supplier", status="active")
    invoice = SupplierInvoice.objects.create(
        tenant=tenant_a, vendor=party, invoice_number="SUP-EVIL-1",
        invoice_date=timezone.localdate(), status="approved", invoice_type="standard",
        currency=usd)
    SupplierInvoiceLine.objects.create(
        invoice=invoice, description="@SUM(1+1)*cmd", sku_hint="EVL-1",
        quantity=Decimal("1"), unit_price=Decimal("99.00"), gl_account=gl_expense_a)
    return party


# ==================================================================== 1. cross-tenant IDOR
def test_spend_cross_tenant_pks_404_on_every_scoped_route(
        client_a, spend_rule_b, spend_finding_b, spend_report_b, spend_snapshot_b,
        spend_vendor_b, spend_category_b, spend_invoice_b, spend_po_b):
    """Tenant A's admin aiming any pk-scoped 6.14 route at a tenant-B row gets 404 - reads,
    edits, deletes and every verb alike - and every tenant-B row is byte-identical afterwards.

    No rule is previewed (which would stamp ``match_count``), no finding is disposed, no report is
    run and no snapshot is minted or destroyed out of another workspace's data.
    """
    before = (_spend_rule_state(spend_rule_b), _spend_finding_state(spend_finding_b),
              _spend_report_state(spend_report_b), _spend_snapshot_state(spend_snapshot_b))
    counts = _spend_counts()

    probes = [
        # --- SpendClassificationRule
        ("GET", "procurement:spendrule_detail", spend_rule_b.pk, None),
        ("GET", "procurement:spendrule_edit", spend_rule_b.pk, None),
        ("POST", "procurement:spendrule_edit", spend_rule_b.pk,
         _spend_rule_payload(name="hijacked", vendor=str(spend_vendor_b.pk),
                             category=str(spend_category_b.pk))),
        ("POST", "procurement:spendrule_delete", spend_rule_b.pk, None),
        ("POST", "procurement:spendrule_preview", spend_rule_b.pk, None),
        # --- MaverickSpendFinding
        ("GET", "procurement:maverickfinding_detail", spend_finding_b.pk, None),
        ("GET", "procurement:maverickfinding_edit", spend_finding_b.pk, None),
        ("POST", "procurement:maverickfinding_edit", spend_finding_b.pk,
         _spend_finding_payload(detail="hijacked", vendor=str(spend_vendor_b.pk),
                                supplier_invoice=str(spend_invoice_b.pk))),
        ("POST", "procurement:maverickfinding_delete", spend_finding_b.pk, None),
        ("POST", "procurement:maverickfinding_disposition", spend_finding_b.pk,
         {"action": "dismiss", "resolution_note": "not yours"}),
        # --- SpendReport
        ("GET", "procurement:spendreport_detail", spend_report_b.pk, None),
        ("GET", "procurement:spendreport_edit", spend_report_b.pk, None),
        ("POST", "procurement:spendreport_edit", spend_report_b.pk,
         _spend_report_payload(name="hijacked")),
        ("GET", "procurement:spendreport_export", spend_report_b.pk, None),
        ("POST", "procurement:spendreport_delete", spend_report_b.pk, None),
        ("POST", "procurement:spendreport_run", spend_report_b.pk, None),
        ("POST", "procurement:spendreport_snapshot", spend_report_b.pk, None),
        ("POST", "procurement:spendreport_favorite", spend_report_b.pk, None),
        # --- SpendReportSnapshot
        ("GET", "procurement:spendreportsnapshot_detail", spend_snapshot_b.pk, None),
        ("GET", "procurement:spendreportsnapshot_export", spend_snapshot_b.pk, None),
        ("POST", "procurement:spendreportsnapshot_delete", spend_snapshot_b.pk, None),
    ]
    for method, name, pk, payload in probes:
        url = reverse(name, args=[pk])
        resp = client_a.post(url, payload or {}) if method == "POST" else client_a.get(url)
        assert resp.status_code == 404, (method, name)

    assert (_spend_rule_state(spend_rule_b), _spend_finding_state(spend_finding_b),
            _spend_report_state(spend_report_b),
            _spend_snapshot_state(spend_snapshot_b)) == before
    assert _spend_counts() == counts


def test_spend_own_tenant_rows_reachable_on_the_same_routes(
        client_a, spend_rule_vendor_a, spend_finding_open_a, spend_report_a, spend_snapshot_a):
    """L44 pair for the IDOR matrix: the identical routes against tenant A's OWN rows render -
    the 404s above are tenant scoping, not a broken URLconf or a missing template."""
    pk_for = {"rule": spend_rule_vendor_a.pk, "finding": spend_finding_open_a.pk,
              "report": spend_report_a.pk, "snapshot": spend_snapshot_a.pk}
    for name, kind in _SPEND_PK_ROUTES:
        resp = client_a.get(reverse(name, args=[pk_for[kind]]))
        assert resp.status_code == 200, name


def test_spend_cross_tenant_scan_never_touches_another_workspace(
        client_a, tenant_b, spend_invoice_a, spend_invoice_line_a, spend_po_a, spend_po_line_a,
        spend_invoice_b, spend_invoice_line_b, spend_po_b, spend_po_line_b, spend_finding_b):
    """The detector run is workspace-scoped at the ENGINE, not merely at the page: tenant A's
    admin scanning their own window raises nothing against tenant B's invoices and orders, and
    leaves tenant B's existing finding exactly as it was."""
    before = _spend_finding_state(spend_finding_b)
    b_before = MaverickSpendFinding.objects.filter(tenant=tenant_b).count()

    resp = client_a.post(reverse("procurement:maverick_scan"), {"range": "last_90"})
    assert resp.status_code == 302

    assert MaverickSpendFinding.objects.filter(tenant=tenant_b).count() == b_before
    assert _spend_finding_state(spend_finding_b) == before


# ============================================================= 2. in-workspace visibility
def test_spend_private_report_is_404_for_a_colleague_in_the_same_workspace(
        client_a, spend_report_private_a, spend_snapshot_private_a):
    """``is_shared=False`` is an access-control claim the pages PRINT, so the code has to mean it:
    every fetch goes through ``visible_reports`` / ``_snapshot_qs``, and a colleague's private
    report - same tenant, different owner - is a 404 on all nine of its routes."""
    before = (_spend_report_state(spend_report_private_a),
              _spend_snapshot_state(spend_snapshot_private_a))
    counts = _spend_counts()

    probes = [
        ("GET", "procurement:spendreport_detail", spend_report_private_a.pk, None),
        ("GET", "procurement:spendreport_edit", spend_report_private_a.pk, None),
        ("POST", "procurement:spendreport_edit", spend_report_private_a.pk,
         _spend_report_payload(name="taken over")),
        ("GET", "procurement:spendreport_export", spend_report_private_a.pk, None),
        ("POST", "procurement:spendreport_delete", spend_report_private_a.pk, None),
        ("POST", "procurement:spendreport_run", spend_report_private_a.pk, None),
        ("POST", "procurement:spendreport_snapshot", spend_report_private_a.pk, None),
        ("POST", "procurement:spendreport_favorite", spend_report_private_a.pk, None),
        ("GET", "procurement:spendreportsnapshot_detail", spend_snapshot_private_a.pk, None),
        ("GET", "procurement:spendreportsnapshot_export", spend_snapshot_private_a.pk, None),
        ("POST", "procurement:spendreportsnapshot_delete", spend_snapshot_private_a.pk, None),
    ]
    for method, name, pk, payload in probes:
        url = reverse(name, args=[pk])
        resp = client_a.post(url, payload or {}) if method == "POST" else client_a.get(url)
        assert resp.status_code == 404, (method, name)

    assert (_spend_report_state(spend_report_private_a),
            _spend_snapshot_state(spend_snapshot_private_a)) == before
    assert _spend_counts() == counts


def test_spend_private_report_absent_from_the_register_and_its_stats(
        client_a, spend_report_a, spend_report_private_a, spend_snapshot_a,
        spend_snapshot_private_a):
    """A private report is not merely unlabelled on somebody else's register - it is not there,
    and neither it nor its snapshots are folded into the stat strip above the list."""
    resp = client_a.get(reverse("procurement:spendreport_list"))
    assert resp.status_code == 200
    pks = [row.pk for row in resp.context["object_list"]]
    assert spend_report_a.pk in pks
    assert spend_report_private_a.pk not in pks
    assert resp.context["stats"]["total"] == 1
    assert resp.context["stats"]["snapshots"] == 1

    # The export page lists saved reports too, under the SAME rule.
    resp = client_a.get(reverse("procurement:spend_export"))
    assert resp.status_code == 200
    panel = [row.pk for row in resp.context["reports"]]
    assert spend_report_a.pk in panel
    assert spend_report_private_a.pk not in panel
    assert spend_snapshot_private_a.pk not in [row.pk for row in resp.context["snapshots"]]


def test_spend_private_report_still_belongs_to_its_owner(
        member_client, spend_report_private_a, spend_snapshot_private_a):
    """L44 pair for the visibility rule: the OWNER reads, runs, exports and lists their own
    private report exactly as before - the 404s above are the rule working, not the feature
    broken."""
    for name in ("procurement:spendreport_detail", "procurement:spendreport_edit",
                 "procurement:spendreport_export"):
        resp = member_client.get(reverse(name, args=[spend_report_private_a.pk]))
        assert resp.status_code == 200, name
    assert member_client.get(reverse(
        "procurement:spendreportsnapshot_detail",
        args=[spend_snapshot_private_a.pk])).status_code == 200

    resp = member_client.get(reverse("procurement:spendreport_list"))
    assert spend_report_private_a.pk in [row.pk for row in resp.context["object_list"]]

    resp = member_client.post(reverse("procurement:spendreport_run",
                                      args=[spend_report_private_a.pk]))
    assert resp.status_code == 302
    spend_report_private_a.refresh_from_db()
    assert spend_report_private_a.last_run_at is not None


# ======================================================= 3. register & computed-page isolation
def test_spend_registers_never_render_another_workspaces_rows(
        client_a, spend_rule_vendor_a, spend_finding_open_a, spend_report_a,
        spend_rule_b, spend_finding_b, spend_report_b):
    """All three 6.14 registers, in one pass: tenant A's own row is present (positive) and tenant
    B's row is absent (negative) in the SAME response."""
    checks = (
        ("procurement:spendrule_list", spend_rule_vendor_a.pk, spend_rule_b.pk),
        ("procurement:maverickfinding_list", spend_finding_open_a.pk, spend_finding_b.pk),
        ("procurement:spendreport_list", spend_report_a.pk, spend_report_b.pk),
    )
    for name, mine, theirs in checks:
        resp = client_a.get(reverse(name))
        assert resp.status_code == 200, name
        pks = [row.pk for row in resp.context["object_list"]]
        assert mine in pks, name
        assert theirs not in pks, name


def test_spend_computed_pages_never_render_another_workspaces_spend(
        client_a, spend_invoice_a, spend_invoice_line_a, spend_vendor_a,
        spend_invoice_b, spend_invoice_line_b, spend_vendor_b):
    """The dashboard, the category page and the export are COMPUTED - nothing narrows them but
    the tenant scoping itself, so a slip here puts another workspace's suppliers and invoice
    values on this buyer's board."""
    mine, theirs = spend_vendor_a.name, spend_vendor_b.name

    resp = client_a.get(reverse("procurement:spend_dashboard"))
    assert resp.status_code == 200
    labels = [row["label"] for row in resp.context["by_supplier"]]
    assert mine in labels
    assert theirs not in labels

    resp = client_a.get(reverse("procurement:category_spend"))
    assert resp.status_code == 200
    labels = [row["label"] for row in resp.context["rows"]]
    assert mine in labels
    assert theirs not in labels

    resp = client_a.get(reverse("procurement:spend_export"), {"dimension": "none"})
    assert resp.status_code == 200
    cells = [str(cell) for row in resp.context["preview_rows"] for cell in row]
    assert mine in cells
    assert theirs not in cells

    body = client_a.get(reverse("procurement:spend_export_download"),
                        {"dimension": "none"}).content.decode()
    assert mine in body
    assert theirs not in body
    assert spend_invoice_b.invoice_number not in body


def test_spend_workbench_and_maverick_board_never_render_another_workspaces_rows(
        client_a, spend_po_a, spend_po_line_a, spend_vendor_a, spend_finding_open_a,
        spend_po_b, spend_po_line_b, spend_vendor_b, spend_finding_b):
    """The other two computed pages get their own probe: the classification workbench (grouped
    unclassified lines) and the maverick board (grouped findings). Committed basis on the
    workbench, because a PO line carries no item FK and therefore always lands in the
    unclassified queue - a row that dropped out for being classified would prove nothing."""
    resp = client_a.get(reverse("procurement:classification_workbench"),
                        {"basis": "committed", "group_by": "vendor"})
    assert resp.status_code == 200
    labels = [row["label"] for row in resp.context["rows"]]
    assert spend_vendor_a.name in labels
    assert spend_vendor_b.name not in labels

    resp = client_a.get(reverse("procurement:maverick_dashboard"))
    assert resp.status_code == 200
    labels = [row["label"] for row in resp.context["by_vendor"]]
    assert spend_vendor_a.name in labels
    assert spend_vendor_b.name not in labels
    assert resp.context["stats"]["findings"] == 1


def test_spend_tenantless_superuser_sees_nobodys_rows(
        db, spend_rule_vendor_a, spend_finding_open_a, spend_report_a, spend_snapshot_a,
        spend_rule_b, spend_report_b):
    """The superuser carries ``tenant=None`` by design: the registers come back EMPTY (never
    every workspace's rows), every computed page and every write page refuses with a redirect to
    the dashboard rather than rendering somebody's spend or minting an orphan row, and a
    tenant-scoped detail is a 404 for them too."""
    from apps.accounts.models import User
    root = User.objects.create_superuser(email="root@naverp.test", username="root_spend",
                                         password="TestPass123!")
    assert root.tenant is None
    c = Client()
    c.force_login(root)

    for name in ("procurement:spendrule_list", "procurement:spendreport_list"):
        resp = c.get(reverse(name))
        assert resp.status_code == 200, name
        assert list(resp.context["object_list"]) == [], name

    home = reverse("dashboard:home")
    for name in ("procurement:spend_dashboard", "procurement:category_spend",
                 "procurement:spend_export", "procurement:spend_export_download",
                 "procurement:classification_workbench", "procurement:maverick_dashboard",
                 "procurement:maverickfinding_list", "procurement:spendrule_create",
                 "procurement:maverickfinding_create", "procurement:spendreport_create"):
        resp = c.get(reverse(name))
        assert resp.status_code == 302, name
        assert resp["Location"] == home, name

    pk_for = {"rule": spend_rule_vendor_a.pk, "finding": spend_finding_open_a.pk,
              "report": spend_report_a.pk, "snapshot": spend_snapshot_a.pk}
    for name, kind in _SPEND_PK_ROUTES:
        assert c.get(reverse(name, args=[pk_for[kind]])).status_code == 404, name


# ==================================================================== 4. the authz ladder
def test_spend_anonymous_redirected_to_login_on_every_route(
        db, spend_rule_vendor_a, spend_finding_open_a, spend_report_a, spend_snapshot_a):
    """No 6.14 URL - page, pk page or verb - answers an unauthenticated request; each one bounces
    to ``/login/`` and every row is untouched afterwards."""
    anon = Client()
    login_prefix = reverse("accounts:login")
    assert login_prefix == "/login/"
    before = (_spend_rule_state(spend_rule_vendor_a),
              _spend_finding_state(spend_finding_open_a),
              _spend_report_state(spend_report_a),
              _spend_snapshot_state(spend_snapshot_a))
    counts = _spend_counts()

    pk_for = {"rule": spend_rule_vendor_a.pk, "finding": spend_finding_open_a.pk,
              "report": spend_report_a.pk, "snapshot": spend_snapshot_a.pk}

    for name in _SPEND_PAGE_ROUTES:
        resp = anon.get(reverse(name))
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    for name, kind in _SPEND_PK_ROUTES:
        resp = anon.get(reverse(name, args=[pk_for[kind]]))
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    for name, kind, body in _SPEND_VERB_ROUTES:
        resp = anon.post(reverse(name, args=[pk_for[kind]]), body)
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    resp = anon.post(reverse("procurement:maverick_scan"), {"range": "last_90"})
    assert resp.status_code == 302
    assert resp["Location"].startswith(login_prefix)

    assert (_spend_rule_state(spend_rule_vendor_a),
            _spend_finding_state(spend_finding_open_a),
            _spend_report_state(spend_report_a),
            _spend_snapshot_state(spend_snapshot_a)) == before
    assert _spend_counts() == counts


def test_spend_member_refused_on_every_admin_only_route(
        member_client, spend_finding_open_a, spend_vendor_a, spend_invoice_a, tenant_a):
    """``@tenant_admin_required`` guards exactly three 6.14 routes - the detector scan (it
    re-reads a whole window of spend), the finding disposition (accepting maverick spend as
    "justified" is a governance decision) and the finding delete (strictly stronger than
    dismissing one). A plain workspace member gets PermissionDenied (403) on all three, by GET
    and by POST alike, and nothing moves."""
    before = _spend_finding_state(spend_finding_open_a)
    counts = _spend_counts()

    bodies = {
        "procurement:maverick_scan": {"range": "last_90"},
        "procurement:maverickfinding_delete": {},
        "procurement:maverickfinding_disposition": {"action": "dismiss",
                                                    "resolution_note": "member says so"},
    }
    for name, kind in _SPEND_ADMIN_ONLY_ROUTES:
        url = reverse(name) if kind is None else reverse(name, args=[spend_finding_open_a.pk])
        assert member_client.post(url, bodies[name]).status_code == 403, name
        # The gate sits OUTSIDE @require_POST, so a member is refused before the method check.
        assert member_client.get(url).status_code == 403, name

    assert _spend_finding_state(spend_finding_open_a) == before
    assert _spend_counts() == counts


def test_spend_member_may_use_every_other_route(
        member_client, spend_rule_vendor_a, spend_finding_open_a, spend_report_a,
        spend_snapshot_a, spend_vendor_a, spend_category_a, spend_po_a):
    """L44 pair for the admin gate: 6.14 is deliberately open to any workspace member everywhere
    else - the buyer who owns the category is the person who writes its rules. Every page
    renders, a rule can be written, previewed and deleted, a finding can be raised and a report
    can be built - the two the gate must NOT catch are ``spendrule_delete`` and
    ``spendrule_preview``."""
    for name in _SPEND_PAGE_ROUTES:
        assert member_client.get(reverse(name)).status_code == 200, name

    pk_for = {"rule": spend_rule_vendor_a.pk, "finding": spend_finding_open_a.pk,
              "report": spend_report_a.pk, "snapshot": spend_snapshot_a.pk}
    for name, kind in _SPEND_PK_ROUTES:
        assert member_client.get(reverse(name, args=[pk_for[kind]])).status_code == 200, name

    resp = member_client.post(reverse("procurement:spendrule_preview",
                                      args=[spend_rule_vendor_a.pk]))
    assert resp.status_code == 302
    spend_rule_vendor_a.refresh_from_db()
    assert spend_rule_vendor_a.last_matched_at is not None

    resp = member_client.post(
        reverse("procurement:maverickfinding_create"),
        _spend_finding_payload(vendor=str(spend_vendor_a.pk),
                               purchase_order=str(spend_po_a.pk)))
    assert resp.status_code == 302
    assert MaverickSpendFinding.objects.filter(reason="no_requisition").exists()

    resp = member_client.post(reverse("procurement:spendrule_delete",
                                      args=[spend_rule_vendor_a.pk]))
    assert resp.status_code == 302
    assert not SpendClassificationRule.objects.filter(pk=spend_rule_vendor_a.pk).exists()


def test_spend_csrf_enforced_on_every_post_route(
        admin_user, spend_rule_vendor_a, spend_finding_open_a, spend_report_a, spend_snapshot_a,
        spend_vendor_a, spend_category_a, spend_po_a):
    """A logged-in session is not enough: every mutating 6.14 POST needs a CSRF token. Without
    one each is rejected 403 and nothing is created, stamped, disposed or deleted."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    before = (_spend_rule_state(spend_rule_vendor_a),
              _spend_finding_state(spend_finding_open_a),
              _spend_report_state(spend_report_a),
              _spend_snapshot_state(spend_snapshot_a))
    counts = _spend_counts()

    posts = [
        (reverse("procurement:spendrule_create"),
         _spend_rule_payload(vendor=str(spend_vendor_a.pk),
                             category=str(spend_category_a.pk))),
        (reverse("procurement:spendrule_edit", args=[spend_rule_vendor_a.pk]),
         _spend_rule_payload(vendor=str(spend_vendor_a.pk),
                             category=str(spend_category_a.pk))),
        (reverse("procurement:spendrule_delete", args=[spend_rule_vendor_a.pk]), {}),
        (reverse("procurement:spendrule_preview", args=[spend_rule_vendor_a.pk]), {}),
        (reverse("procurement:maverickfinding_create"),
         _spend_finding_payload(vendor=str(spend_vendor_a.pk),
                                purchase_order=str(spend_po_a.pk))),
        (reverse("procurement:maverickfinding_edit", args=[spend_finding_open_a.pk]),
         _spend_finding_payload(vendor=str(spend_vendor_a.pk),
                                purchase_order=str(spend_po_a.pk))),
        (reverse("procurement:maverickfinding_delete", args=[spend_finding_open_a.pk]), {}),
        (reverse("procurement:maverickfinding_disposition", args=[spend_finding_open_a.pk]),
         {"action": "dismiss", "resolution_note": "no token"}),
        (reverse("procurement:maverick_scan"), {"range": "last_90"}),
        (reverse("procurement:spendreport_create"), _spend_report_payload()),
        (reverse("procurement:spendreport_edit", args=[spend_report_a.pk]),
         _spend_report_payload(name="no token")),
        (reverse("procurement:spendreport_delete", args=[spend_report_a.pk]), {}),
        (reverse("procurement:spendreport_run", args=[spend_report_a.pk]), {}),
        (reverse("procurement:spendreport_snapshot", args=[spend_report_a.pk]), {}),
        (reverse("procurement:spendreport_favorite", args=[spend_report_a.pk]), {}),
        (reverse("procurement:spendreportsnapshot_delete", args=[spend_snapshot_a.pk]), {}),
    ]
    for url, body in posts:
        assert csrf_client.post(url, body).status_code == 403, url

    assert (_spend_rule_state(spend_rule_vendor_a),
            _spend_finding_state(spend_finding_open_a),
            _spend_report_state(spend_report_a),
            _spend_snapshot_state(spend_snapshot_a)) == before
    assert _spend_counts() == counts

    # L44 pair: the SAME csrf-enforcing session reads happily - only unsafe methods are gated.
    assert csrf_client.get(reverse("procurement:spendreport_detail",
                                   args=[spend_report_a.pk])).status_code == 200


def test_spend_get_on_post_only_verbs_is_405_and_never_mutates(
        client_a, spend_rule_vendor_a, spend_finding_open_a, spend_report_a, spend_snapshot_a):
    """``@require_POST`` fires before ``crud_delete``'s own self-defence: a GET on any 6.14 verb
    URL is refused outright - no rule previewed, no report run, no snapshot minted - and every
    row survives untouched."""
    pk_for = {"rule": spend_rule_vendor_a.pk, "finding": spend_finding_open_a.pk,
              "report": spend_report_a.pk, "snapshot": spend_snapshot_a.pk}
    before = (_spend_rule_state(spend_rule_vendor_a),
              _spend_finding_state(spend_finding_open_a),
              _spend_report_state(spend_report_a),
              _spend_snapshot_state(spend_snapshot_a))
    counts = _spend_counts()

    for name, kind, _body in _SPEND_VERB_ROUTES:
        assert client_a.get(reverse(name, args=[pk_for[kind]])).status_code == 405, name
    assert client_a.get(reverse("procurement:maverick_scan")).status_code == 405

    assert (_spend_rule_state(spend_rule_vendor_a),
            _spend_finding_state(spend_finding_open_a),
            _spend_report_state(spend_report_a),
            _spend_snapshot_state(spend_snapshot_a)) == before
    assert _spend_counts() == counts


# ==================================================================== 5. mass assignment
def test_spend_rule_create_rejects_another_workspaces_foreign_keys(
        client_a, spend_vendor_a, spend_category_a, spend_vendor_b, spend_category_b,
        gl_expense_b, org_unit_b, gl_expense_a, org_unit_a):
    """A narrowed ``<select>`` is UX, not a boundary: a hand-crafted POST naming tenant B's
    supplier, GL account, cost centre or category lands as a FIELD error and saves nothing.

    Each scope is posted on its own, with every OTHER field a valid tenant-A value, so the
    rejection can only be the crafted one.
    """
    before = SpendClassificationRule.objects.count()
    url = reverse("procurement:spendrule_create")

    crafted = (
        ("vendor", spend_vendor_b.pk, {"match_type": "vendor"}),
        ("gl_account", gl_expense_b.pk, {"match_type": "gl_account", "vendor": ""}),
        ("org_unit", org_unit_b.pk, {"match_type": "org_unit", "vendor": ""}),
        ("category", spend_category_b.pk, {"match_type": "vendor"}),
    )
    for field, value, extra in crafted:
        # Tenant A's own valid pks first, then this case's overrides (a gl_account / org_unit rule
        # clears ``vendor``), then the ONE crafted foreign pk. Merged into a single dict rather
        # than splatted alongside ``vendor=``/``category=`` keywords, because ``extra``
        # deliberately re-specifies ``vendor`` and passing both is a TypeError.
        fields = {"vendor": str(spend_vendor_a.pk), "category": str(spend_category_a.pk), **extra}
        fields[field] = str(value)
        payload = _spend_rule_payload(**fields)
        resp = client_a.post(url, payload)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field

    assert SpendClassificationRule.objects.count() == before


def test_spend_rule_create_saves_with_the_request_tenant_and_ignores_forged_stamps(
        client_a, tenant_a, tenant_b, spend_vendor_a, spend_category_a):
    """L44 pair for the crafted-FK matrix, and the mass-assignment probe in one: the same POST
    with tenant A's own pks SAVES - and the forged ``tenant`` / ``match_count`` /
    ``last_matched_at`` keys riding along are ignored, because none of them is a form field."""
    resp = client_a.post(
        reverse("procurement:spendrule_create"),
        _spend_rule_payload(name="Meridian catch-all", vendor=str(spend_vendor_a.pk),
                            category=str(spend_category_a.pk),
                            tenant=str(tenant_b.pk), match_count="999",
                            last_matched_at="2020-01-01T00:00", id="1"))
    assert resp.status_code == 302

    rule = SpendClassificationRule.objects.get(name="Meridian catch-all")
    assert rule.tenant_id == tenant_a.pk
    assert rule.match_count == 0
    assert rule.last_matched_at is None
    assert rule.vendor_id == spend_vendor_a.pk


def test_spend_finding_create_rejects_another_workspaces_foreign_keys(
        client_a, spend_vendor_a, spend_po_a, spend_vendor_b, spend_category_b, org_unit_b,
        spend_invoice_b, spend_invoice_line_b, spend_po_b, spend_contract_b):
    """Every FK on the finding form re-checked after the POST - including ``invoice_line``, which
    has NO tenant column of its own and is therefore scoped through its header rather than by the
    shared ``_reject_foreign`` helper."""
    before = MaverickSpendFinding.objects.count()
    url = reverse("procurement:maverickfinding_create")

    crafted = (
        ("vendor", spend_vendor_b.pk),
        ("category", spend_category_b.pk),
        ("org_unit", org_unit_b.pk),
        ("contract", spend_contract_b.pk),
        ("supplier_invoice", spend_invoice_b.pk),
        ("invoice_line", spend_invoice_line_b.pk),
        ("purchase_order", spend_po_b.pk),
    )
    for field, value in crafted:
        payload = _spend_finding_payload(vendor=str(spend_vendor_a.pk),
                                         purchase_order=str(spend_po_a.pk))
        payload[field] = str(value)
        resp = client_a.post(url, payload)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field

    assert MaverickSpendFinding.objects.count() == before


def test_spend_finding_create_saves_with_the_request_tenant_and_ignores_forged_stamps(
        client_a, tenant_a, tenant_b, admin_b, spend_vendor_a, spend_po_a):
    """L44 pair, plus the system-owned block: ``status`` / ``number`` / ``dedupe_key`` /
    ``leakage_amount`` / ``detected_at`` / ``resolved_by`` / ``resolution_note`` are all
    ``editable=False``, so a POST carrying every one of them files an ordinary OPEN finding with
    a system number and a derived leakage of zero."""
    resp = client_a.post(
        reverse("procurement:maverickfinding_create"),
        _spend_finding_payload(
            vendor=str(spend_vendor_a.pk), purchase_order=str(spend_po_a.pk),
            detail="Raised by hand.", tenant=str(tenant_b.pk), number="MSF-99999",
            status="remediated", dedupe_key="hijacked", leakage_amount="99999.99",
            detected_at="2020-01-01T00:00", resolved_by=str(admin_b.pk),
            resolution_note="pre-approved", resolved_at="2020-01-01T00:00"))
    assert resp.status_code == 302

    finding = MaverickSpendFinding.objects.get(detail="Raised by hand.")
    assert finding.tenant_id == tenant_a.pk
    assert finding.status == "open"
    assert finding.number.startswith("MSF-")
    assert finding.number != "MSF-99999"
    assert finding.dedupe_key == f"no_requisition:po:{spend_po_a.pk}"
    assert finding.leakage_amount == Decimal("0.00")
    assert finding.resolved_by_id is None
    assert finding.resolution_note == ""
    assert finding.resolved_at is None
    assert finding.detected_at.date() == timezone.localdate()


def test_spend_report_create_rejects_another_workspaces_foreign_keys(
        client_a, spend_vendor_b, spend_category_b, org_unit_b, gl_expense_b):
    """The saved report's four narrowing axes, re-checked after the POST: a crafted pk lands as a
    field error, so a report can never be pointed at another workspace's supplier or cost
    centre."""
    before = SpendReport.objects.count()
    url = reverse("procurement:spendreport_create")

    for field, value in (("vendor", spend_vendor_b.pk), ("category", spend_category_b.pk),
                         ("org_unit", org_unit_b.pk), ("gl_account", gl_expense_b.pk)):
        resp = client_a.post(url, _spend_report_payload(**{field: str(value)}))
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field

    assert SpendReport.objects.count() == before


def test_spend_report_create_stamps_the_request_user_as_owner_not_the_posted_one(
        client_a, admin_user, member_user, tenant_a, tenant_b):
    """L44 pair, plus the authorship probe: ``owner`` is taken from ``request.user`` on CREATE
    and is not a form field, so a POST naming a colleague cannot attribute a report to them - and
    ``number`` / ``last_run_at`` are system-owned in the same way."""
    resp = client_a.post(
        reverse("procurement:spendreport_create"),
        _spend_report_payload(name="Owned by me", owner=str(member_user.pk),
                              tenant=str(tenant_b.pk), number="SPR-99999",
                              last_run_at="2020-01-01T00:00"))
    assert resp.status_code == 302

    report = SpendReport.objects.get(name="Owned by me")
    assert report.owner_id == admin_user.pk
    assert report.tenant_id == tenant_a.pk
    assert report.number.startswith("SPR-")
    assert report.number != "SPR-99999"
    assert report.last_run_at is None


def test_spend_report_edit_never_transfers_authorship(
        client_a, admin_user, member_user, spend_report_a):
    """``owner`` is stamped on CREATE ONLY: amending a shared report - by anybody who can see it -
    must not silently make the editor its author, and must not accept a posted owner either."""
    original_owner = spend_report_a.owner_id
    resp = client_a.post(reverse("procurement:spendreport_edit", args=[spend_report_a.pk]),
                         _spend_report_payload(name="Amended in place",
                                               owner=str(member_user.pk)))
    assert resp.status_code == 302
    spend_report_a.refresh_from_db()
    assert spend_report_a.name == "Amended in place"
    assert spend_report_a.owner_id == original_owner == admin_user.pk


# ==================================================================== 6. hostile input
@pytest.mark.parametrize("params", _SPEND_JUNK_QUERIES)
def test_spend_junk_query_params_render_200_on_every_page(
        client_a, params, spend_rule_vendor_a, spend_finding_open_a, spend_report_a,
        spend_invoice_a, spend_invoice_line_a, spend_po_a, spend_po_line_a):
    """A hand-edited query string is something anybody can type into the address bar: a junk FK
    pk, an over-range pk, a Unicode superscript, a bogus enum, an unparseable date, a reversed
    custom range and a page past the end must each SKIP the filter and render, never 500 (L11).
    """
    for name in _SPEND_PAGE_ROUTES:
        resp = client_a.get(reverse(name), params)
        assert resp.status_code == 200, (name, params)


def test_spend_junk_filters_do_not_silently_widen_or_empty_the_registers(
        client_a, spend_rule_vendor_a, spend_finding_open_a, spend_report_a, spend_rule_b):
    """L44 pair for the junk sweep: a skipped filter is a SKIPPED filter - the register still
    shows this workspace's rows - and the working filter still narrows, so the guard did not just
    disable filtering."""
    resp = client_a.get(reverse("procurement:spendrule_list"), {"category": "abc"})
    pks = [row.pk for row in resp.context["object_list"]]
    assert spend_rule_vendor_a.pk in pks
    assert spend_rule_b.pk not in pks

    # …and the same filter with a REAL pk still narrows.
    resp = client_a.get(reverse("procurement:spendrule_list"),
                        {"category": str(spend_rule_vendor_a.category_id)})
    assert [row.pk for row in resp.context["object_list"]] == [spend_rule_vendor_a.pk]
    resp = client_a.get(reverse("procurement:spendrule_list"), {"match_type": "keyword"})
    assert list(resp.context["object_list"]) == []

    resp = client_a.get(reverse("procurement:maverickfinding_list"), {"status": "open"})
    assert [row.pk for row in resp.context["object_list"]] == [spend_finding_open_a.pk]


def test_spend_page_past_the_end_clamps_and_page_two_renders(client_a, tenant_a,
                                                             spend_category_a, spend_vendor_a):
    """``crud_list`` pages at 15: with 18 rules, page 2 renders the remainder and ``?page=999`` /
    ``?page=abc`` clamp to a real page rather than raising (L9)."""
    for index in range(18):
        SpendClassificationRule.objects.create(
            tenant=tenant_a, name=f"Rule {index:02d}", match_type="keyword",
            keyword=f"kw{index:02d}", category=spend_category_a, priority=100 + index)

    url = reverse("procurement:spendrule_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert len(resp.context["object_list"]) == 15
    assert resp.context["page_obj"].paginator.num_pages == 2

    resp = client_a.get(url, {"page": "2"})
    assert resp.status_code == 200
    assert len(resp.context["object_list"]) == 3

    for junk in ("999", "abc", "0", "-1"):
        resp = client_a.get(url, {"page": junk})
        assert resp.status_code == 200, junk
        assert resp.context["page_obj"].number in (1, 2), junk


def test_spend_workbench_page_two_renders_over_grouped_rows(
        client_a, tenant_a, usd, gl_expense_a):
    """The workbench paginates a plain Python LIST of grouped rows at 25, not a queryset - so it
    needs 26 distinct suppliers to reach page 2, and ``?page=999`` must clamp there too."""
    from apps.core.models import Party, PartyRole
    from apps.procurement.models import SupplierInvoice, SupplierInvoiceLine

    for index in range(26):
        party = Party.objects.create(tenant=tenant_a, name=f"Tail supplier {index:02d}",
                                     kind="organization")
        PartyRole.objects.create(tenant=tenant_a, party=party, role="supplier", status="active")
        invoice = SupplierInvoice.objects.create(
            tenant=tenant_a, vendor=party, invoice_number=f"TAIL-{index:02d}",
            invoice_date=timezone.localdate(), status="approved", currency=usd)
        SupplierInvoiceLine.objects.create(
            invoice=invoice, description=f"Tail line {index:02d}", sku_hint=f"TL-{index:02d}",
            quantity=Decimal("1"), unit_price=Decimal("10.00"), gl_account=gl_expense_a)

    url = reverse("procurement:classification_workbench")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["paginator"].num_pages == 2
    assert len(resp.context["rows"]) == 25

    resp = client_a.get(url, {"page": "2"})
    assert resp.status_code == 200
    assert len(resp.context["rows"]) == 1

    resp = client_a.get(url, {"page": "999"})
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2


def test_spend_rule_prefill_never_preselects_another_workspaces_row(
        client_a, spend_vendor_a, spend_vendor_b, gl_expense_b, org_unit_b):
    """The workbench deep-links ``spendrule_create`` with a pk in the query string. That link is
    a convenience, never an authorization path: a junk pk, an over-range pk, another workspace's
    pk and a bogus vocabulary value must each render the empty form rather than pre-selecting
    somebody else's supplier."""
    url = reverse("procurement:spendrule_create")
    for params in ({"vendor": "abc"},
                   {"vendor": "999999999999999999999"},
                   {"vendor": str(spend_vendor_b.pk)},
                   {"gl_account": str(gl_expense_b.pk)},
                   {"org_unit": str(org_unit_b.pk)},
                   {"match_type": "not-a-match-type"},
                   {"invoice_type": "not-an-invoice-type"}):
        resp = client_a.get(url, params)
        assert resp.status_code == 200, params
        initial = resp.context["form"].initial
        for field in ("vendor", "gl_account", "org_unit", "match_type", "invoice_type"):
            assert initial.get(field) in (None, "", False), (params, field)

    # L44 pair: a HONEST prefill still lands, and an over-long keyword is truncated, not refused.
    resp = client_a.get(url, {"vendor": str(spend_vendor_a.pk), "match_type": "vendor",
                              "invoice_type": "service", "keyword": "z" * 400})
    assert resp.status_code == 200
    initial = resp.context["form"].initial
    assert initial["vendor"] == spend_vendor_a.pk
    assert initial["match_type"] == "vendor"
    assert initial["invoice_type"] == "service"
    assert len(initial["keyword"]) == 120


def test_spend_favorite_next_param_cannot_redirect_off_host(client_a, spend_report_a):
    """``next`` on the favourite toggle is validated with
    ``url_has_allowed_host_and_scheme``: an off-host value falls back to the report's own detail
    page instead of bouncing the operator to somebody else's site."""
    url = reverse("procurement:spendreport_favorite", args=[spend_report_a.pk])
    detail = reverse("procurement:spendreport_detail", args=[spend_report_a.pk])

    for hostile in ("http://evil.example.com/steal",
                    "//evil.example.com/steal",
                    "https://evil.example.com"):
        resp = client_a.post(url, {"next": hostile})
        assert resp.status_code == 302, hostile
        assert resp["Location"] == detail, hostile

    # L44 pair: a same-host relative next IS honoured - the guard did not break the feature.
    resp = client_a.post(url, {"next": reverse("procurement:spendreport_list")})
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:spendreport_list")


def test_spend_snapshot_renders_a_malformed_stored_payload_without_raising(
        client_a, tenant_a, spend_report_a, admin_user):
    """A snapshot payload is DATA read back years later, never trusted to be shaped: a string
    where a dict belongs, an int where a chart type belongs and two mismatched parallel series
    must all render (chart falling back to ``table``), not 500."""
    hostile = SpendReportSnapshot.objects.create(
        tenant=tenant_a, report=spend_report_a, title="Malformed run",
        generated_by=admin_user, summary="not-a-list",
        data={"columns": "not-a-list", "rows": {"nope": 1}, "chart_type": 7,
              "chart_labels": ["a", "b", "c"], "chart_data": [1]},
        row_count=0)

    resp = client_a.get(reverse("procurement:spendreportsnapshot_detail", args=[hostile.pk]))
    assert resp.status_code == 200
    assert resp.context["chart_type"] == "table"
    assert resp.context["columns"] == []
    assert resp.context["rows"] == []
    assert resp.context["summary"] == []
    assert len(resp.context["chart_rows"]) == 1

    assert client_a.get(reverse("procurement:spendreportsnapshot_export",
                                args=[hostile.pk])).status_code == 200


def test_spend_exported_cells_are_neutralised_against_formula_injection(
        client_a, _spend_hostile_vendor_a, spend_report_a):
    """A supplier name and a line description are user-authored text, and a spreadsheet EXECUTES
    a cell that opens with ``=``, ``+``, ``-`` or ``@``. Every cell of every 6.14 download goes
    through ``csv_safe``, so the payload arrives as a quoted string on all three routes."""
    hostile = _spend_hostile_vendor_a.name
    assert hostile.startswith("=")

    downloads = [
        client_a.get(reverse("procurement:spend_export_download"), {"dimension": "none"}),
        client_a.get(reverse("procurement:spend_export_download"), {"dimension": "supplier"}),
        client_a.get(reverse("procurement:spendreport_export", args=[spend_report_a.pk])),
    ]
    for resp in downloads:
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/csv"
        assert "attachment;" in resp["Content-Disposition"]
        body = resp.content.decode()
        assert hostile in body                       # the row really is in the file…
        assert f"'{hostile}" in body                 # …and it is quoted, not live
        for line in body.splitlines():
            for cell in line.split(","):
                assert not cell.strip('"').startswith(("=", "+", "@")), cell


def test_spend_money_forms_refuse_the_whole_decimal_family(
        client_a, spend_vendor_a, spend_po_a):
    """Both money surfaces declare their own ``DecimalField(max_digits=18, decimal_places=2,
    min_value=0)`` rather than hand-parsing a POST, so ``NaN`` / ``Infinity`` / garbage / a
    negative / an over-``max_digits`` value is a FIELD error on a 200 page - never a driver 500
    and never a saved row (L35)."""
    hostile = ("NaN", "Infinity", "-Infinity", "not-a-number", "-1",
               "9" * 20, "1e400", "0x10", "1,000")

    findings_before = MaverickSpendFinding.objects.count()
    url = reverse("procurement:maverickfinding_create")
    for value in hostile:
        resp = client_a.post(url, _spend_finding_payload(
            vendor=str(spend_vendor_a.pk), purchase_order=str(spend_po_a.pk), amount=value))
        assert resp.status_code == 200, value
        assert "amount" in resp.context["form"].errors, value
    assert MaverickSpendFinding.objects.count() == findings_before

    # The benchmark is optional, so it is hardened separately - a bad one must not slip through.
    for value in ("NaN", "Infinity", "-5", "9" * 20):
        resp = client_a.post(url, _spend_finding_payload(
            vendor=str(spend_vendor_a.pk), purchase_order=str(spend_po_a.pk),
            amount="250.00", benchmark_amount=value))
        assert resp.status_code == 200, value
        assert "benchmark_amount" in resp.context["form"].errors, value
    assert MaverickSpendFinding.objects.count() == findings_before

    reports_before = SpendReport.objects.count()
    url = reverse("procurement:spendreport_create")
    for value in hostile:
        resp = client_a.post(url, _spend_report_payload(min_amount=value))
        assert resp.status_code == 200, value
        assert "min_amount" in resp.context["form"].errors, value
    assert SpendReport.objects.count() == reports_before


def test_spend_money_forms_still_accept_a_real_figure(client_a, spend_vendor_a, spend_po_a):
    """L44 pair for the decimal family: an ordinary amount, an ordinary benchmark and an
    ordinary floor all save, and the derived leakage is computed from the gap."""
    resp = client_a.post(reverse("procurement:maverickfinding_create"), _spend_finding_payload(
        vendor=str(spend_vendor_a.pk), purchase_order=str(spend_po_a.pk),
        amount="250.00", benchmark_amount="200.00", detail="Real figures."))
    assert resp.status_code == 302
    finding = MaverickSpendFinding.objects.get(detail="Real figures.")
    assert finding.amount == Decimal("250.00")
    assert finding.leakage_amount == Decimal("50.00")

    resp = client_a.post(reverse("procurement:spendreport_create"),
                         _spend_report_payload(name="Floored", min_amount="100.50"))
    assert resp.status_code == 302
    assert SpendReport.objects.get(name="Floored").min_amount == Decimal("100.50")


def test_spend_report_custom_range_bounds_are_validated_not_crashed(client_a):
    """The saved report carries its own date pair into ``range_bounds``, which adds a day to it -
    so a year outside 1900..9999, a reversed pair and a half-filled custom range are refused at
    the FORM, and the ones that are merely odd degrade rather than raising."""
    url = reverse("procurement:spendreport_create")
    before = SpendReport.objects.count()

    cases = (
        ({"date_range": "custom", "date_from": "", "date_to": _spend_iso()}, "date_from"),
        ({"date_range": "custom", "date_from": _spend_iso(), "date_to": ""}, "date_to"),
        ({"date_range": "custom", "date_from": _spend_iso(),
          "date_to": _spend_iso(-30)}, "date_from"),
        ({"date_range": "custom", "date_from": "1799-01-01",
          "date_to": _spend_iso()}, "date_from"),
        ({"dimension_1": "supplier", "dimension_2": "supplier"}, "dimension_2"),
    )
    for overrides, field in cases:
        resp = client_a.post(url, _spend_report_payload(**overrides))
        assert resp.status_code == 200, overrides
        assert field in resp.context["form"].errors, overrides
    assert SpendReport.objects.count() == before

    # L44 pair: a legitimate custom range saves and its detail page renders the clamped window.
    resp = client_a.post(url, _spend_report_payload(
        name="Custom window", date_range="custom", date_from=_spend_iso(-30),
        date_to=_spend_iso()))
    assert resp.status_code == 302
    report = SpendReport.objects.get(name="Custom window")
    assert client_a.get(reverse("procurement:spendreport_detail",
                                args=[report.pk])).status_code == 200


def test_spend_scan_narrows_on_a_hand_edited_reason_and_range(
        client_a, tenant_a, spend_invoice_a, spend_invoice_line_a):
    """The scan's window and reason list come off a POST checkbox group: an unknown reason must
    NARROW the run and an unknown range must fall back to the default - never a 500, and never a
    detector nobody asked for."""
    dashboard = reverse("procurement:maverick_dashboard")

    resp = client_a.post(reverse("procurement:maverick_scan"),
                         {"range": "not-a-range", "reason": ["nonsense", "'; DROP TABLE--"]})
    assert resp.status_code == 302
    assert resp["Location"] == f"{dashboard}?range=last_90"
    # Every posted reason was junk, so the scan narrowed to nothing and raised nothing.
    assert MaverickSpendFinding.objects.filter(tenant=tenant_a).count() == 0

    # L44 pair: one REAL reason among the junk still runs that detector.
    resp = client_a.post(reverse("procurement:maverick_scan"),
                         {"range": "last_90", "reason": ["po_less_invoice", "nonsense"]})
    assert resp.status_code == 302
    assert resp["Location"] == f"{dashboard}?range=last_90"
    raised = MaverickSpendFinding.objects.filter(tenant=tenant_a)
    assert raised.exists()
    assert set(raised.values_list("reason", flat=True)) == {"po_less_invoice"}


# ================================================== 7. absent prerequisites are REJECTED (L35)
def test_spend_disposition_without_a_note_is_refused_not_approved(
        client_a, spend_finding_open_a):
    """The three terminal verbs need a reason on the record. A POST with no ``resolution_note``
    must be REFUSED - the finding stays open - rather than falling through to a justification
    nobody can account for (L35). A blank ``action`` is refused the same way."""
    url = reverse("procurement:maverickfinding_disposition", args=[spend_finding_open_a.pk])
    detail = reverse("procurement:maverickfinding_detail", args=[spend_finding_open_a.pk])
    before = _spend_finding_state(spend_finding_open_a)

    for body in ({"action": "justify"},
                 {"action": "remediate", "resolution_note": "   "},
                 {"action": "dismiss", "resolution_note": ""},
                 # the 6.13 dispute view's key is ``resolution_note``; ``note`` is not it
                 {"action": "justify", "note": "wrong key"},
                 {"action": ""},
                 {"action": "approve"},
                 {"action": "delete", "resolution_note": "nice try"},
                 {}):
        resp = client_a.post(url, body)
        assert resp.status_code == 302, body
        assert resp["Location"] == detail, body
        assert _spend_finding_state(spend_finding_open_a) == before, body

    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "open"
    assert spend_finding_open_a.resolved_by_id is None
    assert spend_finding_open_a.resolved_at is None


def test_spend_disposition_with_a_note_moves_the_finding(client_a, admin_user,
                                                         spend_finding_open_a):
    """L44 pair: the same route WITH the note the guard asked for records the decision, its
    author and its timestamp - the refusals above are the guard, not a broken verb."""
    url = reverse("procurement:maverickfinding_disposition", args=[spend_finding_open_a.pk])

    resp = client_a.post(url, {"action": "acknowledge"})
    assert resp.status_code == 302
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "acknowledged"

    resp = client_a.post(url, {"action": "justify", "resolution_note": "Emergency purchase."})
    assert resp.status_code == 302
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.status == "justified"
    assert spend_finding_open_a.resolution_note == "Emergency purchase."
    assert spend_finding_open_a.resolved_by_id == admin_user.pk
    assert spend_finding_open_a.resolved_at is not None


def test_spend_disposed_finding_cannot_be_re_disposed_edited_or_deleted(
        client_a, spend_finding_dismissed_a, spend_vendor_a, spend_po_a):
    """A disposed finding carries a recorded decision, its note and its ``resolved_by`` stamp:
    that is an audit trail, not a row. Every verb re-checks its own guard INSIDE the model, so a
    stale page's POST is refused rather than applied - and the delete is refused outright."""
    before = _spend_finding_state(spend_finding_dismissed_a)
    detail = reverse("procurement:maverickfinding_detail", args=[spend_finding_dismissed_a.pk])

    for body in ({"action": "acknowledge"},
                 {"action": "justify", "resolution_note": "second thoughts"},
                 {"action": "remediate", "resolution_note": "second thoughts"},
                 {"action": "dismiss", "resolution_note": "again"}):
        resp = client_a.post(
            reverse("procurement:maverickfinding_disposition",
                    args=[spend_finding_dismissed_a.pk]), body)
        assert resp.status_code == 302, body
        assert resp["Location"] == detail, body
        assert _spend_finding_state(spend_finding_dismissed_a) == before, body

    # Editing it would rewrite what the decision was recorded against.
    resp = client_a.get(reverse("procurement:maverickfinding_edit",
                                args=[spend_finding_dismissed_a.pk]))
    assert resp.status_code == 302
    assert resp["Location"] == detail
    resp = client_a.post(
        reverse("procurement:maverickfinding_edit", args=[spend_finding_dismissed_a.pk]),
        _spend_finding_payload(vendor=str(spend_vendor_a.pk),
                               purchase_order=str(spend_po_a.pk), amount="1.00"))
    assert resp.status_code == 302
    assert resp["Location"] == detail

    # …and deleting it is stronger than dismissing it, so it is refused outright.
    resp = client_a.post(reverse("procurement:maverickfinding_delete",
                                 args=[spend_finding_dismissed_a.pk]))
    assert resp.status_code == 302
    assert resp["Location"] == detail
    assert MaverickSpendFinding.objects.filter(pk=spend_finding_dismissed_a.pk).exists()
    assert _spend_finding_state(spend_finding_dismissed_a) == before


def test_spend_open_finding_may_still_be_edited_and_deleted(
        client_a, spend_finding_open_a, spend_vendor_a, spend_invoice_a):
    """L44 pair for the disposed-finding refusals: an OPEN finding amends and deletes normally,
    so the guard above is about the recorded decision and not about the routes being broken."""
    resp = client_a.post(
        reverse("procurement:maverickfinding_edit", args=[spend_finding_open_a.pk]),
        _spend_finding_payload(reason="no_contract", vendor=str(spend_vendor_a.pk),
                               supplier_invoice=str(spend_invoice_a.pk),
                               amount="275.00", detail="Amended."))
    assert resp.status_code == 302
    spend_finding_open_a.refresh_from_db()
    assert spend_finding_open_a.amount == Decimal("275.00")
    assert spend_finding_open_a.status == "open"

    resp = client_a.post(reverse("procurement:maverickfinding_delete",
                                 args=[spend_finding_open_a.pk]))
    assert resp.status_code == 302
    assert not MaverickSpendFinding.objects.filter(pk=spend_finding_open_a.pk).exists()


def test_spend_finding_with_no_evidence_is_rejected(client_a, spend_vendor_a):
    """A finding with no invoice, no invoice line and no purchase order cannot be reviewed by
    anybody, so the absent prerequisite is a field error rather than a row on the board (L35)."""
    before = MaverickSpendFinding.objects.count()
    resp = client_a.post(reverse("procurement:maverickfinding_create"),
                         _spend_finding_payload(vendor=str(spend_vendor_a.pk)))
    assert resp.status_code == 200
    assert "supplier_invoice" in resp.context["form"].errors
    assert MaverickSpendFinding.objects.count() == before


def test_spend_finding_line_from_a_different_invoice_is_rejected(
        client_a, spend_vendor_a, spend_invoice_a, spend_invoice_line_a, spend_invoice_draft_a):
    """Pointing a finding at an invoice AND at a line belonging to a different invoice is an
    inconsistent pair of facts - refused on the line, not silently reconciled."""
    before = MaverickSpendFinding.objects.count()
    resp = client_a.post(reverse("procurement:maverickfinding_create"),
                         _spend_finding_payload(
                             vendor=str(spend_vendor_a.pk),
                             supplier_invoice=str(spend_invoice_draft_a.pk),
                             invoice_line=str(spend_invoice_line_a.pk)))
    assert resp.status_code == 200
    assert "invoice_line" in resp.context["form"].errors
    assert MaverickSpendFinding.objects.count() == before


def test_spend_rule_without_its_subject_is_rejected(
        client_a, spend_category_a, spend_vendor_a, gl_expense_a, org_unit_a):
    """The single most damaging thing this table can do is a subject-less rule: a ``vendor`` rule
    with no vendor would match EVERY line on both bases and swallow the whole cube into one
    category. Each ``match_type`` is refused on the field it demands, and an unknown match type is
    refused on ``match_type``."""
    before = SpendClassificationRule.objects.count()
    url = reverse("procurement:spendrule_create")

    for match_type, field in (("vendor", "vendor"), ("gl_account", "gl_account"),
                              ("org_unit", "org_unit"), ("keyword", "keyword"),
                              ("invoice_type", "invoice_type")):
        resp = client_a.post(url, _spend_rule_payload(
            match_type=match_type, category=str(spend_category_a.pk)))
        assert resp.status_code == 200, match_type
        assert field in resp.context["form"].errors, match_type

    resp = client_a.post(url, _spend_rule_payload(
        match_type="telepathy", category=str(spend_category_a.pk)))
    assert resp.status_code == 200
    assert "match_type" in resp.context["form"].errors

    # An invoice-type rule cannot govern committed (PO) spend - a purchase order has no type.
    resp = client_a.post(url, _spend_rule_payload(
        match_type="invoice_type", invoice_type="service", applies_to="committed",
        category=str(spend_category_a.pk)))
    assert resp.status_code == 200
    assert "applies_to" in resp.context["form"].errors

    # A rule with no category has no taxonomy target at all.
    resp = client_a.post(url, _spend_rule_payload(vendor=str(spend_vendor_a.pk), category=""))
    assert resp.status_code == 200
    assert "category" in resp.context["form"].errors

    assert SpendClassificationRule.objects.count() == before


def test_spend_rule_with_its_subject_saves(client_a, tenant_a, spend_category_a,
                                           spend_vendor_a, gl_expense_a):
    """L44 pair: every ``match_type`` above saves the moment its own subject is supplied."""
    url = reverse("procurement:spendrule_create")
    cases = (
        ("vendor", {"vendor": str(spend_vendor_a.pk)}),
        ("gl_account", {"gl_account": str(gl_expense_a.pk)}),
        ("keyword", {"keyword": "toner"}),
        ("invoice_type", {"invoice_type": "service", "applies_to": "invoiced"}),
    )
    for index, (match_type, extra) in enumerate(cases):
        resp = client_a.post(url, _spend_rule_payload(
            name=f"Valid {match_type}", match_type=match_type,
            category=str(spend_category_a.pk), priority=str(10 + index), **extra))
        assert resp.status_code == 302, match_type
        rule = SpendClassificationRule.objects.get(name=f"Valid {match_type}")
        assert rule.tenant_id == tenant_a.pk
        assert rule.match_type == match_type


def test_spend_report_detail_never_stamps_a_run(client_a, spend_report_a):
    """Opening a report is not running it: the detail page computes and renders and stamps
    NOTHING, so ``last_run_at`` never claims a colleague ran a report they merely read. Only the
    explicit verbs move it."""
    assert spend_report_a.last_run_at is None
    for _ in range(3):
        assert client_a.get(reverse("procurement:spendreport_detail",
                                    args=[spend_report_a.pk])).status_code == 200
    spend_report_a.refresh_from_db()
    assert spend_report_a.last_run_at is None

    resp = client_a.post(reverse("procurement:spendreport_run", args=[spend_report_a.pk]))
    assert resp.status_code == 302
    spend_report_a.refresh_from_db()
    assert spend_report_a.last_run_at is not None


# ==================================================================== 8. N+1
def test_spend_registers_hold_their_query_count(
        django_assert_max_num_queries, client_a, tenant_a, admin_user, spend_category_a,
        spend_vendor_a, spend_invoice_a, org_unit_a, gl_expense_a):
    """Each register ``select_related``s every hop its rows (and their ``__str__``) walk, so the
    query count is a fixed cost plus the joins - not one query per row per FK."""
    for index in range(12):
        SpendClassificationRule.objects.create(
            tenant=tenant_a, name=f"Rule {index:02d}", match_type="vendor",
            vendor=spend_vendor_a, gl_account=gl_expense_a, org_unit=org_unit_a,
            category=spend_category_a, priority=10 + index)
        MaverickSpendFinding.objects.create(
            tenant=tenant_a, vendor=spend_vendor_a, category=spend_category_a,
            org_unit=org_unit_a, supplier_invoice=spend_invoice_a, reason="no_contract",
            document_date=timezone.localdate(), amount=Decimal("10.00"),
            dedupe_key=f"no_contract:manual:{index:02d}")
        SpendReport.objects.create(tenant=tenant_a, name=f"Report {index:02d}",
                                   owner=admin_user, vendor=spend_vendor_a,
                                   category=spend_category_a, org_unit=org_unit_a,
                                   gl_account=gl_expense_a)

    with django_assert_max_num_queries(18):
        resp = client_a.get(reverse("procurement:spendrule_list"))
        assert resp.status_code == 200
        assert [str(row) for row in resp.context["object_list"]]

    with django_assert_max_num_queries(18):
        resp = client_a.get(reverse("procurement:maverickfinding_list"))
        assert resp.status_code == 200
        assert [str(row) for row in resp.context["object_list"]]

    with django_assert_max_num_queries(18):
        resp = client_a.get(reverse("procurement:spendreport_list"))
        assert resp.status_code == 200
        assert [str(row) for row in resp.context["object_list"]]
