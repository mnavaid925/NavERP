"""Tests for HRM 3.1 Employee Management (completion) — EmployeeDocument +
EmployeeLifecycleEvent + EmployeeProfile masking helpers + associated views/forms/security.

Fixture dependencies (from root conftest + hrm conftest):
  tenant_a, tenant_b, admin_user, admin_b, member_user,
  client_a (admin_user logged-in), client_b, member_client,
  employee_a, employee_b, person_a, designation_a.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.core.exceptions import PermissionDenied

pytestmark = pytest.mark.django_db


# ============================================================
# Local fixtures (employee record objects; reuse conftest ones)
# ============================================================

@pytest.fixture
def doc_a(db, tenant_a, employee_a):
    """A pending, non-confidential EmployeeDocument for tenant_a."""
    from apps.hrm.models import EmployeeDocument
    return EmployeeDocument.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        document_type="passport",
        title="Alice Passport",
        document_number="P1234567",
        issuing_authority="Passport Office",
        is_confidential=False,
    )


@pytest.fixture
def doc_confidential_a(db, tenant_a, employee_a):
    """A confidential EmployeeDocument for tenant_a."""
    from apps.hrm.models import EmployeeDocument
    return EmployeeDocument.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        document_type="national_id",
        title="Alice NID",
        document_number="NID-001",
        is_confidential=True,
    )


@pytest.fixture
def doc_b(db, tenant_b, employee_b):
    """An EmployeeDocument for tenant_b (IDOR tests)."""
    from apps.hrm.models import EmployeeDocument
    return EmployeeDocument.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        document_type="passport",
        title="Bob Passport",
        is_confidential=False,
    )


@pytest.fixture
def verified_doc_a(db, tenant_a, employee_a, admin_user):
    """A verified EmployeeDocument for tenant_a."""
    from apps.hrm.models import EmployeeDocument
    from django.utils import timezone
    doc = EmployeeDocument.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        document_type="degree_certificate",
        title="Alice Degree",
        is_confidential=False,
    )
    doc.verification_status = "verified"
    doc.verified_by = admin_user
    doc.verified_at = timezone.now()
    doc.save(update_fields=["verification_status", "verified_by", "verified_at", "updated_at"])
    return doc


@pytest.fixture
def lifecycle_a(db, tenant_a, employee_a, admin_user):
    """A promotion EmployeeLifecycleEvent for employee_a, tenant_a."""
    from apps.hrm.models import EmployeeLifecycleEvent
    event = EmployeeLifecycleEvent.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        event_type="promotion",
        effective_date=datetime.date(2025, 6, 1),
        reason="Performance",
        initiated_by=admin_user,
    )
    return event


@pytest.fixture
def lifecycle_b(db, tenant_b, employee_b):
    """An EmployeeLifecycleEvent for tenant_b (IDOR tests)."""
    from apps.hrm.models import EmployeeLifecycleEvent
    return EmployeeLifecycleEvent.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        event_type="hire",
        effective_date=datetime.date(2025, 1, 1),
    )


# ============================================================
# Model Tests: EmployeeDocument
# ============================================================

class TestEmployeeDocumentModel:
    """Auto-number, __str__, is_expired, is_expiring_soon."""

    def test_number_prefix(self, doc_a):
        assert doc_a.number.startswith("EDOC-")

    def test_number_format_first(self, doc_a):
        assert doc_a.number == "EDOC-00001"

    def test_str_contains_number_and_title(self, doc_a):
        s = str(doc_a)
        assert "EDOC-00001" in s
        assert "Alice Passport" in s

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.models import EmployeeDocument
        dA = EmployeeDocument.objects.create(
            tenant=tenant_a, employee=employee_a, document_type="passport", title="Doc A")
        dB = EmployeeDocument.objects.create(
            tenant=tenant_b, employee=employee_b, document_type="passport", title="Doc B")
        assert dA.number == "EDOC-00001"
        assert dB.number == "EDOC-00001"

    def test_status_default_pending(self, doc_a):
        assert doc_a.verification_status == "pending"

    def test_verification_status_choices(self):
        from apps.hrm.models import EmployeeDocument
        keys = [k for k, _ in EmployeeDocument.VERIFICATION_STATUS_CHOICES]
        assert set(keys) == {"pending", "verified", "rejected"}

    # --- is_expired ---
    def test_is_expired_no_expiry(self, doc_a):
        doc_a.expires_on = None
        assert doc_a.is_expired is False

    def test_is_expired_future_date(self, doc_a):
        doc_a.expires_on = datetime.date.today() + datetime.timedelta(days=100)
        assert doc_a.is_expired is False

    def test_is_expired_today(self, doc_a):
        """Expiry on today is NOT expired (boundary: expires_on < today)."""
        doc_a.expires_on = datetime.date.today()
        assert doc_a.is_expired is False

    def test_is_expired_yesterday(self, doc_a):
        doc_a.expires_on = datetime.date.today() - datetime.timedelta(days=1)
        assert doc_a.is_expired is True

    def test_is_expired_past_date(self, doc_a):
        doc_a.expires_on = datetime.date(2020, 1, 1)
        assert doc_a.is_expired is True

    # --- is_expiring_soon ---
    def test_is_expiring_soon_no_expiry(self, doc_a):
        doc_a.expires_on = None
        assert doc_a.is_expiring_soon is False

    def test_is_expiring_soon_past_already_expired(self, doc_a):
        """Already-expired docs return False (days < 0)."""
        doc_a.expires_on = datetime.date.today() - datetime.timedelta(days=1)
        assert doc_a.is_expiring_soon is False

    def test_is_expiring_soon_today_boundary(self, doc_a):
        """Expiry today (days == 0) → True."""
        doc_a.expires_on = datetime.date.today()
        assert doc_a.is_expiring_soon is True

    def test_is_expiring_soon_day_20(self, doc_a):
        """20 days out → True."""
        doc_a.expires_on = datetime.date.today() + datetime.timedelta(days=20)
        assert doc_a.is_expiring_soon is True

    def test_is_expiring_soon_day_30(self, doc_a):
        """Exactly 30 days out → True (boundary: 0 <= days <= 30)."""
        doc_a.expires_on = datetime.date.today() + datetime.timedelta(days=30)
        assert doc_a.is_expiring_soon is True

    def test_is_expiring_soon_day_31(self, doc_a):
        """31 days out → False (just outside the 30-day window)."""
        doc_a.expires_on = datetime.date.today() + datetime.timedelta(days=31)
        assert doc_a.is_expiring_soon is False

    def test_is_expiring_soon_far_future(self, doc_a):
        doc_a.expires_on = datetime.date.today() + datetime.timedelta(days=365)
        assert doc_a.is_expiring_soon is False


# ============================================================
# Model Tests: EmployeeLifecycleEvent
# ============================================================

class TestEmployeeLifecycleEventModel:
    """Auto-number, __str__, ordering."""

    def test_number_prefix(self, lifecycle_a):
        assert lifecycle_a.number.startswith("ELC-")

    def test_number_format_first(self, lifecycle_a):
        assert lifecycle_a.number == "ELC-00001"

    def test_str_contains_number_name_event(self, lifecycle_a):
        s = str(lifecycle_a)
        assert "ELC-00001" in s
        assert "Alice Smith" in s
        assert "Promotion" in s

    def test_str_contains_effective_date(self, lifecycle_a):
        s = str(lifecycle_a)
        assert "2025-06-01" in s

    def test_ordering_by_effective_date_descending(self, tenant_a, employee_a, admin_user):
        """Events must be returned most-recent-first (-effective_date, -created_at)."""
        from apps.hrm.models import EmployeeLifecycleEvent
        e1 = EmployeeLifecycleEvent.objects.create(
            tenant=tenant_a, employee=employee_a, event_type="hire",
            effective_date=datetime.date(2023, 1, 1))
        e2 = EmployeeLifecycleEvent.objects.create(
            tenant=tenant_a, employee=employee_a, event_type="promotion",
            effective_date=datetime.date(2025, 3, 1))
        events = list(EmployeeLifecycleEvent.objects.filter(tenant=tenant_a, employee=employee_a))
        assert events[0].pk == e2.pk  # more recent first

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.models import EmployeeLifecycleEvent
        eA = EmployeeLifecycleEvent.objects.create(
            tenant=tenant_a, employee=employee_a, event_type="hire",
            effective_date=datetime.date(2024, 1, 1))
        eB = EmployeeLifecycleEvent.objects.create(
            tenant=tenant_b, employee=employee_b, event_type="hire",
            effective_date=datetime.date(2024, 1, 1))
        assert eA.number == "ELC-00001"
        assert eB.number == "ELC-00001"

    def test_event_type_choices_include_key_events(self):
        from apps.hrm.models import LIFECYCLE_EVENT_TYPE_CHOICES
        keys = [k for k, _ in LIFECYCLE_EVENT_TYPE_CHOICES]
        for expected in ("hire", "promotion", "demotion", "salary_revision", "transfer",
                         "separation", "confirmation"):
            assert expected in keys


# ============================================================
# Model Tests: EmployeeProfile — masking helpers
# ============================================================

class TestEmployeeProfileMasking:
    """_mask_last4 drives masked_national_id / masked_passport_number / masked_bank_routing."""

    def test_masked_national_id_last4(self, employee_a):
        """employee_a has no national_id by default — we set it here."""
        employee_a.national_id = "123456789"
        assert employee_a.masked_national_id() == "••••6789"

    def test_masked_national_id_short_value(self, employee_a):
        """Value shorter than 4 chars → ••••."""
        employee_a.national_id = "AB"
        assert employee_a.masked_national_id() == "••••"

    def test_masked_national_id_exactly_4(self, employee_a):
        employee_a.national_id = "1234"
        assert employee_a.masked_national_id() == "••••1234"

    def test_masked_national_id_empty(self, employee_a):
        employee_a.national_id = ""
        assert employee_a.masked_national_id() == ""

    def test_masked_national_id_none(self, employee_a):
        employee_a.national_id = None
        assert employee_a.masked_national_id() == ""

    def test_masked_passport_number(self, employee_a):
        employee_a.passport_number = "P9876543"
        assert employee_a.masked_passport_number() == "••••6543"

    def test_masked_passport_number_empty(self, employee_a):
        employee_a.passport_number = ""
        assert employee_a.masked_passport_number() == ""

    def test_masked_bank_routing(self, employee_a):
        """employee_a.bank_routing = 'DEMO0001' from conftest."""
        assert employee_a.masked_bank_routing() == "••••0001"

    def test_masked_bank_routing_short(self, employee_a):
        employee_a.bank_routing = "AB"
        assert employee_a.masked_bank_routing() == "••••"

    def test_masked_bank_account(self, employee_a):
        """employee_a.bank_account = '123456789012' from conftest."""
        assert employee_a.masked_bank_account() == "••••9012"


# ============================================================
# Form Tests — EmployeeDocumentForm security (field exclusion)
# ============================================================

class TestEmployeeDocumentForm:
    """Verify PII/workflow fields are excluded and cannot be spoofed via POST."""

    def test_verification_status_not_a_form_field(self, tenant_a):
        from apps.hrm.forms import EmployeeDocumentForm
        form = EmployeeDocumentForm(tenant=tenant_a)
        assert "verification_status" not in form.fields

    def test_verified_by_not_a_form_field(self, tenant_a):
        from apps.hrm.forms import EmployeeDocumentForm
        form = EmployeeDocumentForm(tenant=tenant_a)
        assert "verified_by" not in form.fields

    def test_verified_at_not_a_form_field(self, tenant_a):
        from apps.hrm.forms import EmployeeDocumentForm
        form = EmployeeDocumentForm(tenant=tenant_a)
        assert "verified_at" not in form.fields

    def test_crafted_post_cannot_self_verify(self, client_a, tenant_a, employee_a):
        """A POST that includes verification_status=verified must NOT verify the document."""
        from apps.hrm.models import EmployeeDocument
        resp = client_a.post(reverse("hrm:employee_document_create"), {
            "employee": employee_a.pk,
            "document_type": "passport",
            "title": "Self Verify Attempt",
            "document_number": "FAKE001",
            "issuing_authority": "",
            "issuing_country": "",
            "is_confidential": "",
            "notes": "",
            "verification_status": "verified",   # crafted
        })
        # On success the view redirects to employee_detail
        assert resp.status_code == 302
        doc = EmployeeDocument.objects.filter(tenant=tenant_a, title="Self Verify Attempt").first()
        assert doc is not None
        assert doc.verification_status == "pending"  # must stay pending

    def test_employee_queryset_scoped_to_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        """The employee FK dropdown must only contain tenant_a employees."""
        from apps.hrm.forms import EmployeeDocumentForm
        form = EmployeeDocumentForm(tenant=tenant_a)
        qs = form.fields["employee"].queryset
        pks = list(qs.values_list("pk", flat=True))
        assert employee_a.pk in pks
        assert employee_b.pk not in pks


# ============================================================
# Form Tests — EmployeeLifecycleEventForm security
# ============================================================

class TestEmployeeLifecycleEventForm:
    """initiated_by must not be a form field."""

    def test_initiated_by_not_a_form_field(self, tenant_a):
        from apps.hrm.forms import EmployeeLifecycleEventForm
        form = EmployeeLifecycleEventForm(tenant=tenant_a)
        assert "initiated_by" not in form.fields

    def test_employee_queryset_scoped_to_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.forms import EmployeeLifecycleEventForm
        form = EmployeeLifecycleEventForm(tenant=tenant_a)
        qs = form.fields["employee"].queryset
        pks = list(qs.values_list("pk", flat=True))
        assert employee_a.pk in pks
        assert employee_b.pk not in pks

    def test_from_manager_queryset_scoped_to_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.forms import EmployeeLifecycleEventForm
        form = EmployeeLifecycleEventForm(tenant=tenant_a)
        pks = list(form.fields["from_manager"].queryset.values_list("pk", flat=True))
        assert employee_b.pk not in pks


# ============================================================
# Views / CRUD — EmployeeDocument
# ============================================================

class TestEmployeeDocumentViews:
    """Full CRUD 200/302 for tenant admin."""

    def test_list_200(self, client_a, doc_a):
        resp = client_a.get(reverse("hrm:employee_document_list"))
        assert resp.status_code == 200

    def test_list_contains_own(self, client_a, doc_a):
        resp = client_a.get(reverse("hrm:employee_document_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert doc_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, doc_a, doc_b):
        resp = client_a.get(reverse("hrm:employee_document_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert doc_b.pk not in pks

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:employee_document_create"))
        assert resp.status_code == 200

    def test_create_post_saves_with_correct_tenant(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import EmployeeDocument
        resp = client_a.post(reverse("hrm:employee_document_create"), {
            "employee": employee_a.pk,
            "document_type": "degree_certificate",
            "title": "Degree",
            "document_number": "DEG001",
            "issuing_authority": "MIT",
            "issuing_country": "USA",
            "is_confidential": "",
            "notes": "",
        })
        assert resp.status_code == 302
        assert EmployeeDocument.objects.filter(tenant=tenant_a, title="Degree").exists()

    def test_create_post_redirects_to_employee_detail(self, client_a, employee_a):
        """After create, the view redirects to the employee's detail hub."""
        resp = client_a.post(reverse("hrm:employee_document_create"), {
            "employee": employee_a.pk,
            "document_type": "passport",
            "title": "Redirect Test",
            "document_number": "RD001",
            "issuing_authority": "",
            "issuing_country": "",
            "is_confidential": "",
            "notes": "",
        })
        assert resp.status_code == 302
        assert str(employee_a.pk) in resp["Location"]

    def test_detail_200(self, client_a, doc_a):
        resp = client_a.get(reverse("hrm:employee_document_detail", args=[doc_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200_on_pending(self, client_a, doc_a):
        resp = client_a.get(reverse("hrm:employee_document_edit", args=[doc_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_saves(self, client_a, doc_a, employee_a):
        from apps.hrm.models import EmployeeDocument
        resp = client_a.post(reverse("hrm:employee_document_edit", args=[doc_a.pk]), {
            "employee": employee_a.pk,
            "document_type": "driving_license",
            "title": "Updated Title",
            "document_number": "DL-999",
            "issuing_authority": "",
            "issuing_country": "",
            "is_confidential": "",
            "notes": "",
        })
        assert resp.status_code == 302
        doc_a.refresh_from_db()
        assert doc_a.title == "Updated Title"

    def test_delete_removes_pending_doc(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import EmployeeDocument
        doc = EmployeeDocument.objects.create(
            tenant=tenant_a, employee=employee_a, document_type="other", title="Delete Me")
        pk = doc.pk
        resp = client_a.post(reverse("hrm:employee_document_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmployeeDocument.objects.filter(pk=pk).exists()

    def test_anon_list_redirects_to_login(self, client):
        resp = client.get(reverse("hrm:employee_document_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anon_create_redirects_to_login(self, client):
        resp = client.get(reverse("hrm:employee_document_create"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================
# Views / CRUD — EmployeeLifecycleEvent
# ============================================================

class TestEmployeeLifecycleViews:
    """Full CRUD 200/302 for tenant admin; list/detail accessible to member."""

    def test_list_200(self, client_a, lifecycle_a):
        resp = client_a.get(reverse("hrm:employee_lifecycle_list"))
        assert resp.status_code == 200

    def test_list_contains_own(self, client_a, lifecycle_a):
        resp = client_a.get(reverse("hrm:employee_lifecycle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lifecycle_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, lifecycle_a, lifecycle_b):
        resp = client_a.get(reverse("hrm:employee_lifecycle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lifecycle_b.pk not in pks

    def test_create_get_200_for_admin(self, client_a):
        resp = client_a.get(reverse("hrm:employee_lifecycle_create"))
        assert resp.status_code == 200

    def test_create_post_saves_and_stamps_initiated_by(self, client_a, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeLifecycleEvent
        resp = client_a.post(reverse("hrm:employee_lifecycle_create"), {
            "employee": employee_a.pk,
            "event_type": "transfer",
            "effective_date": "2025-09-01",
            "reason": "Org reorg",
            "from_location": "",
            "to_location": "",
            "from_job_title": "",
            "to_job_title": "",
            "from_employee_type": "",
            "to_employee_type": "",
            "notes": "",
        })
        assert resp.status_code == 302
        event = EmployeeLifecycleEvent.objects.filter(tenant=tenant_a, event_type="transfer").first()
        assert event is not None
        assert event.initiated_by_id == admin_user.pk

    def test_detail_200(self, client_a, lifecycle_a):
        resp = client_a.get(reverse("hrm:employee_lifecycle_detail", args=[lifecycle_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200_for_admin(self, client_a, lifecycle_a):
        resp = client_a.get(reverse("hrm:employee_lifecycle_edit", args=[lifecycle_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_saves(self, client_a, lifecycle_a, employee_a):
        from apps.hrm.models import EmployeeLifecycleEvent
        resp = client_a.post(reverse("hrm:employee_lifecycle_edit", args=[lifecycle_a.pk]), {
            "employee": employee_a.pk,
            "event_type": "salary_revision",
            "effective_date": "2025-07-01",
            "reason": "Updated reason",
            "from_location": "",
            "to_location": "",
            "from_job_title": "",
            "to_job_title": "",
            "from_employee_type": "",
            "to_employee_type": "",
            "notes": "",
        })
        assert resp.status_code == 302
        lifecycle_a.refresh_from_db()
        assert lifecycle_a.event_type == "salary_revision"

    def test_delete_removes_row(self, client_a, tenant_a, employee_a, admin_user):
        from apps.hrm.models import EmployeeLifecycleEvent
        event = EmployeeLifecycleEvent.objects.create(
            tenant=tenant_a, employee=employee_a, event_type="other",
            effective_date=datetime.date(2025, 12, 1))
        pk = event.pk
        resp = client_a.post(reverse("hrm:employee_lifecycle_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmployeeLifecycleEvent.objects.filter(pk=pk).exists()

    def test_anon_list_redirects(self, client):
        resp = client.get(reverse("hrm:employee_lifecycle_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ============================================================
# Workflow — mark_verified / reject
# ============================================================

class TestEmployeeDocumentWorkflow:
    """mark_verified: pending→verified; reject: pending/verified→rejected (idempotent guard)."""

    def test_mark_verified_pending_doc(self, client_a, doc_a, admin_user):
        resp = client_a.post(reverse("hrm:employee_document_mark_verified", args=[doc_a.pk]))
        assert resp.status_code == 302
        doc_a.refresh_from_db()
        assert doc_a.verification_status == "verified"

    def test_mark_verified_stamps_verified_by(self, client_a, doc_a, admin_user):
        client_a.post(reverse("hrm:employee_document_mark_verified", args=[doc_a.pk]))
        doc_a.refresh_from_db()
        assert doc_a.verified_by_id == admin_user.pk
        assert doc_a.verified_at is not None

    def test_mark_verified_already_verified_noop(self, client_a, verified_doc_a):
        """A non-pending document must not change status (guard: only pending can be verified)."""
        client_a.post(reverse("hrm:employee_document_mark_verified", args=[verified_doc_a.pk]))
        verified_doc_a.refresh_from_db()
        assert verified_doc_a.verification_status == "verified"

    def test_reject_pending_doc(self, client_a, doc_a):
        resp = client_a.post(reverse("hrm:employee_document_reject", args=[doc_a.pk]))
        assert resp.status_code == 302
        doc_a.refresh_from_db()
        assert doc_a.verification_status == "rejected"

    def test_reject_clears_verified_by(self, client_a, verified_doc_a):
        client_a.post(reverse("hrm:employee_document_reject", args=[verified_doc_a.pk]))
        verified_doc_a.refresh_from_db()
        assert verified_doc_a.verified_by_id is None
        assert verified_doc_a.verified_at is None

    def test_reject_verified_doc_changes_to_rejected(self, client_a, verified_doc_a):
        client_a.post(reverse("hrm:employee_document_reject", args=[verified_doc_a.pk]))
        verified_doc_a.refresh_from_db()
        assert verified_doc_a.verification_status == "rejected"

    def test_reject_already_rejected_is_noop(self, client_a, tenant_a, employee_a):
        """Rejecting an already-rejected doc must not error — the guard message fires."""
        from apps.hrm.models import EmployeeDocument
        doc = EmployeeDocument.objects.create(
            tenant=tenant_a, employee=employee_a, document_type="other", title="Rejected Doc")
        doc.verification_status = "rejected"
        doc.save(update_fields=["verification_status", "updated_at"])
        resp = client_a.post(reverse("hrm:employee_document_reject", args=[doc.pk]))
        assert resp.status_code == 302
        doc.refresh_from_db()
        assert doc.verification_status == "rejected"


# ============================================================
# Workflow — verified document blocks edit/delete
# ============================================================

class TestVerifiedDocumentGuard:
    """A verified document cannot be edited or deleted."""

    def test_edit_verified_doc_redirects(self, client_a, verified_doc_a):
        resp = client_a.get(reverse("hrm:employee_document_edit", args=[verified_doc_a.pk]))
        assert resp.status_code == 302

    def test_edit_verified_doc_does_not_save(self, client_a, verified_doc_a, employee_a):
        client_a.post(reverse("hrm:employee_document_edit", args=[verified_doc_a.pk]), {
            "employee": employee_a.pk,
            "document_type": "other",
            "title": "Should Not Change",
            "document_number": "",
            "issuing_authority": "",
            "issuing_country": "",
            "is_confidential": "",
            "notes": "",
        })
        verified_doc_a.refresh_from_db()
        assert verified_doc_a.title != "Should Not Change"

    def test_delete_verified_doc_blocked(self, client_a, verified_doc_a):
        from apps.hrm.models import EmployeeDocument
        resp = client_a.post(reverse("hrm:employee_document_delete", args=[verified_doc_a.pk]))
        assert resp.status_code == 302
        assert EmployeeDocument.objects.filter(pk=verified_doc_a.pk).exists()


# ============================================================
# employee_detail hub — documents + lifecycle_events context
# ============================================================

class TestEmployeeDetailHub:
    """employee_detail renders 200 with documents and lifecycle_events context keys."""

    def test_detail_200(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_documents_context(self, client_a, employee_a, doc_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert "documents" in resp.context

    def test_detail_documents_includes_employee_doc(self, client_a, employee_a, doc_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        pks = [d.pk for d in resp.context["documents"]]
        assert doc_a.pk in pks

    def test_detail_has_lifecycle_events_context(self, client_a, employee_a, lifecycle_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert "lifecycle_events" in resp.context

    def test_detail_lifecycle_events_includes_event(self, client_a, employee_a, lifecycle_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        pks = [e.pk for e in resp.context["lifecycle_events"]]
        assert lifecycle_a.pk in pks

    def test_employee_prefill_valid_digit(self, client_a, employee_a):
        """?employee=<valid pk> → create form with the employee pre-filled (no 500)."""
        url = reverse("hrm:employee_document_create") + f"?employee={employee_a.pk}"
        resp = client_a.get(url)
        assert resp.status_code == 200

    def test_employee_prefill_invalid_string_no_500(self, client_a):
        """?employee=abc → should NOT 500 (cancel_employee is None, no reversal crash)."""
        url = reverse("hrm:employee_document_create") + "?employee=abc"
        resp = client_a.get(url)
        assert resp.status_code == 200

    def test_employee_prefill_negative_no_500(self, client_a):
        """?employee=-1 → should not 500."""
        url = reverse("hrm:employee_document_create") + "?employee=-1"
        resp = client_a.get(url)
        assert resp.status_code == 200


# ============================================================
# Security — is_confidential enforcement
# ============================================================

class TestConfidentialDocumentSecurity:
    """Confidential docs: 403 for member on detail; excluded from member list; admin sees them."""

    def test_member_cannot_view_confidential_detail(self, member_client, doc_confidential_a):
        resp = member_client.get(
            reverse("hrm:employee_document_detail", args=[doc_confidential_a.pk]))
        assert resp.status_code == 403

    def test_admin_can_view_confidential_detail(self, client_a, doc_confidential_a):
        resp = client_a.get(
            reverse("hrm:employee_document_detail", args=[doc_confidential_a.pk]))
        assert resp.status_code == 200

    def test_member_list_excludes_confidential(self, member_client, doc_a, doc_confidential_a):
        resp = member_client.get(reverse("hrm:employee_document_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert doc_confidential_a.pk not in pks

    def test_member_list_includes_non_confidential(self, member_client, doc_a):
        resp = member_client.get(reverse("hrm:employee_document_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert doc_a.pk in pks

    def test_admin_list_includes_confidential(self, client_a, doc_a, doc_confidential_a):
        resp = client_a.get(reverse("hrm:employee_document_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert doc_confidential_a.pk in pks

    def test_member_cannot_edit_confidential_doc(self, member_client, doc_confidential_a):
        resp = member_client.get(
            reverse("hrm:employee_document_edit", args=[doc_confidential_a.pk]))
        assert resp.status_code == 403

    def test_member_cannot_delete_confidential_doc(self, member_client, doc_confidential_a):
        resp = member_client.post(
            reverse("hrm:employee_document_delete", args=[doc_confidential_a.pk]))
        assert resp.status_code == 403


# ============================================================
# Security — @tenant_admin_required on workflow actions
# ============================================================

class TestWorkflowAdminRequired:
    """mark_verified and reject must return 403 for a non-admin member."""

    def test_mark_verified_blocked_for_member(self, member_client, doc_a):
        resp = member_client.post(
            reverse("hrm:employee_document_mark_verified", args=[doc_a.pk]))
        assert resp.status_code == 403

    def test_reject_blocked_for_member(self, member_client, doc_a):
        resp = member_client.post(
            reverse("hrm:employee_document_reject", args=[doc_a.pk]))
        assert resp.status_code == 403


class TestLifecycleAdminRequired:
    """Lifecycle create/edit/delete must return 403 for a member; list/detail remain 200."""

    def test_lifecycle_create_blocked_for_member(self, member_client):
        resp = member_client.get(reverse("hrm:employee_lifecycle_create"))
        assert resp.status_code == 403

    def test_lifecycle_edit_blocked_for_member(self, member_client, lifecycle_a):
        resp = member_client.get(
            reverse("hrm:employee_lifecycle_edit", args=[lifecycle_a.pk]))
        assert resp.status_code == 403

    def test_lifecycle_delete_blocked_for_member(self, member_client, lifecycle_a):
        resp = member_client.post(
            reverse("hrm:employee_lifecycle_delete", args=[lifecycle_a.pk]))
        assert resp.status_code == 403

    def test_lifecycle_list_200_for_member(self, member_client, lifecycle_a):
        resp = member_client.get(reverse("hrm:employee_lifecycle_list"))
        assert resp.status_code == 200

    def test_lifecycle_detail_200_for_member(self, member_client, lifecycle_a):
        resp = member_client.get(
            reverse("hrm:employee_lifecycle_detail", args=[lifecycle_a.pk]))
        assert resp.status_code == 200


# ============================================================
# Multi-tenant isolation (IDOR)
# ============================================================

class TestMultiTenantIsolation:
    """Tenant-A admin requesting tenant-B objects → 404."""

    def test_doc_detail_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.get(reverse("hrm:employee_document_detail", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_doc_edit_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.get(reverse("hrm:employee_document_edit", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_doc_delete_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.post(reverse("hrm:employee_document_delete", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_doc_mark_verified_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.post(reverse("hrm:employee_document_mark_verified", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_doc_reject_cross_tenant_404(self, client_a, doc_b):
        resp = client_a.post(reverse("hrm:employee_document_reject", args=[doc_b.pk]))
        assert resp.status_code == 404

    def test_lifecycle_detail_cross_tenant_404(self, client_a, lifecycle_b):
        resp = client_a.get(reverse("hrm:employee_lifecycle_detail", args=[lifecycle_b.pk]))
        assert resp.status_code == 404

    def test_lifecycle_edit_cross_tenant_404(self, client_a, lifecycle_b):
        resp = client_a.get(reverse("hrm:employee_lifecycle_edit", args=[lifecycle_b.pk]))
        assert resp.status_code == 404

    def test_lifecycle_delete_cross_tenant_404(self, client_a, lifecycle_b):
        resp = client_a.post(reverse("hrm:employee_lifecycle_delete", args=[lifecycle_b.pk]))
        assert resp.status_code == 404

    def test_doc_list_never_contains_other_tenant(self, client_a, doc_a, doc_b):
        resp = client_a.get(reverse("hrm:employee_document_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert doc_b.pk not in pks

    def test_lifecycle_list_never_contains_other_tenant(self, client_a, lifecycle_a, lifecycle_b):
        resp = client_a.get(reverse("hrm:employee_lifecycle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert lifecycle_b.pk not in pks


# ============================================================
# Seeder — _seed_employee_records idempotency
# ============================================================

class TestSeedEmployeeRecordsIdempotency:
    """Running _seed_employee_records twice must not create duplicate EmployeeDocument rows."""

    def _run_seeder(self, flush=False):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("seed_hrm", flush=flush, stdout=out, stderr=out)
        return out.getvalue()

    def test_seeder_creates_employee_documents(self, tenant_a):
        from apps.hrm.models import EmployeeDocument
        self._run_seeder()
        assert EmployeeDocument.objects.filter(tenant=tenant_a).exists()

    def test_seeder_creates_lifecycle_events(self, tenant_a):
        from apps.hrm.models import EmployeeLifecycleEvent
        self._run_seeder()
        assert EmployeeLifecycleEvent.objects.filter(tenant=tenant_a).exists()

    def test_seeder_employee_docs_idempotent(self, tenant_a):
        """Second run must NOT create duplicate EmployeeDocument rows."""
        from apps.hrm.models import EmployeeDocument
        self._run_seeder()
        count1 = EmployeeDocument.objects.filter(tenant=tenant_a).count()
        self._run_seeder()
        count2 = EmployeeDocument.objects.filter(tenant=tenant_a).count()
        assert count1 == count2

    def test_seeder_second_run_outputs_skip_notice(self, tenant_a):
        """Second invocation must print a 'already exists' or 'use --flush' notice."""
        self._run_seeder()
        output = self._run_seeder()
        assert "already exists" in output.lower() or "use --flush" in output.lower()

    def test_seeder_seeds_verified_national_id_docs(self, tenant_a):
        """The national_id documents seeded are marked confidential + verified."""
        from apps.hrm.models import EmployeeDocument
        self._run_seeder()
        nid_docs = EmployeeDocument.objects.filter(
            tenant=tenant_a, document_type="national_id")
        assert nid_docs.exists()
        assert all(d.is_confidential for d in nid_docs)
        assert all(d.verification_status == "verified" for d in nid_docs)

    def test_seeder_seeds_passport_docs_pending(self, tenant_a):
        """Passport docs seeded as pending (default status)."""
        from apps.hrm.models import EmployeeDocument
        self._run_seeder()
        passport_docs = EmployeeDocument.objects.filter(
            tenant=tenant_a, document_type="passport")
        assert passport_docs.exists()
        assert all(d.verification_status == "pending" for d in passport_docs)

    def test_seeder_flush_reseeds_docs(self, tenant_a):
        """--flush wipes and re-seeds; count stays the same."""
        from apps.hrm.models import EmployeeDocument
        self._run_seeder()
        count1 = EmployeeDocument.objects.filter(tenant=tenant_a).count()
        self._run_seeder(flush=True)
        count2 = EmployeeDocument.objects.filter(tenant=tenant_a).count()
        assert count2 == count1


# ============================================================
# Query budget — no N+1 on list views
# ============================================================

class TestQueryBudgets:
    """List views must stay within a reasonable query bound."""

    def test_doc_list_query_budget(
        self, client_a, tenant_a, employee_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import EmployeeDocument
        # Create a handful of documents to catch N+1 patterns.
        for i in range(5):
            EmployeeDocument.objects.create(
                tenant=tenant_a, employee=employee_a, document_type="other",
                title=f"Doc {i}", document_number=f"D{i}")
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:employee_document_list"))

    def test_lifecycle_list_query_budget(
        self, client_a, tenant_a, employee_a, django_assert_max_num_queries
    ):
        from apps.hrm.models import EmployeeLifecycleEvent
        for i in range(5):
            EmployeeLifecycleEvent.objects.create(
                tenant=tenant_a, employee=employee_a, event_type="other",
                effective_date=datetime.date(2025, 1, i + 1))
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:employee_lifecycle_list"))
