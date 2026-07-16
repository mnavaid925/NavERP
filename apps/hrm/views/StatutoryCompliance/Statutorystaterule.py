"""HRM 3.15 Statutory Compliance — Statutorystaterule views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    INDIAN_STATE_CHOICES,
    StatutoryStateRule,
)
from apps.hrm.forms import (
    StatutoryStateRuleForm,
)


# ---------------------------------------------- StatutoryStateRule (PT + LWF slabs)
@login_required
def statutorystaterule_list(request):
    return crud_list(
        request,
        StatutoryStateRule.objects.filter(tenant=request.tenant),
        "hrm/statutory/statutorystaterule/list.html",
        search_fields=["state", "registration_number"],
        filters=[("scheme", "scheme", False), ("state", "state", False),
                 ("is_active", "is_active", False)],
        extra_context={
            "scheme_choices": StatutoryStateRule.SCHEME_CHOICES,
            "state_choices": INDIAN_STATE_CHOICES,
        },
    )


@login_required
def statutorystaterule_create(request):
    return crud_create(request, form_class=StatutoryStateRuleForm,
                       template="hrm/statutory/statutorystaterule/form.html",
                       success_url="hrm:statutorystaterule_list")


@login_required
def statutorystaterule_detail(request, pk):
    return crud_detail(request, model=StatutoryStateRule, pk=pk,
                       template="hrm/statutory/statutorystaterule/detail.html")


@login_required
def statutorystaterule_edit(request, pk):
    return crud_edit(request, model=StatutoryStateRule, pk=pk, form_class=StatutoryStateRuleForm,
                     template="hrm/statutory/statutorystaterule/form.html",
                     success_url="hrm:statutorystaterule_list")


@login_required
@require_POST
def statutorystaterule_delete(request, pk):
    return crud_delete(request, model=StatutoryStateRule, pk=pk,
                       success_url="hrm:statutorystaterule_list")
