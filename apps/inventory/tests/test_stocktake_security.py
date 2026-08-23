"""Inventory 5.11 Stocktaking & Cycle Counting — multi-tenancy IDOR & security tests.

Adversarial coverage around BOTH 5.11 entities: cross-tenant IDOR on every read and
write shape (detail/edit GETs, start/reconcile/cancel/delete/run POSTs), the anonymous
wall over all FIFTEEN routes, method discipline (every mutating verb answers GET with a
405), server-side lifecycle guards behind the hidden buttons (start only from draft,
reconcile only while counting, cancel only from draft|counting, Run refuses an inactive
cadence), the mass-assignment contract (status/is_frozen/requested_by/number/
last_run_date stay OFF the forms so a crafted POST cannot forge them), escaping of
attacker-controlled program/event text, tenant isolation on the variance report, and
the audit trail left by a successful Start/Run.

House note: ``base.html`` ships legit ``<script>`` tags, so escape probes assert the
FULL payload (``<script>alert(1)</script>``) is absent — never the bare ``<script>``
prefix.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.inventory.forms.StocktakingCycleCounting.CountPrograms import (
    CountProgramForm,
    PhysicalInventoryForm,
)
from apps.inventory.models import CountProgram, PhysicalInventory

pytestmark = pytest.mark.django_db

_XSS_SCRIPT = "<script>alert(1)</script>"


# ---- module-level helpers -------------------------------------------------------------------------

def _stocktake_assert_login_redirect(response):
    assert response.status_code == 302
    assert "/login" in response.url or response.url.endswith("login")


def _stocktake_pi_payload(warehouse, **overrides):
    """A minimal VALID PhysicalInventoryForm body; overrides carry the adversarial bits."""
    data = {
        "warehouse": warehouse.pk,
        "scheduled_date": timezone.localdate().isoformat(),
        "notes": "Security probe event",
    }
    data.update(overrides)
    return data


def _stocktake_sheet_count(event):
    """How many CC- sheets this event owns under its provenance marker."""
    return event.spawned_tasks().count()


def _stocktake_program_marker_count(program):
    """Sheets minted BY this cadence (the 'Via count program {number}' stamp)."""
    from apps.scm.models import CycleCountTask

    return CycleCountTask.objects.filter(
        tenant_id=program.tenant_id,
        notes__startswith=f"Via count program {program.number}").count()


def _stocktake_audit_logs(obj):
    """Every core.AuditLog row written about ``obj`` (house pattern: ContentType + id)."""
    ct = ContentType.objects.get_for_model(type(obj))
    return AuditLog.objects.filter(content_type=ct, object_id=obj.pk)


def _stocktake_reconciled_event(tenant, user, warehouse):
    """A REALLY reconciled event built through the REAL verbs: start() spawns its two
    sheets, the tests mark them reconciled (ordinary spine data), reconcile() closes."""
    event = PhysicalInventory.objects.create(
        tenant=tenant, warehouse=warehouse,
        scheduled_date=timezone.localdate(), requested_by=user)
    event.start(user)
    for sheet in event.spawned_tasks():
        sheet.status = "reconciled"
        sheet.save(update_fields=["status"])
    return event.reconcile(user)


# ---- auth wall --------------------------------------------------------------------------------------

def test_stocktake_anonymous_redirected_to_login_on_all_routes(client, stocktake_event_a,
                                                               stocktake_program_a):
    """Every 5.11 route sits behind @login_required — the six plain pages, the eight
    detail-shaped routes and the variance report. No exception."""
    plain_routes = ["physicalinventory_list", "physicalinventory_create",
                    "countprogram_list", "countprogram_create", "variance_report"]
    detail_routes = ["physicalinventory_detail", "physicalinventory_edit",
                     "physicalinventory_delete", "physicalinventory_start",
                     "physicalinventory_reconcile", "physicalinventory_cancel",
                     "countprogram_detail", "countprogram_edit",
                     "countprogram_run", "countprogram_delete"]
    targets = dict(physicalinventory=stocktake_event_a, countprogram=stocktake_program_a)
    for name in plain_routes:
        _stocktake_assert_login_redirect(client.get(reverse(f"inventory:{name}")))
    for name in detail_routes:
        prefix = name.split("_")[0]
        url = reverse(f"inventory:{name}", args=[targets[prefix].pk])
        _stocktake_assert_login_redirect(client.get(url))


# ---- IDOR -------------------------------------------------------------------------------------------

def test_stocktake_physicalinventory_cross_tenant_reads_404(client_a, stocktake_event_b):
    """A foreign event pk must read as nonexistent to another workspace's admin."""
    for name in ["physicalinventory_detail", "physicalinventory_edit"]:
        url = reverse(f"inventory:{name}", args=[stocktake_event_b.pk])
        assert client_a.get(url).status_code == 404


