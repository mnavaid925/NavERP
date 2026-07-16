"""HRM 3.16 Tax & Investment — Investmentproof views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.TaxInvestment._helpers import _proof_window_open, _set_proof_status
from apps.hrm.models import (
    InvestmentDeclarationLine,
    InvestmentProof,
)
from apps.hrm.forms import (
    InvestmentProofForm,
)
from apps.hrm.views.TaxInvestment._helpers import _proof_window_open, _set_proof_status


@login_required
def investmentproof_upload(request, line_pk):
    line = get_object_or_404(
        InvestmentDeclarationLine.objects.select_related("declaration"), pk=line_pk, tenant=request.tenant)
    declaration = line.declaration
    # Gate on the PROOF window (not is_editable) — proofs are typically uploaded after the declaration
    # is locked. If no window is configured, allow (draft/open by default).
    if not _proof_window_open(declaration):
        messages.error(request, "The proof-submission window for this declaration is not open.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    if request.method == "POST":
        form = InvestmentProofForm(
            request.POST, request.FILES,
            instance=InvestmentProof(tenant=request.tenant, declaration_line=line),
            tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, declaration, "update", {"action": "proof_upload"})
            messages.success(request, "Proof uploaded.")
            return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    else:
        form = InvestmentProofForm(tenant=request.tenant)
    return render(request, "hrm/tax/investmentproof/form.html",
                  {"form": form, "line": line, "declaration": declaration})


@login_required
def investmentproof_list(request):
    return crud_list(
        request,
        InvestmentProof.objects.filter(tenant=request.tenant)
        .select_related("declaration_line__declaration__employee__party"),
        "hrm/tax/investmentproof/list.html",
        search_fields=["title"],
        filters=[("verification_status", "verification_status", False)],
        extra_context={"verification_status_choices": InvestmentProof.VERIFICATION_STATUS_CHOICES},
    )


@login_required
def investmentproof_detail(request, pk):
    obj = get_object_or_404(
        InvestmentProof.objects.select_related(
            "declaration_line__declaration__employee__party", "verified_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/investmentproof/detail.html", {"obj": obj})


@tenant_admin_required
@require_POST
def investmentproof_verify(request, pk):
    obj, changed = _set_proof_status(request, pk, "verified")
    if changed:
        messages.success(request, "Proof verified.")
    return redirect("hrm:investmentproof_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def investmentproof_reject(request, pk):
    obj, changed = _set_proof_status(request, pk, "rejected",
                                     reason=request.POST.get("rejection_reason", "").strip()[:2000])
    if changed:
        messages.success(request, "Proof rejected.")
    return redirect("hrm:investmentproof_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def investmentproof_on_hold(request, pk):
    obj, changed = _set_proof_status(request, pk, "on_hold",
                                     reason=request.POST.get("rejection_reason", "").strip()[:2000])
    if changed:
        messages.success(request, "Proof put on hold.")
    return redirect("hrm:investmentproof_detail", pk=obj.pk)
