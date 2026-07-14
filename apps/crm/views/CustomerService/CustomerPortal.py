"""CRM 1.4 Customer Service & Support — CustomerPortal views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Case,
    CaseComment,
    CustomerPortalAccess,
    SlaPolicy,
)
from apps.crm.forms import (
    PublicCommentForm,
)


# ------------------------------------------------------------ Customer self-service portal (1.4, login)
def _customer_portal_access(request):
    """Return the active CustomerPortalAccess for the logged-in portal user, or None."""
    if not request.user.is_authenticated:
        return None
    return (CustomerPortalAccess.objects
            .filter(portal_user=request.user, tenant=request.tenant, is_active=True)
            .select_related("customer_party").first())


@login_required
def portal_case_list(request):
    access = _customer_portal_access(request)
    if access is None:
        messages.error(request, "You don't have customer portal access.")
        return redirect("dashboard:home")
    party = access.customer_party
    if party is None:  # WARNING: without this, Q(account=None)|Q(contact=None) would match
        # every unlinked case in the tenant — leaking cases to a misconfigured portal account.
        messages.error(request, "Your portal account has no linked customer — contact support.")
        return redirect("dashboard:home")
    cases = (Case.objects.filter(tenant=request.tenant)
             .filter(Q(account=party) | Q(contact=party))
             .select_related("owner").order_by("-created_at"))
    page_obj = paginate(request, cases)
    return render(request, "crm/service/portal_case_list.html", {
        "access": access, "object_list": page_obj.object_list, "page_obj": page_obj})


@login_required
def portal_case_detail(request, pk):
    access = _customer_portal_access(request)
    if access is None:
        messages.error(request, "You don't have customer portal access.")
        return redirect("dashboard:home")
    party = access.customer_party
    if party is None:  # no linked customer → no scope; refuse rather than match null-party cases
        messages.error(request, "Your portal account has no linked customer — contact support.")
        return redirect("dashboard:home")
    # Scoped to the portal user's own party — they can never open another customer's case.
    case = get_object_or_404(
        Case.objects.filter(tenant=request.tenant).filter(Q(account=party) | Q(contact=party)), pk=pk)
    comment_form = PublicCommentForm()
    if request.method == "POST":
        if not access.can_submit_cases:  # explicit reject (don't silently no-op a crafted POST)
            messages.error(request, "You don't have permission to reply.")
            return redirect("crm:portal_case_detail", pk=case.pk)
        comment_form = PublicCommentForm(request.POST)
        if comment_form.is_valid():
            CaseComment.objects.create(
                tenant=request.tenant, case=case, author=request.user,
                author_name=request.user.get_full_name() or request.user.username,
                body=comment_form.cleaned_data["body"], is_public=True)
            messages.success(request, "Your reply was sent.")
            return redirect("crm:portal_case_detail", pk=case.pk)
    return render(request, "crm/service/portal_case_detail.html", {
        "access": access, "case": case,
        "comments": CaseComment.objects.filter(
            tenant=request.tenant, case=case, is_public=True).select_related("author"),
        "comment_form": comment_form,
    })


@login_required
def portal_case_create(request):
    access = _customer_portal_access(request)
    if access is None or not access.can_submit_cases:
        messages.error(request, "You can't submit support tickets.")
        return redirect("crm:portal_case_list" if access else "dashboard:home")
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()[:255]
        if not subject:
            messages.error(request, "A subject is required.")
        else:
            priority = request.POST.get("priority", "medium")
            if priority not in dict(Case.PRIORITY_CHOICES):
                priority = "medium"
            # Force the party + origin server-side — a portal user can't file for another customer.
            default_sla = SlaPolicy.objects.filter(
                tenant=request.tenant, is_default=True, is_active=True).first()
            case = Case.objects.create(
                tenant=request.tenant, subject=subject,
                description=request.POST.get("description", "").strip()[:5000],
                priority=priority, status="new", origin="portal",
                account=access.customer_party, sla_policy=default_sla)
            messages.success(request, f"Ticket {case.number} submitted.")
            return redirect("crm:portal_case_detail", pk=case.pk)
    return render(request, "crm/service/portal_case_form.html", {
        "access": access, "priority_choices": Case.PRIORITY_CHOICES})
