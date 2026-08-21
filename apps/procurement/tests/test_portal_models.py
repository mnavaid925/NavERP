"""Procurement 6.1 - model invariants.

The portal's contract lives at the model boundary: the alert lifecycle that cannot be restated
by hand, the link guard that keeps alert cards on-site, badge classes that exist in theme.css,
and widget preferences where ABSENCE of a row means visible.
"""
from django.core.exceptions import ValidationError

import pytest

from apps.procurement.models import ProcurementAlert, WidgetPreference

pytestmark = pytest.mark.django_db

VALID_LINK = "/procurement/quick-requisition/"


# ------------------------------------------------------------------ lifecycle


class TestAlertLifecycle:
    def test_acknowledge_stamps_who_and_when_once(self, alert_open, admin_user):
        assert alert_open.acknowledge(admin_user) is True
        assert alert_open.status == "acknowledged"
        assert alert_open.acknowledged_by_id == admin_user.pk
        first_at = alert_open.acknowledged_at
        # A second acknowledge is a no-op, not a re-stamp.
        assert alert_open.acknowledge(admin_user) is False
        assert alert_open.acknowledged_at == first_at

    def test_acknowledge_refuses_on_resolved(self, alert_resolved, admin_user):
        assert alert_resolved.acknowledge(admin_user) is False
        assert alert_resolved.status == "resolved"

    def test_resolve_from_open_is_a_normal_fast_path(self, alert_open, admin_user):
        assert alert_open.resolve(admin_user, note="closed directly") is True
        assert alert_open.status == "resolved"
        assert alert_open.resolved_by_id == admin_user.pk
        assert alert_open.resolution_note == "closed directly"

    def test_resolve_is_idempotent_and_never_rewrites_history(self, alert_resolved, admin_user):
        """CR-2 regression: a crafted second resolve must not overwrite who/when/note."""
        who = alert_resolved.resolved_by_id
        when = alert_resolved.resolved_at
        note = alert_resolved.resolution_note
        assert alert_resolved.resolve(admin_user, note="hijack") is False
        alert_resolved.refresh_from_db()
        assert alert_resolved.resolved_by_id == who
        assert alert_resolved.resolved_at == when
        assert alert_resolved.resolution_note == note


# ------------------------------------------------------------------ overdue


class TestIsOverdue:
    def test_overdue_open_alert(self, alert_overdue):
        assert alert_overdue.is_overdue is True

    def test_resolved_alerts_are_never_overdue(self, db, tenant_a):
        from django.utils import timezone
        import datetime
        row = _alert(tenant_a, status="resolved", resolved_at=timezone.now(),
                     due_at=timezone.now() - datetime.timedelta(days=3))
        assert row.is_overdue is False

    def test_no_due_date_means_no_overdue(self, alert_unassigned):
        assert alert_unassigned.due_at is None
        assert alert_unassigned.is_overdue is False


def _alert(tenant, **overrides):
    fields = dict(tenant=tenant, kind="task", severity="info", status="open",
                  title="x")
    fields.update(overrides)
    return ProcurementAlert.objects.create(**fields)


# ------------------------------------------------------------------ link guard (CR-1)


class TestLinkUrlGuard:
    @pytest.mark.parametrize("good", [VALID_LINK, "/scm/requisitions/", ""])
    def test_internal_paths_pass(self, tenant_a, good):
        row = _alert(tenant_a, link_url=good)
        row.full_clean()  # no ValidationError

    @pytest.mark.parametrize("bad", ["https://evil.com", "//evil.com", "/\\evil.com",
                                     "javascript:alert(1)", "relative/no-slash"])
    def test_off_site_shapes_raise(self, tenant_a, bad):
        """Browsers canonicalize backslashes to slashes, so '/\\evil.com' IS '//'evil.com."""
        row = _alert(tenant_a, link_url=bad)
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "link_url" in exc.value.error_dict

    def test_status_cannot_be_edited_into_resolved_without_stamp(self, tenant_a):
        row = _alert(tenant_a)
        row.status = "resolved"
        with pytest.raises(ValidationError) as exc:
            row.full_clean()
        assert "status" in exc.value.error_dict


