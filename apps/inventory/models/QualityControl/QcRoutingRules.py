"""Inventory 5.15 Quality Control (QC) & Inspection — QcRoutingRule + resolver.

**Inspection Routing** bullet: decide whether an inbound receipt goes STRAIGHT to storage
or detours through a QC zone first. Nothing else answers that question — SCM 4.9's plans
say *how* to inspect, 5.4's PutawayRules say *where* accepted goods bin out; this rule is
the gate BETWEEN them, and its ``qc_location`` is the zone goods wait in while the
checklist/inspection runs.

The engine is the deterministic most-specific-wins resolver the app already proved twice
(5.4 :func:`~apps.inventory.models.ReceivingPutaway.resolve_putaway_suggestion`, 5.10
:func:`~apps.inventory.models.ReturnsManagement.resolve_disposition_routing`): item tier (3)
beats category tier (2) beats catch-all (1); a vendor-pinned rule adds a specificity point
and only fires when that vendor's receipt is being judged — a vendor rule must never fire
blind on an unknown supplier; then priority ASC, id ASC. Overlapping rules are LEGAL — the
resolver decides, so there is no unique_together to brick legitimate configurations.

Zero stock effect: routing is advice for the receiving flow, not a movement.
"""
from django.core.exceptions import ValidationError

from apps.inventory.models._base import *  # noqa: F401,F403


class QcRoutingRule(TenantOwned):
    """Standing rule deciding if an inbound receipt inspects before putaway, and where."""

    VERDICT_CHOICES = [
        ("inspect", "Route via QC Zone"),
        ("bypass", "Straight to Storage"),
    ]

    name = models.CharField(max_length=100, help_text="e.g. 'ACME electronics inspect', 'Spare parts bypass'")
    item = models.ForeignKey(
        "scm.Item", on_delete=models.CASCADE, null=True, blank=True,
        related_name="inventory_qc_routing_rules",
        help_text="Specific product (blank for category or workspace-wide rule)")
    category = models.ForeignKey(
        "scm.ItemCategory", on_delete=models.CASCADE, null=True, blank=True,
        related_name="inventory_qc_routing_rules",
        help_text="Item category this rule applies to (blank if item-pinned or workspace-wide)")
    vendor = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inventory_qc_routing_rules",
        help_text="Only receipts from this supplier match; blank = any vendor")
    verdict = models.CharField(
        max_length=7, choices=VERDICT_CHOICES, default="inspect",
        help_text="Whether matching receipts detour through the QC zone")
    qc_location = models.ForeignKey(
        "scm.Location", on_delete=models.PROTECT, null=True, blank=True,
        related_name="inventory_qc_routing_rules",
        help_text="The restricted QC zone matching receipts wait in (required when verdict is inspect)")
    priority = models.PositiveIntegerField(default=10, help_text="Tie-breaker — lower numbers win")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="inv_qcr_tnt_act_pri_idx"),
            models.Index(fields=["tenant", "verdict"], name="inv_qcr_tnt_verdict_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_verdict_display()})"

    def clean(self):
        super().clean()
        tenant_id = getattr(self, "tenant_id", None)
        if not tenant_id:
            return
        errors = {}
        if self.item_id and getattr(self.item, "tenant_id", None) != tenant_id:
            errors["item"] = "That item belongs to another workspace."
        if self.category_id and getattr(self.category, "tenant_id", None) != tenant_id:
            errors["category"] = "That category belongs to another workspace."
        if self.vendor_id and getattr(self.vendor, "tenant_id", None) != tenant_id:
            errors["vendor"] = "That vendor belongs to another workspace."
        if self.qc_location_id:
            if getattr(self.qc_location, "tenant_id", None) != tenant_id:
                errors["qc_location"] = "That location belongs to another workspace."
        elif self.verdict == "inspect":
            # Keyed on the field the form renders, so a missing zone reads as
            # "required" instead of 500ing deep inside the resolver (review C1 pattern).
            errors["qc_location"] = "Name the QC zone goods are routed through for inspection."
        if errors:
            raise ValidationError(errors)


def resolve_qc_routing(item, vendor=None, *, rules=None, category=None):
    """Resolve which routing rule governs one inbound receipt line.

    Hierarchy: specificity tier DESC (item=3 > category=2 > catch-all=1) →
    vendor-specific beats vendor-agnostic → priority ASC → id ASC.
    A rule pinned to vendor V matches ONLY when ``vendor`` is that party.

    Returns ``(rule|None, verdict|None, qc_location|None, reason)`` — ``qc_location``
    is populated only for an ``inspect`` verdict, and every refusal starts
    ``"No Rule Matched"`` rather than guessing.
    """
    if item is None:
        return None, None, None, "No Rule Matched — no item specified."

    effective_tenant = getattr(item, "tenant", None)
    vendor_id = getattr(vendor, "pk", vendor)
    if rules is None:
        if effective_tenant is None:
            return None, None, None, "No Rule Matched — no tenant context available."
        rules = list(
            QcRoutingRule.objects.filter(tenant=effective_tenant, is_active=True)
            .select_related("item", "category", "vendor", "qc_location")
            .order_by("priority", "id")
        )
    elif effective_tenant is not None:
        # A caller-supplied list is trusted for ORDER, never for TENANCY.
        tenant_pk = getattr(effective_tenant, "pk", None)
        rules = [r for r in rules if r.tenant_id == tenant_pk]

    item_id = getattr(item, "pk", item)
    cat_id = getattr(category, "pk", getattr(item, "category_id", None))

    scored = []
    for rule in rules:
        if rule.vendor_id and rule.vendor_id != vendor_id:
            continue  # a vendor-pinned rule never fires for other/unknown suppliers
        if rule.item_id:
            if rule.item_id != item_id:
                continue
            tier = 3
        elif rule.category_id:
            if not cat_id or rule.category_id != cat_id:
                continue
            tier = 2
        else:
            tier = 1
        vendor_specificity = 2 if rule.vendor_id else 1
        scored.append((tier, vendor_specificity, rule.priority, rule.id, rule))

    if not scored:
        return None, None, None, "No Rule Matched — no active routing rule covers this receipt."

    scored.sort(key=lambda x: (-x[0], -x[1], x[2], x[3]))
    best = scored[0][4]
    scope = "item" if best.item_id else ("category" if best.category_id else "catch-all")
    pin = ", vendor-pinned" if best.vendor_id else ""
    reason = f"Matched {scope} rule '{best.name}' (priority {best.priority}){pin}"
    return best, best.verdict, (best.qc_location if best.verdict == "inspect" else None), reason
