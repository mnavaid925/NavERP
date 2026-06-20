"""Tests for core app models: __str__, defaults, scoping, utils."""
import pytest
from django.utils import timezone

from apps.core.models import (
    Activity,
    Address,
    AuditLog,
    ContactMethod,
    Document,
    Employment,
    OrgUnit,
    Party,
    PartyRelationship,
    PartyRole,
    Tenant,
)
from apps.core.utils import next_number, write_audit_log


pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ Tenant
class TestTenant:
    def test_str(self, tenant_a):
        assert str(tenant_a) == "Acme Corp"

    def test_defaults(self, tenant_a):
        assert tenant_a.plan == "free"
        assert tenant_a.is_active is True

    def test_slug_unique(self, tenant_a):
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Tenant.objects.create(name="Duplicate", slug="acme")

    def test_plan_choices(self):
        plans = [c[0] for c in Tenant.PLAN_CHOICES]
        assert "free" in plans
        assert "starter" in plans
        assert "pro" in plans
        assert "enterprise" in plans


# ------------------------------------------------------------------ OrgUnit
class TestOrgUnit:
    def test_str(self, tenant_a):
        ou = OrgUnit.objects.create(tenant=tenant_a, name="Engineering", kind="department")
        assert str(ou) == "Engineering"

    def test_default_kind(self, tenant_a):
        ou = OrgUnit.objects.create(tenant=tenant_a, name="Sales")
        assert ou.kind == "department"

    def test_parent_self_fk(self, tenant_a):
        parent = OrgUnit.objects.create(tenant=tenant_a, name="HQ", kind="company")
        child = OrgUnit.objects.create(tenant=tenant_a, name="Branch", kind="branch", parent=parent)
        assert child.parent == parent

    def test_tenant_scoped(self, tenant_a, tenant_b):
        OrgUnit.objects.create(tenant=tenant_a, name="Acme Dept")
        OrgUnit.objects.create(tenant=tenant_b, name="Globex Dept")
        assert OrgUnit.objects.filter(tenant=tenant_a).count() == 1
        assert OrgUnit.objects.filter(tenant=tenant_b).count() == 1


# ------------------------------------------------------------------ Party
class TestParty:
    def test_str(self, party_a):
        assert str(party_a) == "Acme Party"

    def test_default_kind(self, tenant_a):
        p = Party.objects.create(tenant=tenant_a, name="John Doe")
        assert p.kind == "person"

    def test_kind_choices(self):
        kinds = [c[0] for c in Party.KIND_CHOICES]
        assert "person" in kinds
        assert "organization" in kinds

    def test_tenant_isolation(self, party_a, party_b):
        assert Party.objects.filter(tenant=party_a.tenant).count() == 1
        assert Party.objects.filter(tenant=party_b.tenant).count() == 1


# ------------------------------------------------------------------ PartyRole
class TestPartyRole:
    def test_str(self, party_a):
        role = PartyRole.objects.create(
            tenant=party_a.tenant, party=party_a, role="customer"
        )
        assert "Acme Party" in str(role)
        assert "Customer" in str(role)

    def test_default_status(self, party_a):
        role = PartyRole.objects.create(
            tenant=party_a.tenant, party=party_a, role="vendor"
        )
        assert role.status == "active"

    def test_unique_together(self, party_a):
        from django.db import IntegrityError
        PartyRole.objects.create(tenant=party_a.tenant, party=party_a, role="customer")
        with pytest.raises(IntegrityError):
            PartyRole.objects.create(tenant=party_a.tenant, party=party_a, role="customer")

    def test_status_choices(self):
        statuses = [c[0] for c in PartyRole.STATUS_CHOICES]
        assert "active" in statuses
        assert "inactive" in statuses
        assert "archived" in statuses


# ------------------------------------------------------------------ Address
class TestAddress:
    def test_str_with_city(self, party_a):
        addr = Address.objects.create(
            tenant=party_a.tenant, party=party_a,
            line1="123 Main St", city="Springfield"
        )
        assert "123 Main St" in str(addr)
        assert "Springfield" in str(addr)

    def test_str_without_city(self, party_a):
        addr = Address.objects.create(
            tenant=party_a.tenant, party=party_a, line1="PO Box 1"
        )
        assert str(addr) == "PO Box 1"

    def test_default_kind(self, party_a):
        addr = Address.objects.create(
            tenant=party_a.tenant, party=party_a, line1="Test St"
        )
        assert addr.kind == "billing"


# ------------------------------------------------------------------ ContactMethod
class TestContactMethod:
    def test_str(self, party_a):
        cm = ContactMethod.objects.create(
            tenant=party_a.tenant, party=party_a, kind="email", value="test@example.com"
        )
        assert "Email" in str(cm)
        assert "test@example.com" in str(cm)

    def test_default_kind(self, party_a):
        cm = ContactMethod.objects.create(
            tenant=party_a.tenant, party=party_a, value="555-1234"
        )
        assert cm.kind == "email"


