"""core — 0.21 bullets 1-3: control frameworks, corporate policies and the risk register.

**Where this file sits in the reconciliation (L29/L36).** Three of `core`'s earlier sub-modules
already built things whose *names* collide with the obvious 0.21 names, and two of them collide on
*substance*. Read this before adding a model here:

* **There is deliberately no class called `ComplianceFramework`.** 0.8's `RegulatoryFramework`
  (`Privacy.py:72`) already answers "which regimes is this workspace under", and already carries
  `dsar_window_days` and `data_residency_region`. A second framework table listing GDPR and HIPAA
  would give one workspace two answers to the same question at audit time, which is the exact
  duplication L36 exists to prevent. So 0.21 ships **`ControlFramework`** — the *certification
  programme* (SOC 2, ISO 27001, PCI-DSS) — and leaves `RegulatoryFramework` completely untouched.
* **`CorporatePolicy` is not a `RetentionPolicy`.** 0.8 owns that (`Retention.py`) and it is a data
  retention schedule. Also distinct from `hrm.HrPolicy` (3.x).
* **`ControlFrameworkMapping` is not `scm.ComplianceRequirement`** (4.13), which is a *supplier and
  contract* trade-compliance requirement, nor `accounting.InternalControl` (2.x). A control here is
  an attestation activity a named person owns and evidences.
* **`PolicyAcknowledgement` is not `core.AuditLog`** (0.1). `AuditLog` is the system-written
  who/what/when change trail. A later 0.21 pass will add `ComplianceAudit` — a human engagement
  with a period and an auditor — and it must not be conflated with either.

**The posture, inherited verbatim from 0.16/0.17/0.18/0.20: a register, not a runtime.** NavERP is
a single-region Django application with one database, no mail dispatcher and no background worker.
So **nothing in this file enforces anything.** A control marked `effective` is a sentence a person
typed, and no control gates any action in any module. An acknowledgement row records that somebody
pressed save; nobody is ever reminded, because there is no dispatcher.

**Numbering.** `core` has no `TenantNumbered` base, so these mint exactly the way 0.20's five do: a
hardcoded literal in `save()` through `apps.core.utils.next_number`. That makes them invisible to
`prefix_usage()`'s `NUMBER_PREFIX` scan, which is why all four are registered in
`core.settings_engine.LITERAL_PREFIX_MODELS`.

`ControlFrameworkMapping` and `PolicyAcknowledgement` are **deliberately unnumbered child rows**,
exactly as 0.20's `FeatureRollout`: they are only ever addressed through their parents, so a prefix
would mint a number no operator ever looks up.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403
from apps.core.utils import next_number


#: The kind of thing a `ControlFramework` is. `attestation` is the default because it is the case
#: with no home anywhere else in `core` — you get *certified* against SOC 2. `regulatory` is here
#: only as a cross-link: 0.8's `RegulatoryFramework` owns a regime's obligations, and this value
#: lets a control point at one without re-declaring it.
FRAMEWORK_TYPE_CHOICES = [
    ("attestation", "Attestation / certification"),
    ("regulatory", "Regulatory regime"),
    ("industry", "Industry standard"),
    ("internal", "Internal standard"),
]

#: How a control is doing. **`effective` is the dangerous one** — it is the state an auditor reads
#: as "this is operating". Nothing in NavERP checks it, which is why `clean()` refuses an
#: `effective` control that nobody has ever reviewed on a date.
CONTROL_STATUS_CHOICES = [
    ("not_started", "Not started"),
    ("in_progress", "In progress"),
    ("implemented", "Implemented"),
    ("effective", "Effective"),
    ("not_applicable", "Not applicable"),
]

#: How much of a framework clause one control actually covers. `not_applicable` carries the same
#: burden as the control's own: `clean()` on both refuses it without a written reason, because an
#: unexplained "not applicable" is a gap wearing a costume.
COVERAGE_CHOICES = [
    ("not_started", "Not started"),
    ("partial", "Partial"),
    ("covered", "Covered"),
    ("not_applicable", "Not applicable"),
]

#: What kind of policy this is. Deliberately NOT `RetentionPolicy` — see the file docstring.
POLICY_TYPE_CHOICES = [
    ("security", "Security"),
    ("acceptable_use", "Acceptable use"),
    ("access_control", "Access control"),
    ("data_handling", "Data handling"),
    ("incident_response", "Incident response"),
    ("business_continuity", "Business continuity"),
    ("code_of_conduct", "Code of conduct"),
]

#: The policy lifecycle. **`status` IS user-writable** (a lifecycle a person owns, not workflow
#: state a verb owns) — contrast 0.20's `ChangeRequest.status`, which is verb-driven and therefore
#: off its form. The verb-driven part of a policy is *acknowledgement*, its own child table.
POLICY_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("published", "Published"),
    ("retired", "Retired"),
]


#: Archer's five-point likelihood scale. `LIKELIHOOD_VALUES` below is the scoring half and the two
#: MUST stay in step.
LIKELIHOOD_CHOICES = [
    ("rare", "Rare"),
    ("unlikely", "Unlikely"),
    ("possible", "Possible"),
    ("likely", "Likely"),
    ("almost_certain", "Almost certain"),
]

#: The numeric half of the likelihood scale. Module-level and separate from the CHOICES list on
#: purpose: `RiskRegister.clean()` multiplies through it, and a second source of truth for "what
#: does `likely` score" is how a risk register starts disagreeing with itself.
LIKELIHOOD_VALUES = {
    "rare": 1,
    "unlikely": 2,
    "possible": 3,
    "likely": 4,
    "almost_certain": 5,
}

#: The five-point impact scale. **Deliberately NOT `ChangeRequest.RISK_LEVEL_CHOICES` (0.20) and
#: NOT `VulnerabilityFinding.SEVERITY_BAND_CHOICES` (0.18).** A change's risk level, a CVSS band
#: and an enterprise risk's impact are three different facts that happen to share some words;
#: 0.20's `Change.py` records the same ruling, and this file follows it.
RISK_IMPACT_CHOICES = [
    ("negligible", "Negligible"),
    ("minor", "Minor"),
    ("moderate", "Moderate"),
    ("major", "Major"),
    ("severe", "Severe"),
]

#: The numeric half of the impact scale, same rule and same reason as `LIKELIHOOD_VALUES`.
RISK_IMPACT_VALUES = {
    "negligible": 1,
    "minor": 2,
    "moderate": 3,
    "major": 4,
    "severe": 5,
}

#: What is being done about the risk. ServiceNow IRM's four responses, verbatim. "Accept" is on the
#: list on purpose — declining to act is a decision that has to be recorded just as much as acting.
TREATMENT_CHOICES = [
    ("accept", "Accept"),
    ("mitigate", "Mitigate"),
    ("transfer", "Transfer"),
    ("avoid", "Avoid"),
]

#: The register lifecycle, Archer's. `closed` is the only terminal state and `clean()` requires a
#: `reviewed_on` for it, so a risk cannot quietly disappear without somebody having looked at it.
RISK_STATUS_CHOICES = [
    ("identified", "Identified"),
    ("assessing", "Assessing"),
    ("treating", "Treating"),
    ("monitoring", "Monitoring"),
    ("closed", "Closed"),
]


def _active_user_count(tenant_id):
    """How many ACTIVE users a tenant has — the denominator of an acknowledgement rate.

    Active, not total: a rate that counts deactivated accounts as people who failed to acknowledge
    is a number that quietly degrades every time somebody leaves, which is the opposite of what a
    compliance page is for.

    Imported lazily because `apps.core.models` is still being assembled when this module is
    imported, so a module-level `get_user_model` plus an app-registry read is a circular-import
    crash. `get_user_model()` is exactly the one thing `_base.py` does not star-export.
    """
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(tenant_id=tenant_id, is_active=True).count()


class ControlFramework(models.Model):
    """A certification programme this workspace is measured against. [CFW-]

    **Not a `RegulatoryFramework`.** Read the file docstring: 0.8 owns the *laws* (GDPR, CCPA,
    HIPAA, LGPD, PIPEDA) and their obligations, this owns the *programmes you get certified
    against* (SOC 2, ISO 27001, PCI-DSS). The two are different facts with different lifecycles,
    and the `regulatory` type value exists so a control can point at an 0.8 regime by reference
    without this file re-declaring it.

    **`is_active` records a decision; it enforces nothing.** Turning a framework off does not
    remove a single mapped control, and turning it on does not create a task for anybody.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="control_frameworks", db_index=True)
    #: CFW-##### — literal mint; see `core.settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    framework_type = models.CharField(max_length=20, choices=FRAMEWORK_TYPE_CHOICES,
                                      default="attestation")
    #: The edition. "2017" for SOC 2, "2022" for ISO 27001:01 — a framework is a moving target and
    #: an audit is always against a particular edition of it.
    version = models.CharField(max_length=30, blank=True)
    #: The issuing body ("AICPA", "ISO", "PCI SSC"). Free text, because the authority is not a
    #: closed set this application can enumerate without going stale every time one appears.
    authority = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    #: Deliberately left NULL by the seeder. A framework a seeder created is NOT adopted, and a
    #: workspace that "adopted SOC 2" because a demo row said so is a compliance lie.
    adopted_on = models.DateField(null=True, blank=True)
    review_due_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    FRAMEWORK_TYPE_CHOICES = FRAMEWORK_TYPE_CHOICES

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        verbose_name_plural = "control frameworks"
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="cfw_tenant_active_idx"),
            models.Index(fields=["tenant", "framework_type"], name="cfw_tenant_type_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        # Five attempts: `next_number()` is existence-guarded max+1 and is explicitly documented
        # as not atomic under concurrency, so a collision is possible and must be survivable.
        for _ in range(5):
            self.number = next_number(ControlFramework, self.tenant, "CFW")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.adopted_on and self.review_due_on and self.review_due_on < self.adopted_on:
            raise ValidationError({"review_due_on": "A framework cannot be due for review before "
                                                   "the day it was adopted."})

    @property
    def control_count(self):
        return self.mappings.count()

    @property
    def is_overdue_review(self):
        """Derived, never stored. A NULL `review_due_on` is *not* an overdue review."""
        return bool(self.review_due_on and self.review_due_on < timezone.localdate())

    def __str__(self):
        return "%s — %s" % (self.code, self.name)


class ComplianceControl(models.Model):
    """One attestation activity a named person owns and evidences. [CTL-]

    **Framework-agnostic on purpose.** Drata's control framework is explicit that controls are the
    hub and requirements hang off them, because "one control addresses the same requirement across
    several frameworks" is the normal case, not an exception. A control belonging to exactly one
    framework would force a duplicate control per framework and the register would stop being a
    register. The framework↔control relationship is `ControlFrameworkMapping`.

    **Nothing here enforces the control.** `status="effective"` is a sentence somebody typed. No
    code path anywhere in NavERP reads this table to gate an action, and no test asserts that one
    does. The pages say this in words.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="compliance_controls", db_index=True)
    #: CTL-##### — literal mint; see `core.settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    code = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    #: Free text rather than a closed set: a control category is a per-framework taxonomy and
    #: enumerating it here would be wrong the first time an unknown framework is added.
    category = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=16, choices=CONTROL_STATUS_CHOICES, default="not_started")
    #: WHO owns it. `SET_NULL` + `related_name="+"` per the actor-FK convention: an ownership trail
    #: that loses its name to a deleted account is still a truthful record, whereas a hard FK would
    #: delete the control and take its mapped frameworks with it.
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="+")
    #: **Recorded, never scheduled.** "Quarterly" is a sentence in a field; there is no scheduler
    #: (0.20's `JobDefinition` is a register too) and nothing ever acts on this.
    frequency = models.CharField(max_length=20, blank=True)
    #: A **pointer** to evidence that lives elsewhere — 0.1's `core.Document` owns file upload and
    #: storage, and this file does not re-declare a document table (L36). 0.21 does not resolve,
    #: verify or fetch it.
    evidence_reference = models.CharField(max_length=255, blank=True)
    last_reviewed_on = models.DateField(null=True, blank=True)
    next_review_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = CONTROL_STATUS_CHOICES

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        indexes = [
            models.Index(fields=["tenant", "status"], name="ctl_tenant_status_idx"),
            models.Index(fields=["tenant", "category"], name="ctl_tenant_cat_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        for _ in range(5):
            self.number = next_number(ComplianceControl, self.tenant, "CTL")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if (self.next_review_on and self.last_reviewed_on
                and self.next_review_on < self.last_reviewed_on):
            raise ValidationError({"next_review_on": "The next review cannot be due before the "
                                                     "last one happened."})
        if self.status == "effective" and not self.last_reviewed_on:
            raise ValidationError({"last_reviewed_on": "A control cannot be declared effective "
                                                       "without somebody having reviewed it on a "
                                                       "date."})
        # "Not applicable" is the single most abused control state in every real register, because
        # it is how a gap gets renamed. Requiring the reason is the whole defence.
        if self.status == "not_applicable" and not (self.notes or "").strip():
            raise ValidationError({"notes": "Say why this control does not apply — an "
                                            "unexplained 'not applicable' is a gap, not a "
                                            "decision."})

    @property
    def framework_count(self):
        return self.mappings.count()

    @property
    def is_overdue_review(self):
        """Derived, never stored. A NULL `next_review_on` is *not* an overdue review."""
        return bool(self.next_review_on and self.next_review_on < timezone.localdate())

    def __str__(self):
        return "%s — %s" % (self.code, self.title)


class ControlFrameworkMapping(models.Model):
    """How much of one framework clause one control actually covers.

    **The row that makes bullet 1 real.** Drata is explicit that mapping several controls to a
    single requirement "is a common and accepted practice", and that a requirement may need several
    controls to be fully satisfied. Without this join the framework↔control relationship does not
    exist at all, and bullet 1 collapses into a flat list of controls.

    **A child row, deliberately with no `number` and no prefix**, exactly as 0.20's
    `FeatureRollout`: a mapping is only ever addressed through its two parents, so a prefix would
    mint a number no operator ever looks up.

    **`coverage="covered"` asserts nothing.** It is what somebody typed. No code in NavERP tests a
    control to decide whether a clause is satisfied.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="control_framework_mappings", db_index=True)
    framework = models.ForeignKey(ControlFramework, on_delete=models.CASCADE,
                                  related_name="mappings")
    control = models.ForeignKey(ComplianceControl, on_delete=models.CASCADE, related_name="mappings")
    #: The clause this mapping addresses — "CC1.1" (SOC 2), "A.8.15" (ISO 27001:2022), "6.1.2".
    #: Free text: these namespaces belong to the frameworks, not to this application.
    clause_reference = models.CharField(max_length=40, blank=True)
    coverage = models.CharField(max_length=16, choices=COVERAGE_CHOICES, default="not_started")
    notes = models.TextField(blank=True)

    COVERAGE_CHOICES = COVERAGE_CHOICES

    class Meta:
        # Ordered through both parents so the list reads "for each framework, its controls in
        # order", which is the only order the register is ever used in.
        ordering = ["framework__code", "control__code"]
        unique_together = (("framework", "control"),)
        indexes = [
            models.Index(fields=["framework", "coverage"], name="cfmap_fw_cov_idx"),
        ]

    def clean(self):
        super().clean()
        # The same ruling as `ComplianceControl.clean()`, for the same reason: an unexplained
        # "not applicable" on a clause is the easiest gap in a register to invent.
        if self.coverage == "not_applicable" and not (self.notes or "").strip():
            raise ValidationError({"notes": "Say why this control does not cover this clause — an "
                                            "unexplained 'not applicable' is a gap, not a "
                                            "decision."})
        # Both parents must be the SAME tenant. The two FKs are independently settable, so a
        # cross-tenant mapping is reachable by constructing the row directly, and it would surface
        # one workspace's control inside another's framework page. `unique_together` does not
        # prevent it and the database cannot.
        if (self.framework_id and self.control_id
                and self.framework.tenant_id != self.control.tenant_id):
            raise ValidationError({"control": "The control and the framework must belong to the "
                                              "same workspace."})

    def __str__(self):
        return "%s / %s" % (self.framework.code, self.control.code)


