from django import forms
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.crm.models import EmailCampaign, Lead, Territory
from apps.core.models import ConsentPurpose


class TenantUniqueMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant

    def validate_unique(self):
        exclude = set(self._get_validation_exclusions())
        exclude.discard("tenant")
        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as exc:
            self._update_errors(exc)


def _reject_foreign(form, cleaned, names):
    tenant_id = form.tenant.pk if form.tenant is not None else None
    for name in names:
        value = cleaned.get(name)
        if value is None:
            continue
        values = value if isinstance(value, QuerySet) else [value]
        for chosen in values:
            if getattr(chosen, "tenant_id", None) != tenant_id:
                form.add_error(name, "That record belongs to another workspace.")


def tenant_users(tenant):
    if tenant is None:
        return User.objects.none()
    return User.objects.filter(tenant=tenant, is_active=True)


def tenant_leads(tenant):
    if tenant is None:
        return Lead.objects.none()
    return Lead.objects.filter(tenant=tenant)


def tenant_territories(tenant):
    if tenant is None:
        return Territory.objects.none()
    return Territory.objects.filter(tenant=tenant, is_active=True)


def tenant_drip_campaigns(tenant):
    if tenant is None:
        return EmailCampaign.objects.none()
    return EmailCampaign.objects.filter(tenant=tenant, send_type="drip")


def tenant_consent_purposes(tenant):
    if tenant is None:
        return ConsentPurpose.objects.none()
    return ConsentPurpose.objects.filter(tenant=tenant, is_active=True)


class TenantActionForm(forms.Form):
    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant
        super().__init__(*args, **kwargs)
