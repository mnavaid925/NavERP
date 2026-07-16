"""HRM 3.6 Candidate Management — CareersList views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    JobRequisition,
)


# --------------------------------------------------------------- Public career portal (3.6, UNAUTHENTICATED)
# WARNING: these two views are intentionally login-free. The requisition's unguessable public_token is
# the bearer credential. Add per-IP rate-limiting (django-ratelimit) / WAF throttling in production to
# stop scripted application floods. CSRF is enforced by the form's {% csrf_token %}; tenant-authored
# text is rendered ESCAPED by the templates.
def careers_list(request):
    """Public job board for ONE tenant, resolved via ``?tenant=<slug>`` (no cross-tenant listing)."""
    slug = request.GET.get("tenant", "").strip()
    tenant_obj = None
    requisitions = JobRequisition.objects.none()
    # Anonymous visitors pin the tenant via ?tenant=<slug>; a logged-in staff member with no slug
    # sees their own workspace's openings (so the sidebar "Public Careers Page" link isn't blank).
    if not slug and getattr(request, "tenant", None) is not None:
        tenant_obj = request.tenant
        slug = request.tenant.slug
    elif slug:
        from apps.core.models import Tenant
        tenant_obj = Tenant.objects.filter(slug=slug, is_active=True).first()
    if tenant_obj is not None:
        requisitions = (JobRequisition.objects
                        .filter(tenant=tenant_obj, status="posted",
                                posting_type__in=["external", "both"])
                        .exclude(public_token__isnull=True)  # only tokenized openings have a working Apply link
                        .select_related("department", "designation").order_by("-posted_at"))
    return render(request, "hrm/candidates/careers_list.html", {
        "tenant_obj": tenant_obj, "slug": slug, "requisitions": requisitions,
        "submitted": request.GET.get("submitted") == "1"})
