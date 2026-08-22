"""Procurement 6.2 Requisition Management — RequisitionTemplates views.

**Requisition Templates** bullet: pre-defined forms for recurring orders. Full CRUD for the
blueprint (header + line formset), plus the Apply action that turns one into a fresh
``scm.PurchaseRequisition`` DRAFT under the signed-in user's name — the spine stays scm's (L36),
so applying is a write INTO ``scm`` tables inside one transaction, followed by the duplicate
check warning when a near-identical request already exists.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.crud import crud_delete, crud_list
from apps.procurement.forms import (
    RequisitionTemplateForm,
    RequisitionTemplateLineFormSet,
)
from apps.procurement.models import RequisitionTemplate
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import DUPLICATE_WINDOW_DAYS, find_duplicate_requisitions
from apps.scm.models import PurchaseRequisition, PurchaseRequisitionLine


@login_required
def template_list(request):
    qs = RequisitionTemplate.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "procurement/requisitionmanagement/templates/list.html",
        search_fields=["number", "name", "description"],
        filters=[("is_active", "is_active", False)],
        extra_context={"status_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@login_required
def template_detail(request, pk):
    obj = get_object_or_404(
        RequisitionTemplate.objects.select_related("org_unit", "currency", "created_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "procurement/requisitionmanagement/templates/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("gl_account"),
    })


@login_required
def template_create(request):
    return _template_form(request, instance=None)


@login_required
def template_edit(request, pk):
    obj = get_object_or_404(RequisitionTemplate, pk=pk, tenant=request.tenant)
    return _template_form(request, instance=obj)


def _template_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating templates.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = RequisitionTemplateForm(request.POST, request.FILES, instance=instance,
                                       tenant=request.tenant)
        formset = RequisitionTemplateLineFormSet(request.POST, instance=instance,
                                                 form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                template = form.save(commit=False)
                template.tenant = request.tenant
                if not is_edit:
                    template.created_by = request.user
                template.save()
                formset.instance = template
                formset.save()
            write_audit_log(request.user, template, "update" if is_edit else "create")
            messages.success(request, f"Template {template.number or template.name} saved.")
            return redirect("procurement:template_detail", pk=template.pk)
    else:
        form = RequisitionTemplateForm(instance=instance, tenant=request.tenant)
        formset = RequisitionTemplateLineFormSet(instance=instance,
                                                 form_kwargs={"tenant": request.tenant})
    return render(request, "procurement/requisitionmanagement/templates/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
@require_POST
def template_delete(request, pk):
    """A template is referenced by nothing (apply COPIES it), so deletion is always safe."""
    return crud_delete(request, model=RequisitionTemplate, pk=pk,
                       success_url="procurement:template_list")


@login_required
@require_POST
def template_apply(request, pk):
    """Turn a template into a fresh draft requisition on the scm spine.

    Everything sensitive defaults safely — requester is the SIGNED-IN user (never choosable),
    status starts at ``draft`` so 4.1's approval workflow still sees it, and the total comes from
    ``recalc_totals()`` rather than any stored figure. If the freshly drafted requisition looks
    like an existing recent request, the duplicate check says so right away.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before raising requisitions.")
        return redirect("dashboard:home")
    template = get_object_or_404(RequisitionTemplate, pk=pk, tenant=request.tenant)
    lines = list(template.lines.all())
    if not lines:
        messages.error(request, "This template has no lines — add at least one before applying.")
        return redirect("procurement:template_detail", pk=pk)

    with transaction.atomic():
        req = PurchaseRequisition.objects.create(
            tenant=request.tenant,
            title=template.name[:255],
            requester=request.user,
            org_unit=template.org_unit,
            currency=template.currency,
            required_by=(timezone.now().date() + timedelta(days=template.default_lead_days))
            if template.default_lead_days else None,
            justification=template.justification or "",
        )
        # Individual creates, NOT bulk_create: the spine line derives its stored ``line_total``
        # inside save(), which bulk_create silently bypasses — the header total would read zero.
        for line in lines:
            PurchaseRequisitionLine.objects.create(
                requisition=req,
                item_description=line.item_description,
                sku_hint=line.sku_hint or "",
                uom_hint=line.uom_hint or "",
                quantity=line.quantity,
                estimated_unit_price=line.estimated_unit_price,
                gl_account_id=line.gl_account_id,
            )
        req.recalc_totals()
    write_audit_log(request.user, req, "create", {"from_template": template.number})

    duplicates = find_duplicate_requisitions(req)
    messages.success(request, f"Requisition {req.number} drafted from template "
                              f"{template.number} — review and submit it for approval when ready.")
    if duplicates:
        matches = ", ".join(d["requisition"].number or str(d["requisition"].pk)
                            for d in duplicates)
        messages.warning(request,
                         f"Heads-up: this looks similar to {len(duplicates)} recent request(s) "
                         f"({matches}) within the last {DUPLICATE_WINDOW_DAYS} days — check "
                         f"before submitting.")
    return redirect("procurement:req_detail", pk=req.pk)
