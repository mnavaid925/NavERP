"""Sales 8.7 — the effective-dated account-to-territory assignment ledger (``TAS-``).

This is the table every 8.7 board reads and the only place an account's territory is *recorded*.
It is a **ledger, not a pointer**: a row carries ``effective_from`` / ``effective_to``, so an annual
rebalance supersedes the previous assignment instead of overwriting it, and "which territory was this
account in last March" stays answerable after the territories have been re-cut.

``territory`` is ``SET_NULL`` **on purpose**. That matches ``crm.Opportunity.territory`` and
``crm.SalesQuota.territory`` exactly, and the reason is the same in both places: deleting a territory
should orphan its assignments rather than cascade away a book of coverage history. The orphans are
then surfaced explicitly by the ``territory_coverage_gap`` board rather than hidden behind a CASCADE
(research §5.6). ``TerritoryMember.territory`` is ``CASCADE`` instead, because a membership in a
deleted territory is meaningless — the two on_delete choices are not an inconsistency.

``assigned_by`` is ``editable=False`` **frozen evidence** (L22): who made an assignment is a fact
about a decision, not a field a later form edit may rewrite. It is stamped once, by the view, from
``request.user``.

The ``account`` FK points at ``core.Party`` with ``kind="organization"`` — there is **no customer
table in 8.7** (L29), and a person is not assignable to a territory, so ``clean()`` refuses one.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered, settings
from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import TerritoryRule


class AccountTerritoryAssignment(TenantNumbered):
    """One account's placement in one ``crm.Territory`` for a window of time."""

    NUMBER_PREFIX = "TAS"

    ASSIGNMENT_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("rule", "Assignment Rule"),
        ("named_account", "Named Account"),
        ("inherited", "Inherited From Parent"),
    ]

    account = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="sales_territory_assignments",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_account_assignments",
    )
    rule = models.ForeignKey(
        "sales.TerritoryRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_assignments",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_territory_assignments",
    )
    #: REUSED VERBATIM from TerritoryRule — the single source of truth for 8.7's alignment
    #: vocabulary. Re-spelling this list here is how the two drift apart and a board ends up
    #: grouping on a value the other half of 8.7 never emits.
    alignment_type = models.CharField(
        max_length=8,
        choices=TerritoryRule.ALIGNMENT_TYPE_CHOICES,
        default="primary",
    )
    assignment_source = models.CharField(
        max_length=16,
        choices=ASSIGNMENT_SOURCE_CHOICES,
        default="manual",
    )
    effective_from = models.DateField(default=timezone.localdate)
    #: NULL means CURRENT. Every "is this assignment live?" question in 8.7 is
    #: `effective_to IS NULL`, computed in the views, never a stored boolean (L37: derive, don't
    #: remember).
    effective_to = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # --- FROZEN EVIDENCE. editable=False, so auto-excluded from every ModelForm (L22).
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="sales_territory_assignments_made",
    )

    class Meta:
        ordering = ["account__name", "alignment_type", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "account", "territory"],
                name="sales_atas_tenant_account_terr_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account"], name="sales_atas_tnt_acct_idx"),
            models.Index(fields=["tenant", "territory", "alignment_type"], name="sales_atas_tnt_terr_align_idx"),
            models.Index(fields=["tenant", "effective_to"], name="sales_atas_tnt_effto_idx"),
        ]

    # ------------------------------------------------------------------ helpers

    def _relation_belongs_to_tenant(self, field_name):
        """True when the named FK is unset or points at a row in THIS workspace.

        The exact one-FK-one-check helper already used by ``OpportunityTeams`` and
        ``OrderValidationRule``. An FK to a tenant-scoped model *looks* safe but is not: a
        hand-built row handed to ``save()`` by a seeder, a service or the shell bypasses every
        form. Never write a variant of this — four copies of one idea is how they diverge.
        """
        if not self.tenant_id:
            return True
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    # ------------------------------------------------------------------ validation

    def clean(self):
        super().clean()
        if not self.tenant_id:
            return
        errors = {}
        # A PERSON is not assignable to a territory. `core.Party` holds both kinds, so the
        # dropdown narrows to organizations AND the model refuses one here — the dropdown is a
        # convenience, this is the guarantee.
        if not self.account_id:
            errors["account"] = "Choose an organization account."
        else:
            account = type(self)._meta.get_field("account").remote_field.model._default_manager.filter(
                pk=self.account_id,
                tenant_id=self.tenant_id,
                kind="organization",
            ).first()
            if account is None:
                errors["account"] = "Choose a same-tenant organization account."
        for field_name in ("territory", "rule", "owner", "assigned_by"):
            if not self._relation_belongs_to_tenant(field_name):
                errors[field_name] = "That record must belong to this workspace."
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            errors["effective_to"] = "The end date cannot precede the start date."
        # `assignment_source="rule"` REQUIRES a rule; the other three FORBID one. A row reaching
        # save() with a rule attached and source="manual" is the shape that makes an audit trail
        # lie about how an account was assigned, which is the one thing this table exists to say.
        if self.assignment_source == "rule" and not self.rule_id:
            errors["rule"] = "A rule-sourced assignment must name the rule that made it."
        elif self.assignment_source != "rule" and self.rule_id:
            errors["rule"] = "Only a rule-sourced assignment can name a rule."
        if errors:
            raise ValidationError(errors)
        # At most ONE active PRIMARY row per account. Checked in Python over a fetched set rather
        # than as a partial-unique constraint because "active" means `effective_to IS NULL`, and a
        # partial index on a tenant-scoped, nullable window is a much harder thing to reason about
        # in a migration than the one rule this spells out. Excluding self.pk is what makes an
        # EDIT of the current primary row legal instead of a self-collision.
        if self.account_id and self.alignment_type == "primary" and not self.effective_to:
            siblings = type(self)._default_manager.filter(
                tenant_id=self.tenant_id,
                account_id=self.account_id,
                alignment_type="primary",
                effective_to__isnull=True,
            )
            if self.pk:
                siblings = siblings.exclude(pk=self.pk)
            if siblings.exists():
                raise ValidationError({
                    "alignment_type": (
                        "This account already has an active primary territory. Close the "
                        "current one before opening another."
                    ),
                })

    def __str__(self):
        label = self.territory.number if self.territory_id and self.territory else "—"
        return f"{self.number or '—'} · {self.account} → {label}"

