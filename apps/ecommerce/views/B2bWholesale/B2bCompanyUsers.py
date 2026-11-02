from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.B2bWholesale.B2bCompanyUsers import B2bCompanyUserForm
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bCompanyUsers import B2bCompanyUser
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def b2bcompanyuser_list(request):
    qs = ecommerce_scope(
        B2bCompanyUser.objects.select_related("company", "user", "party", "reports_to_approver"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
            | Q(company__company_name__icontains=q)
            | Q(job_title__icontains=q)
            | Q(department__icontains=q)
            | Q(number__icontains=q)
        )

    selected_role = request.GET.get("role", "").strip()
    if selected_role:
        qs = qs.filter(role=selected_role)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_company = request.GET.get("company", "").strip()
    if selected_company and selected_company.isdigit():
        qs = qs.filter(company_id=selected_company)

    stats = ecommerce_scope(B2bCompanyUser.objects.all(), request).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
    )
    total_count = stats["total"] or 0
    active_count = stats["active"] or 0

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    companies = ecommerce_scope(B2bCompanyAccount.objects.order_by("company_name"), request)

    context = {
        "company_users": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "role_choices": B2bCompanyUser.ROLE_CHOICES,
        "status_choices": B2bCompanyUser.STATUS_CHOICES,
        "companies": companies,
        "search_query": q,
        "selected_role": selected_role,
        "selected_status": selected_status,
        "selected_company": selected_company,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_user/list.html", context)


@login_required
def b2bcompanyuser_detail(request, pk):
    company_user = ecommerce_object(
        request,
        B2bCompanyUser,
        pk,
        select_related=("company", "user", "party", "reports_to_approver"),
    )

    subordinate_buyers = company_user.subordinate_buyers.select_related("user").order_by("user__username")

    context = {
        "company_user": company_user,
        "subordinate_buyers": subordinate_buyers,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_user/detail.html", context)


@login_required
@tenant_admin_required
def b2bcompanyuser_create(request):
    initial = {}
    company_id = request.GET.get("company")
    if company_id:
        initial["company"] = company_id

    if request.method == "POST":
        form = B2bCompanyUserForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cu = form.save(commit=False)
            cu.tenant = request.tenant
            cu.save()
            write_audit_log(
                request.user,
                cu,
                "create",
                {"number": cu.number, "username": cu.user.username},
                tenant=request.tenant,
            )
            messages.success(request, f"Company buyer {cu.user.username} added successfully.")
            return redirect("ecommerce:b2bcompanyuser_detail", pk=cu.pk)
    else:
        form = B2bCompanyUserForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "title": "Add Company Buyer / User",
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_user/form.html", context)


@login_required
@tenant_admin_required
def b2bcompanyuser_edit(request, pk):
    cu = ecommerce_object(request, B2bCompanyUser, pk)
    if request.method == "POST":
        form = B2bCompanyUserForm(request.POST, instance=cu, tenant=request.tenant)
        if form.is_valid():
            cu = form.save()
            write_audit_log(
                request.user,
                cu,
                "update",
                {"number": cu.number, "username": cu.user.username},
                tenant=request.tenant,
            )
            messages.success(request, f"Company buyer {cu.user.username} updated successfully.")
            return redirect("ecommerce:b2bcompanyuser_detail", pk=cu.pk)
    else:
        form = B2bCompanyUserForm(instance=cu, tenant=request.tenant)

    context = {
        "form": form,
        "company_user": cu,
        "title": f"Edit Company Buyer: {cu.user.username}",
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_company_user/form.html", context)


@login_required
@tenant_admin_required
def b2bcompanyuser_delete(request, pk):
    cu = ecommerce_object(request, B2bCompanyUser, pk)
    if request.method == "POST":
        username = cu.user.username
        co_name = cu.company.company_name
        num = cu.number
        cu.delete()
        write_audit_log(
            request.user,
            cu,
            "delete",
            {"number": num, "username": username, "company": co_name},
            tenant=request.tenant,
        )
        messages.success(request, f"Company buyer {username} has been removed.")
        return redirect("ecommerce:b2bcompanyuser_list")

    return render(
        request,
        "ecommerce/b2b_wholesale/b2b_company_user/detail.html",
        {"company_user": cu, "show_delete_confirm": True},
    )
