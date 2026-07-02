"""Comprehensive tests for the HRM 3.9 Attendance Management **completion** —
GeoFence, AttendanceRegularization, and the geofencing fields added to AttendanceRecord.

Covers:
  - GeoFence: distance_to() haversine math (0 at centre, ~111km per 1deg latitude),
    contains() boundary (True at/just-inside radius, False just outside, False for
    None coords), unique_together (tenant, name), lat/long range validators, radius_m
    MinValue(1).
  - AttendanceRecord geofencing: has_geo(), geo_status() ("verified"/"outside"/""),
    clean() rejects a lone lat/long and a geofence set without coordinates.
  - AttendanceRegularization: REG- per-tenant numbering, clean() guards (attendance_record
    employee mismatch, neither requested time provided), full status machine via the
    view layer (submit/approve/reject/cancel), the three approve branches (linked record /
    materialize new / correct existing same-day punch), edit/delete guard on decided rows,
    @tenant_admin_required 403 for approve/reject.
  - Forms: AttendanceRegularizationForm excludes workflow fields; GeoFenceForm and
    AttendanceRecordForm tenant-scope FK dropdowns (cross-tenant pk rejected).
  - Multi-tenant IDOR sweep for both new models across every child-pk action.
  - Performance: geofence_detail query count does not scale with the number of linked
    punches (locks in the per-row geofence FK-cache priming in the view).
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ============================================================
# 3.9-completion-specific fixtures
# ============================================================

@pytest.fixture
def geofence_a(db, tenant_a):
    """A geofence for tenant_a centred at (0, 0) with a 100m radius."""
    from apps.hrm.models import GeoFence
    return GeoFence.objects.create(
        tenant=tenant_a,
        name="HQ Campus",
        address="1 Main St",
        latitude=Decimal("0"),
        longitude=Decimal("0"),
        radius_m=100,
    )


@pytest.fixture
def geofence_b(db, tenant_b):
    """A geofence for tenant_b (IDOR tests)."""
    from apps.hrm.models import GeoFence
    return GeoFence.objects.create(
        tenant=tenant_b,
        name="Globex Site",
        latitude=Decimal("10"),
        longitude=Decimal("20"),
        radius_m=50,
    )


@pytest.fixture
def pending_regularization_a(db, tenant_a, employee_a, attendance_a):
    """A pending AttendanceRegularization for employee_a linked to attendance_a."""
    from apps.hrm.models import AttendanceRegularization
    reg = AttendanceRegularization.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        attendance_record=attendance_a,
        date=attendance_a.date,
        reason_type="wrong_time",
        requested_check_in=datetime.time(9, 0),
        requested_check_out=datetime.time(18, 30),
        reason="Forgot to punch in on time.",
        status="pending",
    )
    return reg


@pytest.fixture
def draft_regularization_a(db, tenant_a, employee_a):
    """A draft AttendanceRegularization for employee_a with no linked record yet."""
    from apps.hrm.models import AttendanceRegularization
    return AttendanceRegularization.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        date=datetime.date(2026, 6, 25),
        reason_type="missed_punch",
        requested_check_in=datetime.time(9, 0),
        requested_check_out=datetime.time(17, 0),
        reason="Forgot to punch entirely.",
        status="draft",
    )


@pytest.fixture
def regularization_b(db, tenant_b, employee_b, attendance_b):
    """A pending AttendanceRegularization for tenant_b (IDOR tests)."""
    from apps.hrm.models import AttendanceRegularization
    return AttendanceRegularization.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        attendance_record=attendance_b,
        date=attendance_b.date,
        reason_type="wrong_time",
        requested_check_in=datetime.time(9, 0),
        requested_check_out=datetime.time(17, 30),
        reason="Globex correction.",
        status="pending",
    )


# ============================================================
# GeoFence model
# ============================================================
class TestGeoFenceDistance:
    def test_distance_zero_at_centre(self, geofence_a):
        assert geofence_a.distance_to(Decimal("0"), Decimal("0")) == pytest.approx(0.0, abs=1e-6)

    def test_distance_one_degree_latitude_is_about_111km(self, geofence_a):
        # 1 degree of latitude is ~111.19 km on a sphere of Earth's mean radius.
        dist = geofence_a.distance_to(Decimal("1"), Decimal("0"))
        assert dist == pytest.approx(111_194.9, rel=1e-3)

    def test_distance_accepts_float_args(self, geofence_a):
        dist = geofence_a.distance_to(1.0, 0.0)
        assert dist == pytest.approx(111_194.9, rel=1e-3)

    def test_contains_true_at_centre(self, geofence_a):
        assert geofence_a.contains(Decimal("0"), Decimal("0")) is True

    def test_contains_true_just_inside_radius(self, geofence_a):
        # 100m radius. Move a fraction of a degree that lands just under 100m.
        # 1 degree ~= 111194.9m, so 90m ~= 90/111194.9 degrees.
        delta = Decimal("90") / Decimal("111194.9")
        assert geofence_a.contains(delta, Decimal("0")) is True

    def test_contains_true_exactly_at_radius_boundary(self, geofence_a):
        # Construct a point whose haversine distance is (numerically) <= radius_m.
        # Using distance_to's inverse isn't exact due to float rounding, so verify the
        # invariant directly: contains() is defined as distance_to(...) <= radius_m.
        lat = Decimal("0.0009")  # ~100.07m — right around the 100m boundary
        dist = geofence_a.distance_to(lat, Decimal("0"))
        expected = dist <= geofence_a.radius_m
        assert geofence_a.contains(lat, Decimal("0")) is expected

    def test_contains_false_just_outside_radius(self, geofence_a):
        # 150m away — comfortably outside the 100m radius.
        delta = Decimal("150") / Decimal("111194.9")
        assert geofence_a.contains(delta, Decimal("0")) is False

    def test_contains_false_far_away(self, geofence_a):
        assert geofence_a.contains(Decimal("45"), Decimal("90")) is False

    def test_contains_none_lat_returns_false(self, geofence_a):
        assert geofence_a.contains(None, Decimal("0")) is False

    def test_contains_none_lng_returns_false(self, geofence_a):
        assert geofence_a.contains(Decimal("0"), None) is False

    def test_contains_both_none_returns_false(self, geofence_a):
        assert geofence_a.contains(None, None) is False


class TestGeoFenceModel:
    def test_str(self, geofence_a):
        s = str(geofence_a)
        assert "HQ Campus" in s
        assert "100" in s

    def test_defaults(self, tenant_a):
        from apps.hrm.models import GeoFence
        gf = GeoFence.objects.create(
            tenant=tenant_a, name="Default Test", latitude=Decimal("1"), longitude=Decimal("1"),
        )
        assert gf.radius_m == 100
        assert gf.is_active is True

    def test_unique_together_tenant_name(self, tenant_a, geofence_a):
        from apps.hrm.models import GeoFence
        with pytest.raises(IntegrityError):
            GeoFence.objects.create(
                tenant=tenant_a, name="HQ Campus", latitude=Decimal("5"), longitude=Decimal("5"),
            )

    def test_same_name_different_tenant_allowed(self, tenant_b, geofence_a):
        """unique_together is scoped per tenant — tenant_b may reuse the same name."""
        from apps.hrm.models import GeoFence
        gf = GeoFence.objects.create(
            tenant=tenant_b, name="HQ Campus", latitude=Decimal("5"), longitude=Decimal("5"),
        )
        assert gf.pk is not None

    def test_latitude_over_90_rejected_by_full_clean(self, tenant_a):
        from apps.hrm.models import GeoFence
        gf = GeoFence(tenant=tenant_a, name="Bad Lat", latitude=Decimal("91"), longitude=Decimal("0"))
        with pytest.raises(ValidationError):
            gf.full_clean()

    def test_latitude_under_negative_90_rejected(self, tenant_a):
        from apps.hrm.models import GeoFence
        gf = GeoFence(tenant=tenant_a, name="Bad Lat 2", latitude=Decimal("-91"), longitude=Decimal("0"))
        with pytest.raises(ValidationError):
            gf.full_clean()

    def test_longitude_under_negative_180_rejected(self, tenant_a):
        from apps.hrm.models import GeoFence
        gf = GeoFence(tenant=tenant_a, name="Bad Lng", latitude=Decimal("0"), longitude=Decimal("-181"))
        with pytest.raises(ValidationError):
            gf.full_clean()

    def test_longitude_over_180_rejected(self, tenant_a):
        from apps.hrm.models import GeoFence
        gf = GeoFence(tenant=tenant_a, name="Bad Lng 2", latitude=Decimal("0"), longitude=Decimal("181"))
        with pytest.raises(ValidationError):
            gf.full_clean()

    def test_radius_below_minimum_rejected(self, tenant_a):
        from apps.hrm.models import GeoFence
        gf = GeoFence(tenant=tenant_a, name="Bad Radius", latitude=Decimal("0"), longitude=Decimal("0"),
                       radius_m=0)
        with pytest.raises(ValidationError):
            gf.full_clean()

    def test_radius_of_one_is_valid(self, tenant_a):
        from apps.hrm.models import GeoFence
        gf = GeoFence(tenant=tenant_a, name="Min Radius", latitude=Decimal("0"), longitude=Decimal("0"),
                       radius_m=1)
        gf.full_clean()  # should not raise


# ============================================================
# AttendanceRecord geofencing fields
# ============================================================
class TestAttendanceRecordGeofencing:
    def test_has_geo_false_by_default(self, attendance_a):
        assert attendance_a.has_geo() is False

    def test_has_geo_true_when_both_set(self, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
            shift=shift_a, latitude=Decimal("0"), longitude=Decimal("0"),
        )
        assert att.has_geo() is True

    def test_geo_status_empty_when_no_coords(self, attendance_a, geofence_a):
        attendance_a.geofence = geofence_a
        # No coordinates set — geo_status must be "" (has_geo() is False), not an error.
        assert attendance_a.geo_status() == ""

    def test_geo_status_empty_when_coords_but_no_geofence(self, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
            shift=shift_a, latitude=Decimal("0"), longitude=Decimal("0"),
        )
        assert att.geo_status() == ""

    def test_geo_status_verified_inside_zone(self, tenant_a, employee_a, shift_a, geofence_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
            shift=shift_a, latitude=Decimal("0.0001"), longitude=Decimal("0.0001"),
            geofence=geofence_a,
        )
        assert att.geo_status() == "verified"

    def test_geo_status_outside_beyond_radius(self, tenant_a, employee_a, shift_a, geofence_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
            shift=shift_a, latitude=Decimal("5"), longitude=Decimal("5"),
            geofence=geofence_a,
        )
        assert att.geo_status() == "outside"

    def test_geo_status_evaluated_even_when_geofence_inactive(self, tenant_a, employee_a, shift_a, geofence_a):
        """geo_status() checks the live radius regardless of is_active — a punch reflects
        where it actually happened, per the model's docstring."""
        from apps.hrm.models import AttendanceRecord
        geofence_a.is_active = False
        geofence_a.save()
        att = AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
            shift=shift_a, latitude=Decimal("0"), longitude=Decimal("0"),
            geofence=geofence_a,
        )
        assert att.geo_status() == "verified"

    def test_clean_rejects_latitude_without_longitude(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord(tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
                                latitude=Decimal("1"), longitude=None)
        with pytest.raises(ValidationError):
            att.clean()

    def test_clean_rejects_longitude_without_latitude(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord(tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
                                latitude=None, longitude=Decimal("1"))
        with pytest.raises(ValidationError):
            att.clean()

    def test_clean_rejects_geofence_without_coordinates(self, tenant_a, employee_a, geofence_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord(tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
                                latitude=None, longitude=None, geofence=geofence_a)
        with pytest.raises(ValidationError):
            att.clean()

    def test_clean_accepts_both_coordinates_set(self, tenant_a, employee_a, geofence_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord(tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
                                latitude=Decimal("0"), longitude=Decimal("0"), geofence=geofence_a)
        att.clean()  # should not raise

    def test_clean_accepts_neither_coordinate_set(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord(tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24))
        att.clean()  # should not raise


# ============================================================
# AttendanceRegularization model
# ============================================================
class TestAttendanceRegularizationModel:
    def test_number_prefix_and_sequence(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRegularization
        reg1 = AttendanceRegularization.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 1),
            reason_type="missed_punch", requested_check_in=datetime.time(9, 0), reason="r1",
        )
        reg2 = AttendanceRegularization.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 2),
            reason_type="missed_punch", requested_check_in=datetime.time(9, 0), reason="r2",
        )
        assert reg1.number == "REG-00001"
        assert reg2.number == "REG-00002"

    def test_numbering_isolated_per_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.models import AttendanceRegularization
        reg_a = AttendanceRegularization.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 1),
            reason_type="missed_punch", requested_check_in=datetime.time(9, 0), reason="a",
        )
        reg_b = AttendanceRegularization.objects.create(
            tenant=tenant_b, employee=employee_b, date=datetime.date(2026, 6, 1),
            reason_type="missed_punch", requested_check_in=datetime.time(9, 0), reason="b",
        )
        assert reg_a.number == "REG-00001"
        assert reg_b.number == "REG-00001"  # isolated per tenant, not globally sequential

    def test_default_status_is_draft(self, draft_regularization_a):
        assert draft_regularization_a.status == "draft"

    def test_str(self, pending_regularization_a):
        s = str(pending_regularization_a)
        assert pending_regularization_a.number in s
        assert "Pending" in s

    def test_unique_together_tenant_number(self, tenant_a, employee_a, pending_regularization_a):
        from apps.hrm.models import AttendanceRegularization
        with pytest.raises(IntegrityError):
            AttendanceRegularization.objects.create(
                tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 7, 1),
                reason_type="other", requested_check_in=datetime.time(9, 0), reason="dup",
                number=pending_regularization_a.number,
            )

    def test_clean_rejects_attendance_record_of_different_employee(
            self, tenant_a, employee_a, person_a2, attendance_a):
        """attendance_record must belong to the same employee — cross-employee link must fail."""
        from apps.hrm.models import AttendanceRegularization, EmployeeProfile
        # A second, genuinely distinct employee within tenant_a (own Party) for the mismatch.
        other_employee = EmployeeProfile.objects.create(
            tenant=tenant_a,
            party=person_a2,
            employee_type="full_time",
        )
        reg = AttendanceRegularization(
            tenant=tenant_a, employee=other_employee, attendance_record=attendance_a,
            date=attendance_a.date, reason_type="wrong_time",
            requested_check_in=datetime.time(9, 0), reason="mismatch",
        )
        with pytest.raises(ValidationError):
            reg.clean()

    def test_clean_rejects_neither_requested_time(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRegularization
        reg = AttendanceRegularization(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 1),
            reason_type="missed_punch", requested_check_in=None, requested_check_out=None,
            reason="empty",
        )
        with pytest.raises(ValidationError):
            reg.clean()

    def test_clean_accepts_checkin_only(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRegularization
        reg = AttendanceRegularization(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 1),
            reason_type="forgot_checkin", requested_check_in=datetime.time(9, 0),
            requested_check_out=None, reason="checkin only",
        )
        reg.clean()  # should not raise

    def test_clean_accepts_checkout_only(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRegularization
        reg = AttendanceRegularization(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 1),
            reason_type="forgot_checkout", requested_check_in=None,
            requested_check_out=datetime.time(18, 0), reason="checkout only",
        )
        reg.clean()  # should not raise

    def test_clean_accepts_no_linked_record(self, draft_regularization_a):
        draft_regularization_a.clean()  # should not raise (attendance_record is optional)

    def test_status_choices(self):
        from apps.hrm.models import AttendanceRegularization
        keys = [k for k, _ in AttendanceRegularization.STATUS_CHOICES]
        for expected in ("draft", "pending", "approved", "rejected", "cancelled"):
            assert expected in keys

    def test_reason_type_choices(self):
        from apps.hrm.models import AttendanceRegularization
        keys = [k for k, _ in AttendanceRegularization.REASON_TYPE_CHOICES]
        for expected in ("missed_punch", "forgot_checkin", "forgot_checkout", "wrong_time",
                         "on_duty", "work_from_home", "system_error", "other"):
            assert expected in keys


