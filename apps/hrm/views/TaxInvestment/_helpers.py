"""HRM 3.16 Tax & Investment — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    InvestmentProof,
)


def _computation_breakdown(obj):
    """The derived tax breakdown for a TaxComputation, computed once (each property fires queries)."""
    return {
        "gross": obj.gross_annual_income,
        "hra_exemption": obj.hra_exemption,
        "chapter_via": obj.total_chapter_via_deductions,
        "capped_sections": obj.capped_sections,
        "taxable_old": obj.taxable_income_old,
        "taxable_new": obj.taxable_income_new,
        "tax_old": obj.tax_old_regime,
        "tax_new": obj.tax_new_regime,
        "cheaper": obj.cheaper_regime,
        "savings": abs(obj.tax_old_regime - obj.tax_new_regime),
    }


# ------------------------------------------------------ InvestmentProof (upload + verify)
def _proof_window_open(declaration):
    """True when the declaration's proof window is currently open (proofs upload even after the
    declaration itself is locked — the proof window is deliberately later than the declaration one)."""
    today = timezone.localdate()
    if declaration.proof_window_open and today < declaration.proof_window_open:
        return False
    if declaration.proof_window_close and today > declaration.proof_window_close:
        return False
    return True


def _set_proof_status(request, pk, status, *, reason=""):
    obj = get_object_or_404(
        InvestmentProof.objects.select_related("declaration_line"), pk=pk, tenant=request.tenant)
    # Only a pending/on-hold proof can be (re)decided — a verified/rejected proof is terminal and is not
    # re-transitioned via a stray POST (matches the template, which only exposes the buttons then).
    if obj.verification_status not in ("pending", "on_hold"):
        messages.error(request, "This proof has already been decided.")
        return obj, False
    obj.verification_status = status
    obj.verified_by = request.user
    obj.verified_at = timezone.now()
    obj.rejection_reason = reason
    obj.save(update_fields=["verification_status", "verified_by", "verified_at",
                            "rejection_reason", "updated_at"])
    # Roll the parent line's verified_amount up from its verified proofs.
    obj.declaration_line.recompute_verified()
    write_audit_log(request.user, obj, "update", {"action": f"proof_{status}"})
    return obj, True
