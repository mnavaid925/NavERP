"""Procurement 6.17 Risk & Compliance Management — PolicyAttestation, the sign-off ledger.

**NavERP.md bullet 5, "Policy Management & Acknowledgment".** One row per (policy, person): who
was assigned a published policy, when they must sign it off, whether they did, and — for the
people who genuinely cannot be asked to — the recorded exemption and its reason.

---

**THE OWNERSHIP CALL — why there is no ``ProcurementPolicy`` in this file** (L36/L29/L37, decided
2026-09-05 mid-build and recorded in ``.claude/tasks/contract-procurement-6.17.md`` §6a).

6.19 Document & Knowledge Management shipped ``procurement.ProcurementPolicy`` [PPOL-] at
``apps/procurement/models/DocumentKnowledgeManagement/Policies.py`` **before** 6.17 reached this
entity. Django permits exactly one model of a given name per app, so the 6.17 build plan's second
``ProcurementPolicy`` is not merely duplicative — it cannot load at all::

    RuntimeError: Conflicting 'procurementpolicy' models in application 'procurement'

The two sub-modules already agreed on the split before either was written: 6.19's own model
docstring reserves this work for 6.17 in as many words ("*Policy Management & Acknowledgment is
6.17's sub-module, and it owns the acknowledgement ledger*"), and its ``requires_acknowledgment``
column is documented as a bare hook meaning "*6.17 should collect acknowledgements for this one
when it ships*". Only the 6.17 plan — written before 6.19 landed — was out of date.

So the split, as built:

* **6.19 owns the policy table** — authoring, the version chain (``previous_version``), the
  publish and archive verbs, and the ``ppolicy_*`` register.
* **6.17 owns this ledger** — the roster, the signatures, the overdue chase and the exemptions.

Everything in this file follows from that. ``policy`` is a **string FK** to
``"procurement.ProcurementPolicy"``: 6.17 never re-declares that table and never edits 6.19's
files. Because 6.19's publish verb belongs to 6.19, "publishing raises the roster" is **inverted**
into a 6.17-owned, idempotent, admin-gated verb — :func:`raise_attestations`, reached from
``procurement:policy_raise_attestations`` — which raises the roster for an ALREADY-published
policy. Zero edits to 6.19's code, and bullet 5 is served in full.

6.19's model also has no ``attestation_due_days`` column, which is why the due window is
:data:`DEFAULT_ATTESTATION_DUE_DAYS`, owned here.

---

**A signature is only a signature when its own owner made it.** :meth:`PolicyAttestation.acknowledge`
refuses any user that is not ``self.user`` — **including a tenant administrator, including a
superuser**. The guard is in the MODEL and not only in the view, because that is the entire
evidentiary value of a sign-off: a "signature" an administrator could apply on somebody's behalf
records nothing anybody would testify to. An administrator who believes a person should not have
to sign has one honest option, and it is a different verb with a different word on it:
:meth:`PolicyAttestation.mark_exempt`, which demands a reason and stamps who granted it.

**Versions never inherit signatures.** A row keys on ONE policy row, and 6.19 models a new version
as a NEW row. So v1's attestations stay attached to v1 and remain true statements about v1, and
:func:`raise_attestations` on v2 raises a fresh roster that cannot reach, rewrite or reuse v1's.
That is not a rule enforced by a check somewhere; it is what keying on the row rather than on the
title *means*.

**Idempotence is structural, not best-effort.** The roster raiser is one
``get_or_create(tenant=…, policy=…, user=…)`` per resolved person, standing on the
``("tenant", "policy", "user")`` unique constraint. Running it twice raises nothing the second
time and cannot disturb a signature already on file — which matters because it is the repair
button an administrator presses when somebody joins the department after the policy went out.

**Import discipline.** Every cross-app and cross-sub-module FK is a STRING, so nothing here
imports 6.19 or 6.1 at module level and no import order can bite. ``ProcurementAlert`` is imported
inside the one method that raises one, mirroring the 6.14/6.15 rule entities 1-3 follow.
"""
from collections import namedtuple
from datetime import timedelta

