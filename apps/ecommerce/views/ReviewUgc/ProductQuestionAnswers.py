from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ReviewUgc.ProductQuestionAnswers import (
    ProductQuestionAnswerForm,
    ProductQuestionAnswerResponseForm,
)
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ReviewUgc.ProductQuestionAnswers import ProductQuestionAnswer
from apps.ecommerce.views._common import ecommerce_object


@login_required
def productquestionanswer_list(request):
    qs = ProductQuestionAnswer.objects.filter(tenant=request.tenant).select_related(
        "product", "customer", "answered_by_user"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(question_text__icontains=query)
            | Q(answer_text__icontains=query)
            | Q(author_name__icontains=query)
            | Q(number__icontains=query)
            | Q(product__name__icontains=query)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_product = request.GET.get("product", "").strip()
    if selected_product and selected_product.isdigit():
        qs = qs.filter(product_id=int(selected_product))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    products = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "questions": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "status_choices": ProductQuestionAnswer.STATUS_CHOICES,
        "products": products,
        "selected_status": selected_status,
        "selected_product": selected_product,
        "query": query,
    }
    return render(request, "ecommerce/review_ugc/product_question/list.html", context)


@login_required
def productquestionanswer_detail(request, pk):
    question = ecommerce_object(
        request,
        ProductQuestionAnswer,
        pk,
        select_related=("product", "customer__customer", "answered_by_user"),
    )
    return render(
        request,
        "ecommerce/review_ugc/product_question/detail.html",
        {"question": question},
    )


@login_required
def productquestionanswer_create(request):
    if request.method == "POST":
        form = ProductQuestionAnswerForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            question = form.save(commit=False)
            question.tenant = request.tenant
            if question.answer_text and not question.answered_at:
                question.answered_at = timezone.now()
                if request.user.is_authenticated and not question.answered_by_user:
                    question.answered_by_user = request.user
            question.save()
            write_audit_log(
                request.user,
                question,
                "create",
                {"number": question.number, "product": question.product.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Question {question.number} submitted.")
            return redirect("ecommerce:productquestionanswer_detail", pk=question.pk)
    else:
        form = ProductQuestionAnswerForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/product_question/form.html",
        {"form": form, "question": None},
    )


@login_required
def productquestionanswer_edit(request, pk):
    question = ecommerce_object(request, ProductQuestionAnswer, pk)
    if request.method == "POST":
        form = ProductQuestionAnswerForm(request.POST, instance=question, tenant=request.tenant)
        if form.is_valid():
            question = form.save(commit=False)
            if question.answer_text and not question.answered_at:
                question.answered_at = timezone.now()
                if request.user.is_authenticated and not question.answered_by_user:
                    question.answered_by_user = request.user
            question.save()
            write_audit_log(
                request.user,
                question,
                "update",
                {"status": question.status},
                tenant=request.tenant,
            )
            messages.success(request, f"Question {question.number} updated.")
            return redirect("ecommerce:productquestionanswer_detail", pk=question.pk)
    else:
        form = ProductQuestionAnswerForm(instance=question, tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/product_question/form.html",
        {"form": form, "question": question},
    )


@login_required
@tenant_admin_required
@require_POST
def productquestionanswer_delete(request, pk):
    question = ecommerce_object(request, ProductQuestionAnswer, pk)
    number = question.number
    pk_val = question.pk
    question.delete()
    write_audit_log(
        request.user,
        question,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Question {number} deleted.")
    return redirect("ecommerce:productquestionanswer_list")


@login_required
@tenant_admin_required
def productquestionanswer_respond(request, pk):
    question = ecommerce_object(request, ProductQuestionAnswer, pk)
    if request.method == "POST":
        form = ProductQuestionAnswerResponseForm(request.POST, instance=question, tenant=request.tenant)
        if form.is_valid():
            question = form.save(commit=False)
            question.answered_by_user = request.user
            question.answered_at = timezone.now()
            if not question.answered_by_name:
                question.answered_by_name = request.user.get_full_name() or request.user.username
            question.save()
            write_audit_log(
                request.user,
                question,
                "respond",
                {"status": question.status, "answer_text": question.answer_text[:100]},
                tenant=request.tenant,
            )
            messages.success(request, f"Response saved for question {question.number}.")
            return redirect("ecommerce:productquestionanswer_detail", pk=question.pk)
    else:
        initial = {}
        if not question.answered_by_name:
            initial["answered_by_name"] = request.user.get_full_name() or request.user.username
        if not question.answer_text:
            initial["is_staff_answer"] = True
        form = ProductQuestionAnswerResponseForm(instance=question, initial=initial, tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/product_question/form.html",
        {"form": form, "question": question, "is_response": True},
    )
