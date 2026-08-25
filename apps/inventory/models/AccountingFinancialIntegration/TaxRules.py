"""Inventory 5.18 Accounting & Financial Integration — TaxRule.

**Tax Management** bullet: "Applying correct tax rules based on product type and
geography." The RATE masters live in ``accounting.TaxCode`` (Module 2 owns tax, L29);
what nothing else decides is WHICH code a given stock line earns. SCM 4.18's
``DutyTariff`` answers a different question (HS-code × origin IMPORT duty), so this is
the product-catalog lens: a rule pins a product scope (a specific SKU beats its category
beats the catch-all) and optionally a country, and resolves to one TaxCode whose rate
the AP/AR sync stamps onto drafted Bill/Invoice lines.

Matching semantics mirror 5.4's PutawayRule / 5.10's DispositionRoutingRule: every
non-blank dimension must match the query (blank = wildcard), overlapping rules are LEGAL,
and the deterministic resolver decides — specificity score DESC → priority ASC → id ASC.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class TaxRule(TenantNumbered):
    """Which ``accounting.TaxCode`` applies to a product at a geography [TRT-]."""

    NUMBER_PREFIX = "TRT"

    name = models.CharField(max_length=64)
    # Product scope: a pinned item wins over its category wins over the catch-all.
    # Both pinned is legal and acts as an ITEM-tier rule (the PutawayRule ruling) — it
    # never falls through to its category leg.
    item = models.ForeignKey(
        "scm.Item", on_delete=models.PROTECT, null=True, blank=True,
        related_name="tax_rules",
        help_text="Pin to one SKU (highest specificity)")
    category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.PROTECT, null=True, blank=True,
        related_name="tax_rules",
        help_text="Applies to every item in this category (when no SKU rule matches)")
    # Geography scope: blank matches any country; otherwise case-insensitive equality
    # against the counterparty's billing country as recorded on core.Address.
    country = models.CharField(
        max_length=120, blank=True,
        help_text="Billing country this rule covers — blank = any geography")
    tax_code = models.ForeignKey(
        "accounting.TaxCode", on_delete=models.PROTECT, related_name="inventory_tax_rules",
        help_text="The rate applied when this rule wins")
    priority = models.PositiveSmallIntegerField(
        default=100,
        help_text="Tie-break between equally specific rules — lower wins")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["priority", "id"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="inv_taxrule_active_idx")]

    # -- resolution ------------------------------------------------------------------------------

    #: Specificity score: a pinned SKU (8) dominates a category pin (4) which dominates a
    #: named country (2); the sum ranks rules deterministically across mixed scopes.
    @staticmethod
    def _specificity(instance):
        return ((8 if instance.item_id else 0)
                + (4 if instance.category_id else 0)
                + (2 if (instance.country or "").strip() else 0))

    def matches(self, item=None, country=""):
        """Whether this rule covers the query. Blank dimensions are wildcards."""
        if self.item_id and (item is None or self.item_id != item.pk):
            return False
        if self.category_id and (item is None or item.category_id != self.category_id):
            return False
        own = (self.country or "").strip().lower()
        if own and own != (country or "").strip().lower():
            return False
        return True

    @classmethod
    def resolve(cls, tenant, item=None, country="", *, rules=None):
        """Most-specific-wins winner for (item, country), or None when nothing governs.

        Inactive rules are skipped, as are rules pointing at a DEACTIVATED TaxCode —
        a code switched off in Accounting must stop resolving immediately, not keep
        flowing through whatever rule still references it. ``rules`` lets batch callers
        preload once per request (include tax_code in the select_related); bare calls
        stay self-loading for tests and one-off verbs.
        """
        if rules is None:
            rules = cls.objects.filter(tenant=tenant, is_active=True).select_related("item", "category", "tax_code")
        best = None
        best_key = None
        for rule in rules:
            if rule.tax_code_id and not rule.tax_code.is_active:
                continue
            if not rule.matches(item=item, country=country):
                continue
            key = (-rule._specificity(rule), rule.priority, rule.pk)
            if best is None or key < best_key:
                best, best_key = rule, key
        return best

    @classmethod
    def rate_for(cls, tenant, item=None, country="", *, rules=None):
        """The winning rule's rate_pct, or Decimal 0 when nothing governs."""
        from decimal import Decimal

        winner = cls.resolve(tenant, item=item, country=country, rules=rules)
        return winner.tax_code.rate_pct if winner is not None else Decimal("0")

    # -- guards ----------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}
        if self.item_id and self.item.tenant_id != self.tenant_id:
            errors["item"] = "That item belongs to another workspace."
        if self.category_id and self.category.tenant_id != self.tenant_id:
            errors["category"] = "That category belongs to another workspace."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.number or 'TRT'} · {self.name}"


def resolve_tax_rule(tenant, item=None, country="", *, rules=None):
    """Module-level alias kept next to the model so views/tests import one name."""
    return TaxRule.resolve(tenant, item=item, country=country, rules=rules)
