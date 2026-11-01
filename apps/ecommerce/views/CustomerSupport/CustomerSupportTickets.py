from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerSupport.CustomerSupportTickets import CustomerSupportTicketForm
from apps.ecommerce.models.CustomerSupport.CustomerSupportTickets import CustomerSupportTicket
from apps.ecommerce.views._common import ecommerce_object

User = get_user_model()


@login_required
def customersupportticket_list(request):
    qs = CustomerSupportTicket.objects.filter(tenant=request.tenant).select_related(
        "customer__customer", "order", "assigned_agent"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(subject__icontains=query)
            | Q(initial_message__icontains=query)
            | Q(number__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(customer_email__icontains=query)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_priority = request.GET.get("priority", "").strip()
    if selected_priority:
        qs = qs.filter(priority=selected_priority)

    selected_channel = request.GET.get("channel", "").strip()
    if selected_channel:
        qs = qs.filter(channel=selected_channel)

    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        qs = qs.filter(category=selected_category)

    selected_agent = request.GET.get("agent", "").strip()
    if selected_agent and selected_agent.isdigit():
        qs = qs.filter(assigned_agent_id=int(selected_agent))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    agents = User.objects.filter(is_active=True).order_by("username")

    context = {
        "tickets": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "status_choices": CustomerSupportTicket.STATUS_CHOICES,
        "priority_choices": CustomerSupportTicket.PRIORITY_CHOICES,
        "channel_choices": CustomerSupportTicket.CHANNEL_CHOICES,
        "category_choices": CustomerSupportTicket.CATEGORY_CHOICES,
        "agents": agents,
        "selected_status": selected_status,
        "selected_priority": selected_priority,
        "selected_channel": selected_channel,
        "selected_category": selected_category,
        "selected_agent": selected_agent,
        "query": query,
    }
    return render(request, "ecommerce/customer_support/ticket/list.html", context)


@login_required
def customersupportticket_detail(request, pk):
    ticket = ecommerce_object(
        request,
        CustomerSupportTicket,
        pk,
        select_related=("customer__customer", "order", "assigned_agent"),
    )
    return render(request, "ecommerce/customer_support/ticket/detail.html", {"ticket": ticket})


@login_required
def customersupportticket_create(request):
    if request.method == "POST":
        form = CustomerSupportTicketForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.tenant = request.tenant
            ticket.save()
            write_audit_log(
                request.user,
                ticket,
                "create",
                {"number": ticket.number, "subject": ticket.subject, "priority": ticket.priority},
                tenant=request.tenant,
            )
            messages.success(request, f"Ticket {ticket.number} opened successfully.")
            return redirect("ecommerce:customersupportticket_detail", pk=ticket.pk)
    else:
        form = CustomerSupportTicketForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/ticket/form.html",
        {"form": form, "ticket": None},
    )


@login_required
def customersupportticket_edit(request, pk):
    ticket = ecommerce_object(request, CustomerSupportTicket, pk)
    if request.method == "POST":
        form = CustomerSupportTicketForm(request.POST, instance=ticket, tenant=request.tenant)
        if form.is_valid():
            ticket = form.save()
            write_audit_log(
                request.user,
                ticket,
                "update",
                {"status": ticket.status, "priority": ticket.priority},
                tenant=request.tenant,
            )
            messages.success(request, f"Ticket {ticket.number} updated successfully.")
            return redirect("ecommerce:customersupportticket_detail", pk=ticket.pk)
    else:
        form = CustomerSupportTicketForm(instance=ticket, tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/ticket/form.html",
        {"form": form, "ticket": ticket},
    )


@login_required
@tenant_admin_required
@require_POST
def customersupportticket_delete(request, pk):
    ticket = ecommerce_object(request, CustomerSupportTicket, pk)
    number = ticket.number
    write_audit_log(
        request.user,
        ticket,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    ticket.delete()
    messages.success(request, f"Ticket {number} deleted.")
    return redirect("ecommerce:customersupportticket_list")
