"""HRM 3.2 Organizational Structure — CompanySetup views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


@login_required
def company_setup(request):
    """Read-only company overview (3.2 Company Setup) — the company ``OrgUnit`` node plus the
    branding the Tenants module (Module 0) owns. Branding edits stay in ``tenants:brandingsetting_list``."""
    from apps.tenants.models import BrandingSetting

    tenant = request.tenant
    company_unit = branding = None
    departments = cost_centers = 0
    if tenant is not None:
        company_unit = OrgUnit.objects.filter(tenant=tenant, kind="company").first()
        branding = BrandingSetting.objects.filter(tenant=tenant).first()
        departments = OrgUnit.objects.filter(tenant=tenant, kind="department").count()
        cost_centers = OrgUnit.objects.filter(tenant=tenant, kind="cost_center").count()
    return render(request, "hrm/organization/company_setup.html", {
        "company_unit": company_unit,
        "branding": branding,
        "departments": departments,
        "cost_centers": cost_centers,
    })
