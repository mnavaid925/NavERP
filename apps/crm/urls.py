from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    # Analytics & Reporting overview (1.6) — module landing page
    path("", views.overview, name="overview"),

    # Leads (1.1)
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/add/", views.lead_create, name="lead_create"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/edit/", views.lead_edit, name="lead_edit"),
    path("leads/<int:pk>/delete/", views.lead_delete, name="lead_delete"),
    path("leads/<int:pk>/convert/", views.lead_convert, name="lead_convert"),

    # Opportunities (1.2)
    path("opportunities/", views.opportunity_list, name="opportunity_list"),
    path("opportunities/add/", views.opportunity_create, name="opportunity_create"),
    path("opportunities/<int:pk>/", views.opportunity_detail, name="opportunity_detail"),
    path("opportunities/<int:pk>/edit/", views.opportunity_edit, name="opportunity_edit"),
    path("opportunities/<int:pk>/delete/", views.opportunity_delete, name="opportunity_delete"),

    # Campaigns (1.3)
    path("campaigns/", views.campaign_list, name="campaign_list"),
    path("campaigns/add/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/edit/", views.campaign_edit, name="campaign_edit"),
    path("campaigns/<int:pk>/delete/", views.campaign_delete, name="campaign_delete"),

    # Cases / Tickets (1.4)
    path("cases/", views.case_list, name="case_list"),
    path("cases/add/", views.case_create, name="case_create"),
    path("cases/<int:pk>/", views.case_detail, name="case_detail"),
    path("cases/<int:pk>/edit/", views.case_edit, name="case_edit"),
    path("cases/<int:pk>/delete/", views.case_delete, name="case_delete"),

    # Knowledge base / Solutions (1.4)
    path("knowledge/", views.knowledgearticle_list, name="knowledgearticle_list"),
    path("knowledge/add/", views.knowledgearticle_create, name="knowledgearticle_create"),
    path("knowledge/<int:pk>/", views.knowledgearticle_detail, name="knowledgearticle_detail"),
    path("knowledge/<int:pk>/edit/", views.knowledgearticle_edit, name="knowledgearticle_edit"),
    path("knowledge/<int:pk>/delete/", views.knowledgearticle_delete, name="knowledgearticle_delete"),

    # Tasks (1.5)
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/add/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),

    # Accounts — core.Party (organization) + AccountProfile (1.1)
    path("accounts/", views.account_list, name="account_list"),
    path("accounts/add/", views.account_create, name="account_create"),
    path("accounts/<int:pk>/", views.account_detail, name="account_detail"),
    path("accounts/<int:pk>/edit/", views.account_edit, name="account_edit"),
    path("accounts/<int:pk>/delete/", views.account_delete, name="account_delete"),

    # Contacts — core.Party (person) + ContactProfile (1.1)
    path("contacts/", views.contact_list, name="contact_list"),
    path("contacts/add/", views.contact_create, name="contact_create"),
    path("contacts/<int:pk>/", views.contact_detail, name="contact_detail"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact_edit"),
    path("contacts/<int:pk>/delete/", views.contact_delete, name="contact_delete"),
]