# ------------------------------------------------------------------ Employment
class TestEmployment:
    def test_str_with_title(self, party_a):
        emp = Employment.objects.create(
            tenant=party_a.tenant, party=party_a, job_title="Software Engineer"
        )
        assert "Acme Party" in str(emp)
        assert "Software Engineer" in str(emp)

    def test_str_without_title(self, party_a):
        emp = Employment.objects.create(tenant=party_a.tenant, party=party_a)
        assert str(emp) == "Acme Party"

    def test_default_status(self, party_a):
        emp = Employment.objects.create(tenant=party_a.tenant, party=party_a)
        assert emp.status == "active"

    def test_status_choices(self):
        statuses = [c[0] for c in Employment.STATUS_CHOICES]
        assert "active" in statuses
        assert "on_leave" in statuses
        assert "terminated" in statuses


# ------------------------------------------------------------------ Activity
class TestActivity:
    def test_str(self, tenant_a, admin_user):
        act = Activity.objects.create(
            tenant=tenant_a, subject="Follow up call", kind="call"
        )
        assert str(act) == "Follow up call"

    def test_defaults(self, tenant_a):
        act = Activity.objects.create(tenant=tenant_a, subject="Task")
        assert act.kind == "task"
        assert act.status == "open"

    def test_kind_choices(self):
        kinds = [c[0] for c in Activity.KIND_CHOICES]
        assert "task" in kinds
        assert "call" in kinds
        assert "email" in kinds
        assert "meeting" in kinds
        assert "note" in kinds

    def test_status_choices(self):
        statuses = [c[0] for c in Activity.STATUS_CHOICES]
        assert "open" in statuses
        assert "in_progress" in statuses
        assert "done" in statuses
        assert "cancelled" in statuses


# ------------------------------------------------------------------ AuditLog
class TestAuditLog:
    def test_str(self, tenant_a, admin_user, party_a):
        log = AuditLog.objects.create(
            tenant=tenant_a, user=admin_user, target="Acme Party", action="create"
        )
        assert "Create" in str(log)
        assert "Acme Party" in str(log)

    def test_action_choices(self):
        actions = [c[0] for c in AuditLog.ACTION_CHOICES]
        assert "create" in actions
        assert "update" in actions
        assert "delete" in actions


# ------------------------------------------------------------------ Document
class TestDocument:
    def test_str(self, tenant_a):
        doc = Document.objects.create(
            tenant=tenant_a, name="Contract.pdf",
            file="documents/2024/01/contract.pdf",
        )
        assert str(doc) == "Contract.pdf"

    def test_default_classification(self, tenant_a):
        doc = Document.objects.create(
            tenant=tenant_a, name="Doc", file="documents/doc.pdf"
        )
        assert doc.classification == "internal"


# ------------------------------------------------------------------ next_number utility
class TestNextNumber:
    def test_first_number(self, tenant_a):
        from apps.tenants.models import SubscriptionInvoice
        num = next_number(SubscriptionInvoice, tenant_a, "SINV")
        assert num == "SINV-00001"

    def test_sequential_numbers(self, tenant_a):
        from apps.tenants.models import SubscriptionInvoice
        # Create first invoice to seed the sequence
        inv1 = SubscriptionInvoice.objects.create(
            tenant=tenant_a, status="open", amount=100
        )
        assert inv1.number == "SINV-00001"
        inv2 = SubscriptionInvoice.objects.create(
            tenant=tenant_a, status="open", amount=200
        )
        assert inv2.number == "SINV-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.tenants.models import SubscriptionInvoice
        inv_a = SubscriptionInvoice.objects.create(
            tenant=tenant_a, status="open", amount=100
        )
        inv_b = SubscriptionInvoice.objects.create(
            tenant=tenant_b, status="open", amount=200
        )
        # Each tenant starts from 00001
        assert inv_a.number == "SINV-00001"
        assert inv_b.number == "SINV-00001"


# ------------------------------------------------------------------ write_audit_log
class TestWriteAuditLog:
    def test_creates_auditlog_row(self, tenant_a, admin_user, party_a):
        log = write_audit_log(admin_user, party_a, "create")
        assert log.pk is not None
        assert log.action == "create"
        assert log.target == str(party_a)
        assert log.tenant == tenant_a
        assert log.user == admin_user

    def test_update_action(self, tenant_a, admin_user, party_a):
        log = write_audit_log(admin_user, party_a, "update", {"name": "New Name"})
        assert log.action == "update"
        assert log.changes == {"name": "New Name"}

    def test_delete_action(self, tenant_a, admin_user, party_a):
        log = write_audit_log(admin_user, party_a, "delete")
        assert log.action == "delete"

    def test_anonymous_user(self, tenant_a, party_a):
        from django.contrib.auth.models import AnonymousUser
        log = write_audit_log(AnonymousUser(), party_a, "create")
        assert log.user is None
        assert log.tenant == tenant_a

    def test_content_type_captured(self, admin_user, party_a):
        from django.contrib.contenttypes.models import ContentType
        log = write_audit_log(admin_user, party_a, "create")
        expected_ct = ContentType.objects.get_for_model(Party)
        assert log.content_type == expected_ct
        assert log.object_id == party_a.pk
