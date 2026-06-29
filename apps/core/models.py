"""Core spine models — the shared backbone every NavERP module reuses.

This foundation pass builds the Module-0 subset of NavERP-ERD.md: the Tenant, the
Party model (one record, many roles), org structure, employment, and the cross-cutting
anchors Activity / AuditLog / Document. The remaining masters and the two ledgers
(Item, GLAccount, StockMove, JournalEntry, …) arrive with their owning modules and
FK back to these tables by string.

Every business table carries ``tenant`` (indexed) and is filtered by ``request.tenant``
in views — the superuser ``admin`` has ``tenant=None`` by design.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Tenant(models.Model):
    """A customer workspace. Root of all tenant-scoped data."""

    PLAN_CHOICES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrgUnit(models.Model):
    """Company / branch / department / team / cost-center hierarchy."""

    KIND_CHOICES = [
        ("company", "Company"),
        ("branch", "Branch"),
        ("department", "Department"),
        ("team", "Team"),
        ("cost_center", "Cost Center"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="org_units", db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="department")
    name = models.CharField(max_length=255)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Party(models.Model):
    """One record per real-world person or organization. Roles are attached via PartyRole."""

    KIND_CHOICES = [("person", "Person"), ("organization", "Organization")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="parties", db_index=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="person")
    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "parties"

    def __str__(self):
        return self.name


class PartyRole(models.Model):
    """The role a Party plays — customer, vendor, employee, lead, etc."""

    ROLE_CHOICES = [
        ("customer", "Customer"),
        ("vendor", "Vendor"),
        ("supplier", "Supplier"),
        ("employee", "Employee"),
        ("lead", "Lead"),
        ("candidate", "Candidate"),
        ("contact", "Contact"),
        ("partner", "Partner"),
    ]
    STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive"), ("archived", "Archived")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="party_roles", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="roles")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    start_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["party__name", "role"]
        unique_together = ("party", "role")

    def __str__(self):
        return f"{self.party} · {self.get_role_display()}"


class Address(models.Model):
    KIND_CHOICES = [("billing", "Billing"), ("shipping", "Shipping"), ("home", "Home")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="addresses", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="addresses")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="billing")
    line1 = models.CharField(max_length=255)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["party__name", "kind"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.line1}, {self.city}" if self.city else self.line1


class ContactMethod(models.Model):
    KIND_CHOICES = [("email", "Email"), ("phone", "Phone"), ("mobile", "Mobile")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="contact_methods", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="contact_methods")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="email")
    value = models.CharField(max_length=255)

    class Meta:
        ordering = ["party__name", "kind"]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"


class PartyRelationship(models.Model):
    KIND_CHOICES = [
        ("employee_of", "Employee of"),
        ("contact_of", "Contact of"),
        ("subsidiary_of", "Subsidiary of"),
        ("reports_to", "Reports to"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="party_relationships", db_index=True)
    from_party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="relationships_from")
    to_party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="relationships_to")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)

    class Meta:
        ordering = ["from_party__name"]

    def __str__(self):
        return f"{self.from_party} {self.get_kind_display()} {self.to_party}"


class Employment(models.Model):
    """HR's view of a Party-with-an-employee-role: job, department, manager."""

    STATUS_CHOICES = [("active", "Active"), ("on_leave", "On Leave"), ("terminated", "Terminated")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="employments", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.CASCADE, related_name="employments")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="employments")
    manager = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_employments")
    job_title = models.CharField(max_length=255, blank=True)
    hired_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        ordering = ["party__name"]
        indexes = [
            # HRM employee_list filters by employment status (employment__status) per tenant.
            models.Index(fields=["tenant", "status"], name="core_emp_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.party} — {self.job_title}" if self.job_title else str(self.party)


class Activity(models.Model):
    """Generic task / call / email / meeting / note attachable to any record."""

    KIND_CHOICES = [
        ("task", "Task"),
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("note", "Note"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="activities", db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="task")
    subject = models.CharField(max_length=255)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-due_at", "-created_at"]
        verbose_name_plural = "activities"
        indexes = [
            models.Index(fields=["tenant", "status"], name="activity_tenant_status_idx"),
            models.Index(fields=["tenant", "owner"], name="activity_tenant_owner_idx"),
        ]

    def __str__(self):
        return self.subject


class AuditLog(models.Model):
    """Append-only record of data/config changes (who / what / when / before→after)."""

    ACTION_CHOICES = [("create", "Create"), ("update", "Update"), ("delete", "Delete")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs", db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")
    target = models.CharField(max_length=255, blank=True)  # human label of the affected object
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    changes = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["tenant", "at"], name="auditlog_tenant_at_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} {self.target} @ {self.at:%Y-%m-%d %H:%M}"


class Document(models.Model):
    """Generic file attachment for any record (DMS module later layers folders/versions on top)."""

    CLASSIFICATION_CHOICES = [
        ("public", "Public"),
        ("internal", "Internal"),
        ("confidential", "Confidential"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="documents", db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")
    file = models.FileField(upload_to="documents/%Y/%m/")
    name = models.CharField(max_length=255)
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default="internal")
    version = models.CharField(max_length=20, default="1.0")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.name
