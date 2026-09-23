"""core — 0.16 `LegalHold`: the event that SUSPENDS a retention schedule.

**Why this is its own model and not a field on `RetentionPolicy`** (0.8, `apps/core/models/Retention.py`).
The research confirmed it three independent ways, and the reasoning is worth keeping next to the code:

1. **Case law, which is where the concept comes from.** *Zubulake v. UBS Warburg* — once litigation is
   reasonably anticipated, a party "must **suspend** its routine document retention/destruction policy".
   The mechanism is described as a suspension *of the schedule*, not as a property of one.
2. **Object storage, which is where it operates at scale.** AWS S3 Object Lock: a legal hold has **no
   expiration date**, is **independent of** the retention period, and "if the retention period expires,
   the object doesn't lose its WORM protection — the legal hold continues to protect the object until an
   authorized user explicitly removes the legal hold."
3. **SaaS practice.** Rubrik attaches legal hold to the SLA domain as a property that **outlives** the
   retention window.

So a hold **cannot** be expressed as a field on a policy, for two structural reasons:
**a hold has no window** — its end is an *event* (`released_at`), not a duration — and **a hold acts
negatively**, defeating a policy that would otherwise apply, *including one created later*. A boolean
`is_on_hold` on `RetentionPolicy` has no release date, no matter reference, no issuer, and cannot cover a
category spanning several policies. Hence a peer table, evaluated as a live override.

**The consequence for every page built on this:** 0.8's `retention_board` is the board that says what is
past its window. When a hold covers that scope, the board must **name the hold** rather than report a
"due for deletion" figure it cannot justify — the same discipline as its *"Reporting 0 here would be a
false all-clear"* rule. `suspends_policy()` below is the hook for that.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403
# The tenant-consistency model edge (I2). Defined in `Backup.py`, which holds the other six 0.16
# models; `Backup.py` does not import this module, so the import is one-way and cycle-free.
from apps.core.models.Backup import TenantConsistentMixin


class LegalHold(TenantConsistentMixin, models.Model):
    """A preservation order: it overrides every retention window covering its scope, until released."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("released", "Released"),
        ("expired", "Expired"),
        ("superseded", "Superseded"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="legal_holds", db_index=True)
    name = models.CharField(max_length=150)
    #: Who or what is subject to the hold. Free text because a custodian may be a person, a team, or a
    #: system that is not modelled as a `Party`.
    custodian = models.CharField(max_length=200, blank=True)
    #: Optional structured link when the custodian IS a Party.
    subject_party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="+")
    matter_reference = models.CharField(max_length=150, blank=True,
                                        help_text="Case or matter number.")
    issuing_authority = models.CharField(max_length=200, blank=True,
                                         help_text="Court, regulator, or internal counsel.")
    scope = models.TextField(blank=True, help_text="What data and systems the hold covers.")
    #: POINTS AT 0.8 — WHICH schedule is suspended. Optional, because a hold may cover a category that
    #: has no policy pinned yet, and it must still apply when one is created later.
    retention_policy = models.ForeignKey("core.RetentionPolicy", on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="legal_holds")
    #: The entity/category in scope, in 0.8's `app_label.Model` vocabulary, so a hold can be matched
    #: against a policy that is pinned to a model.
    model_label = models.CharField(max_length=120, blank=True)
    issued_at = models.DateTimeField(default=timezone.now)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name="+")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    #: THE RELEASE EVENT. This field is the whole reason a schedule cannot express a hold.
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="released_legal_holds")
    release_reason = models.CharField(max_length=255, blank=True,
                                      help_text="Documenting the release is what proves good faith.")
    authority_reference = models.CharField(max_length=255, blank=True,
                                           help_text="Preservation order or notice reference.")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issued_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="lghold_tenant_status_idx"),
            models.Index(fields=["tenant", "model_label"], name="lghold_tenant_model_idx"),
        ]

    def __str__(self):
        return f"{self.name} · {self.get_status_display()}"

    def clean(self):
        """Three rules. The second is the one that prevents spoliation; the third closes an incoherence."""
        super().clean()

        # 1. A release cannot precede the order it releases.
        if self.released_at is not None and self.released_at < self.issued_at:
            raise ValidationError(
                {"released_at": "A hold cannot be released before it was issued."})

        # 1b. STATUS MUST AGREE WITH THE RELEASE EVENT. Without this, `status="active"` + a release date
        #     is a storable state, and `is_active` (which requires BOTH `status=="active"` and
        #     `released_at is None`) then disagrees with the status badge on the same page: the detail view
        #     announced "the retention schedule has resumed" while the register still said Active. Two
        #     fields that must agree are one field's worth of information, so the rule belongs here rather
        #     than in a template branch that can only choose which of the two to disbelieve.
        if self.released_at is not None and self.status == "active":
            raise ValidationError(
                {"status": "This hold has a release date, so it cannot still be Active. Set the status to "
                           "Released (or clear the release date if the hold is genuinely still in force)."})
        if self.status == "released" and self.released_at is None:
            raise ValidationError(
                {"released_at": "A hold marked Released needs the date it was released — the release is an "
                                "event, and recording it is what proves good faith."})

        # 2. ANTI-SPOLIATION. Releasing this hold while another active hold covers the same scope would
        #    strand the data: the schedule would resume and destroy records the other hold still
        #    protects. This is Exterro's "no mistaken release" control, and it is the reason this check
        #    exists at the model edge rather than in the form — the admin and the seeder get it too.
        if self.status == "released":
            others = LegalHold.objects.filter(tenant=self.tenant, status="active")
            if self.pk:
                others = others.exclude(pk=self.pk)
            # Releasing must not strand on a sibling hold covering the same scope. Scope is matched by
            # policy OR by model label, because a hold may be pinned either way.
            scope_query = models.Q(pk__in=[])
            if self.retention_policy_id is not None:
                scope_query |= models.Q(retention_policy_id=self.retention_policy_id)
            if self.model_label:
                scope_query |= models.Q(model_label=self.model_label)
            conflicting = others.filter(scope_query) if self.retention_policy_id or self.model_label else others.none()
            if conflicting.exists():
                blocking = conflicting.first()
                raise ValidationError(
                    {"status": f"Another active hold ('{blocking.name}') covers this scope. Releasing "
                               f"this one would resume the retention schedule while that hold is still "
                               f"in force — releasing data it protects. Release that hold first."})

    # ---- derived ----
    @property
    def is_active(self):
        return self.status == "active" and self.released_at is None

    @property
    def age_days(self):
        return (timezone.now() - self.issued_at).days

    @property
    def scope_label(self):
        """A human answer to "what does this protect" without opening the record."""
        if self.model_label:
            return self.model_label
        if self.retention_policy is not None:
            return self.retention_policy.name
        return "workspace-wide"

    def suspends_policy(self, policy):
        """Does this hold override `policy`? Used by the boards to name a held scope.

        Matched on the policy FK **or** on the model label, because 0.8 lets a policy be pinned to a
        model as well as written as a category.
        """
        if not self.is_active or policy is None:
            return False
        if self.retention_policy_id is not None and self.retention_policy_id == policy.pk:
            return True
        if self.model_label and policy.model_label and self.model_label == policy.model_label:
            return True
        return False

    @classmethod
    def active_for_tenant(cls, tenant):
        return cls.objects.filter(tenant=tenant, status="active", released_at__isnull=True)
