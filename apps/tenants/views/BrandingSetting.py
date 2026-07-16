"""tenants — BrandingSetting views (split from apps/tenants/views.py)."""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    BrandingSetting,
)
from apps.tenants.forms import (
    BrandingSettingForm,
)


# ============================================================== Branding
@tenant_admin_required
def brandingsetting_list(request):
    return crud_list(
        request, BrandingSetting.objects.filter(tenant=request.tenant),
        "tenants/brandingsetting/list.html", search_fields=["email_from_name"],
    )


@tenant_admin_required
def brandingsetting_create(request):
    existing = BrandingSetting.objects.filter(tenant=request.tenant).first()
    if existing:  # OneToOne — edit the existing record instead of failing on the unique constraint
        return redirect("tenants:brandingsetting_edit", pk=existing.pk)
    return crud_create(request, form_class=BrandingSettingForm,
                       template="tenants/brandingsetting/form.html",
                       success_url="tenants:brandingsetting_list")


@tenant_admin_required
def brandingsetting_detail(request, pk):
    obj = get_object_or_404(BrandingSetting, pk=pk, tenant=request.tenant)
    return render(request, "tenants/brandingsetting/detail.html", {"obj": obj})


@tenant_admin_required
def brandingsetting_edit(request, pk):
    return crud_edit(request, model=BrandingSetting, pk=pk, form_class=BrandingSettingForm,
                     template="tenants/brandingsetting/form.html",
                     success_url="tenants:brandingsetting_list")


@tenant_admin_required
@require_POST
def brandingsetting_delete(request, pk):
    return crud_delete(request, model=BrandingSetting, pk=pk, success_url="tenants:brandingsetting_list")
