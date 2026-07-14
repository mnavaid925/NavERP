"""CRM 1.3 Marketing Automation — LandingPages views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Campaign,
    FormSubmission,
    LandingPage,
)
from apps.crm.forms import (
    LandingPageForm,
    PublicLeadForm,
)


def _client_ip(request):
    """Best-effort client IP for a public submission. Uses REMOTE_ADDR only —
    X-Forwarded-For is client-spoofable, so we never trust it for storage.
    # WARNING: behind a reverse proxy REMOTE_ADDR is the proxy IP. For accurate visitor IPs in
    # production, resolve via django-ipware with a configured trusted-proxy count."""
    return request.META.get("REMOTE_ADDR") or None


# ------------------------------------------------------------ Landing pages (1.3)
@login_required
def landingpage_list(request):
    return crud_list(
        request,
        # defer the large HTML body — it's never shown on the list.
        LandingPage.objects.filter(tenant=request.tenant).select_related(
            "campaign", "routing_owner").defer("body"),
        "crm/marketing/landingpage/list.html",
        search_fields=["number", "name", "headline", "slug"],
        filters=[("status", "status", False), ("campaign", "campaign_id", True)],
        extra_context={"status_choices": LandingPage.STATUS_CHOICES,
                       "campaigns": Campaign.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def landingpage_create(request):
    return crud_create(request, form_class=LandingPageForm,
                       template="crm/marketing/landingpage/form.html",
                       success_url="crm:landingpage_list")


@login_required
def landingpage_detail(request, pk):
    obj = get_object_or_404(
        LandingPage.objects.select_related("campaign", "routing_owner", "owner"), pk=pk, tenant=request.tenant)
    return render(request, "crm/marketing/landingpage/detail.html", {
        "obj": obj,
        "submissions": FormSubmission.objects.filter(
            tenant=request.tenant, landing_page=obj).select_related(
            "converted_lead").defer("message")[:20],  # message not shown in the panel
    })


@login_required
def landingpage_edit(request, pk):
    return crud_edit(request, model=LandingPage, pk=pk, form_class=LandingPageForm,
                     template="crm/marketing/landingpage/form.html",
                     success_url="crm:landingpage_list")


@login_required
@require_POST
def landingpage_delete(request, pk):
    return crud_delete(request, model=LandingPage, pk=pk, success_url="crm:landingpage_list")


@tenant_admin_required  # publishing exposes a live public web-to-lead URL — admin-gated
@require_POST
def landingpage_publish(request, pk):
    """Toggle a landing page between draft and published. Publishing makes it live on a public
    URL accepting leads, so this transition is admin-only (the content form excludes `status`)."""
    page = get_object_or_404(LandingPage, pk=pk, tenant=request.tenant)
    new_status = "draft" if page.status == "published" else "published"
    LandingPage.objects.filter(pk=page.pk, tenant=request.tenant).update(status=new_status)
    write_audit_log(request.user, page, "update",
                    {"action": "publish" if new_status == "published" else "unpublish"})
    messages.success(request, f"{page.number} is now {new_status}.")
    return redirect("crm:landingpage_detail", pk=page.pk)


def landing_public(request, token):
    """Public landing page + web-to-lead form (1.3). No login; the unguessable public_token is
    the bearer credential and only a *published* page resolves (draft/archived → 404). CSRF is
    enforced by the template's {% csrf_token %}; the tenant-authored body is rendered ESCAPED.
    # WARNING: unauthenticated endpoint — add per-IP rate-limiting (django-ratelimit) or a WAF
    # throttle in production to stop scripted FormSubmission floods."""
    page = get_object_or_404(
        LandingPage.objects.select_related("campaign"), public_token=token, status="published")
    form = PublicLeadForm()
    if request.method == "POST":
        form = PublicLeadForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                FormSubmission.objects.create(
                    tenant=page.tenant, landing_page=page,
                    name=cd["name"], email=cd["email"],
                    phone=cd["phone"] if page.capture_phone else "",
                    company=cd["company"] if page.capture_company else "",
                    message=cd["message"] if page.capture_message else "",
                    status="new", routed_to=page.routing_owner, ip_address=_client_ip(request),
                )
                LandingPage.objects.filter(pk=page.pk).update(submission_count=F("submission_count") + 1)
            # Post/Redirect/Get — a browser refresh after submit won't re-post the form.
            return redirect(f"{reverse('crm:landing_public', args=[token])}?submitted=1")
    return render(request, "crm/marketing/landing_public.html", {
        "page": page, "form": form, "submitted": request.GET.get("submitted") == "1"})
