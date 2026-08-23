"""Inventory 5.10 Returns Management — DispositionRoutingRule and routing resolver.

**OWNERSHIP (L36/L29):**
SCM 4.10's ``ReturnDisposition`` executes physical restock or scrap transactions on the append-only
ledger. What 5.10 adds is the warehouse configuration rule engine: standing policies mapping
item/category + condition grade into suggested dispositions, target destination bins, and
supervisor sign-off requirements.
"""
from django.core.exceptions import ValidationError
from django.db import models

from apps.inventory.models._base import *  # noqa: F401,F403


class DispositionRoutingRule(TenantOwned):
    """Standing rule mapping item attributes and condition grade to destination warehouse routing."""

    GRADE_FILTER_CHOICES = [
        ("all", "All Condition Grades"),
        ("a", "Grade A — Like New"),
        ("b", "Grade B — Minor Wear / Refurbishable"),
        ("c", "Grade C — Heavy Wear / Secondary"),
        ("d", "Grade D — Defective / Unsellable"),
    ]

    DISPOSITION_SUGGESTION_CHOICES = [
        ("restock", "Restock into Sellable Inventory"),
        ("refurbish", "Route to Refurbishment / Testing"),
        ("scrap", "Route to Scrap / Disposal"),
        ("donate", "Route to Donation"),
        ("recycle", "Route to Recycling"),
        ("liquidate", "Route to Liquidation Channel"),
        ("return_to_vendor", "Return to Vendor (RTV / Warranty Claim)"),
        ("quarantine", "Quarantine Hold"),
    ]

    name = models.CharField(
        max_length=100,
        help_text="Descriptive rule name (e.g. 'Grade A Electronics Restock', 'Defective Audio Scrap')",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inventory_disposition_rules",
        help_text="Specific item SKU (blank for category or workspace-wide rule)",
    )
    category = models.ForeignKey(
        "scm.ItemCategory",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inventory_disposition_rules",
        help_text="Item category this rule applies to (blank if item-pinned or workspace-wide)",
    )
    condition_grade = models.CharField(
        max_length=4,
        choices=GRADE_FILTER_CHOICES,
        default="all",
        help_text="Condition grade condition matching this rule",
    )
    suggested_disposition = models.CharField(
        max_length=20,
        choices=DISPOSITION_SUGGESTION_CHOICES,
        default="restock",
        help_text="Recommended disposition action",
    )
    destination_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_disposition_rules",
        help_text="Suggested destination warehouse/zone/bin location for the routed items",
    )
    priority = models.PositiveIntegerField(
        default=10,
        help_text="Evaluation order — lower numbers fire first",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this rule is active in the routing engine",
    )
    requires_supervisor_approval = models.BooleanField(
        default=False,
        help_text="Flag requiring supervisor sign-off before executing this disposition",
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Internal routing guidelines or instructions for warehouse operators",
    )

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="inv_drr_tnt_act_pri_idx"),
            models.Index(fields=["tenant", "condition_grade"], name="inv_drr_tnt_grd_idx"),
        ]

    def __str__(self):
        return f"{self.name} (Priority {self.priority})"

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return

        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            raise ValidationError({"item": "Item belongs to another workspace."})
        if self.category_id and getattr(self.category, "tenant_id", None) != tenant_id:
            raise ValidationError({"category": "Category belongs to another workspace."})
        if self.destination_location_id and getattr(self.destination_location, "tenant_id", None) != tenant_id:
            raise ValidationError({"destination_location": "Destination location belongs to another workspace."})


def resolve_disposition_routing(item, condition_grade="a", category=None, *, rules=None, tenant=None):
    """Resolve the highest-priority matching disposition routing rule.

    Evaluation hierarchy:
    1. Specificity Tier:
       - Item match (tier 3)
       - Category match (tier 2)
       - Catch-all (tier 1)
    2. Grade Match: exact grade match preferred over 'all'
    3. Priority ASC
    4. ID ASC

    Returns:
        tuple (rule, suggested_disposition, destination_location, reason) or (None, None, None, reason)
    """
    if item is None:
        return None, None, None, "No item specified for disposition routing."

    effective_tenant = tenant or getattr(item, "tenant", None)
    if rules is None:
        if effective_tenant is None:
            return None, None, None, "No tenant context available."
        rules = list(
            DispositionRoutingRule.objects.filter(tenant=effective_tenant, is_active=True)
            .select_related("item", "category", "destination_location")
            .order_by("priority", "id")
        )
    elif effective_tenant is not None:
        # A caller-supplied list is trusted for ORDER, never for TENANCY — filter it here
        # so a future unfiltered caller cannot leak another workspace's routing rules.
        tenant_pk = getattr(effective_tenant, "pk", None)
        rules = [r for r in rules if r.tenant_id == tenant_pk]

    item_id = getattr(item, "pk", item)
    cat_id = getattr(category, "pk", getattr(item, "category_id", None))

    scored_matches = []
    for rule in rules:
        # Check grade match
        if rule.condition_grade not in ("all", condition_grade):
            continue

        # Check item / category tier
        if rule.item_id:
            if rule.item_id == item_id:
                tier = 3
            else:
                continue
        elif rule.category_id:
            if cat_id and rule.category_id == cat_id:
                tier = 2
            else:
                continue
        else:
            tier = 1  # Catch-all rule

        grade_specificity = 2 if rule.condition_grade == condition_grade else 1
        # Order by (-tier, -grade_specificity, priority, id)
        scored_matches.append((tier, grade_specificity, rule.priority, rule.id, rule))

    if not scored_matches:
        return None, None, None, "No active routing rule matches item and condition grade."

    scored_matches.sort(key=lambda x: (-x[0], -x[1], x[2], x[3]))
    best_rule = scored_matches[0][4]
    tier_name = "item rule" if best_rule.item_id else ("category rule" if best_rule.category_id else "catch-all rule")
    reason = f"Matched {tier_name} '{best_rule.name}' (priority {best_rule.priority})"

    return best_rule, best_rule.suggested_disposition, best_rule.destination_location, reason
