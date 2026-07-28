"""SCM 4.10 Returns Management — ReturnPolicy form (the published promise)."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import ReturnPolicy

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


class ReturnPolicyForm(TenantModelForm):
    """Every field is user-owned. ``item_category`` is auto-scoped by ``TenantModelForm`` because
    ``scm.ItemCategory`` has its own ``tenant`` column; ``ItemCategory.__str__`` is a plain name
    with no FK walk, so no ``select_related`` is needed here (§7.6 applies to the dropdowns whose
    target's ``__str__`` reaches through a second FK — those are on the RMA and bench forms)."""

    class Meta:
        model = ReturnPolicy
        fields = ["name", "is_active", "is_default", "priority", "item_category",
                  "window_basis", "window_days", "require_delivery_confirmation", "fallback_days",
                  "allow_refund", "allow_store_credit", "allow_exchange", "allow_keep_item",
                  "refund_basis", "refund_pct", "restocking_fee_type", "restocking_fee_value",
                  "return_shipping_paid_by", "auto_approve",
                  "grade_a_cost_pct", "grade_b_cost_pct", "grade_c_cost_pct", "grade_d_cost_pct",
                  "warranty_window_days", "return_to_address", "portal_instructions"]
        widgets = {
            "return_to_address": forms.Textarea(attrs={"rows": 4}),
            "portal_instructions": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("refund_basis") == "percentage" and (cleaned.get("refund_pct") or ZERO) <= ZERO:
            self.add_error("refund_pct",
                           "A percentage refund of 0% refunds nothing — set a percentage or "
                           "change the basis to 'No refund'.")
        fee_type = cleaned.get("restocking_fee_type")
        fee_value = cleaned.get("restocking_fee_value") or ZERO
        if fee_type and fee_type != "none" and fee_value <= ZERO:
            self.add_error("restocking_fee_value",
                           "A restocking fee is configured but its value is zero.")
        if fee_type == "percent_of_value" and fee_value > ONE_HUNDRED:
            self.add_error("restocking_fee_value",
                           "A percentage restocking fee cannot exceed 100%.")
        if (cleaned.get("window_days") or 0) == 0 and (cleaned.get("fallback_days") or 0) == 0:
            self.add_error("window_days",
                           "A zero-day window on both the basis and the fallback accepts no "
                           "return at all.")
        # The grade ladder should not go UP as condition goes down. Not fatal — a tenant may have a
        # genuine reason — so it flags the field it is about rather than blocking the save.
        grades = [cleaned.get(f"grade_{g}_cost_pct") for g in ("a", "b", "c", "d")]
        if all(g is not None for g in grades) and grades != sorted(grades, reverse=True):
            self.add_error("grade_b_cost_pct",
                           "The grade ladder rises as the condition falls — a B-grade unit worth "
                           "more than an A-grade one will write returns UP in value.")
        return cleaned
