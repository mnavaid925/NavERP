"""HRM 3.16 Tax & Investment — Investmentdeclaration views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    InvestmentDeclaration,
    InvestmentDeclarationLine,
    InvestmentProof,
)
from apps.hrm.forms import (
    InvestmentDeclarationForm,
    InvestmentDeclarationLineForm,
)


# --------------------------------------------- InvestmentDeclaration (+ inline lines)
@login_required
def investmentdeclaration_list(request):
    return crud_list(
        request,
        InvestmentDeclaration.objects.filter(tenant=request.tenant).select_related("employee__party"),
        "hrm/tax/investmentdeclaration/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("financial_year", "financial_year", False), ("regime_elected", "regime_elected", False),
                 ("status", "status", False), ("employee", "employee_id", True)],
        extra_context={
            "status_choices": InvestmentDeclaration.STATUS_CHOICES,
            "regime_choices": InvestmentDeclaration.REGIME_CHOICES,
            "employees": EmployeeProfile.objects.filter(tenant=request.tenant).select_related("party"),
        },
    )


@login_required
def investmentdeclaration_create(request):
    return crud_create(request, form_class=InvestmentDeclarationForm,
                       template="hrm/tax/investmentdeclaration/form.html",
                       success_url="hrm:investmentdeclaration_list")


@login_required
def investmentdeclaration_detail(request, pk):
    obj = get_object_or_404(
        InvestmentDeclaration.objects.select_related("employee__party"), pk=pk, tenant=request.tenant)
    lines = obj.lines.order_by("section_code")
    # Flat proofs list (across all lines) so the proofs table can use a single {% empty %} — a nested
    # loop can't tell "no lines" from "lines but no proofs".
    proofs = (InvestmentProof.objects.filter(declaration_line__declaration=obj)
              .select_related("declaration_line")
              .order_by("declaration_line__section_code", "-created_at"))
    return render(request, "hrm/tax/investmentdeclaration/detail.html", {
        "obj": obj,
        "lines": lines,
        "proofs": proofs,
        "line_form": InvestmentDeclarationLineForm(tenant=request.tenant),
    })


@login_required
def investmentdeclaration_edit(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft declaration can be edited.")
        return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)
    return crud_edit(request, model=InvestmentDeclaration, pk=pk, form_class=InvestmentDeclarationForm,
                     template="hrm/tax/investmentdeclaration/form.html",
                     success_url="hrm:investmentdeclaration_list")


@login_required
@require_POST
def investmentdeclaration_delete(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft declaration can be deleted.")
        return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)
    # TaxComputation.declaration is PROTECT — pre-check for a friendly message (mirrors paycomponent_delete).
    if obj.tax_computations.exists():
        messages.error(request, "This declaration has a linked tax computation and cannot be deleted.")
        return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)
    return crud_delete(request, model=InvestmentDeclaration, pk=pk,
                       success_url="hrm:investmentdeclaration_list")


@login_required
@require_POST
def investmentdeclaration_submit(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "submitted"
        obj.submitted_at = timezone.now()
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Declaration {obj.number} submitted.")
    return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def investmentdeclaration_lock(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if obj.status == "submitted":
        obj.status = "locked"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "lock"})
        messages.success(request, f"Declaration {obj.number} locked.")
    return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)


@login_required
@require_POST
def investmentdeclarationline_create(request, declaration_pk):
    declaration = get_object_or_404(InvestmentDeclaration, pk=declaration_pk, tenant=request.tenant)
    if not declaration.is_editable:
        messages.error(request, "Lines can only be added while the declaration is a draft.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    form = InvestmentDeclarationLineForm(
        request.POST,
        instance=InvestmentDeclarationLine(tenant=request.tenant, declaration=declaration),
        tenant=request.tenant)
    if form.is_valid():
        try:
            # Savepoint so a duplicate-section IntegrityError rolls back only this insert instead of
            # poisoning the whole request transaction (which would 500/400 the end-of-request commit).
            with transaction.atomic():
                form.save()
            write_audit_log(request.user, declaration, "update", {"action": "line_add"})
            messages.success(request, "Declaration line added.")
        except IntegrityError:
            messages.error(request, "A line for that section already exists on this declaration.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)


@login_required
def investmentdeclarationline_edit(request, declaration_pk, pk):
    declaration = get_object_or_404(InvestmentDeclaration, pk=declaration_pk, tenant=request.tenant)
    line = get_object_or_404(InvestmentDeclarationLine, pk=pk, tenant=request.tenant, declaration=declaration)
    if not declaration.is_editable:
        messages.error(request, "Lines can only be edited while the declaration is a draft.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    if request.method == "POST":
        form = InvestmentDeclarationLineForm(request.POST, instance=line, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, declaration, "update", {"action": "line_edit"})
            messages.success(request, "Declaration line updated.")
            return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    else:
        form = InvestmentDeclarationLineForm(instance=line, tenant=request.tenant)
    return render(request, "hrm/tax/investmentdeclaration/line_form.html",
                  {"form": form, "obj": line, "declaration": declaration, "is_edit": True})


@login_required
@require_POST
def investmentdeclarationline_delete(request, declaration_pk, pk):
    declaration = get_object_or_404(InvestmentDeclaration, pk=declaration_pk, tenant=request.tenant)
    line = get_object_or_404(InvestmentDeclarationLine, pk=pk, tenant=request.tenant, declaration=declaration)
    if not declaration.is_editable:
        messages.error(request, "Lines can only be removed while the declaration is a draft.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    line.delete()
    write_audit_log(request.user, declaration, "update", {"action": "line_delete"})
    messages.success(request, "Declaration line removed.")
    return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
