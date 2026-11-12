"""Function-based views for Asset Operator Certifications & Training Records (11.16)."""

import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDocumentKnowledge.AssetOperatorCertifications import (
    AssetOperatorCertificationForm,
)
from apps.assets.models.AssetDocumentKnowledge.AssetOperatingProcedures import (
    AssetOperatingProcedure,
)
from apps.assets.models.AssetDocumentKnowledge.AssetOperatorCertifications import (
    AssetOperatorCertification,
)
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetDocumentKnowledge._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_tenant_admin_user,
    serve_protected_attachment,
)
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.scm.models.AssetManagement.Assets import Asset


def _add_one_year(base_date):
    """Advance a calendar date by 1 year safely handling Feb 29."""
    target_year = base_date.year + 1
    day = min(base_date.day, calendar.monthrange(target_year, base_date.month)[1])
    return date(target_year, base_date.month, day)


_CERT_LIST_SELECT_RELATED = (
    "operator_party",
    "operator_user",
    "employee_profile__party",
    "operational_asset",
    "asset_category",
    "operating_procedure",
)
_CERT_EXPORT_SELECT_RELATED = (
    "operator_party",
    "operator_user",
    "employee_profile__party",
    "operating_procedure",
)


def _filter_certification_queryset(
    request, base_qs, select_related=_CERT_LIST_SELECT_RELATED
):
    """Apply search and dropdown GET filters to AssetOperatorCertification queryset."""
    qs = base_qs.select_related(*select_related) if select_related else base_qs
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(qualification_code__icontains=search_query)
            | Q(certificate_reference__icontains=search_query)
            | Q(issuing_authority__icontains=search_query)
            | Q(operator_party__name__icontains=search_query)
            | Q(operator_user__username__icontains=search_query)
            | Q(operator_user__first_name__icontains=search_query)
            | Q(operator_user__last_name__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "qualification_type",
        allowed_values={
            val for val, _ in AssetOperatorCertification.QUALIFICATION_TYPE_CHOICES
        },
    )
    qs = apply_choice_filter(
        qs,
        request,
        "proficiency_level",
        allowed_values={
            val for val, _ in AssetOperatorCertification.PROFICIENCY_LEVEL_CHOICES
        },
    )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in AssetOperatorCertification.STATUS_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "operational_asset")
    qs = apply_fk_filter(qs, request, "operating_procedure")
    return qs


@login_required
def asset_operator_certification_list(request):
    """Operator qualification, LOTO competency, and expiry tracking list view."""
    base_qs = assets_scope(AssetOperatorCertification.objects.all(), request)
    filtered_qs = _filter_certification_queryset(request, base_qs).defer("notes")
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    kpis = base_qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        expiring_soon_count=Count("id", filter=Q(status="expiring_soon")),
        expired_count=Count("id", filter=Q(status="expired")),
    )

    context = {
        "certifications": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": kpis["total_count"] or 0,
        "active_count": kpis["active_count"] or 0,
        "expiring_soon_count": kpis["expiring_soon_count"] or 0,
        "expired_count": kpis["expired_count"] or 0,
        "qualification_type_choices": AssetOperatorCertification.QUALIFICATION_TYPE_CHOICES,
        "proficiency_choices": AssetOperatorCertification.PROFICIENCY_LEVEL_CHOICES,
        "status_choices": AssetOperatorCertification.STATUS_CHOICES,
        "assets_list": Asset.objects.filter(tenant=request.tenant).order_by("name"),
        "procedures": AssetOperatingProcedure.objects.filter(
            tenant=request.tenant
        ).order_by("number"),
        "can_manage": is_tenant_admin_user(request.user),
        "search_query": request.GET.get("q", "").strip(),
    }
    return render(
        request,
        "assets/assetdocumentknowledge/asset_operator_certification/list.html",
        context,
    )