class CorporatePolicy(models.Model):
    """A written policy a workspace puts in force and asks people to acknowledge. [CPOL-]

    **Not a `RetentionPolicy`** — 0.8 owns that (`Retention.py`) and it is a data-retention
    schedule keyed on `data_category` and `retention_months`. Also distinct from `hrm.HrPolicy`
    (3.x), which is HRM's employment-policy table. A policy here is a security/acceptable-use/
    data-handling document this workspace publishes.

    **`status` is on the form; acknowledgement is not a field.** `status` is a lifecycle a person
    owns, so it is theirs to set — contrast 0.20's `ChangeRequest.status`, which is verb-driven and
    therefore deliberately off its form. The verb-driven part of a policy is *acknowledgement*,
    which is its own child table (`PolicyAcknowledgement`) rather than a column here, because a
    policy is acknowledged by many people at many times and one column cannot be that.

    **Nothing is enforced and nobody is reminded.** A `published` policy is a document record.
    There is no dispatcher in this application, so an unacknowledged policy produces no email, no
    task and no escalation — ever.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="corporate_policies", db_index=True)
    #: CPOL-##### — literal mint; see `core.settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    code = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE_CHOICES, default="security")
    #: The version people acknowledge. Acknowledging v1 is not the same act as acknowledging v2 —
    #: which is why `PolicyAcknowledgement` snapshots it.
    version = models.CharField(max_length=20, default="1.0")
    status = models.CharField(max_length=12, choices=POLICY_STATUS_CHOICES, default="draft")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="+")
    effective_on = models.DateField(null=True, blank=True)
    review_due_on = models.DateField(null=True, blank=True)
    requires_acknowledgement = models.BooleanField(default=True)
    #: The document text. Plain text on purpose: this application has no rich-text editor, and
    #: storing markup nobody renders would be a field with no reader.
    body = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    POLICY_TYPE_CHOICES = POLICY_TYPE_CHOICES
    STATUS_CHOICES = POLICY_STATUS_CHOICES

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        verbose_name_plural = "corporate policies"
        indexes = [
            models.Index(fields=["tenant", "status"], name="cpol_tenant_status_idx"),
            models.Index(fields=["tenant", "policy_type"], name="cpol_tenant_type_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        for _ in range(5):
            self.number = next_number(CorporatePolicy, self.tenant, "CPOL")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # A published policy with no effective date has not been in force on any date at all, so
        # "when did this take effect?" has no answer. That is worth refusing.
        if self.status == "published" and not self.effective_on:
            raise ValidationError({"effective_on": "A published policy needs the date it takes "
                                                   "effect."})
        if (self.review_due_on and self.effective_on
                and self.review_due_on < self.effective_on):
            raise ValidationError({"review_due_on": "A policy cannot be due for review before the "
                                                    "day it took effect."})
        if (self.status == "retired" and self.review_due_on
                and self.review_due_on >= timezone.localdate()):
            raise ValidationError({"review_due_on": "A retired policy is not due a review."})

    @property
    def acknowledged_count(self):
        return self.acknowledgements.count()

    @property
    def acknowledgement_rate(self):
        """Acknowledged / expected, or **None** when there is nothing to acknowledge against.

        The zero rule, twice over. `None` when the policy does not require acknowledgement (the
        template prints an em dash, never a fake 100%), and `None` rather than `0` when the
        expected count is zero — "0% acknowledged" of nobody is a false statement about a
        workspace, not a measurement of it.
        """
        if not self.requires_acknowledgement:
            return None
        expected = _active_user_count(self.tenant_id)
        if not expected:
            return None
        return self.acknowledged_count / expected

    def __str__(self):
        return "%s v%s — %s" % (self.code, self.version, self.title)


class PolicyAcknowledgement(models.Model):
    """One person acknowledging one version of one policy, once.

    **A child row, deliberately with no `number` and no prefix** — same rule as
    `ControlFrameworkMapping` and 0.20's `FeatureRollout`: it is only ever read through its policy.

    **`user` is the actor and `policy_version` is a stamp. Neither is ever a form field.** A form
    carrying `user` would let a member acknowledge a policy on somebody else's behalf, and a form
    carrying `policy_version` would let them write "I acknowledged v2.0" onto a v1
    acknowledgement. Both are set by the POST-only `policy_acknowledge` view, the only writer —
    the 0.16 evidence-stamp ruling, applied to an attestation.

    **`policy_version` is a SNAPSHOT, not a read-through.** If it read through to `policy.version`,
    re-versioning a policy would silently rewrite what every historical row claims somebody agreed
    to — the one thing an attestation must never do.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="policy_acknowledgements", db_index=True)
    policy = models.ForeignKey(CorporatePolicy, on_delete=models.CASCADE,
                               related_name="acknowledgements")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="+")
    policy_version = models.CharField(max_length=20, editable=False)
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-acknowledged_at", "-id"]
        # The version is in the key, so acknowledging a NEW version is allowed and acknowledging
        # the same one twice is not. That is the whole difference between this and a unique key on
        # (policy, user), which would refuse a legitimate re-acknowledgement after a re-version.
        unique_together = (("policy", "user", "policy_version"),)
        indexes = [
            models.Index(fields=["policy", "acknowledged_at"], name="ack_pol_time_idx"),
        ]

    def __str__(self):
        return "%s → %s v%s" % (self.user, self.policy.code, self.policy_version)