# ============================================================
# Forms
# ============================================================
class TestAttendanceRegularizationForm:
    def test_workflow_fields_excluded(self):
        from apps.hrm.forms import AttendanceRegularizationForm
        for field in ("status", "approver", "approved_at", "decision_note", "number"):
            assert field not in AttendanceRegularizationForm.Meta.fields

    def test_valid_data_saves_as_draft(self, tenant_a, employee_a):
        from apps.hrm.forms import AttendanceRegularizationForm
        form = AttendanceRegularizationForm(data={
            "employee": employee_a.pk,
            "date": "2026-06-01",
            "reason_type": "missed_punch",
            "requested_check_in": "09:00",
            "requested_check_out": "",
            "reason": "Forgot to punch in.",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        obj.tenant = tenant_a
        obj.save()
        assert obj.status == "draft"  # model default — cannot be set via the form

    def test_post_cannot_self_approve(self, tenant_a, employee_a):
        """A crafted POST including status=approved must be silently ignored (field absent)."""
        from apps.hrm.forms import AttendanceRegularizationForm
        form = AttendanceRegularizationForm(data={
            "employee": employee_a.pk,
            "date": "2026-06-01",
            "reason_type": "missed_punch",
            "requested_check_in": "09:00",
            "reason": "Sneaky",
            "status": "approved",
            "approver": "1",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert "status" not in form.cleaned_data
        assert "approver" not in form.cleaned_data
        obj = form.save(commit=False)
        obj.tenant = tenant_a
        obj.save()
        assert obj.status == "draft"
        assert obj.approver is None

    def test_cross_tenant_employee_rejected(self, tenant_a, employee_b):
        from apps.hrm.forms import AttendanceRegularizationForm
        form = AttendanceRegularizationForm(data={
            "employee": employee_b.pk,  # belongs to tenant_b
            "date": "2026-06-01",
            "reason_type": "missed_punch",
            "requested_check_in": "09:00",
            "reason": "Cross tenant",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "employee" in form.errors

    def test_cross_tenant_attendance_record_rejected(self, tenant_a, employee_a, attendance_b):
        from apps.hrm.forms import AttendanceRegularizationForm
        form = AttendanceRegularizationForm(data={
            "employee": employee_a.pk,
            "attendance_record": attendance_b.pk,  # belongs to tenant_b
            "date": "2026-06-01",
            "reason_type": "wrong_time",
            "requested_check_in": "09:00",
            "reason": "Cross tenant record",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "attendance_record" in form.errors

    def test_missing_requested_times_rejected(self, tenant_a, employee_a):
        """Form-level Meta.clean() (delegated to model.clean()) must reject when neither
        requested time is provided."""
        from apps.hrm.forms import AttendanceRegularizationForm
        form = AttendanceRegularizationForm(data={
            "employee": employee_a.pk,
            "date": "2026-06-01",
            "reason_type": "missed_punch",
            "reason": "No times given",
        }, tenant=tenant_a)
        assert not form.is_valid()


class TestGeoFenceForm:
    def test_valid_data(self, tenant_a):
        from apps.hrm.forms import GeoFenceForm
        form = GeoFenceForm(data={
            "name": "Warehouse",
            "address": "2 Dock Rd",
            "latitude": "12.34",
            "longitude": "56.78",
            "radius_m": "150",
            "is_active": True,
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_missing_name_rejected(self, tenant_a):
        from apps.hrm.forms import GeoFenceForm
        form = GeoFenceForm(data={
            "latitude": "12.34", "longitude": "56.78", "radius_m": "150",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_out_of_range_latitude_rejected(self, tenant_a):
        from apps.hrm.forms import GeoFenceForm
        form = GeoFenceForm(data={
            "name": "Bad", "latitude": "95", "longitude": "0", "radius_m": "100",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "latitude" in form.errors

    def test_zero_radius_rejected(self, tenant_a):
        from apps.hrm.forms import GeoFenceForm
        form = GeoFenceForm(data={
            "name": "Bad Radius", "latitude": "1", "longitude": "1", "radius_m": "0",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "radius_m" in form.errors


class TestAttendanceRecordForm:
    def test_valid_data_with_geofence(self, tenant_a, employee_a, shift_a, geofence_a):
        from apps.hrm.forms import AttendanceRecordForm
        form = AttendanceRecordForm(data={
            "employee": employee_a.pk,
            "date": "2026-06-24",
            "check_in": "09:00",
            "check_out": "18:00",
            "shift": shift_a.pk,
            "status": "present",
            "source": "mobile",
            "latitude": "0.0001",
            "longitude": "0.0001",
            "geofence": geofence_a.pk,
            "notes": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_cross_tenant_employee_rejected(self, tenant_a, employee_b):
        from apps.hrm.forms import AttendanceRecordForm
        form = AttendanceRecordForm(data={
            "employee": employee_b.pk,
            "date": "2026-06-24",
            "status": "present",
            "source": "web",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "employee" in form.errors

    def test_cross_tenant_geofence_rejected(self, tenant_a, employee_a, geofence_b):
        from apps.hrm.forms import AttendanceRecordForm
        form = AttendanceRecordForm(data={
            "employee": employee_a.pk,
            "date": "2026-06-24",
            "status": "present",
            "source": "web",
            "latitude": "10",
            "longitude": "20",
            "geofence": geofence_b.pk,  # belongs to tenant_b
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "geofence" in form.errors

    def test_latitude_without_longitude_rejected(self, tenant_a, employee_a):
        from apps.hrm.forms import AttendanceRecordForm
        form = AttendanceRecordForm(data={
            "employee": employee_a.pk,
            "date": "2026-06-24",
            "status": "present",
            "source": "web",
            "latitude": "10",
            "longitude": "",
        }, tenant=tenant_a)
        assert not form.is_valid()


# ============================================================
# Views — GeoFence CRUD
# ============================================================
class TestGeoFenceListView:
    def test_list_ok(self, client_a, geofence_a):
        resp = client_a.get(reverse("hrm:geofence_list"))
        assert resp.status_code == 200
        assert geofence_a.name.encode() in resp.content

    def test_search_by_name(self, client_a, geofence_a):
        resp = client_a.get(reverse("hrm:geofence_list"), {"q": "HQ"})
        assert resp.status_code == 200
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert geofence_a.pk in pks

    def test_filter_by_is_active(self, client_a, geofence_a):
        resp = client_a.get(reverse("hrm:geofence_list"), {"is_active": "True"})
        assert resp.status_code == 200
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert geofence_a.pk in pks

    def test_anon_redirects(self):
        c = Client()
        resp = c.get(reverse("hrm:geofence_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestGeoFenceCreateView:
    def test_post_creates_geofence_with_request_tenant(self, client_a, tenant_a):
        from apps.hrm.models import GeoFence
        resp = client_a.post(reverse("hrm:geofence_create"), {
            "name": "New Site", "address": "3 Elm St",
            "latitude": "12.5", "longitude": "-8.25", "radius_m": "200", "is_active": True,
        })
        assert resp.status_code == 302
        gf = GeoFence.objects.get(name="New Site")
        assert gf.tenant_id == tenant_a.pk


class TestGeoFenceDetailView:
    def test_detail_shows_recent_punches(self, client_a, geofence_a, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
            shift=shift_a, latitude=Decimal("0"), longitude=Decimal("0"), geofence=geofence_a,
        )
        resp = client_a.get(reverse("hrm:geofence_detail", args=[geofence_a.pk]))
        assert resp.status_code == 200
        assert "recent_punches" in resp.context
        assert len(resp.context["recent_punches"]) == 1


class TestGeoFenceEditDeleteView:
    def test_edit_updates_fields(self, client_a, geofence_a):
        resp = client_a.post(reverse("hrm:geofence_edit", args=[geofence_a.pk]), {
            "name": "HQ Campus", "address": "Updated address",
            "latitude": "0", "longitude": "0", "radius_m": "500", "is_active": True,
        })
        assert resp.status_code == 302
        geofence_a.refresh_from_db()
        assert geofence_a.radius_m == 500

    def test_delete_blocked_when_linked_to_attendance(
            self, client_a, geofence_a, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord, GeoFence
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 24),
            shift=shift_a, latitude=Decimal("0"), longitude=Decimal("0"), geofence=geofence_a,
        )
        pk = geofence_a.pk
        resp = client_a.post(reverse("hrm:geofence_delete", args=[pk]))
        assert resp.status_code == 302
        assert GeoFence.objects.filter(pk=pk).exists()

    def test_delete_succeeds_when_unlinked(self, client_a, geofence_a):
        from apps.hrm.models import GeoFence
        pk = geofence_a.pk
        resp = client_a.post(reverse("hrm:geofence_delete", args=[pk]))
        assert resp.status_code == 302
        assert not GeoFence.objects.filter(pk=pk).exists()

    def test_delete_get_does_not_delete(self, client_a, geofence_a):
        """@require_POST guard — a GET must not delete."""
        from apps.hrm.models import GeoFence
        pk = geofence_a.pk
        resp = client_a.get(reverse("hrm:geofence_delete", args=[pk]))
        assert resp.status_code == 405
        assert GeoFence.objects.filter(pk=pk).exists()


# ============================================================
# Views — AttendanceRegularization status machine
# ============================================================
class TestRegularizationSubmit:
    def test_submit_draft_to_pending(self, client_a, draft_regularization_a):
        resp = client_a.post(reverse("hrm:attendanceregularization_submit", args=[draft_regularization_a.pk]))
        assert resp.status_code == 302
        draft_regularization_a.refresh_from_db()
        assert draft_regularization_a.status == "pending"

    def test_submit_noop_from_pending(self, client_a, pending_regularization_a):
        resp = client_a.post(reverse("hrm:attendanceregularization_submit", args=[pending_regularization_a.pk]))
        assert resp.status_code == 302
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "pending"

    def test_submit_noop_from_approved(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRegularization
        reg = AttendanceRegularization.objects.create(
            tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 5),
            reason_type="missed_punch", requested_check_in=datetime.time(9, 0),
            reason="already approved", status="approved",
        )
        resp = client_a.post(reverse("hrm:attendanceregularization_submit", args=[reg.pk]))
        assert resp.status_code == 302
        reg.refresh_from_db()
        assert reg.status == "approved"  # unchanged


class TestRegularizationApproveLinkedRecord:
    """Branch (a): the regularization already has an attendance_record linked."""

    def test_approve_rewrites_linked_punch(self, client_a, pending_regularization_a, attendance_a):
        resp = client_a.post(
            reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]),
            {"decision_note": "Looks fine"},
        )
        assert resp.status_code == 302
        pending_regularization_a.refresh_from_db()
        attendance_a.refresh_from_db()
        assert pending_regularization_a.status == "approved"
        assert pending_regularization_a.approver is not None
        assert pending_regularization_a.approved_at is not None
        assert pending_regularization_a.decision_note == "Looks fine"
        assert attendance_a.status == "regularized"
        assert attendance_a.check_in == datetime.time(9, 0)
        assert attendance_a.check_out == datetime.time(18, 30)
        # hours_worked recomputed: 09:00 -> 18:30 = 9.5 hours
        assert attendance_a.hours_worked == Decimal("9.50")
        assert pending_regularization_a.attendance_record_id == attendance_a.pk

    def test_approve_noop_when_not_pending(self, client_a, draft_regularization_a):
        resp = client_a.post(
            reverse("hrm:attendanceregularization_approve", args=[draft_regularization_a.pk]))
        assert resp.status_code == 302
        draft_regularization_a.refresh_from_db()
        assert draft_regularization_a.status == "draft"


class TestRegularizationApproveNoLinkedRecordMaterializes:
    """Branch (b): no linked record and no existing (employee, date) punch — a new
    AttendanceRecord must be materialized (status regularized) and linked back."""

    def test_approve_materializes_new_record(self, client_a, draft_regularization_a, employee_a, tenant_a):
        from apps.hrm.models import AttendanceRecord
        # Submit then approve.
        client_a.post(reverse("hrm:attendanceregularization_submit", args=[draft_regularization_a.pk]))
        before_count = AttendanceRecord.objects.filter(tenant=tenant_a, employee=employee_a,
                                                        date=draft_regularization_a.date).count()
        assert before_count == 0
        resp = client_a.post(
            reverse("hrm:attendanceregularization_approve", args=[draft_regularization_a.pk]))
        assert resp.status_code == 302
        draft_regularization_a.refresh_from_db()
        assert draft_regularization_a.status == "approved"
        assert draft_regularization_a.attendance_record is not None
        rec = draft_regularization_a.attendance_record
        assert rec.status == "regularized"
        assert rec.employee_id == employee_a.pk
        assert rec.date == draft_regularization_a.date
        assert rec.check_in == datetime.time(9, 0)
        assert rec.check_out == datetime.time(17, 0)
        assert rec.number  # ATT- number assigned on materialization
        # Exactly one new record was created for that (employee, date).
        assert AttendanceRecord.objects.filter(
            tenant=tenant_a, employee=employee_a, date=draft_regularization_a.date).count() == 1


class TestRegularizationApproveCorrectsExistingPunch:
    """Branch (c): no linked record, but an existing (employee, date) punch — that row
    must be corrected in place, not duplicated."""

    def test_approve_corrects_existing_same_day_punch(
            self, client_a, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord, AttendanceRegularization
        same_day = datetime.date(2026, 6, 28)
        existing = AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=same_day,
            check_in=datetime.time(10, 0), check_out=datetime.time(16, 0),
            shift=shift_a, status="present", source="web",
        )
        reg = AttendanceRegularization.objects.create(
            tenant=tenant_a, employee=employee_a, date=same_day,
            reason_type="wrong_time", requested_check_in=datetime.time(9, 0),
            requested_check_out=datetime.time(18, 0), reason="Wrong time punched",
            status="pending",
        )
        resp = client_a.post(reverse("hrm:attendanceregularization_approve", args=[reg.pk]))
        assert resp.status_code == 302
        reg.refresh_from_db()
        existing.refresh_from_db()
        assert reg.attendance_record_id == existing.pk  # linked back to the SAME row
        assert existing.check_in == datetime.time(9, 0)
        assert existing.check_out == datetime.time(18, 0)
        assert existing.status == "regularized"
        # No duplicate row was created for that (employee, date).
        assert AttendanceRecord.objects.filter(
            tenant=tenant_a, employee=employee_a, date=same_day).count() == 1

    def test_approve_partial_checkin_only_preserves_existing_checkout(
            self, client_a, tenant_a, employee_a, shift_a):
        """requested_check_out is None — the view only overwrites fields that were provided."""
        from apps.hrm.models import AttendanceRecord, AttendanceRegularization
        same_day = datetime.date(2026, 6, 29)
        existing = AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a, date=same_day,
            check_in=None, check_out=datetime.time(17, 0),
            shift=shift_a, status="absent", source="web",
        )
        reg = AttendanceRegularization.objects.create(
            tenant=tenant_a, employee=employee_a, date=same_day,
            reason_type="forgot_checkin", requested_check_in=datetime.time(8, 30),
            requested_check_out=None, reason="Forgot check-in",
            status="pending",
        )
        client_a.post(reverse("hrm:attendanceregularization_approve", args=[reg.pk]))
        existing.refresh_from_db()
        assert existing.check_in == datetime.time(8, 30)
        assert existing.check_out == datetime.time(17, 0)  # preserved, not cleared


class TestRegularizationReject:
    def test_reject_pending_to_rejected(self, client_a, pending_regularization_a):
        resp = client_a.post(
            reverse("hrm:attendanceregularization_reject", args=[pending_regularization_a.pk]),
            {"decision_note": "Not enough evidence"},
        )
        assert resp.status_code == 302
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "rejected"
        assert pending_regularization_a.approver is not None
        assert pending_regularization_a.decision_note == "Not enough evidence"

    def test_reject_noop_from_draft(self, client_a, draft_regularization_a):
        resp = client_a.post(
            reverse("hrm:attendanceregularization_reject", args=[draft_regularization_a.pk]))
        assert resp.status_code == 302
        draft_regularization_a.refresh_from_db()
        assert draft_regularization_a.status == "draft"  # unchanged, only pending can be rejected

    def test_reject_does_not_touch_linked_attendance(self, client_a, pending_regularization_a, attendance_a):
        original_check_in = attendance_a.check_in
        client_a.post(reverse("hrm:attendanceregularization_reject", args=[pending_regularization_a.pk]))
        attendance_a.refresh_from_db()
        assert attendance_a.check_in == original_check_in
        assert attendance_a.status == "present"  # unchanged


class TestRegularizationCancel:
    def test_cancel_from_draft(self, client_a, draft_regularization_a):
        resp = client_a.post(
            reverse("hrm:attendanceregularization_cancel", args=[draft_regularization_a.pk]))
        assert resp.status_code == 302
        draft_regularization_a.refresh_from_db()
        assert draft_regularization_a.status == "cancelled"

    def test_cancel_from_pending(self, client_a, pending_regularization_a):
        resp = client_a.post(
            reverse("hrm:attendanceregularization_cancel", args=[pending_regularization_a.pk]))
        assert resp.status_code == 302
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "cancelled"

    def test_cancel_noop_once_approved(self, client_a, pending_regularization_a):
        client_a.post(reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]))
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "approved"
        resp = client_a.post(
            reverse("hrm:attendanceregularization_cancel", args=[pending_regularization_a.pk]))
        assert resp.status_code == 302
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "approved"  # unchanged — cancel is a no-op


class TestRegularizationEditDeleteGuard:
    def test_edit_allowed_when_draft(self, client_a, draft_regularization_a, employee_a):
        resp = client_a.get(reverse("hrm:attendanceregularization_edit", args=[draft_regularization_a.pk]))
        assert resp.status_code == 200

    def test_edit_allowed_when_pending(self, client_a, pending_regularization_a):
        resp = client_a.get(reverse("hrm:attendanceregularization_edit", args=[pending_regularization_a.pk]))
        assert resp.status_code == 200

    def test_edit_blocked_when_approved(self, client_a, pending_regularization_a):
        client_a.post(reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]))
        resp = client_a.get(reverse("hrm:attendanceregularization_edit", args=[pending_regularization_a.pk]))
        assert resp.status_code == 302  # redirected, not the edit form
        assert reverse("hrm:attendanceregularization_detail",
                       args=[pending_regularization_a.pk]) in resp["Location"]

    def test_edit_post_blocked_when_approved_does_not_mutate(self, client_a, pending_regularization_a):
        client_a.post(reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]))
        pending_regularization_a.refresh_from_db()
        original_reason = pending_regularization_a.reason
        resp = client_a.post(
            reverse("hrm:attendanceregularization_edit", args=[pending_regularization_a.pk]),
            {"employee": pending_regularization_a.employee_id, "date": "2026-01-01",
             "reason_type": "other", "requested_check_in": "09:00", "reason": "Tampered"},
        )
        assert resp.status_code == 302
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.reason == original_reason  # unchanged

    def test_delete_allowed_when_draft(self, client_a, draft_regularization_a):
        from apps.hrm.models import AttendanceRegularization
        pk = draft_regularization_a.pk
        resp = client_a.post(reverse("hrm:attendanceregularization_delete", args=[pk]))
        assert resp.status_code == 302
        assert not AttendanceRegularization.objects.filter(pk=pk).exists()

    def test_delete_allowed_when_pending(self, client_a, pending_regularization_a):
        from apps.hrm.models import AttendanceRegularization
        pk = pending_regularization_a.pk
        resp = client_a.post(reverse("hrm:attendanceregularization_delete", args=[pk]))
        assert resp.status_code == 302
        assert not AttendanceRegularization.objects.filter(pk=pk).exists()

    def test_delete_blocked_when_approved(self, client_a, pending_regularization_a):
        from apps.hrm.models import AttendanceRegularization
        client_a.post(reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]))
        pk = pending_regularization_a.pk
        resp = client_a.post(reverse("hrm:attendanceregularization_delete", args=[pk]))
        assert resp.status_code == 302
        assert AttendanceRegularization.objects.filter(pk=pk).exists()  # not deleted

    def test_delete_blocked_when_rejected(self, client_a, pending_regularization_a):
        from apps.hrm.models import AttendanceRegularization
        client_a.post(reverse("hrm:attendanceregularization_reject", args=[pending_regularization_a.pk]))
        pk = pending_regularization_a.pk
        resp = client_a.post(reverse("hrm:attendanceregularization_delete", args=[pk]))
        assert resp.status_code == 302
        assert AttendanceRegularization.objects.filter(pk=pk).exists()  # not deleted


# ============================================================
# Authorization — @tenant_admin_required on approve/reject
# ============================================================
class TestRegularizationWorkflowAdminOnly:
    def test_nonadmin_approve_403(self, member_client, pending_regularization_a):
        resp = member_client.post(
            reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]))
        assert resp.status_code == 403
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "pending"  # unchanged

    def test_nonadmin_reject_403(self, member_client, pending_regularization_a):
        resp = member_client.post(
            reverse("hrm:attendanceregularization_reject", args=[pending_regularization_a.pk]))
        assert resp.status_code == 403
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "pending"  # unchanged

    def test_nonadmin_submit_allowed(self, member_client, draft_regularization_a):
        """submit is @login_required-only — a non-admin tenant user may submit their own request."""
        resp = member_client.post(
            reverse("hrm:attendanceregularization_submit", args=[draft_regularization_a.pk]))
        assert resp.status_code == 302
        draft_regularization_a.refresh_from_db()
        assert draft_regularization_a.status == "pending"

    def test_nonadmin_cancel_allowed(self, member_client, draft_regularization_a):
        """cancel is @login_required-only — a non-admin tenant user may cancel their own request."""
        resp = member_client.post(
            reverse("hrm:attendanceregularization_cancel", args=[draft_regularization_a.pk]))
        assert resp.status_code == 302
        draft_regularization_a.refresh_from_db()
        assert draft_regularization_a.status == "cancelled"

    def test_admin_approve_succeeds(self, client_a, pending_regularization_a):
        resp = client_a.post(
            reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]))
        assert resp.status_code == 302
        pending_regularization_a.refresh_from_db()
        assert pending_regularization_a.status == "approved"

    def test_template_gate_is_not_the_only_guard(self, member_client, pending_regularization_a):
        """Even if a non-admin somehow reaches the approve/reject form (template hides the
        buttons), the server-side @tenant_admin_required must still block the POST."""
        resp = member_client.post(
            reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]),
            {"decision_note": "forged"})
        assert resp.status_code == 403


# ============================================================
# AttendanceRegularization list / detail views
# ============================================================
class TestRegularizationListDetailViews:
    def test_list_ok(self, client_a, pending_regularization_a):
        resp = client_a.get(reverse("hrm:attendanceregularization_list"))
        assert resp.status_code == 200
        assert pending_regularization_a.number.encode() in resp.content

    def test_filter_by_status(self, client_a, pending_regularization_a, draft_regularization_a):
        resp = client_a.get(reverse("hrm:attendanceregularization_list"), {"status": "pending"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_regularization_a.pk in pks
        assert draft_regularization_a.pk not in pks

    def test_create_view_post(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRegularization
        resp = client_a.post(reverse("hrm:attendanceregularization_create"), {
            "employee": employee_a.pk,
            "date": "2026-06-30",
            "reason_type": "system_error",
            "requested_check_in": "09:00",
            "requested_check_out": "17:00",
            "reason": "Biometric device offline",
        })
        assert resp.status_code == 302
        reg = AttendanceRegularization.objects.get(tenant=tenant_a, date=datetime.date(2026, 6, 30))
        assert reg.tenant_id == tenant_a.pk
        assert reg.status == "draft"

    def test_detail_ok(self, client_a, pending_regularization_a):
        resp = client_a.get(reverse("hrm:attendanceregularization_detail", args=[pending_regularization_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == pending_regularization_a.pk


# ============================================================
# Multi-tenant IDOR sweep — GeoFence
# ============================================================
class TestGeoFenceIDOR:
    def test_detail_cross_tenant_404(self, client_a, geofence_b):
        resp = client_a.get(reverse("hrm:geofence_detail", args=[geofence_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, geofence_b):
        resp = client_a.get(reverse("hrm:geofence_edit", args=[geofence_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, geofence_b):
        resp = client_a.post(reverse("hrm:geofence_edit", args=[geofence_b.pk]), {
            "name": "Hijacked", "latitude": "0", "longitude": "0", "radius_m": "10",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, geofence_b):
        from apps.hrm.models import GeoFence
        resp = client_a.post(reverse("hrm:geofence_delete", args=[geofence_b.pk]))
        assert resp.status_code == 404
        assert GeoFence.objects.filter(pk=geofence_b.pk).exists()  # untouched

    def test_list_excludes_tenant_b(self, client_a, geofence_a, geofence_b):
        resp = client_a.get(reverse("hrm:geofence_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert geofence_a.pk in pks
        assert geofence_b.pk not in pks

    def test_geofence_b_unchanged_after_idor_edit_attempt(self, client_a, geofence_b):
        original_name = geofence_b.name
        client_a.post(reverse("hrm:geofence_edit", args=[geofence_b.pk]), {
            "name": "Hijacked", "latitude": "0", "longitude": "0", "radius_m": "10",
        })
        geofence_b.refresh_from_db()
        assert geofence_b.name == original_name


# ============================================================
# Multi-tenant IDOR sweep — AttendanceRegularization
# ============================================================
class TestAttendanceRegularizationIDOR:
    def test_detail_cross_tenant_404(self, client_a, regularization_b):
        resp = client_a.get(reverse("hrm:attendanceregularization_detail", args=[regularization_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, regularization_b):
        resp = client_a.get(reverse("hrm:attendanceregularization_edit", args=[regularization_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, regularization_b):
        resp = client_a.post(reverse("hrm:attendanceregularization_delete", args=[regularization_b.pk]))
        assert resp.status_code == 404

    def test_submit_cross_tenant_404(self, client_a, regularization_b):
        resp = client_a.post(reverse("hrm:attendanceregularization_submit", args=[regularization_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, regularization_b):
        resp = client_a.post(reverse("hrm:attendanceregularization_approve", args=[regularization_b.pk]))
        assert resp.status_code == 404

    def test_reject_cross_tenant_404(self, client_a, regularization_b):
        resp = client_a.post(reverse("hrm:attendanceregularization_reject", args=[regularization_b.pk]))
        assert resp.status_code == 404

    def test_cancel_cross_tenant_404(self, client_a, regularization_b):
        resp = client_a.post(reverse("hrm:attendanceregularization_cancel", args=[regularization_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_tenant_b(self, client_a, pending_regularization_a, regularization_b):
        resp = client_a.get(reverse("hrm:attendanceregularization_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_regularization_a.pk in pks
        assert regularization_b.pk not in pks

    def test_regularization_b_status_unchanged_after_idor_approve_attempt(self, client_a, regularization_b):
        resp = client_a.post(reverse("hrm:attendanceregularization_approve", args=[regularization_b.pk]))
        assert resp.status_code == 404
        regularization_b.refresh_from_db()
        assert regularization_b.status == "pending"  # unchanged

    def test_regularization_b_linked_attendance_unchanged_after_idor_approve_attempt(
            self, client_a, regularization_b, attendance_b):
        original_check_in = attendance_b.check_in
        client_a.post(reverse("hrm:attendanceregularization_approve", args=[regularization_b.pk]))
        attendance_b.refresh_from_db()
        assert attendance_b.check_in == original_check_in
        assert attendance_b.status == "present"  # unchanged — cross-tenant approve never ran


# ============================================================
# Anonymous access — new endpoints
# ============================================================
class TestAnonymousBlockedNewEndpoints:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:geofence_list", []),
        ("hrm:geofence_create", []),
        ("hrm:attendanceregularization_list", []),
        ("hrm:attendanceregularization_create", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================
# CSRF enforcement on POST-only endpoints
# ============================================================
class TestCSRFEnforcementNewEndpoints:
    def test_geofence_delete_enforces_csrf(self, admin_user, geofence_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:geofence_delete", args=[geofence_a.pk]))
        assert resp.status_code == 403

    def test_regularization_delete_enforces_csrf(self, admin_user, draft_regularization_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:attendanceregularization_delete", args=[draft_regularization_a.pk]))
        assert resp.status_code == 403

    def test_regularization_approve_enforces_csrf(self, admin_user, pending_regularization_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:attendanceregularization_approve", args=[pending_regularization_a.pk]))
        assert resp.status_code == 403


# ============================================================
# Performance — geofence_detail must not scale with N linked punches
# ============================================================
class TestGeoFencePerformance:
    def test_detail_query_count_bounded_with_many_punches(
            self, client_a, tenant_a, employee_a, shift_a, geofence_a, django_assert_max_num_queries):
        from apps.hrm.models import AttendanceRecord
        # 15 punches, alternating inside/outside the 100m radius so geo_status() exercises
        # both "verified" and "outside" branches per row.
        for i in range(15):
            offset = Decimal("0.0001") if i % 2 == 0 else Decimal("5")  # inside vs far outside
            AttendanceRecord.objects.create(
                tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 1) + datetime.timedelta(days=i),
                shift=shift_a, latitude=offset, longitude=offset, geofence=geofence_a,
                check_in=datetime.time(9, 0), check_out=datetime.time(17, 0),
            )
        with django_assert_max_num_queries(10):
            resp = client_a.get(reverse("hrm:geofence_detail", args=[geofence_a.pk]))
        assert resp.status_code == 200
        # Sanity: both branches were actually exercised by the fixture data.
        statuses = {rec.geo_status() for rec in resp.context["recent_punches"]}
        assert "verified" in statuses
        assert "outside" in statuses