def test_stocktake_physicalinventory_cross_tenant_writes_404_and_intact(
        client_a, stocktake_event_b):
    """The write shapes are where an IDOR would do damage: ALL THREE lifecycle verb
    POSTs and delete must 404 on a foreign pk and leave Globex's draft untouched."""
    for name in ["physicalinventory_start", "physicalinventory_reconcile",
                 "physicalinventory_cancel"]:
        url = reverse(f"inventory:{name}", args=[stocktake_event_b.pk])
        assert client_a.post(url).status_code == 404

    total_before = PhysicalInventory.objects.count()
    assert client_a.post(
        reverse("inventory:physicalinventory_delete", args=[stocktake_event_b.pk])
    ).status_code == 404
    assert PhysicalInventory.objects.count() == total_before

    stocktake_event_b.refresh_from_db()  # raises if deleted
    assert stocktake_event_b.status == "draft"
    assert stocktake_event_b.is_frozen is False


def test_stocktake_countprogram_cross_tenant_reads_404(client_a, stocktake_program_b):
    """A foreign cadence pk must read as nonexistent to another workspace's admin."""
    for name in ["countprogram_detail", "countprogram_edit"]:
        url = reverse(f"inventory:{name}", args=[stocktake_program_b.pk])
        assert client_a.get(url).status_code == 404


def test_stocktake_countprogram_cross_tenant_run_delete_404(client_a, stocktake_program_b):
    """Run and delete POSTs against Globex's cadence must 404, leave it intact and mint
    NO spine sheet under its provenance marker."""
    assert client_a.post(
        reverse("inventory:countprogram_run", args=[stocktake_program_b.pk])
    ).status_code == 404

    total_before = CountProgram.objects.count()
    assert client_a.post(
        reverse("inventory:countprogram_delete", args=[stocktake_program_b.pk])
    ).status_code == 404
    assert CountProgram.objects.count() == total_before

    stocktake_program_b.refresh_from_db()
    assert stocktake_program_b.last_run_date is None
    assert _stocktake_program_marker_count(stocktake_program_b) == 0


# ---- method discipline ------------------------------------------------------------------------------

def test_stocktake_post_only_verbs_reject_get_with_405(client_a, stocktake_event_a,
                                                       stocktake_program_a):
    """GET on every mutating route is a 405 — start/reconcile/cancel/delete and run all
    carry require_POST explicitly — and nothing moved behind the probes."""
    pi_verbs = ["physicalinventory_start", "physicalinventory_reconcile",
                "physicalinventory_cancel", "physicalinventory_delete"]
    ctp_verbs = ["countprogram_run", "countprogram_delete"]
    for name in pi_verbs:
        url = reverse(f"inventory:{name}", args=[stocktake_event_a.pk])
        assert client_a.get(url).status_code == 405
    for name in ctp_verbs:
        url = reverse(f"inventory:{name}", args=[stocktake_program_a.pk])
        assert client_a.get(url).status_code == 405

    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "draft"
    assert stocktake_program_a.last_run_date is None
    assert _stocktake_sheet_count(stocktake_event_a) == 0
    assert _stocktake_program_marker_count(stocktake_program_a) == 0


# ---- lifecycle guards (hidden-button bypass must fail) ----------------------------------------------

