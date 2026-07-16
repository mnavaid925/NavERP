"""HRM 3.25 Personal Information — Emergencycontact models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.25 Personal Information (Self-Service) — the Employee Self-Service (ESS) layer over the
# existing ``EmployeeProfile``. This is NOT a re-model of the profile: ``EmployeeProfile`` already
# carries flat columns for bank details, two emergency-contact slots, addresses, contact info and
# personal-file fields (national_id/passport/dob/…). What every researched ESS product adds on top
# of a flat HR record is (1) the employee-facing self-view/self-edit surface (the ``my_info`` hub —
# a view, no model), (2) proper CHILD tables the 2-slot/1-slot flat columns can't model — unlimited
# emergency contacts, multiple bank accounts with one designated salary account, and family/dependent
# members, and (3) a maker-checker CHANGE-REQUEST workflow that gates the sensitive fields (legal
# name, DOB, national ID, passport, all bank writes, all family writes) behind HR review.
#
# Reuses: ``EmployeeProfile`` (parent of all three child tables; the ESS surface reads/edits its
# existing flat columns — nothing duplicated), ``core.Party.name`` (the real legal-name column —
# ``EmployeeProfile.name`` is a @property proxy, so the change-request ``apply()`` special-cases
# ``legal_name`` to write ``party.name``), and the ``django.contrib.contenttypes`` GenericForeignKey
# pattern already used by ``core.AuditLog``/``core.Activity``/``core.Document`` (this is the FIRST
# GenericForeignKey inside apps/hrm). ``EmployeeBankAccount`` ports ``EmployeeProfile._mask_last4``
# verbatim (per-model duplication convention, matching ``EmployeeStatutoryIdentifier``).
# ---------------------------------------------------------------------------
class EmergencyContact(TenantOwned):
    """3.25 Emergency Contacts — an unlimited roster of who-to-call, replacing the two hard-coded
    ``EmployeeProfile.emergency_contact_*`` slots (kept as legacy quick-reference, not migrated away).
    Direct self-edit: an employee manages their OWN contacts with no HR-approval gate (matches the
    majority of the ESS leaders surveyed). ``is_primary`` is auto-demote-on-save (one True per
    employee) rather than a hard validation error, for a friction-free UX."""

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100, blank=True, help_text="e.g. Spouse, Parent, Sibling, Friend.")
    phone = models.CharField(max_length=30)
    alt_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=False, help_text="Which contact to call first.")
    priority_order = models.PositiveSmallIntegerField(default=1)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["employee", "priority_order", "-is_primary"]
        indexes = [models.Index(fields=["tenant", "employee"], name="hrm_ec_tenant_emp_idx")]

    def save(self, *args, **kwargs):
        # Auto-demote siblings so at most one contact per employee is primary (same pattern as
        # EmployeeBankAccount.is_salary_account below).
        if self.is_primary and self.tenant_id and self.employee_id:
            with transaction.atomic():
                EmergencyContact.objects.filter(
                    tenant_id=self.tenant_id, employee_id=self.employee_id, is_primary=True
                ).exclude(pk=self.pk).update(is_primary=False)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    def __str__(self):
        rel = f" ({self.relationship})" if self.relationship else ""
        return f"{self.name}{rel} - {self.employee}"