@login_required
def asset_operator_certification_export_csv(request):
    """Export filtered tenant operator certifications as a hardened CSV download."""
    base_qs = assets_scope(AssetOperatorCertification.objects.all(), request)
    filtered_qs = (
        _filter_certification_queryset(
            request, base_qs, select_related=_CERT_EXPORT_SELECT_RELATED
        )
        .only(
            "id",
            "number",
            "title",
            "qualification_code",
            "qualification_type",
            "proficiency_level",
            "sop_acknowledged",
            "issued_date",
            "expires_on",
            "status",
            "operator_party",
            "operator_user",
            "employee_profile",
            "employee_profile__party",
            "operating_procedure",
        )[:10000]
        .iterator(chunk_size=1000)
    )
    headers = [
        "Cert #",
        "Title",
        "Operator",
        "Qual Code",
        "Qual Type",
        "Proficiency",
        "SOP Linked",
        "SOP Ack?",
        "Issued",
        "Expires On",
        "Status",
    ]
    rows = (
        [
            cert.number,
            cert.title,
            cert.operator_display_name,
            cert.qualification_code,
            cert.get_qualification_type_display(),
            cert.get_proficiency_level_display(),
            cert.operating_procedure.number if cert.operating_procedure else "",
            "Yes" if cert.sop_acknowledged else "No",
            cert.issued_date.isoformat() if cert.issued_date else "",
            cert.expires_on.isoformat() if cert.expires_on else "",
            cert.get_status_display(),
        ]
        for cert in filtered_qs
    )
    return csv_export_response(
        filename="asset_operator_certifications_11_16.csv",
        headers=headers,
        rows=rows,
    )


@login_required
def asset_operator_certification_detail(request, pk):
    """Operator certification detail view showing verification, SOP sign-off, and renewal state."""
    cert = assets_object(
        request,
        AssetOperatorCertification,
        pk,
        select_related=(
            "org_unit",
            "operator_party",
            "operator_user",
            "employee_profile__party",
            "hrm_certificate__employee__party",
            "issuing_party",
            "assessor",
            "operational_asset",
            "asset_category",
            "asset_model",
            "operating_procedure",
            "compliance_framework",
        ),
    )
    is_admin = is_tenant_admin_user(request.user)
    context = {
        "certification": cert,
        "can_edit": is_admin and cert.status in AssetOperatorCertification.EDITABLE_STATUSES,
        "can_verify": is_admin and cert.status == "pending",
        "can_acknowledge_sop": (
            (cert.operator_user_id == request.user.id or is_admin)
            and cert.status != "revoked"
            and not cert.sop_acknowledged
        ),
        "can_renew": is_admin and cert.status in ("active", "expiring_soon", "expired"),
        "can_revoke": is_admin and cert.status != "revoked",
    }
    return render(
        request,
        "assets/assetdocumentknowledge/asset_operator_certification/detail.html",
        context,
    )