def test_stocktake_start_on_counting_event_refused_no_extra_sheets(
        client_a, stocktake_zone_a, stocktake_bin_a, stocktake_event_counting_a):
    """A counting (frozen) event re-posted through Start stays exactly where it was —
    same status, same freeze, same TWO spawned sheets."""
    response = client_a.post(reverse("inventory:physicalinventory_start",
                                     args=[stocktake_event_counting_a.pk]))
    assert response.status_code == 302

    stocktake_event_counting_a.refresh_from_db()
    assert stocktake_event_counting_a.status == "counting"
    assert stocktake_event_counting_a.is_frozen is True
    assert _stocktake_sheet_count(stocktake_event_counting_a) == 2


def test_stocktake_start_on_reconciled_event_refused_no_new_sheets(
        client_a, tenant_a, admin_user, stocktake_warehouse_a,
        stocktake_zone_a, stocktake_bin_a):
    """A closed event cannot be resurrected through the verb: Start on reconciled is
    refused and mints nothing new."""
    event = _stocktake_reconciled_event(tenant_a, admin_user, stocktake_warehouse_a)

    response = client_a.post(reverse("inventory:physicalinventory_start", args=[event.pk]))
    assert response.status_code == 302

    event.refresh_from_db()
    assert event.status == "reconciled"
    assert event.is_frozen is False
    assert _stocktake_sheet_count(event) == 2


def test_stocktake_reconcile_on_draft_event_refused(client_a, stocktake_event_a):
    """Reconcile before Start would lift a freeze that was never raised — refused; the
    event stays draft and unfrozen."""
    response = client_a.post(reverse("inventory:physicalinventory_reconcile",
                                     args=[stocktake_event_a.pk]))
    assert response.status_code == 302

    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "draft"
    assert stocktake_event_a.is_frozen is False
    assert stocktake_event_a.closed_at is None


def test_stocktake_cancel_only_from_draft_or_counting(client_a, tenant_a, admin_user,
                                                      stocktake_warehouse_a,
                                                      stocktake_zone_a, stocktake_bin_a,
                                                      stocktake_event_a):
    """A cancelled event cannot be cancelled again, and a reconciled event can never be
    cancelled at all — both refusals leave the statuses untouched."""
    first = client_a.post(reverse("inventory:physicalinventory_cancel",
                                  args=[stocktake_event_a.pk]))
    assert first.status_code == 302
    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "cancelled"

    second = client_a.post(reverse("inventory:physicalinventory_cancel",
                                   args=[stocktake_event_a.pk]))
    assert second.status_code == 302
    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "cancelled"

    reconciled = _stocktake_reconciled_event(tenant_a, admin_user, stocktake_warehouse_a)
    third = client_a.post(reverse("inventory:physicalinventory_cancel",
                                  args=[reconciled.pk]))
    assert third.status_code == 302
    reconciled.refresh_from_db()
    assert reconciled.status == "reconciled"


def test_stocktake_inactive_program_run_refused_mints_nothing(client_a, stocktake_program_a):
    """The hidden Run button is not the guard: a deactivated cadence refuses a direct
    POST too — no spine sheet minted, last_run_date not stamped."""
    stocktake_program_a.is_active = False
    stocktake_program_a.save(update_fields=["is_active"])

    response = client_a.post(reverse("inventory:countprogram_run",
                                     args=[stocktake_program_a.pk]), follow=True)
    assert response.status_code == 200  # flash refusal back on the detail page
    assert "inactive" in response.content.decode()

    stocktake_program_a.refresh_from_db()
    assert stocktake_program_a.is_active is False
    assert stocktake_program_a.last_run_date is None
    assert _stocktake_program_marker_count(stocktake_program_a) == 0


def test_stocktake_delete_of_counting_event_survives_with_sheets(
        client_a, stocktake_zone_a, stocktake_bin_a, stocktake_event_counting_a):
    """Delete is draft-only and refuses anything that already spawned sheets — the
    counting event and both of its CC- sheets survive the direct POST."""
    total_before = PhysicalInventory.objects.count()
    response = client_a.post(reverse("inventory:physicalinventory_delete",
                                     args=[stocktake_event_counting_a.pk]), follow=True)
    assert response.status_code == 200  # flash refusal back on the detail page

    assert PhysicalInventory.objects.count() == total_before
    stocktake_event_counting_a.refresh_from_db()
    assert stocktake_event_counting_a.status == "counting"
    assert _stocktake_sheet_count(stocktake_event_counting_a) == 2


