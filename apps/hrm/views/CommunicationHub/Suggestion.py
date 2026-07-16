"""HRM 3.27 Communication Hub — Suggestion views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Suggestion,
)
from apps.hrm.forms import (
    SuggestionForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _ss_child_create, _ss_child_detail, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _hr_request_edit


# ---- Suggestions (employee idea box — reuses the 3.26 _hr_request_* helpers verbatim) --------
@login_required
def suggestion_list(request):
    qs = _ss_scope(request, Suggestion.objects.filter(tenant=request.tenant)
                   .select_related("employee__party", "approver"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": Suggestion.STATUS_CHOICES,
             "category_choices": Suggestion.CATEGORY_CHOICES}
    filters = [("status", "status", False), ("category", "category", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/communication/suggestion/list.html",
                     search_fields=("number", "title", "body"), filters=filters, extra_context=extra)


@login_required
def suggestion_create(request):
    return _ss_child_create(request, SuggestionForm,
                            "hrm/communication/suggestion/form.html", "hrm:suggestion_list")


@login_required
def suggestion_detail(request, pk):
    return _ss_child_detail(request, Suggestion, pk, "hrm/communication/suggestion/detail.html",
                            select_related=("employee__party", "approver"))


@login_required
def suggestion_edit(request, pk):
    return _hr_request_edit(request, Suggestion, pk, SuggestionForm,
                            "hrm/communication/suggestion/form.html", "hrm:suggestion_detail")
