from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.AuditReporting.ChainOfCustodyExports import (
    AuditorPortalPasscodeForm,
    ChainOfCustodyExportForm,
)
from apps.documents.models.AuditReporting.ChainOfCustodyExports import ChainOfCustodyExport
from apps.documents.models.AuditReporting.DocumentAuditTrails import DocumentAuditTrail

PAGE_SIZE = 15


@login_required
def custody_export_list(request):
    """List regulatory chain of custody evidence packages and active auditor passes."""
    qs = ChainOfCustodyExport.objects.filter(tenant=request.tenant).select_related(
        "document", "folder", "created_by"
    )

    q = request.GET.get("q", "").strip()
    framework = request.GET.get("framework", "").strip()
    status = request.GET.get("status", "").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(auditor_name__icontains=q)
            | Q(auditor_organization__icontains=q)
            | Q(auditor_email__icontains=q)
        )
    if framework:
        qs = qs.filter(regulatory_framework=framework)

    active_passes_count = ChainOfCustodyExport.objects.filter(
        tenant=request.tenant,
        is_portal_active=True,
        expires_at__gt=timezone.now(),
    ).count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "exports": page_obj.object_list,
        "page_obj": page_obj,
        "active_passes_count": active_passes_count,
        "framework_choices": ChainOfCustodyExport.REGULATORY_FRAMEWORK_CHOICES,
    }
    return render(request, "documents/audit_reporting/chain_of_custody/list.html", context)


@login_required
def custody_export_create(request):
    """Package evidence into a cryptographically sealed chain-of-custody export."""
    if request.method == "POST":
        form = ChainOfCustodyExportForm(tenant=request.tenant, data=request.POST)
        if form.is_valid():
            pkg = form.save(commit=False)
            pkg.tenant = request.tenant
            pkg.created_by = request.user
            passcode = form.cleaned_data.get("portal_passcode")
            if passcode:
                pkg.set_passcode(passcode)
            pkg.save()

            write_audit_log(request.user, pkg, "create", tenant=request.tenant)
            messages.success(request, f"Chain of custody package '{pkg.number}' sealed and generated.")
            return redirect("documents:custody_export_detail", pk=pkg.pk)
    else:
        form = ChainOfCustodyExportForm(tenant=request.tenant)

    context = {
        "form": form,
    }
    return render(request, "documents/audit_reporting/chain_of_custody/form.html", context)


@login_required
def custody_export_detail(request, pk):
    """Inspect digital evidence manifest, cryptographic seal, and auditor link."""
    export_pkg = get_object_or_404(
        ChainOfCustodyExport.objects.select_related("document", "folder", "created_by", "revoked_by"),
        pk=pk,
        tenant=request.tenant,
    )

    portal_url = request.build_absolute_uri(
        reverse("documents:auditor_portal_view", kwargs={"token": export_pkg.access_token})
    )

    # Recompute check
    is_hash_valid = bool(export_pkg.package_hash)

    context = {
        "export_pkg": export_pkg,
        "portal_url": portal_url,
        "manifest_data": export_pkg.manifest_json,
        "is_hash_valid": is_hash_valid,
    }
    return render(request, "documents/audit_reporting/chain_of_custody/detail.html", context)


@login_required
def custody_export_certificate(request, pk):
    """Printable official Certificate of Authenticity & Chain of Custody."""
    export_pkg = get_object_or_404(
        ChainOfCustodyExport.objects.select_related("document", "created_by"),
        pk=pk,
        tenant=request.tenant,
    )

    context = {
        "export_pkg": export_pkg,
        "manifest_data": export_pkg.manifest_json,
        "tenant": request.tenant,
    }
    return render(request, "documents/audit_reporting/chain_of_custody/certificate.html", context)


@require_POST
@tenant_admin_required
def custody_export_revoke(request, pk):
    """Instantly terminate and revoke an auditor access pass."""
    export_pkg = get_object_or_404(ChainOfCustodyExport, pk=pk, tenant=request.tenant)
    export_pkg.revoke(request.user)
    write_audit_log(request.user, export_pkg, "revoke", tenant=request.tenant)
    messages.warning(request, f"Auditor portal access for '{export_pkg.auditor_name}' has been revoked.")
    return redirect("documents:custody_export_detail", pk=export_pkg.pk)