@login_required
def asset_operator_certification_create(request):
    """Register a new operator training/competency certification in Pending Verification."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating a certification.")
        return redirect("assets:asset_operator_certification_list")
    if request.method == "POST":
        form = AssetOperatorCertificationForm(
            request.POST, request.FILES, tenant=request.tenant
        )
        if form.is_valid():
            cert = form.save(commit=False)
            cert.tenant = request.tenant
            cert.status = "pending"
            cert.save()
            write_audit_log(request.user, cert, "create", tenant=request.tenant)
            messages.success(request, f"Created certification {cert.number}.")
            return redirect(
                "assets:asset_operator_certification_detail", pk=cert.pk
            )
    else:
        form = AssetOperatorCertificationForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetdocumentknowledge/asset_operator_certification/form.html",
        {
            "form": form,
            "certification": None,
            "is_edit": False,
            "title": "New Operator Certification",
        },
    )


@login_required
@tenant_admin_required
def asset_operator_certification_edit(request, pk):
    """Edit an editable (non-revoked/non-expired) operator certification."""
    cert = assets_object(request, AssetOperatorCertification, pk)
    if cert.status not in AssetOperatorCertification.EDITABLE_STATUSES:
        messages.warning(
            request,
            f"Certification {cert.number} is {cert.get_status_display()} and cannot be edited directly. Use Renew if expired.",
        )
        return redirect("assets:asset_operator_certification_detail", pk=cert.pk)

    if request.method == "POST":
        form = AssetOperatorCertificationForm(
            request.POST,
            request.FILES,
            instance=cert,
            tenant=request.tenant,
        )
        if form.is_valid():
            updated = form.save()
            updated.sync_expiry_status(save=True)
            write_audit_log(request.user, updated, "update", tenant=request.tenant)
            messages.success(request, f"Updated certification {updated.number}.")
            return redirect(
                "assets:asset_operator_certification_detail", pk=updated.pk
            )
    else:
        form = AssetOperatorCertificationForm(instance=cert, tenant=request.tenant)

    return render(
        request,
        "assets/assetdocumentknowledge/asset_operator_certification/form.html",
        {
            "form": form,
            "certification": cert,
            "is_edit": True,
            "title": f"Edit {cert.number}",
        },
    )


@login_required
@require_POST
@tenant_admin_required
def asset_operator_certification_delete(request, pk):
    """Delete a pending or non-revoked certification record."""
    cert = assets_object(request, AssetOperatorCertification, pk)
    if cert.status == "revoked":
        messages.error(
            request,
            f"Revoked certification {cert.number} must be retained for audit compliance.",
        )
        return redirect("assets:asset_operator_certification_detail", pk=cert.pk)
    cert_number = cert.number
    write_audit_log(request.user, cert, "delete", tenant=request.tenant)
    cert.delete()
    messages.success(request, f"Deleted certification {cert_number}.")
    return redirect("assets:asset_operator_certification_list")


@login_required
def asset_operator_certification_download(request, pk):
    """Download the uploaded certificate PDF/image safely as an attachment with nosniff."""
    cert = assets_object(request, AssetOperatorCertification, pk)
    return serve_protected_attachment(
        cert,
        file_attr="certificate_file",
        original_filename_attr="original_filename",
    )


@login_required
@require_POST
@tenant_admin_required
def asset_operator_certification_verify_activate(request, pk):
    """Verify and activate a Pending certification based on its expiry date."""
    with transaction.atomic():
        cert = assets_object(
            request,
            AssetOperatorCertification,
            pk,
            queryset=AssetOperatorCertification.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if cert.status != "pending":
            messages.warning(
                request,
                f"Certification {cert.number} is already in status {cert.get_status_display()}.",
            )
            return redirect(
                "assets:asset_operator_certification_detail", pk=cert.pk
            )
        cert.status = cert.compute_expiry_status()
        if cert.last_assessed_date is None:
            cert.last_assessed_date = timezone.localdate()
        cert.save(update_fields=["status", "last_assessed_date", "updated_at"])
        write_audit_log(request.user, cert, "verify", tenant=request.tenant)
    messages.success(
        request,
        f"Verified certification {cert.number} ({cert.get_status_display()}).",
    )
    return redirect("assets:asset_operator_certification_detail", pk=cert.pk)


@login_required
@require_POST
def asset_operator_certification_acknowledge_sop(request, pk):
    """Record operator or admin SOP read & comprehension acknowledgment."""
    with transaction.atomic():
        cert = assets_object(
            request,
            AssetOperatorCertification,
            pk,
            queryset=AssetOperatorCertification.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if cert.status == "revoked":
            messages.error(
                request,
                f"Revoked certification {cert.number} cannot record SOP acknowledgment.",
            )
            return redirect(
                "assets:asset_operator_certification_detail", pk=cert.pk
            )
        if cert.operator_user_id != request.user.id and not is_tenant_admin_user(
            request.user
        ):
            messages.error(
                request,
                "Only the assigned operator or a tenant administrator can acknowledge this SOP.",
            )
            return redirect(
                "assets:asset_operator_certification_detail", pk=cert.pk
            )
        if cert.sop_acknowledged:
            messages.info(request, f"SOP already acknowledged for {cert.number}.")
            return redirect(
                "assets:asset_operator_certification_detail", pk=cert.pk
            )
        cert.sop_acknowledged = True
        cert.sop_acknowledged_at = timezone.now()
        cert.save(update_fields=["sop_acknowledged", "sop_acknowledged_at", "updated_at"])
        write_audit_log(request.user, cert, "ack_sop", tenant=request.tenant)
    messages.success(request, f"Recorded SOP acknowledgment on {cert.number}.")
    return redirect("assets:asset_operator_certification_detail", pk=cert.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_operator_certification_renew(request, pk):
    """Renew an active/expiring/expired certification for another annual validity cycle."""
    today = timezone.localdate()
    with transaction.atomic():
        cert = assets_object(
            request,
            AssetOperatorCertification,
            pk,
            queryset=AssetOperatorCertification.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if cert.status not in ("active", "expiring_soon", "expired"):
            messages.warning(
                request,
                f"Certification {cert.number} cannot be renewed from {cert.get_status_display()}.",
            )
            return redirect(
                "assets:asset_operator_certification_detail", pk=cert.pk
            )
        anchor = cert.expires_on if (cert.expires_on and cert.expires_on > today) else today
        cert.last_assessed_date = today
        cert.expires_on = _add_one_year(anchor)
        cert.status = cert.compute_expiry_status(as_of=today)
        cert.save(
            update_fields=[
                "last_assessed_date",
                "expires_on",
                "status",
                "updated_at",
            ]
        )
        write_audit_log(request.user, cert, "renew", tenant=request.tenant)
    messages.success(
        request,
        f"Renewed certification {cert.number} through {cert.expires_on.isoformat()}.",
    )
    return redirect("assets:asset_operator_certification_detail", pk=cert.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_operator_certification_revoke(request, pk):
    """Revoke an operator certification immediately for safety or compliance holds."""
    with transaction.atomic():
        cert = assets_object(
            request,
            AssetOperatorCertification,
            pk,
            queryset=AssetOperatorCertification.objects.filter(
                tenant=request.tenant
            ).select_for_update(),
        )
        if cert.status == "revoked":
            messages.info(request, f"Certification {cert.number} is already revoked.")
            return redirect(
                "assets:asset_operator_certification_detail", pk=cert.pk
            )
        cert.status = "revoked"
        cert.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, cert, "revoke", tenant=request.tenant)
    messages.warning(request, f"Revoked certification {cert.number}.")
    return redirect("assets:asset_operator_certification_detail", pk=cert.pk)


@login_required
@require_POST
@tenant_admin_required
def asset_operator_certification_refresh_alerts(request):
    """Recompute active / expiring_soon / expired statuses across all tenant certifications."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before refreshing certification alerts.")
        return redirect("assets:asset_operator_certification_list")
    today = timezone.localdate()
    now = timezone.now()
    changed_certs = []
    with transaction.atomic():
        certs = (
            AssetOperatorCertification.objects.select_for_update()
            .filter(
                tenant=request.tenant,
                status__in=("active", "expiring_soon", "expired"),
            )
            .only("id", "status", "expires_on", "renewal_lead_days", "updated_at")
        )
        for cert in certs:
            if cert.sync_expiry_status(save=False, as_of=today):
                cert.updated_at = now
                changed_certs.append(cert)
        if changed_certs:
            AssetOperatorCertification.objects.bulk_update(
                changed_certs, ["status", "updated_at"]
            )
            first_changed = (
                AssetOperatorCertification.objects.select_related(
                    "operator_party",
                    "operator_user",
                    "employee_profile__party",
                ).get(pk=changed_certs[0].pk)
            )
            write_audit_log(
                request.user,
                first_changed,
                "sync_exp",
                changes={"updated_count": len(changed_certs)},
                tenant=request.tenant,
            )
    messages.success(
        request,
        f"Synchronized certification expiry statuses ({len(changed_certs)} updated).",
    )
    return redirect("assets:asset_operator_certification_list")
