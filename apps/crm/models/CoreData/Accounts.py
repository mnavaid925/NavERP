"""CRM 1.1 Core Data Management — Accounts models (split from apps/crm/models.py)."""
from django.core.exceptions import ValidationError

from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.CoreData.Leads import Lead


INDUSTRY_CHOICES = [
    ("technology", "Technology"),
    ("finance", "Finance & Banking"),
    ("healthcare", "Healthcare"),
    ("manufacturing", "Manufacturing"),
    ("retail", "Retail & E-commerce"),
    ("education", "Education"),
    ("real_estate", "Real Estate"),
    ("energy", "Energy & Utilities"),
    ("media", "Media & Entertainment"),
    ("professional_services", "Professional Services"),
    ("construction", "Construction"),
    ("transportation", "Transportation & Logistics"),
    ("hospitality", "Hospitality"),
    ("nonprofit", "Non-Profit"),
    ("government", "Government"),
    ("other", "Other"),
]


class AccountProfile(models.Model):
    """CRM firmographic + contact-detail extension for an organization ``core.Party``."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="crm_account_profile")
    industry = models.CharField(max_length=40, choices=INDUSTRY_CHOICES, blank=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    annual_revenue = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    employee_count = models.PositiveIntegerField(default=0)
    parent_account = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_child_account_profiles")
    address_line = models.CharField(max_length=255, blank=True)
    address_city = models.CharField(max_length=120, blank=True)
    address_state = models.CharField(max_length=120, blank=True)
    address_postal = models.CharField(max_length=20, blank=True)
    address_country = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=20, choices=Lead.SOURCE_CHOICES, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_account_profiles")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["party__name"]
        indexes = [
            models.Index(fields=["tenant", "industry"], name="crm_accp_tnt_industry_idx"),
            models.Index(fields=["tenant", "source"], name="crm_accp_tnt_source_idx"),
            models.Index(fields=["tenant", "parent_account"], name="crm_accp_tnt_parent_idx"),
        ]

    MAX_HIERARCHY_DEPTH = 100

    def _validate_hierarchy(self, *, lock=False):
        if not self.tenant_id:
            if self.party_id or self.parent_account_id:
                raise ValidationError({"tenant": "Choose an account workspace before saving an account profile."})
            return
        tenant_model = self._meta.get_field("tenant").remote_field.model
        party_model = self._meta.get_field("party").remote_field.model
        if lock:
            with transaction.atomic():
                tenant_model._default_manager.select_for_update().only("pk").get(pk=self.tenant_id)
                profile_rows = list(
                    type(self)._default_manager.select_for_update()
                    .filter(tenant_id=self.tenant_id)
                    .order_by("pk")
                    .values("party_id", "parent_account_id")
                )
                party_ids = {row["party_id"] for row in profile_rows if row["party_id"]}
                if self.party_id:
                    party_ids.add(self.party_id)
                if self.parent_account_id:
                    party_ids.add(self.parent_account_id)
                if party_ids:
                    party_model._default_manager.select_for_update().filter(
                        pk__in=sorted(party_ids),
                        tenant_id=self.tenant_id,
                        kind="organization",
                    )
                self._validate_hierarchy(lock=False)
            return
        if not self.party_id and not getattr(self, "_allow_unbound_party", False):
            raise ValidationError({"party": "The account profile must identify a same-tenant organization Party."})
        profile_rows = list(
            type(self)._default_manager.filter(tenant_id=self.tenant_id)
            .order_by("pk")
            .values("party_id", "parent_account_id")
        )
        profiles = {row["party_id"]: row["parent_account_id"] for row in profile_rows}
        if self.pk:
            previous_party_id = type(self)._default_manager.filter(pk=self.pk).values_list("party_id", flat=True).first()
            if previous_party_id:
                profiles.pop(previous_party_id, None)
        if self.party_id:
            profiles[self.party_id] = self.parent_account_id
        root_id = self.party_id
        required_party_ids = set()
        current_id = self.parent_account_id
        seen = set()
        depth = 0
        while current_id:
            if root_id and current_id == root_id:
                raise ValidationError({"parent_account": "An account cannot be one of its descendants."})
            if current_id in seen:
                raise ValidationError({"parent_account": "The account hierarchy contains a cycle."})
            if depth >= self.MAX_HIERARCHY_DEPTH:
                raise ValidationError({"parent_account": "The account hierarchy exceeds the maximum depth."})
            seen.add(current_id)
            required_party_ids.add(current_id)
            if current_id not in profiles:
                raise ValidationError({"parent_account": "The parent must have a CRM account profile."})
            current_id = profiles[current_id]
            depth += 1
        if root_id:
            required_party_ids.add(root_id)
        if not required_party_ids:
            return
        valid_party_ids = set(
            party_model._default_manager.filter(
                pk__in=required_party_ids,
                tenant_id=self.tenant_id,
                kind="organization",
            ).values_list("pk", flat=True)
        )
        if root_id and root_id not in valid_party_ids:
            raise ValidationError({"party": "The account profile must belong to a same-tenant organization Party."})
        if self.parent_account_id and self.parent_account_id not in valid_party_ids:
            raise ValidationError({"parent_account": "Choose a same-tenant organization account."})
        missing_parent_ids = required_party_ids - valid_party_ids
        if missing_parent_ids:
            raise ValidationError({"parent_account": "Every account in the hierarchy must belong to this workspace as an organization."})

    def clean(self):
        super().clean()
        self._validate_hierarchy()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self._validate_hierarchy(lock=True)
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"Account · {self.party.name}"
