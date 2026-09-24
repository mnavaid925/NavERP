from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import ContactMethod, Party, PartyRole
from apps.crm.models import Lead, Opportunity


def convert_lead(lead, tenant):
    if lead.tenant_id != getattr(tenant, "pk", tenant):
        raise ValidationError("The lead must belong to this workspace.")
    with transaction.atomic():
        locked = Lead.objects.select_for_update().get(pk=lead.pk, tenant=tenant)
        existing = (
            Opportunity.objects.filter(tenant=tenant, source_lead=locked)
            .order_by("-created_at", "-id")
            .first()
        )
        if existing is not None:
            if locked.status != "converted" or not locked.converted_party_id:
                locked.status = "converted"
                locked.converted_party = existing.account or existing.primary_contact
                locked.save(update_fields=["status", "converted_party", "updated_at"])
            return existing
        if locked.status == "converted":
            raise ValidationError("The lead is marked converted but has no opportunity.")
        account = None
        if locked.company:
            account = Party.objects.create(tenant=tenant, kind="organization", name=locked.company)
            PartyRole.objects.create(tenant=tenant, party=account, role="customer", status="active", start_date=timezone.localdate())
        contact = Party.objects.create(tenant=tenant, kind="person", name=locked.name)
        PartyRole.objects.create(tenant=tenant, party=contact, role="contact", status="active", start_date=timezone.localdate())
        if locked.email:
            ContactMethod.objects.create(tenant=tenant, party=contact, kind="email", value=locked.email)
        opportunity = Opportunity.objects.create(
            tenant=tenant,
            name=f"{locked.company or locked.name} Opportunity",
            account=account,
            primary_contact=contact,
            stage="prospecting",
            amount=locked.est_value,
            probability=10,
            owner=locked.owner,
            source_lead=locked,
        )
        locked.status = "converted"
        locked.converted_party = account or contact
        locked.save(update_fields=["status", "converted_party", "updated_at"])
    return opportunity
