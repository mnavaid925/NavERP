"""core — ModuleAccessScope and SensitiveFieldMask (0.6 Application Module Administration).

0.6's thirteen bullets are thirteen per-module access scopes (CRM record/territory access, HRM
personnel-data masking, DMS folder ACLs, …). They share ONE shape — for this tenant, in this module,
how far does a member see, does a change need approval, are sensitive fields masked, and is a
posting period locked — so they are one registry with a row per module rather than thirteen tables.

**Honest scope.** The registry RECORDS the policy; `apps/core/scoping.py` ENFORCES it where a view
opts in via `crud_list(scope_module=…)`. Nothing here retrofits row-level security across the ~150
existing sub-modules, and the access matrix names which modules currently enforce. Most of the
thirteen bullets' finer half — consent management, e-signature (21 CFR Part 11), retention locks,
check-in/out, PCI isolation, dataset certification, BOM change control — is NOT built and is listed
as such rather than implied by a row existing.
"""
from apps.core.models._base import *  # noqa: F401,F403


class ModuleAccessScope(models.Model):
    """One tenant's access policy for one NavERP module."""

    DATA_SCOPE_CHOICES = [
        ("all", "All records"),
        ("team", "Team / department only"),
        ("own", "Own records only"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="module_access_scopes", db_index=True)
    module_number = models.CharField(max_length=4)
    module_slug = models.CharField(max_length=40)
    module_title = models.CharField(max_length=150)
    is_enabled = models.BooleanField(
        default=True, help_text="Off hides the module's data from members of this workspace.")
    data_scope = models.CharField(max_length=10, choices=DATA_SCOPE_CHOICES, default="all")
    requires_approval = models.BooleanField(
        default=False,
        help_text="Adjustments in this module need an approval before they take effect.")
    mask_sensitive = models.BooleanField(
        default=False, help_text="Apply the field masks configured below.")
    #: The accounting posting-period lock (bullet 2). A date, not a boolean, because the useful
    #: statement is "no posting on or before this date" — and a lock with no date cannot be audited.
    period_lock_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module_number", "module_slug"]
        unique_together = ("tenant", "module_slug")
        indexes = [models.Index(fields=["tenant", "module_slug"], name="modscope_tenant_slug_idx")]

    @property
    def enforces_scope(self):
        """True only when this scope would actually change what a member sees.

        `data_scope="all"` is the default posture and narrows nothing, so a row in that state is a
        record of a decision, not an enforced restriction. The matrix reports this distinction so a
        configured-but-inert scope is not mistaken for protection.
        """
        return self.is_enabled and self.data_scope != "all"

    def __str__(self):
        return f"{self.module_slug} · {self.get_data_scope_display()}"


class SensitiveFieldMask(models.Model):
    """A field-level mask rule: hide or partly hide one field of one module from most roles.

    Masking is a DISPLAY rule, not an access rule — the row still exists and is still fetched. What
    this prevents is a value appearing on a page or an export to someone who should not read it;
    it is not row-level security, and it must not be described as such.
    """

    MASK_STYLE_CHOICES = [
        ("full", "Fully hidden"),
        ("partial", "Keep first and last character"),
        ("last4", "Keep the last 4 characters"),
        ("email", "Email style (first letter + domain)"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="sensitive_field_masks", db_index=True)
    scope = models.ForeignKey("core.ModuleAccessScope", on_delete=models.CASCADE,
                              related_name="masks")
    field_name = models.CharField(max_length=64, help_text="The model field to mask, e.g. bank_account.")
    mask_style = models.CharField(max_length=10, choices=MASK_STYLE_CHOICES, default="partial")
    #: Roles that see the real value. Empty means EVERYONE is masked, including admins — which is
    #: the safe default: an unconfigured exemption must not leak, and adding one is explicit.
    exempt_roles = models.ManyToManyField("accounts.Role", blank=True, related_name="+")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scope", "field_name"]
        unique_together = ("scope", "field_name")

    def __str__(self):
        return f"{self.scope.module_slug}.{self.field_name}"
