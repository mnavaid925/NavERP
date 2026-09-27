"""core — 0.20 bullet 3b: the change register and its phased feature rollouts.

`core.Monitoring`'s `Incident.clean()` hands this file its job in as many words: "A maintenance
notice must say when the window opens. This is the notice, not the change record (**0.20 owns
that**)." So `ChangeRequest` is the change record — the Freshservice / Jira Service Management
advisory, with a risk, an impact, a requestor, an approver, a rollback reason and a post-implementation
review — and `FeatureRollout` is its child, carrying the LaunchDarkly progressive rollout.

**Both EXTEND the spine rather than restating it (L29/L36).** `environment` FKs 0.16's
`EnvironmentInstance` (the dev/test/staging/sandbox environments 0.16 bullet 5 already provisions),
`FeatureRollout.feature_flag` FKs 0.10's `FeatureFlag` (the per-tenant toggle), and
`MaintenanceWindow.change_request` points back here. None of those concepts is re-declared.

**Nothing here deploys, builds or rolls anything out.** A `FeatureRollout` row records that a
staged rollout was *planned* and how far it was declared to go; no percentage is ever applied to a
cohort, and `FeatureFlag.is_enabled` is not written by this file. `scheduled_at` and `started_at`
are declarations. The page says so rather than implying a control surface that does not exist.

`CHG-` is minted with a hardcoded literal in `save()`, so `core.settings_engine.LITERAL_PREFIX_MODELS`
is what makes it discoverable to the numbering board.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import IntegrityError, models, transaction

from apps.core.models._base import *  # noqa: F401,F403
from apps.core.utils import next_number


#: How much ceremony a change gets. `emergency` is the break-glass path: it exists so a record can
#: say "we did this under fire", not so the workflow can skip its own review.
CHANGE_TYPE_CHOICES = [
    ("standard", "Standard"),
    ("normal", "Normal"),
    ("emergency", "Emergency"),
]

#: The assessed risk of the change itself. Deliberately NOT `AlertRule.SEVERITY_CHOICES` or
#: `VulnerabilityFinding.SEVERITY_BAND_CHOICES` — a firing severity and a CVSS band are different
#: facts that happen to share three of their words. Overlapping vocabularies are shared BY
#: REFERENCE when they are the same fact (as `UsageQuota` does with `SEVERITY_CHOICES`) and kept
#: separate when they are not; this is the second case, and the file docstring above records why.
RISK_LEVEL_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]

#: What the change does to users if it goes wrong — a different question from how likely it is to
#: go wrong, which is why risk and impact are two fields and not one severity.
IMPACT_LEVEL_CHOICES = [
    ("minor", "Minor"),
    ("moderate", "Moderate"),
    ("major", "Major"),
]

#: The change lifecycle. `draft` through `approved` is the request; `scheduled` through `completed`
#: is the implementation; `rolled_back` is the reversal. Nothing here moves on its own — `submitted`,
#: `approved` and `rolled_back` are written by POST-only verbs and the stamps beside them are the
#: evidence those verbs leave.
CHANGE_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("scheduled", "Scheduled"),
    ("in_progress", "In progress"),
    ("completed", "Completed"),
    ("rolled_back", "Rolled back"),
    ("cancelled", "Cancelled"),
]

#: The LaunchDarkly rollout ladder. `internal` and `general` are the two bookends, `pilot` and
#: `partial` are the middle. A stage's `percentage` is a DECLARATION - no cohort is ever selected.
ROLLOUT_STAGE_CHOICES = [
    ("internal", "Internal only"),
    ("pilot", "Pilot"),
    ("partial", "Partial"),
    ("general", "General availability"),
]

ROLLOUT_STATUS_CHOICES = [
    ("planned", "Planned"),
    ("running", "Running"),
    ("paused", "Paused"),
    ("completed", "Completed"),
    ("rolled_back", "Rolled back"),
]

class ChangeRequest(models.Model):
    """One declared change: what it is, who asked, who approved, and how it went."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="change_requests", db_index=True)
    #: CHG-##### — literal mint; see `core.settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPE_CHOICES, default="normal")
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default="medium")
    impact_level = models.CharField(max_length=10, choices=IMPACT_LEVEL_CHOICES, default="minor")
    status = models.CharField(max_length=20, choices=CHANGE_STATUS_CHOICES, default="draft")
    #: 0.16's provisioned environment, referenced not re-declared (dev/test/staging/sandbox).
    environment = models.ForeignKey("core.EnvironmentInstance", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="change_requests")
    #: WHO asked and WHO approved. Both are SET_NULL `related_name="+"` user FKs rather than a
    #: second party table — people are `accounts.User` rows, and an approval trail that loses its
    #: name to a deleted account is still a truthful record, whereas a hard FK would delete the
    #: change itself and take the audit history with it.
    requestor = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="+")
    approved_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="+")
    #: Evidence stamps for the request/approval/implementation transitions. Each is written by the
    #: POST-only verb that performs the transition (L22) — never by the form, which is why every
    #: one of them is off `ChangeRequestForm`.
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True)
    #: A rollback with no stated reason is an unexplained reversal, so `rolled_back` requires one.
    rollback_reason = models.TextField(blank=True)
    rollback_at = models.DateTimeField(null=True, blank=True)
    #: The Freshservice post-implementation review: what actually happened, as opposed to what the
    #: change said would happen.
    post_review = models.TextField(blank=True)
    downtime_required = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = CHANGE_STATUS_CHOICES
    CHANGE_TYPE_CHOICES = CHANGE_TYPE_CHOICES
    RISK_LEVEL_CHOICES = RISK_LEVEL_CHOICES
    IMPACT_LEVEL_CHOICES = IMPACT_LEVEL_CHOICES

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="chgreq_tenant_status_idx"),
            models.Index(fields=["tenant", "risk_level"], name="chgreq_tenant_risk_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        for _ in range(5):
            self.number = next_number(ChangeRequest, self.tenant, "CHG")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # An approval is a decision somebody made, so it must carry who and when. The `approved_at`
        # half is the same L22 evidence-stamp rule the rest of the repo uses: a status that claims
        # a transition without its stamp is a claim with nothing behind it.
        if self.status == "approved":
            if not self.approved_by_id:
                raise ValidationError({"approved_by": "An approved change must name its approver."})
            if not self.approved_at:
                raise ValidationError({"approved_at": "An approved change must record when."})
        if self.status == "rolled_back":
            if not (self.rollback_reason or "").strip():
                raise ValidationError({"rollback_reason": "A rollback must say why."})
            if not self.rollback_at:
                raise ValidationError({"rollback_at": "A rollback must record when."})

    @property
    def rollout_count(self):
        """How many rollout stages this change declares."""
        return len(self.rollouts.all())

    def __str__(self):
        return "%s %s" % (self.number, self.title)


class FeatureRollout(models.Model):
    """One stage of a phased rollout for one feature flag, under one change request.

    **A child row, deliberately with no `number` and no prefix.** A fifth prefix would mint a
    `ROLL-` number that no operator ever looks up, because a rollout is only ever addressed through
    the change that owns it.

    The `stage`/`percentage` pair is a DECLARATION, not a control: nothing selects a cohort, and
    `FeatureFlag.is_enabled` is never written here. The `clean()` guards exist so the declaration
    cannot be self-contradictory — a "general availability" stage that reaches 40% of users is not a
    record of anything.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="feature_rollouts", db_index=True)
    change = models.ForeignKey(ChangeRequest, on_delete=models.CASCADE, related_name="rollouts")
    #: 0.10's per-tenant toggle. Referenced, not re-declared — this is the flag the rollout stages.
    feature_flag = models.ForeignKey("core.FeatureFlag", on_delete=models.CASCADE,
                                     related_name="rollouts")
    stage = models.CharField(max_length=10, choices=ROLLOUT_STAGE_CHOICES, default="internal")
    percentage = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    cohort_label = models.CharField(max_length=120, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=ROLLOUT_STATUS_CHOICES, default="planned")
    notes = models.TextField(blank=True)

    STAGE_CHOICES = ROLLOUT_STAGE_CHOICES
    STATUS_CHOICES = ROLLOUT_STATUS_CHOICES

    class Meta:
        ordering = ["stage", "id"]
        unique_together = (("change", "feature_flag"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="rollout_tenant_status_idx"),
            models.Index(fields=["change", "stage"], name="rollout_change_stage_idx"),
        ]

    def clean(self):
        super().clean()
        # The ladder bookends are exact, not approximate: "general availability" at 40% is a
        # contradiction, and "internal only" at 90% is worse.
        if self.stage == "internal" and self.percentage != 0:
            raise ValidationError({"percentage": "An internal-only stage reaches no users (0%)."})
        if self.stage == "general" and self.percentage != 100:
            raise ValidationError({"percentage": "General availability is 100%."})
        if self.stage == "partial" and not 0 < self.percentage < 100:
            raise ValidationError({"percentage": "A partial stage must be between 1% and 99%."})
        if self.status == "completed" and not self.completed_at:
            raise ValidationError({"completed_at": "A completed stage must record when it finished."})
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValidationError({"completed_at": "A stage cannot finish before it started."})

    def __str__(self):
        return "%s / %s (%d%%)" % (self.change.number, self.get_stage_display(), self.percentage)