# ---- mass assignment ----------------------------------------------------------------------------------

def test_stocktake_forms_exclude_system_fields_from_cleaned_data(tenant_a,
                                                                 stocktake_warehouse_a,
                                                                 stocktake_zone_a):
    """Unit-level contract: status/is_frozen/requested_by/number/started_at/closed_at
    (event) and last_run_date/number (cadence) are NOT form fields, so a bound payload
    carrying them loses them silently — they can never be written by a save()."""
    event_form = PhysicalInventoryForm(
        data=_stocktake_pi_payload(
            stocktake_warehouse_a,
            status="cancelled", is_frozen="true", requested_by="999",
            number="PHY-99999", started_at="2026-08-01T10:00", closed_at="2026-08-02T18:00"),
        tenant=tenant_a)
    assert event_form.is_valid(), event_form.errors
    for key in ["status", "is_frozen", "requested_by", "number", "started_at", "closed_at"]:
        assert key not in event_form.fields
        assert key not in event_form.cleaned_data

    program_form = CountProgramForm(
        data={"name": "Security probe cadence", "location": stocktake_zone_a.pk,
              "abc_class": "", "frequency": "weekly", "weekday": "0", "day_of_month": "",
              "count_method": "zone", "is_active": "on", "notes": "",
              "last_run_date": "2026-01-01", "number": "CTP-99999"},
        tenant=tenant_a)
    assert program_form.is_valid(), program_form.errors
    for key in ["last_run_date", "number"]:
        assert key not in program_form.fields
        assert key not in program_form.cleaned_data


def test_stocktake_crafted_edit_post_cannot_flip_status_or_freeze(
        client_a, stocktake_event_a):
    """View-level regression: a crafted edit POST injecting status=cancelled plus the
    freeze/system columns saves its LEGITIMATE fields (302) but leaves every verb-driven
    column strictly alone — only the verbs move them."""
    original_requested_by = stocktake_event_a.requested_by_id
    response = client_a.post(
        reverse("inventory:physicalinventory_edit", args=[stocktake_event_a.pk]),
        data=_stocktake_pi_payload(
            stocktake_event_a.warehouse,
            notes="rewritten by probe",
            status="cancelled", is_frozen="true", requested_by="999",
            number="PHY-99999"))
    assert response.status_code == 302  # the edit itself succeeded...

    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.notes == "rewritten by probe"  # ...and really saved
    assert stocktake_event_a.status == "draft"
    assert stocktake_event_a.is_frozen is False
    assert stocktake_event_a.started_at is None
    assert stocktake_event_a.closed_at is None
    assert stocktake_event_a.requested_by_id == original_requested_by
    assert not stocktake_event_a.number.startswith("PHY-99999")


# ---- XSS ---------------------------------------------------------------------------------------------

def test_stocktake_program_name_render_escaped_on_list_and_detail(client_a, tenant_a,
                                                                  stocktake_zone_a):
    """A cadence name is attacker-controlled free text rendered on both pages —
    autoescape is the only sanitizer either may rely on."""
    program = CountProgram.objects.create(
        tenant=tenant_a, name=_XSS_SCRIPT, location=stocktake_zone_a,
        frequency="daily", count_method="zone")

    listing = client_a.get(reverse("inventory:countprogram_list")).content.decode()
    assert _XSS_SCRIPT not in listing
    assert "&lt;script&gt;" in listing

    detail = client_a.get(reverse("inventory:countprogram_detail",
                                  args=[program.pk])).content.decode()
    assert _XSS_SCRIPT not in detail
    assert "&lt;script&gt;" in detail