from apps.procurement.models._base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------------------------

#: Where one person's obligation stands. ``pending`` is the only state either verb moves OUT of,
#: and neither verb has an inverse: un-signing an attestation is not something this module does,
#: because a withdrawn signature is not a correction, it is a second claim about the same day.
STATUS_CHOICES = [
    ("pending", "Pending"),
    ("acknowledged", "Acknowledged"),
    ("exempt", "Exempt"),
]

#: The only state from which anything may happen.
PENDING_STATUS = "pending"

#: Settled, one way or the other. A terminal row is evidence: no edit, no delete, no re-open.
TERMINAL_STATUSES = ("acknowledged", "exempt")

#: theme.css ships ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
#: badge-slate (L33) — a semantic badge-success / badge-warning renders completely unstyled and
#: passes every test, so the mapping lives here rather than in template {% if %} ladders.
STATUS_CSS = {
    "pending": "badge-amber",
    "acknowledged": "badge-green",
    "exempt": "badge-muted",
}

#: An overdue row that has slipped further than this is shown as seriously late rather than
#: merely late. Presentation only — nothing branches on it.
SERIOUSLY_LATE_DAYS = 30

#: How far ahead the "due soon" column on the overdue board looks.
DUE_SOON_DAYS = 7

#: How long somebody gets to read and sign a policy once the roster is raised.
#:
#: **Owned here on purpose.** The plan derived this from a ``ProcurementPolicy.attestation_due_days``
#: column, and 6.19's as-built policy table has no such column. Rather than edit 6.19's model to
#: add one (which 6.17 must not do, and which would put the same number in two places), the window
#: is a 6.17 constant and the raiser takes an override argument. Two working weeks is the common
#: default in the compliance tools the research pass looked at.
DEFAULT_ATTESTATION_DUE_DAYS = 14

#: The ONE ``ProcurementPolicy.status`` value that can carry a roster. A draft is not yet the
#: rule, and an archived policy is no longer it — collecting sign-offs for either would record
#: agreement to something nobody is being asked to follow.
ATTESTABLE_POLICY_STATUS = "published"

#: Ceiling on one roster raise, so a workspace with a very large directory cannot mint an
#: unbounded write from a single click. A refusal is reported; nothing is silently truncated.
MAX_ROSTER_SIZE = 2000

#: What :func:`raise_attestations` reports back. Three numbers rather than one, because the
#: interesting fact on the SECOND run is that ``created`` is zero while ``existing`` is not —
#: that is what "idempotent" looks like from the outside, and the flash message says it.
RosterResult = namedtuple("RosterResult", "created existing audience refusal")


