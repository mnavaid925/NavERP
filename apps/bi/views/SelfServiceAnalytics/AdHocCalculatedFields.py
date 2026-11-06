from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.SelfServiceAnalytics.AdHocCalculatedFields import AdHocCalculatedFieldForm
from apps.bi.models.SelfServiceAnalytics.AdHocCalculatedFields import AdHocCalculatedField
from apps.bi.models.SelfServiceAnalytics.AdHocQueries import AdHocQuery
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def ad_hoc_calculated_field_list(request):
    qs = bi_scope(AdHocCalculatedField.objects.all(), request, owner_field="created_by").select_related(
        "query", "created_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(display_label__icontains=q) | qs.filter(field_name__icontains=q) | qs.filter(formula_expression__icontains=q)

    return_type = request.GET.get("return_type", "").strip()
    if return_type:
        qs = qs.filter(return_type=return_type)

    query_filter = request.GET.get("query", "").strip()
    if query_filter and query_filter.isdigit():
        qs = qs.filter(query_id=int(query_filter))

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "bi/self_service_analytics/ad_hoc_calculated_field/list.html",
        {
            "calculated_fields": page_obj.object_list,
            "page_obj": page_obj,
            "return_type_choices": AdHocCalculatedField.RETURN_TYPE_CHOICES,
            "query_filter": query_filter,
        },
    )


@login_required
def ad_hoc_calculated_field_detail(request, pk):
    cf = bi_object(
        request,
        AdHocCalculatedField,
        pk,
        select_related=("query", "created_by"),
    )
    return render(
        request,
        "bi/self_service_analytics/ad_hoc_calculated_field/detail.html",
        {
            "calculated_field": cf,
            "query": cf.query,
        },
    )


@login_required
def ad_hoc_calculated_field_create(request):
    initial = {}
    q_param = request.GET.get("query")
    if q_param and q_param.isdigit():
        initial["query"] = int(q_param)

    if request.method == "POST":
        form = AdHocCalculatedFieldForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cf = form.save(commit=False)
            cf.tenant = request.tenant
            cf.created_by = request.user
            cf.save()

            write_audit_log(
                user=request.user,
                obj=cf,
                action="create",
                tenant=request.tenant,
                changes={"description": f"Created custom calculated field {cf.display_label} ({cf.number})"},
            )
            messages.success(request, f"Calculated field '{cf.display_label}' created successfully.")
            return redirect("bi:ad_hoc_calculated_field_detail", pk=cf.pk)
    else:
        form = AdHocCalculatedFieldForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "bi/self_service_analytics/ad_hoc_calculated_field/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def ad_hoc_calculated_field_edit(request, pk):
    cf = bi_object(request, AdHocCalculatedField, pk)

    if request.method == "POST":
        form = AdHocCalculatedFieldForm(request.POST, instance=cf, tenant=request.tenant)
        if form.is_valid():
            cf = form.save()
            write_audit_log(
                user=request.user,
                obj=cf,
                action="update",
                tenant=request.tenant,
                changes={"description": f"Updated calculated field {cf.display_label} ({cf.number})"},
            )
            messages.success(request, f"Calculated field '{cf.display_label}' updated successfully.")
            return redirect("bi:ad_hoc_calculated_field_detail", pk=cf.pk)
    else:
        form = AdHocCalculatedFieldForm(instance=cf, tenant=request.tenant)

    return render(
        request,
        "bi/self_service_analytics/ad_hoc_calculated_field/form.html",
        {
            "form": form,
            "calculated_field": cf,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def ad_hoc_calculated_field_delete(request, pk):
    cf = bi_object(request, AdHocCalculatedField, pk)
    query_pk = cf.query_id
    label = cf.display_label
    number = cf.number

    write_audit_log(
        user=request.user,
        obj=cf,
        action="delete",
        tenant=request.tenant,
        changes={"description": f"Deleted calculated field {label} ({number})"},
    )
    cf.delete()
    messages.success(request, f"Calculated field '{label}' ({number}) deleted.")
    return redirect("bi:ad_hoc_calculated_field_list")


@login_required
def ad_hoc_calculated_field_validate(request):
    formula = request.GET.get("formula", "").strip()
    is_valid = True
    errors = []

    if not formula:
        return JsonResponse({"valid": False, "errors": ["Empty formula expression"]})

    if formula.count("[") != formula.count("]"):
        is_valid = False
        errors.append("Unbalanced bracket tokens")

    if formula.count("(") != formula.count(")"):
        is_valid = False
        errors.append("Unbalanced parentheses")

    return JsonResponse({"valid": is_valid, "errors": errors})