def test_stocktake_event_notes_render_escaped_on_detail(client_a, tenant_a,
                                                        admin_user,
                                                        stocktake_warehouse_a):
    """Event free text is attacker-controlled — autoescape is the only sanitizer the
    detail page may rely on."""
    event = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=timezone.localdate(), requested_by=admin_user, notes=_XSS_SCRIPT)

    detail = client_a.get(reverse("inventory:physicalinventory_detail",
                                  args=[event.pk])).content.decode()
    assert _XSS_SCRIPT not in detail
    assert "&lt;script&gt;" in detail


def test_stocktake_warehouse_code_render_escaped_on_list_and_detail(
        client_a, admin_user, tenant_a, stocktake_warehouse_a):
    """The warehouse location code renders on BOTH the event list and the detail page —
    autoescape is the only sanitizer either may rely on."""
    stocktake_warehouse_a.code = _XSS_SCRIPT
    stocktake_warehouse_a.save(update_fields=["code"])
    event = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=timezone.localdate(), requested_by=admin_user)

    listing = client_a.get(reverse("inventory:physicalinventory_list")).content.decode()
    assert _XSS_SCRIPT not in listing
    assert "&lt;script&gt;" in listing

    detail = client_a.get(reverse("inventory:physicalinventory_detail",
                                  args=[event.pk])).content.decode()
    assert _XSS_SCRIPT not in detail
    assert "&lt;script&gt;" in detail


# ---- tenant isolation on the variance report ----------------------------------------------------------

def test_stocktake_variance_report_isolates_tenants(client_a, client_b, tenant_b,
                                                    stocktake_bin_b):
    """The analysis lens merges only the workspace's own completed work: Globex's only
    counted sheet must surface nothing at all through Acme's lens (empty state, zero
    CC- rows), while Globex's own lens finds it."""
    from apps.scm.models import CycleCountTask

    CycleCountTask.objects.create(
        tenant=tenant_b, location=stocktake_bin_b,
        scheduled_date=timezone.localdate(), count_method="full", status="counted")

    acme_page = client_a.get(reverse("inventory:variance_report"))
    assert acme_page.status_code == 200
    html = acme_page.content.decode()
    assert "No counted sheets yet" in html
    assert "CC-" not in html  # no row at all leaked into Acme's lens

    globex_page = client_b.get(reverse("inventory:variance_report"))
    assert globex_page.status_code == 200
    assert "CC-" in globex_page.content.decode()


# ---- audit trail ---------------------------------------------------------------------------------------

def test_stocktake_start_success_writes_audit_row(client_a, admin_user, stocktake_event_a,
                                                  stocktake_zone_a, stocktake_bin_a):
    """A successful Start freezes, spawns its known two-sheet set and lands ONE audit
    row attributed to the acting admin inside the event's own tenant."""
    response = client_a.post(reverse("inventory:physicalinventory_start",
                                     args=[stocktake_event_a.pk]))
    assert response.status_code == 302

    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "counting"
    assert stocktake_event_a.is_frozen is True
    assert _stocktake_sheet_count(stocktake_event_a) == 2

    logs = _stocktake_audit_logs(stocktake_event_a).order_by("id")
    assert [log.action for log in logs] == ["start"]
    log = logs.get()
    assert log.user_id == admin_user.pk
    assert log.tenant_id == stocktake_event_a.tenant_id
    assert log.changes.get("sheets_spawned") == 2


def test_stocktake_active_program_run_mints_one_sheet_and_writes_audit(
        client_a, admin_user, stocktake_program_a):
    """Run on an ACTIVE cadence mints exactly today's spine sheet under the provenance
    marker and writes the run audit attributed to the actor."""
    assert _stocktake_program_marker_count(stocktake_program_a) == 0

    response = client_a.post(reverse("inventory:countprogram_run",
                                     args=[stocktake_program_a.pk]))
    assert response.status_code == 302

    stocktake_program_a.refresh_from_db()
    assert stocktake_program_a.last_run_date == timezone.localdate()
    assert _stocktake_program_marker_count(stocktake_program_a) == 1

    logs = _stocktake_audit_logs(stocktake_program_a).filter(action="run")
    log = logs.get()
    assert log.user_id == admin_user.pk
    assert log.tenant_id == stocktake_program_a.tenant_id
