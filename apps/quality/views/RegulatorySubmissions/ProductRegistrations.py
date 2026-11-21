import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.RegulatorySubmissions.ProductRegistrations import ProductRegistrationForm
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import ProductRegistration
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmission
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def product_registration_list(request):
    base_qs = quality_scope(
        ProductRegistration.objects.all(),
        request,
    )

    today = timezone.now().date()
    in_90_days = today + timedelta(days=90)
    stats = base_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        expiring=Count(
            "id",
            filter=Q(
                status__in=["active", "pending_renewal"],
                expiration_date__lte=in_90_days,
                expiration_date__gte=today,
            ),
        ),
    )
    total_registrations = stats["total"]
    active_count = stats["active"]
    expiring_soon_count = stats["expiring"]

    qs = base_qs.select_related("regulatory_authority", "authorized_representative", "regulatory_lead", "linked_submission")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(registration_title__icontains=q)
            | Q(number__icontains=q)
            | Q(product_name__icontains=q)
            | Q(product_code__icontains=q)
            | Q(license_certificate_number__icontains=q)
            | Q(jurisdiction_country__icontains=q)
            | Q(establishment_id__icontains=q)
        )

    registration_type = request.GET.get("registration_type", "").strip()
    if registration_type:
        qs = qs.filter(registration_type=registration_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    regulatory_authority_id = request.GET.get("regulatory_authority", "").strip()
    if regulatory_authority_id.isdigit():
        qs = qs.filter(regulatory_authority_id=int(regulatory_authority_id))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    authorities = Party.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")

    context = {
        "page_obj": page_obj,
        "product_registrations": page_obj.object_list,
        "registration_type_choices": ProductRegistration.REGISTRATION_TYPE_CHOICES,
        "status_choices": ProductRegistration.STATUS_CHOICES,
        "authorities": authorities,
        "total_registrations": total_registrations,
        "active_count": active_count,
        "expiring_soon_count": expiring_soon_count,
        "search_query": q,
    }
    return render(
        request,
        "quality/regulatory_submissions/product_registration/list.html",
        context,
    )


@login_required
def product_registration_detail(request, pk):
    registration = quality_object(
        request,
        ProductRegistration,
        pk,
        select_related=("regulatory_authority", "authorized_representative", "regulatory_lead", "linked_submission"),
    )
    linked_commitments = registration.regulatory_commitments.filter(tenant=request.tenant).order_by("due_date")
    linked_pms_reports = registration.pms_reports.filter(tenant=request.tenant).order_by("-reporting_period_end")

    context = {
        "product_registration": registration,
        "linked_commitments": linked_commitments,
        "linked_pms_reports": linked_pms_reports,
    }
    return render(
        request,
        "quality/regulatory_submissions/product_registration/detail.html",
        context,
    )


@login_required
def product_registration_create(request):
    linked_sub_id = request.GET.get("submission")
    initial_data = {}
    if linked_sub_id and linked_sub_id.isdigit():
        sub = RegulatorySubmission.objects.filter(tenant=request.tenant, pk=int(linked_sub_id)).first()
        if sub:
            initial_data = {
                "linked_submission": sub,
                "product_name": sub.product_name,
                "product_code": sub.product_code,
                "regulatory_authority": sub.target_authority,
                "registration_title": f"Market Authorization — {sub.product_name}",
            }

    if request.method == "POST":
        form = ProductRegistrationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Product Registration {obj.number} created successfully.")
            return redirect("quality:product_registration_detail", pk=obj.pk)
    else:
        form = ProductRegistrationForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "quality/regulatory_submissions/product_registration/form.html",
        context,
    )


@login_required
def product_registration_edit(request, pk):
    registration = quality_object(request, ProductRegistration, pk)
    if request.method == "POST":
        form = ProductRegistrationForm(request.POST, instance=registration, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Product Registration {obj.number} updated successfully.")
            return redirect("quality:product_registration_detail", pk=obj.pk)
    else:
        form = ProductRegistrationForm(instance=registration, tenant=request.tenant)

    context = {
        "form": form,
        "product_registration": registration,
        "is_edit": True,
    }
    return render(
        request,
        "quality/regulatory_submissions/product_registration/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def product_registration_delete(request, pk):
    registration = quality_object(request, ProductRegistration, pk)
    num = registration.number
    write_audit_log(request.user, registration, "delete", tenant=request.tenant)
    registration.delete()
    messages.success(request, f"Product Registration {num} was deleted.")
    return redirect("quality:product_registration_list")


@login_required
def product_registration_export(request):
    write_audit_log(request.user, ProductRegistration(), "export", tenant=request.tenant)
    qs = (
        quality_scope(ProductRegistration.objects.all(), request)
        .select_related("regulatory_authority", "regulatory_lead")
        .defer("intended_purpose", "notes")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="product_registrations.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Registration Number",
        "Title",
        "Registration Type",
        "Jurisdiction / Country",
        "Regulatory Authority",
        "Product Name",
        "Product Code",
        "License / Certificate Number",
        "Establishment ID",
        "Status",
        "Initial Approval Date",
        "Effective Date",
        "Expiration Date",
        "Renewal Due Date",
        "Days to Expiration",
        "Regulatory Lead",
    ])

    for item in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.registration_title),
            _csv_safe(item.get_registration_type_display()),
            _csv_safe(item.jurisdiction_country),
            _csv_safe(item.regulatory_authority.name if item.regulatory_authority else ""),
            _csv_safe(item.product_name),
            _csv_safe(item.product_code),
            _csv_safe(item.license_certificate_number),
            _csv_safe(item.establishment_id),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.initial_approval_date),
            _csv_safe(item.effective_date),
            _csv_safe(item.expiration_date),
            _csv_safe(item.renewal_due_date),
            _csv_safe(item.days_to_expiration if item.days_to_expiration is not None else ""),
            _csv_safe(item.regulatory_lead.get_full_name() if item.regulatory_lead else ""),
        ])

    return response