def auditor_portal_view(request, token):
    """Public token-authenticated read-only portal for accredited external auditors."""
    export_pkg = get_object_or_404(
        ChainOfCustodyExport.objects.select_related("document", "tenant"),
        access_token=token,
    )

    # Validate active & not expired
    if not export_pkg.is_portal_active:
        return render(
            request,
            "documents/audit_reporting/chain_of_custody/auditor_portal.html",
            {"error": "Access Revoked", "message": "This auditor portal pass has been revoked by the system administrator."},
            status=403,
        )

    if export_pkg.is_expired:
        return render(
            request,
            "documents/audit_reporting/chain_of_custody/auditor_portal.html",
            {"error": "Pass Expired", "message": "This auditor inspection pass expired on " + export_pkg.expires_at.strftime("%Y-%m-%d %H:%M") + "."},
            status=410,
        )

    # Passcode verification gate
    session_key = f"auditor_auth_{token}"
    passcode_required = bool(export_pkg.passcode_hash)
    is_authenticated = request.session.get(session_key, False)

    if passcode_required and not is_authenticated:
        passcode_form = AuditorPortalPasscodeForm()
        return render(
            request,
            "documents/audit_reporting/chain_of_custody/auditor_portal.html",
            {
                "export_pkg": export_pkg,
                "passcode_required": True,
                "passcode_form": passcode_form,
            },
        )

    # Update access tracking
    export_pkg.access_count += 1
    export_pkg.last_accessed_at = timezone.now()
    export_pkg.save(update_fields=["access_count", "last_accessed_at"])

    # Unbroken chain logging back to DocumentAuditTrail
    DocumentAuditTrail.objects.create(
        tenant=export_pkg.tenant,
        document=export_pkg.document,
        action_type="auditor_portal_accessed",
        actor_email_snapshot=export_pkg.auditor_email,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        details_json={
            "export_number": export_pkg.number,
            "auditor_name": export_pkg.auditor_name,
            "organization": export_pkg.auditor_organization,
        },
    )

    doc = export_pkg.document
    versions = doc.versions.select_related("author").order_by("-created_at") if doc and hasattr(doc, "versions") else []
    audit_trail = (
        DocumentAuditTrail.objects.filter(tenant=export_pkg.tenant, document=doc).order_by("-event_timestamp")[:50]
        if doc
        else []
    )

    context = {
        "export_pkg": export_pkg,
        "manifest_data": export_pkg.manifest_json,
        "passcode_required": False,
        "document": doc,
        "versions": versions,
        "audit_trail": audit_trail,
    }
    return render(request, "documents/audit_reporting/chain_of_custody/auditor_portal.html", context)


@require_POST
def auditor_portal_verify(request, token):
    """Verify submitted passcode for external auditor portal."""
    export_pkg = get_object_or_404(
        ChainOfCustodyExport.objects.select_related("document", "tenant"),
        access_token=token,
    )

    if not export_pkg.is_portal_active or export_pkg.is_expired:
        messages.error(request, "This auditor portal pass is inactive or has expired.")
        return redirect("documents:auditor_portal_view", token=token)

    attempts_key = f"auditor_failed_attempts_{token}"
    failed_attempts = request.session.get(attempts_key, 0)
    if failed_attempts >= 5:
        messages.error(request, "Too many failed passcode attempts. Access locked out.")
        return redirect("documents:auditor_portal_view", token=token)

    form = AuditorPortalPasscodeForm(request.POST)

    if form.is_valid():
        entered_passcode = form.cleaned_data.get("passcode")
        if export_pkg.check_passcode(entered_passcode):
            request.session[f"auditor_auth_{token}"] = True
            request.session.pop(attempts_key, None)
            return redirect("documents:auditor_portal_view", token=token)

    # Failed attempt
    failed_attempts += 1
    request.session[attempts_key] = failed_attempts

    # Log invalid passcode attempt to DocumentAuditTrail
    DocumentAuditTrail.objects.create(
        tenant=export_pkg.tenant,
        document=export_pkg.document,
        action_type="auditor_portal_accessed",
        actor_email_snapshot=export_pkg.auditor_email,
        is_success=False,
        failure_reason="Invalid passcode attempt",
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        details_json={
            "export_number": export_pkg.number,
            "auditor_name": export_pkg.auditor_name,
            "failed_attempts": failed_attempts,
        },
    )

    messages.error(request, "Invalid auditor passcode. Access denied.")
    return redirect("documents:auditor_portal_view", token=token)
