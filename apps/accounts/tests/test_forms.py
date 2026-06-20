"""Tests for accounts forms: TenantRegisterForm, UserForm, RoleForm, invites."""
import pytest

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ TenantRegisterForm
class TestTenantRegisterForm:
    def _valid_data(self, email="ceo@newco.com"):
        return {
            "company_name": "New Co",
            "first_name": "Alice",
            "last_name": "Smith",
            "email": email,
            "password1": "SuperSecret123!",
            "password2": "SuperSecret123!",
        }

    def test_valid_form_creates_tenant_and_user(self):
        from apps.accounts.forms import TenantRegisterForm
        from apps.core.models import Tenant
        form = TenantRegisterForm(self._valid_data())
        assert form.is_valid(), form.errors
        user = form.save()
        assert user.pk is not None
        assert user.is_tenant_admin is True
        assert Tenant.objects.filter(name="New Co").count() == 1

    def test_creates_exactly_one_tenant(self):
        from apps.accounts.forms import TenantRegisterForm
        from apps.core.models import Tenant
        form = TenantRegisterForm(self._valid_data(email="ceo2@newco.com"))
        assert form.is_valid(), form.errors
        form.save()
        assert Tenant.objects.filter(name="New Co").count() == 1

    def test_mismatched_passwords_invalid(self):
        from apps.accounts.forms import TenantRegisterForm
        data = self._valid_data()
        data["password2"] = "DifferentPass456!"
        form = TenantRegisterForm(data)
        assert not form.is_valid()
        assert "password2" in form.errors

    def test_duplicate_email_invalid(self, admin_user):
        from apps.accounts.forms import TenantRegisterForm
        data = self._valid_data(email=admin_user.email)
        form = TenantRegisterForm(data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_company_name_required(self):
        from apps.accounts.forms import TenantRegisterForm
        data = self._valid_data()
        data["company_name"] = ""
        form = TenantRegisterForm(data)
        assert not form.is_valid()
        assert "company_name" in form.errors

    def test_slug_auto_generated(self):
        from apps.accounts.forms import TenantRegisterForm
        from apps.core.models import Tenant
        form = TenantRegisterForm(self._valid_data(email="slug_test@test.com"))
        assert form.is_valid(), form.errors
        form.save()
        t = Tenant.objects.get(name="New Co")
        assert t.slug  # not empty
        assert " " not in t.slug  # slugified


# ------------------------------------------------------------------ UserForm
class TestUserForm:
    def test_password_required_on_create(self, tenant_a, role_a):
        from apps.accounts.forms import UserForm
        form = UserForm({
            "email": "new@acme.com",
            "username": "newuser",
            "first_name": "",
            "last_name": "",
            "role": "",
            "is_tenant_admin": False,
            "status": "active",
            "is_active": True,
            "password": "",  # blank password on creation
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "password" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.accounts.forms import UserForm
        form = UserForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_valid_create(self, tenant_a):
        from apps.accounts.forms import UserForm
        form = UserForm({
            "email": "create@acme.com",
            "username": "create_user",
            "first_name": "Create",
            "last_name": "",
            "role": "",
            "is_tenant_admin": False,
            "status": "active",
            "is_active": True,
            "password": "StrongPass123!",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors


# ------------------------------------------------------------------ RoleForm
class TestRoleForm:
    def test_valid_form(self, tenant_a):
        from apps.accounts.forms import RoleForm
        form = RoleForm({"name": "Editor", "description": "", "permissions": []}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_name_required(self, tenant_a):
        from apps.accounts.forms import RoleForm
        form = RoleForm({"name": "", "description": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_tenant_not_a_form_field(self, tenant_a):
        from apps.accounts.forms import RoleForm
        form = RoleForm(tenant=tenant_a)
        assert "tenant" not in form.fields


# ------------------------------------------------------------------ UserInviteForm
class TestUserInviteForm:
    def test_token_not_a_form_field(self, tenant_a):
        from apps.accounts.forms import UserInviteForm
        form = UserInviteForm(tenant=tenant_a)
        assert "token" not in form.fields

    def test_valid_invite_form(self, tenant_a):
        from apps.accounts.forms import UserInviteForm
        form = UserInviteForm({"email": "invite@acme.com", "role": ""}, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_invalid_email(self, tenant_a):
        from apps.accounts.forms import UserInviteForm
        form = UserInviteForm({"email": "not-an-email", "role": ""}, tenant=tenant_a)
        assert not form.is_valid()
        assert "email" in form.errors
