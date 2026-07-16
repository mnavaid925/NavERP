"""HRM 3.25 Personal Information — Changerequest models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.models._base import _json_safe


class EmployeeInfoChangeRequest(TenantNumbered):
    """3.25 maker-checker change request — the workflow connecting all five NavERP.md bullets. An
    employee proposes a change to a SENSITIVE field on their own record; HR approves (which applies it
    atomically) or rejects. Uses a GenericForeignKey so ONE model gates sensitive fields on
    ``EmployeeProfile`` itself (legal name/DOB/national ID/passport) AND ``EmployeeBankAccount`` /
    ``FamilyMember`` create-or-edit changes. ``field_changes`` is a JSON ``{field: {old, new}}`` map
    (JSON-safe values); for a ``profile_field`` request it holds exactly one key, for ``bank``/
    ``family`` it holds a full row (a create when ``object_id`` is None, else an edit)."""

    NUMBER_PREFIX = "ICR"

    REQUEST_TYPE_CHOICES = [
        ("profile_field", "Profile Field"),
        ("bank", "Bank Account"),
        ("family", "Family Member"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    # The sensitive EmployeeProfile fields an employee may only change via approval (Keka's per-field
    # matrix concept, simplified to a fixed list this pass). "legal_name" is a pseudo-field that
    # apply() writes through to core.Party.name (EmployeeProfile.name is a read-only @property).
    SENSITIVE_PROFILE_FIELDS = (
        "legal_name", "date_of_birth", "national_id", "national_id_type",
        "passport_number", "passport_expiry",
    )

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="info_change_requests")
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    # object_id None => this request PROPOSES CREATING a brand-new bank/family row (no existing target
    # yet); set => propose an edit to an existing row.
    object_id = models.BigIntegerField(null=True, blank=True)
    target = GenericForeignKey("content_type", "object_id")
    request_type = models.CharField(max_length=15, choices=REQUEST_TYPE_CHOICES, default="profile_field")
    field_changes = models.JSONField(default=dict, help_text='{"field": {"old": ..., "new": ...}, ...}')
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", editable=False)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     editable=False, related_name="+")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    editable=False, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_icr_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_icr_tenant_status_idx"),
        ]

    OPEN_STATUSES = ("pending",)

    def clean(self):
        if not isinstance(self.field_changes, dict) or not self.field_changes:
            raise ValidationError({"field_changes": "At least one field change is required."})
        if self.request_type == "profile_field":
            # Anti-tamper: a profile change may only target the requester's OWN profile.
            ep_ct = ContentType.objects.get_for_model(EmployeeProfile)
            if self.content_type_id and (self.content_type_id != ep_ct.id or self.object_id != self.employee_id):
                raise ValidationError("A profile change must target your own employee profile.")
        elif self.object_id and self.content_type_id:
            # Editing an existing bank/family row — it must belong to the same employee.
            target = self.target
            if target is not None and getattr(target, "employee_id", None) != self.employee_id:
                raise ValidationError("You can only propose changes to your own records.")

    def apply(self, user):
        """Apply the proposed changes to the target and mark approved — called ONLY from the
        approve action (already @tenant_admin_required + pending-guarded), inside one atomic txn.
        A stale/invalid proposal (target deleted, value no longer valid) raises ValidationError,
        which the view turns into a friendly message instead of a 500."""
        with transaction.atomic():
            if self.request_type == "profile_field":
                obj = self.employee
            elif self.object_id:
                obj = self.target
                if obj is None:
                    raise ValidationError("The record this request targets no longer exists.")
            else:
                model_cls = self.content_type.model_class()
                obj = model_cls(tenant=self.tenant, employee=self.employee)
            # Editing an existing target: guard against a lost update — the stored "old" snapshot must
            # still match the live value, else another change (or admin edit) has drifted the record
            # since this request was submitted. New rows (no existing target) have nothing to compare.
            is_new_row = self.request_type != "profile_field" and self.object_id is None
            for field, change in self.field_changes.items():
                new = change.get("new") if isinstance(change, dict) else change
                if not is_new_row and isinstance(change, dict) and "old" in change:
                    current = obj.party.name if field == "legal_name" else getattr(obj, field, None)
                    if _json_safe(current) != change["old"]:
                        raise ValidationError(
                            f"'{field}' has changed since this request was submitted — "
                            "ask the employee to resubmit with the current value.")
                if new is None:
                    # A None new-value keeps the model default (new row) / current value (edit);
                    # clearing a field via a change request is deferred (v1 simplicity).
                    continue
                if field == "legal_name":
                    party = obj.party
                    party.name = new
                    party.full_clean()
                    party.save(update_fields=["name"])
                else:
                    setattr(obj, field, new)
            obj.full_clean()
            obj.save()
            created_pk = obj.pk
            self.status = "approved"
            self.reviewed_by = user
            self.reviewed_at = timezone.now()
            update_fields = ["status", "reviewed_by", "reviewed_at", "updated_at"]
            if self.object_id is None and self.request_type != "profile_field":
                self.object_id = created_pk  # backfill so the request keeps pointing at what it created
                update_fields.append("object_id")
            self.save(update_fields=update_fields)

    def __str__(self):
        return f"{self.number} · {self.get_request_type_display()} · {self.employee}" if self.number else self.get_request_type_display()