class RiskRegister(models.Model):
    """An identified enterprise risk, scored and given a recorded treatment. [GRC-]

    **The prefix is `GRC-`, NOT `RSK-`.** `RSK` is already `projects.ProjectRisk` (module 9),
    verified by enumerating every `NUMBER_PREFIX` in the repository. `next_number()` scopes by
    `(tenant, prefix)`, so the collision would not crash anything — which is exactly why it is
    dangerous: an operator holding `RSK-00001` would have no way to tell a risk from a project
    risk, and `prefix_usage()` would have reported both as correct. GRC is the name the industry
    gives this whole module, and it is verified free.

    **Not `projects.ProjectRisk` either, and it does not roll up into it.** A project risk is a
    delivery risk on one project; this is an enterprise risk on the workspace. Reconciling the two
    is a cross-module project, not something a 0.21 side effect should invent.

    **`inherent_score` is STORED, and recomputed on every clean().** Stored because it is the
    column the list page sorts on and the number an auditor reads — a `@property` would filesort
    every render. Recomputed because a stored score a POST can set is a forged number: the field
    is off the form, and `clean()` overwrites whatever arrived with the product of the two ordinal
    scales, so a crafted `inherent_score=1` cannot land.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="risk_register", db_index=True)
    #: GRC-##### — literal mint; see `core.settings_engine.LITERAL_PREFIX_MODELS`. NOT `RSK-`:
    #: that prefix belongs to `projects.ProjectRisk`.
    number = models.CharField(max_length=20, editable=False)
    code = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    #: The "if <event>, then <consequence>" statement. A risk with only a title is a worry; this
    #: is the sentence a treatment plan is written against.
    risk_statement = models.TextField()
    description = models.TextField(blank=True)
    category = models.CharField(max_length=40, blank=True)
    likelihood = models.CharField(max_length=14, choices=LIKELIHOOD_CHOICES, default="possible")
    impact = models.CharField(max_length=12, choices=RISK_IMPACT_CHOICES, default="minor")
    #: likelihood x impact, 1-25. See the class docstring for why it is stored.
    inherent_score = models.PositiveSmallIntegerField(default=0)
    #: What is left AFTER treatment. NULL means "not assessed", a different statement from zero —
    #: and `clean()` enforces the distinction by requiring it be <= the inherent score, so a
    #: residual of 0 is only reachable by a deliberate record.
    residual_score = models.PositiveSmallIntegerField(null=True, blank=True)
    treatment = models.CharField(max_length=10, choices=TREATMENT_CHOICES, default="mitigate")
    treatment_plan = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=RISK_STATUS_CHOICES, default="identified")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              blank=True, related_name="+")
    reviewed_on = models.DateField(null=True, blank=True)
    next_review_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    LIKELIHOOD_CHOICES = LIKELIHOOD_CHOICES
    IMPACT_CHOICES = RISK_IMPACT_CHOICES
    TREATMENT_CHOICES = TREATMENT_CHOICES
    STATUS_CHOICES = RISK_STATUS_CHOICES

    #: The statuses that mean "still on the register". Used by the list board and the overview, so
    #: the two cannot disagree about what "open" means.
    OPEN_STATUSES = ("identified", "assessing", "treating", "monitoring")


    class Meta:
        # Highest score first: the register is read top-down under time pressure, and a risk
        # register sorted alphabetically is a register nobody reads.
        ordering = ["-inherent_score", "code"]
        unique_together = ("tenant", "code")
        verbose_name_plural = "risk register"
        indexes = [
            models.Index(fields=["tenant", "status"], name="grc_tenant_status_idx"),
            models.Index(fields=["tenant", "-inherent_score"], name="grc_tenant_score_idx"),
            models.Index(fields=["tenant", "category"], name="grc_tenant_cat_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        for _ in range(5):
            self.number = next_number(RiskRegister, self.tenant, "GRC")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # Recomputed, never trusted. `.get(..., 1)` rather than `[...]` so a value that is not one
        # of the choices (reachable only by bypassing the form) yields a 1 instead of a KeyError on
        # a POST — a wrong number beats a 500, and the form's own validation refuses the junk
        # before this runs.
        self.inherent_score = (LIKELIHOOD_VALUES.get(self.likelihood, 1)
                               * RISK_IMPACT_VALUES.get(self.impact, 1))
        if self.residual_score is not None and self.residual_score > self.inherent_score:
            raise ValidationError({"residual_score": "Treatment cannot leave a risk worse than it "
                                                     "started. If the residual really is higher, "
                                                     "the inherent score is the wrong number."})
        if self.status == "closed" and not self.reviewed_on:
            raise ValidationError({"reviewed_on": "A risk cannot be closed without somebody "
                                                 "having reviewed it on a date."})
        if (self.next_review_on and self.reviewed_on
                and self.next_review_on < self.reviewed_on):
            raise ValidationError({"next_review_on": "The next review cannot be due before the "
                                                     "last one happened."})

    @property
    def score_label(self):
        """The band word for `inherent_score`. Derived, never stored, so it cannot drift.

        A property rather than a column precisely so a number edited by hand, by a seeder or by a
        future migration cannot end up disagreeing with its own label.
        """
        if self.inherent_score <= 4:
            return "low"
        if self.inherent_score <= 9:
            return "medium"
        if self.inherent_score <= 16:
            return "high"
        return "critical"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_overdue_review(self):
        """Derived, never stored. A NULL `next_review_on` is *not* an overdue review."""
        return bool(self.next_review_on and self.next_review_on < timezone.localdate())

    def __str__(self):
        return "%s %s" % (self.number, self.title)
