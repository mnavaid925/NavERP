"""SCM 4.2 SRM — SupplierContract views (incl. renewal-alert lifecycle)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant, _supplier_parties
from apps.scm.models import SupplierContract
from apps.scm.forms import SupplierContractForm


@login_required
def contract_list(request):
    qs = SupplierContract.objects.filter(tenant=request.tenant).select_related("party", "currency")
    # Keep the date-derived status honest on every list load (expiring/expired move silently with time).
    for c in qs.filter(status__in=SupplierContract.AUTO_STATUSES):
        c.refresh_status()
    return crud_list(
        request, qs, "scm/srm/contract/list.html",
        search_fields=["number", "title", "party__name"],
        filters=[("status", "status", False), ("contract_type", "contract_type", False),
                 ("party", "party_id", True)],
        extra_context={
            "status_choices": SupplierContract.STATUS_CHOICES,
            "type_choices": SupplierContract.TYPE_CHOICES,
            "parties": _supplier_parties(request.tenant),
        },
    )


@login_required
def contract_create(request):
    if _need_tenant(request):
        return redirect("scm:contract_list")
    return crud_create(
        request, form_class=SupplierContractForm,
        template="scm/srm/contract/form.html", success_url="scm:contract_list",
    )


@login_required
def contract_edit(request, pk):
    obj = get_object_or_404(SupplierContract, pk=pk, tenant=request.tenant)
    if obj.status in ("terminated", "expired"):
        messages.error(request, "A terminated or expired contract can't be edited.")
        return redirect("scm:contract_detail", pk=pk)
    return crud_edit(
        request, model=SupplierContract, pk=pk, form_class=SupplierContractForm,
        template="scm/srm/contract/form.html", success_url="scm:contract_list",
    )


@login_required
def contract_detail(request, pk):
    obj = get_object_or_404(
        SupplierContract.objects.select_related("party", "currency", "payment_terms", "document"),
        pk=pk, tenant=request.tenant)
    obj.refresh_status()
    return render(request, "scm/srm/contract/detail.html", {
        "obj": obj,
        "days_to_expiry": obj.days_to_expiry(),
        "expiring_soon": obj.is_expiring_soon(),
    })


@login_required
@require_POST
def contract_delete(request, pk):
    obj = get_object_or_404(SupplierContract, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft contract can be deleted — terminate an active one instead.")
        return redirect("scm:contract_detail", pk=pk)
    return crud_delete(request, model=SupplierContract, pk=pk, success_url="scm:contract_list")


@login_required
@require_POST
def contract_activate(request, pk):
    obj = get_object_or_404(SupplierContract, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "This contract is already active or decided.")
        return redirect("scm:contract_detail", pk=pk)
    obj.status = "active"
    obj.save(update_fields=["status", "updated_at"])
    obj.refresh_status()  # may immediately be 'expiring'/'expired' given its dates
    write_audit_log(request.user, obj, "update", {"action": "activate"})
    messages.success(request, f"Contract {obj.number} activated.")
    return redirect("scm:contract_detail", pk=pk)


@login_required
@require_POST
def contract_renew(request, pk):
    """Mark the current contract renewed and open a fresh draft carrying its terms forward."""
    obj = get_object_or_404(SupplierContract, pk=pk, tenant=request.tenant)
    if obj.status not in ("active", "expiring", "expired"):
        messages.error(request, "Only an active, expiring or expired contract can be renewed.")
        return redirect("scm:contract_detail", pk=pk)
    with transaction.atomic():
        new = SupplierContract(
            tenant=request.tenant, party=obj.party, title=f"{obj.title} (renewal)",
            contract_type=obj.contract_type, status="draft", contract_value=obj.contract_value,
            currency=obj.currency, payment_terms=obj.payment_terms, auto_renew=obj.auto_renew,
            renewal_notice_days=obj.renewal_notice_days, terms_summary=obj.terms_summary,
            notes=f"Renewed from {obj.number}.",
        )
        new.save()
        obj.status = "renewed"
        obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "renew", "new_contract": new.number})
    write_audit_log(request.user, new, "create", {"renewed_from": obj.number})
    messages.success(request, f"Contract {obj.number} renewed — draft {new.number} created.")
    return redirect("scm:contract_detail", pk=new.pk)


@tenant_admin_required
@require_POST
def contract_terminate(request, pk):
    """Terminate a contract early. Tenant-admin gated + reason-required."""
    obj = get_object_or_404(SupplierContract, pk=pk, tenant=request.tenant)
    if obj.status in ("terminated", "expired", "renewed"):
        messages.info(request, "This contract is already closed.")
        return redirect("scm:contract_detail", pk=pk)
    reason = (request.POST.get("termination_reason") or "").strip()
    if not reason:
        messages.error(request, "Give a reason when terminating a contract.")
        return redirect("scm:contract_detail", pk=pk)
    obj.status = "terminated"
    obj.terminated_at = timezone.now()
    obj.termination_reason = reason[:2000]
    obj.save(update_fields=["status", "terminated_at", "termination_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "terminate"})
    messages.success(request, f"Contract {obj.number} terminated.")
    return redirect("scm:contract_detail", pk=pk)
