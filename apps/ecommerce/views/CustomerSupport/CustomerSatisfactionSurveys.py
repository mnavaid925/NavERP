from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerSupport.CustomerSatisfactionSurveys import CustomerSatisfactionSurveyForm
from apps.ecommerce.models.CustomerSupport.CustomerSatisfactionSurveys import CustomerSatisfactionSurvey
from apps.ecommerce.views._common import ecommerce_object


@login_required
def customersatisfactionsurvey_list(request):
    qs = CustomerSatisfactionSurvey.objects.filter(tenant=request.tenant).select_related(
        "ticket", "order", "customer__customer", "agent_rated", "reviewed_by"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(feedback_comment__icontains=query)
            | Q(follow_up_notes__icontains=query)
            | Q(ticket__number__icontains=query)
            | Q(order__number__icontains=query)
        )

    selected_survey_type = request.GET.get("survey_type", "").strip()
    if selected_survey_type:
        qs = qs.filter(survey_type=selected_survey_type)

    selected_sentiment = request.GET.get("sentiment", "").strip()
    if selected_sentiment:
        qs = qs.filter(sentiment=selected_sentiment)

    selected_follow_up = request.GET.get("follow_up", "").strip()
    if selected_follow_up:
        qs = qs.filter(follow_up_status=selected_follow_up)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "surveys": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "survey_type_choices": CustomerSatisfactionSurvey.SURVEY_TYPE_CHOICES,
        "sentiment_choices": CustomerSatisfactionSurvey.SENTIMENT_CHOICES,
        "follow_up_choices": CustomerSatisfactionSurvey.FOLLOW_UP_CHOICES,
        "selected_survey_type": selected_survey_type,
        "selected_sentiment": selected_sentiment,
        "selected_follow_up": selected_follow_up,
        "query": query,
    }
    return render(request, "ecommerce/customer_support/survey/list.html", context)


@login_required
def customersatisfactionsurvey_detail(request, pk):
    survey = ecommerce_object(
        request,
        CustomerSatisfactionSurvey,
        pk,
        select_related=("ticket", "order", "customer__customer", "agent_rated", "reviewed_by"),
    )
    return render(request, "ecommerce/customer_support/survey/detail.html", {"survey": survey})


@login_required
def customersatisfactionsurvey_create(request):
    if request.method == "POST":
        form = CustomerSatisfactionSurveyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            survey = form.save(commit=False)
            survey.tenant = request.tenant
            survey.save()
            write_audit_log(
                request.user,
                survey,
                "create",
                {"number": survey.number, "survey_type": survey.survey_type, "rating": survey.rating_score},
                tenant=request.tenant,
            )
            messages.success(request, f"Satisfaction Survey {survey.number} recorded successfully.")
            return redirect("ecommerce:customersatisfactionsurvey_detail", pk=survey.pk)
    else:
        form = CustomerSatisfactionSurveyForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/survey/form.html",
        {"form": form, "survey": None},
    )


@login_required
def customersatisfactionsurvey_edit(request, pk):
    survey = ecommerce_object(request, CustomerSatisfactionSurvey, pk)
    if request.method == "POST":
        form = CustomerSatisfactionSurveyForm(request.POST, instance=survey, tenant=request.tenant)
        if form.is_valid():
            survey = form.save()
            write_audit_log(
                request.user,
                survey,
                "update",
                {"sentiment": survey.sentiment, "follow_up_status": survey.follow_up_status},
                tenant=request.tenant,
            )
            messages.success(request, f"Satisfaction Survey {survey.number} updated successfully.")
            return redirect("ecommerce:customersatisfactionsurvey_detail", pk=survey.pk)
    else:
        form = CustomerSatisfactionSurveyForm(instance=survey, tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/survey/form.html",
        {"form": form, "survey": survey},
    )


@login_required
@tenant_admin_required
@require_POST
def customersatisfactionsurvey_delete(request, pk):
    survey = ecommerce_object(request, CustomerSatisfactionSurvey, pk)
    number = survey.number
    write_audit_log(
        request.user,
        survey,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    survey.delete()
    messages.success(request, f"Survey {number} deleted.")
    return redirect("ecommerce:customersatisfactionsurvey_list")