def resolve_audience(policy):
    """The users a published ``policy`` should be put to, as a queryset (never a list).

    Two rules and no more:

    * **Everyone active in the policy's own workspace** — ``is_active`` AND ``status="active"``,
      because those are two different facts in this codebase (a suspended account is still
      ``is_active`` until somebody disables the login) and an attestation chased from a person who
      cannot sign in is noise in somebody's inbox forever.
    * **Narrowed to an org unit when the policy names one.** There is no ``User -> OrgUnit`` FK in
      this codebase; the path is ``accounts.User.party`` -> ``core.Employment.party`` ->
      ``core.Employment.org_unit``, and the employment must itself be ``active`` and belong to the
      same workspace. All three field names were grepped against the as-built models before this
      was written (L28) — ``Employment`` carries ``tenant``, ``party``, ``org_unit`` and a
      ``status`` whose active value is exactly ``"active"``.

    A policy with no ``applies_to`` addresses the whole workspace, which is what 6.19's own
    ``help_text`` on that column says ("*Blank = the whole workspace*"). Returned as a queryset so
    the caller can ``.count()`` it without pulling rows.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if policy is None or not getattr(policy, "tenant_id", None):
        return User.objects.none()

    audience = User.objects.filter(tenant_id=policy.tenant_id, is_active=True, status="active")
    if policy.applies_to_id:
        audience = audience.filter(
            party__employments__tenant_id=policy.tenant_id,
            party__employments__org_unit_id=policy.applies_to_id,
            party__employments__status="active",
        )
    # distinct(): the employment hop is a to-many join, so a person holding two active employment
    # rows in the same unit would otherwise be counted — and rostered — twice.
    return audience.distinct().order_by("first_name", "last_name", "username", "id")


def raise_attestations(policy, user=None, due_days=None, today=None):
    """Raise (or repair) the sign-off roster for one **already-published** policy.

    This is the inversion described at the top of this module: 6.19 owns the publish verb, so 6.17
    cannot hang roster creation off it, and hooking one in would mean editing another sub-module's
    code. Instead this is a 6.17-owned verb an administrator presses, and it is written so that
    pressing it twice is harmless — which turns it from a workaround into the better design, since
    it doubles as the repair button for somebody who joined the department after the policy went
    out.

    Three refusals, each returned as a SENTENCE for the caller to flash rather than as a silent
    zero — a verb that quietly does nothing is indistinguishable from a broken one:

    1. the policy is not ``published`` — a draft is not yet the rule and an archived one no longer
       is, so neither has a roster worth collecting;
    2. ``requires_acknowledgment`` is False — 6.19's flag is the workspace's statement of intent
       for this policy, and a flag that the ledger ignored would be decorative;
    3. the resolved audience is empty, or larger than :data:`MAX_ROSTER_SIZE`.

    Idempotent by construction: one ``get_or_create`` per person against the
    ``("tenant", "policy", "user")`` unique constraint. A second run creates nothing, leaves every
    signature and every exemption exactly as it found them, and reports ``created=0``.

    ``due_on`` is stamped ONLY in ``defaults``, so re-running never moves a deadline somebody is
    already working to.

    Returns a :data:`RosterResult`.
    """
    if policy is None or not getattr(policy, "pk", None) or not policy.tenant_id:
        return RosterResult(0, 0, 0, "That policy could not be resolved in this workspace.")

    if policy.status != ATTESTABLE_POLICY_STATUS:
        return RosterResult(
            0, 0, 0,
            f"{policy.number} is {policy.get_status_display().lower()}. Only a published policy "
            f"has a roster worth collecting - publish it first, then raise the attestations.")

    if not policy.requires_acknowledgment:
        return RosterResult(
            0, 0, 0,
            f"{policy.number} is not marked as requiring acknowledgment, so no sign-offs are "
            f"collected for it. Turn that on in the policy library first.")

    audience = list(resolve_audience(policy))
    if not audience:
        return RosterResult(
            0, 0, 0,
            "Nobody in this workspace matches that policy's audience - check that the people it "
            "applies to have active accounts, and that the org unit it is scoped to has active "
            "employments.")
    if len(audience) > MAX_ROSTER_SIZE:
        return RosterResult(
            0, 0, len(audience),
            f"That policy resolves to {len(audience)} people, over the {MAX_ROSTER_SIZE} ceiling "
            f"this action will raise in one go. Scope the policy to an org unit and raise it "
            f"there.")

    today = today or timezone.localdate()
    window = DEFAULT_ATTESTATION_DUE_DAYS if due_days is None else max(int(due_days), 0)
    due_on = today + timedelta(days=window)

    created = existing = 0
    with transaction.atomic():
        for person in audience:
            _row, was_created = PolicyAttestation.objects.get_or_create(
                tenant_id=policy.tenant_id, policy=policy, user=person,
                # due_on ONLY in defaults: a repair run must never move a deadline that somebody
                # is already working to, and must never reset a row that is already signed.
                defaults={"due_on": due_on},
            )
            if was_created:
                created += 1
            else:
                existing += 1

    return RosterResult(created, existing, len(audience), None)


class PolicyAttestation(TenantOwned):
    """One person's obligation to sign off one published policy, and what became of it."""

    # Re-exposed on the class so views, templates and tests reach the vocabulary through the model
    # rather than importing the module constants a second time.
    STATUS_CHOICES = STATUS_CHOICES
    STATUS_CSS = STATUS_CSS
    PENDING_STATUS = PENDING_STATUS
    TERMINAL_STATUSES = TERMINAL_STATUSES
    DEFAULT_ATTESTATION_DUE_DAYS = DEFAULT_ATTESTATION_DUE_DAYS
    ATTESTABLE_POLICY_STATUS = ATTESTABLE_POLICY_STATUS
    SERIOUSLY_LATE_DAYS = SERIOUSLY_LATE_DAYS
    DUE_SOON_DAYS = DUE_SOON_DAYS
    MAX_ROSTER_SIZE = MAX_ROSTER_SIZE

    # STRING FK, and the whole ownership call in one line: 6.19 declares this table, 6.17 points
    # at it. CASCADE because an attestation to a policy that no longer exists is not evidence of
    # anything — it is a signature against a blank page.
    policy = models.ForeignKey(
        "procurement.ProcurementPolicy", on_delete=models.CASCADE, related_name="attestations",
        help_text="The published policy this person is being asked to sign off")
    # NavERP.md bullet 5 says "user sign-offs", so this targets the USER and not an employee
    # record — deliberately different from hrm.PolicyAcknowledgment, which targets an employee.
    # The person who signs is the person who logged in.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="procurement_policy_attestations",
        help_text="Who has to read and acknowledge it")

    # editable=False: the workflow column belongs to acknowledge() and mark_exempt(). A status
    # <select> on a form would let a save skip the owner check, the timestamp and the audit row
    # all at once — and this is the one column in the module whose value IS the evidence.
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default=PENDING_STATUS,
                              editable=False)
    due_on = models.DateField(
        null=True, blank=True,
        help_text="When this sign-off is due. Blank means no deadline was set.")

    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledgement_note = models.TextField(blank=True, editable=False)

    exempt_reason = models.CharField(max_length=255, blank=True, editable=False)
    # WHO granted the exemption and WHEN. An exemption with no named grantor is the one hole an
    # attestation ledger cannot afford: it is the only way out of an obligation, so it carries the
    # same evidentiary weight as the signature it replaces. write_audit_log records the act too;
    # these columns keep the row self-contained.
    exempted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_policy_exemptions_granted", editable=False)
    exempted_at = models.DateTimeField(null=True, blank=True, editable=False)

    # The 6.1 inbox item that chased this overdue sign-off, if one was raised. No mail sender is
    # wired anywhere in this codebase, so the alert IS the chase — and the FK is what makes
    # re-running the chase idempotent without a dedupe column.
    alert = models.ForeignKey(
        "procurement.ProcurementAlert", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="policy_attestations", editable=False,
        help_text="The 6.1 alert raised to chase this sign-off, if any")

    class Meta:
        ordering = ["-created_at", "-id"]
        # One obligation per person per policy row. This constraint is what makes the roster
        # raiser idempotent — get_or_create stands on it, not on a pre-check.
        unique_together = (("tenant", "policy", "user"),)
        indexes = [
            models.Index(fields=["tenant", "policy"], name="prc_patt_tnt_policy_idx"),
            models.Index(fields=["tenant", "user", "status"], name="prc_patt_user_status_idx"),
            # Backs both the overdue board and the "my policies" page: status + due date is the
            # question both of them ask.
            models.Index(fields=["tenant", "status", "due_on"], name="prc_patt_status_due_idx"),
            models.Index(fields=["tenant", "-created_at"], name="prc_patt_tnt_created_idx"),
        ]
        verbose_name = "Policy Attestation"
        verbose_name_plural = "Policy Attestations"

    def __str__(self):
        # Guarded on the ids: on an UNSAVED instance (a ModelForm re-rendering its own errors)
        # both FKs raise RelatedObjectDoesNotExist, and a validation page must never 500.
        who = self.user if self.user_id else "-"
        what = self.policy if self.policy_id else "-"
        return f"{who} — {what}"

    # -- derived ------------------------------------------------------------------------------

    @property
    def status_css(self):
        return STATUS_CSS.get(self.status, "badge-muted")

    @property
    def is_pending(self):
        """Still owed. The only state from which either verb does anything."""
        return self.status == PENDING_STATUS

    @property
    def is_terminal(self):
        """Settled — signed or exempted. Evidence: no edit, no delete, no re-open."""
        return self.status in TERMINAL_STATUSES

    @property
    def is_overdue(self):
        """Pending AND past its due date. Computed against today, never a stored flag.

        A stored "overdue" column goes stale the moment nothing runs overnight, and this number
        is read on three pages that must agree with each other.
        """
        return bool(self.is_pending and self.due_on and self.due_on < timezone.localdate())

    @property
    def days_late(self):
        """Whole days past ``due_on`` — negative while still ahead, ``None`` with no deadline."""
        if not self.due_on:
            return None
        return (timezone.localdate() - self.due_on).days

    # -- the two verbs --------------------------------------------------------------------------
    #
    # Each returns a bool and re-checks its own guard, so a direct POST is exactly as safe as a
    # click. Neither has an inverse: there is no un-sign and no un-exempt, because a withdrawn
    # signature is not a correction — it is a second, contradictory claim about the same day.

    @staticmethod
    def _actor(user):
        """The user to stamp, or ``None`` for an anonymous / absent one."""
        return user if getattr(user, "is_authenticated", False) else None

    def acknowledge(self, user, note=""):
        """Sign this attestation off. **Only its own owner may do this.**

        The owner check lives HERE and not only in the view, and it does not exempt tenant
        administrators or superusers, because an administrator's ability to sign on somebody's
        behalf would empty the ledger of the only thing it holds. There is exactly one legitimate
        administrative answer to "this person should not have to sign", and it is
        :meth:`mark_exempt` — a different verb, with a required reason and a named grantor.

        Returns False rather than raising, so the view reports a refusal and the row is untouched.
        """
        if not self.is_pending:
            return False
        actor = self._actor(user)
        if actor is None or actor.pk != self.user_id:
            return False
        self.status = "acknowledged"
        self.acknowledged_at = timezone.now()
        self.acknowledgement_note = (note or "").strip()
        self.save(update_fields=["status", "acknowledged_at", "acknowledgement_note",
                                 "updated_at"])
        return True

    def mark_exempt(self, user, reason):
        """Excuse this person from signing. Administrator-gated at the view; reason required here.

        The reason is not optional and never has been: an exemption is the one way out of a stated
        obligation, so an unexplained one is the first thing an audit asks about and the last thing
        anybody can answer months later.
        """
        if not self.is_pending:
            return False
        reason = (reason or "").strip()
        if not reason:
            return False
        self.status = "exempt"
        self.exempt_reason = reason[:255]
        self.exempted_by = self._actor(user)
        self.exempted_at = timezone.now()
        self.save(update_fields=["status", "exempt_reason", "exempted_by", "exempted_at",
                                 "updated_at"])
        return True

    # -- the 6.1 chase ---------------------------------------------------------------------------

    def raise_chase_alert(self, user=None, link_url=""):
        """Raise ONE 6.1 ``ProcurementAlert`` chasing this overdue sign-off, or return ``None``.

        Called by the overdue board's POST leg, deliberately NOT from ``save()``: a table write
        hidden inside ``save()`` fires in every seeder run and every test fixture, and an inbox
        that fills itself from a fixture is an inbox nobody reads.

        Idempotent, the same way ``SupplierRiskSignal.raise_deterioration_alert`` is — four
        guards, all four required: the row is overdue, it has not already stamped an alert, it is
        assignable to a real person, and no OPEN alert is already chasing the same person for the
        same policy. That last check rides the ``alert`` FK's reverse accessor, so it needs no
        dedupe column: pressing the chase button weekly produces one inbox item per person per
        policy, not one per press.

        WARNING: ``ProcurementAlert.clean()`` requires a single-slash internal path. ``link_url``
        is built by the CALLER with ``reverse()`` and a literal fallback (this sub-module's URLconf
        is not spliced in until the Integrate step); an absolute or scheme-relative value would
        turn the alert card into an open redirect.
        """
        from apps.procurement.models.DashboardPortal.ProcurementAlerts import ProcurementAlert
        # ONE definition of the alert kind for the whole sub-module — entity 2 owns the constant
        # and the hand-off note that goes with it (ProcurementAlert.KIND_CHOICES does not carry
        # "risk" yet; adding it is one surgical Edit at the Integrate step, and until then the
        # chip renders slate instead of red — nothing crashes).
        from apps.procurement.models.RiskComplianceManagement.RiskSignals import ALERT_KIND

        if not self.is_overdue:
            return None
        if self.alert_id is not None:
            return None
        if not (self.pk and self.tenant_id and self.user_id and self.policy_id):
            return None
        if ProcurementAlert.objects.filter(
                tenant_id=self.tenant_id, kind=ALERT_KIND,
                status__in=ProcurementAlert.OPEN_STATUSES,
                assigned_to_id=self.user_id,
                policy_attestations__policy_id=self.policy_id).exists():
            return None

        # Width-guarded: ProcurementAlert.title is 200 chars and a policy title is up to 200 on
        # its own. Truncating the PART keeps the sentence readable; the final slice guarantees the
        # column width whatever the inputs were.
        policy_label = str(self.policy)[:120]
        late = self.days_late
        title = f"Policy sign-off overdue: {policy_label}"
        message = (
            f"{self.policy.number} - {policy_label} was due for your acknowledgment on "
            f"{self.due_on:%d %b %Y}"
            + (f", {late} day(s) ago. " if late is not None else ". ")
            + "Read it and sign it off from My Policies. Nobody else can sign it for you; if you "
              "should not have to, ask an administrator to record an exemption instead.")

        alert = ProcurementAlert.objects.create(
            tenant_id=self.tenant_id,
            kind=ALERT_KIND,
            severity="critical" if (late or 0) >= SERIOUSLY_LATE_DAYS else "warning",
            status="open",
            title=title[:200],
            message=message,
            link_url=link_url,
            assigned_to_id=self.user_id,
            created_by=self._actor(user),
        )
        self.alert = alert
        self.save(update_fields=["alert", "updated_at"])
        return alert

    # -- hygiene ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        tenant_id = getattr(self, "tenant_id", None)

        # Cross-tenant guard on every FK. A narrowed <select> is UX; this is the model-level
        # backstop behind the form's own re-check, and it covers ``alert`` and ``exempted_by``
        # too — both are editable=False, so no form offers them, but the verbs set them.
        #
        # ``user`` is included on purpose: accounts.User carries its own nullable ``tenant``, and
        # a workspace's policy roster must not be able to name somebody from another workspace.
        # A tenant-LESS user (the superuser) fails this comparison and that is correct — the
        # superuser is not a member of any workspace's audience.
        if tenant_id:
            for field in ("policy", "user", "alert", "exempted_by"):
                if not getattr(self, f"{field}_id", None):
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        # An attestation against a draft records agreement to something that is not yet the rule;
        # against an archived one, to something nobody is being asked to follow. Checked only when
        # the policy is in this workspace — walking a foreign row would be a second bug.
        if self.policy_id and "policy" not in errors:
            if self.policy.status != ATTESTABLE_POLICY_STATUS:
                errors["policy"] = (
                    f"{self.policy.number} is "
                    f"{self.policy.get_status_display().lower()}. Sign-offs are only collected "
                    f"for a published policy.")

        if errors:
            raise ValidationError(errors)