# ------------------------------------------------------------------ badges (L33)


class TestBadgeClasses:
    def test_only_colour_named_classes_exist(self):
        allowed = {"badge-green", "badge-red", "badge-amber",
                   "badge-info", "badge-muted", "badge-slate"}
        for severity, _ in ProcurementAlert.SEVERITY_CHOICES:
            assert ProcurementAlert(severity=severity).severity_css in allowed
        for status, _ in ProcurementAlert.STATUS_CHOICES:
            assert ProcurementAlert(status=status).status_css in allowed
        for kind, _ in ProcurementAlert.KIND_CHOICES:
            assert ProcurementAlert(kind=kind).kind_css in allowed

    def test_semantic_names_never_appear(self):
        for field, choices in (("severity", ProcurementAlert.SEVERITY_CHOICES),
                               ("status", ProcurementAlert.STATUS_CHOICES),
                               ("kind", ProcurementAlert.KIND_CHOICES)):
            for value, _ in choices:
                css = ProcurementAlert(**{field: value}).__getattribute__(f"{field}_css")
                assert not any(s in css for s in ("success", "warning", "danger"))

    def test_open_is_red_because_open_means_unattended(self):
        assert ProcurementAlert(status="open").status_css == "badge-red"
        assert ProcurementAlert(status="resolved").status_css == "badge-green"


# ------------------------------------------------------------------ widget preferences


class TestWidgetPreference:
    def test_registry_has_exactly_the_five_widgets(self):
        assert set(WidgetPreference.WIDGETS) == {
            "approvals", "alerts", "spend", "deadlines", "activity"}

    def test_hidden_keys_empty_when_no_rows_exist(self, tenant_a, admin_user):
        """Absence of a row MEANS visible - the default overview is the full set."""
        assert WidgetPreference.hidden_keys(tenant_a, admin_user) == set()

    def test_save_choices_persists_split_and_replaces(self, tenant_a, admin_user):
        WidgetPreference.save_choices(tenant_a, admin_user, {"approvals", "spend"})
        assert WidgetPreference.hidden_keys(tenant_a, admin_user) == {
            "alerts", "deadlines", "activity"}
        WidgetPreference.save_choices(tenant_a, admin_user, set())
        assert WidgetPreference.hidden_keys(tenant_a, admin_user) == set(
            WidgetPreference.WIDGETS)

    def test_unknown_widget_key_rejected(self, tenant_a, admin_user):
        row = WidgetPreference(tenant=tenant_a, user=admin_user, widget_key="nonsense")
        with pytest.raises(ValidationError):
            row.full_clean()

    def test_one_row_per_user_widget(self, tenant_a, admin_user, member_user):
        WidgetPreference.objects.create(tenant=tenant_a, user=admin_user,
                                        widget_key="spend", is_visible=False)
        WidgetPreference.objects.create(tenant=tenant_a, user=member_user,
                                        widget_key="spend", is_visible=True)
        assert WidgetPreference.hidden_keys(tenant_a, admin_user) == {"spend"}
        assert WidgetPreference.hidden_keys(tenant_a, member_user) == set()

    def test_str_renders_state(self, tenant_a, admin_user):
        row = WidgetPreference.objects.create(tenant=tenant_a, user=admin_user,
                                              widget_key="alerts", is_visible=False)
        assert "hidden" in str(row)


# ------------------------------------------------------------------ misc


class TestStrAndOrdering:
    def test_str_carries_severity_and_title(self, alert_open):
        assert alert_open.title in str(alert_open)

    def test_tenant_scoping_is_total(self, alert_open, alert_b):
        """The one query every view starts from must never mix workspaces."""
        acme_titles = list(ProcurementAlert.objects.filter(tenant=alert_open.tenant)
                           .values_list("title", flat=True))
        assert "Globex only alert" not in acme_titles
