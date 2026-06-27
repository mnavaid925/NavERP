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

    # Opportunities (1.2 Opportunity Management)
    path("opportunities/", views.opportunity_list, name="opportunity_list"),
    path("opportunities/board/", views.opportunity_board, name="opportunity_board"),  # Kanban
    path("opportunities/add/", views.opportunity_create, name="opportunity_create"),
    path("opportunities/<int:pk>/", views.opportunity_detail, name="opportunity_detail"),
    path("opportunities/<int:pk>/edit/", views.opportunity_edit, name="opportunity_edit"),
    path("opportunities/<int:pk>/delete/", views.opportunity_delete, name="opportunity_delete"),
    path("opportunities/<int:pk>/advance/", views.opportunity_advance, name="opportunity_advance"),
    path("opportunities/<int:pk>/add-split/", views.opportunitysplit_add, name="opportunitysplit_add"),
    path("opportunity-splits/<int:split_pk>/remove/", views.opportunitysplit_remove, name="opportunitysplit_remove"),

    # Territories (1.2 Forecasting)
    path("territories/", views.territory_list, name="territory_list"),
    path("territories/add/", views.territory_create, name="territory_create"),
    path("territories/<int:pk>/", views.territory_detail, name="territory_detail"),
    path("territories/<int:pk>/edit/", views.territory_edit, name="territory_edit"),
    path("territories/<int:pk>/delete/", views.territory_delete, name="territory_delete"),

    # Products — sales catalog (1.2 Quoting)
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_create, name="product_create"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),

    # Price books (1.2 Quoting)
    path("price-books/", views.pricebook_list, name="pricebook_list"),
    path("price-books/add/", views.pricebook_create, name="pricebook_create"),
    path("price-books/<int:pk>/", views.pricebook_detail, name="pricebook_detail"),
    path("price-books/<int:pk>/edit/", views.pricebook_edit, name="pricebook_edit"),
    path("price-books/<int:pk>/delete/", views.pricebook_delete, name="pricebook_delete"),

    # Quotes (1.2 Quoting)
    path("quotes/", views.quote_list, name="quote_list"),
    path("quotes/add/", views.quote_create, name="quote_create"),
    path("quotes/<int:pk>/", views.quote_detail, name="quote_detail"),
    path("quotes/<int:pk>/edit/", views.quote_edit, name="quote_edit"),
    path("quotes/<int:pk>/delete/", views.quote_delete, name="quote_delete"),
    path("quotes/<int:pk>/print/", views.quote_print, name="quote_print"),
    path("quotes/<int:pk>/add-line/", views.quoteline_add, name="quoteline_add"),
    path("quote-lines/<int:line_pk>/remove/", views.quoteline_remove, name="quoteline_remove"),
    path("quotes/<int:pk>/send/", views.quote_send, name="quote_send"),
    path("quotes/<int:pk>/accept/", views.quote_accept, name="quote_accept"),
    path("quotes/<int:pk>/decline/", views.quote_decline, name="quote_decline"),

    # Sales quotas (1.2 Forecasting)
    path("sales-quotas/", views.salesquota_list, name="salesquota_list"),
    path("sales-quotas/add/", views.salesquota_create, name="salesquota_create"),
    path("sales-quotas/<int:pk>/", views.salesquota_detail, name="salesquota_detail"),
    path("sales-quotas/<int:pk>/edit/", views.salesquota_edit, name="salesquota_edit"),
    path("sales-quotas/<int:pk>/delete/", views.salesquota_delete, name="salesquota_delete"),

    # Forecast dashboard (1.2 Forecasting)
    path("forecast/", views.forecast, name="forecast"),

    # Campaigns (1.3 Campaign Management)
    path("campaigns/", views.campaign_list, name="campaign_list"),
    path("campaigns/add/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/edit/", views.campaign_edit, name="campaign_edit"),
    path("campaigns/<int:pk>/delete/", views.campaign_delete, name="campaign_delete"),
    path("campaigns/<int:pk>/add-member/", views.campaignmember_add, name="campaignmember_add"),

    # Campaign members — target-list segmentation (1.3)
    path("campaign-members/", views.campaignmember_list, name="campaignmember_list"),
    path("campaign-members/add/", views.campaignmember_create, name="campaignmember_create"),
    path("campaign-members/<int:pk>/", views.campaignmember_detail, name="campaignmember_detail"),
    path("campaign-members/<int:pk>/edit/", views.campaignmember_edit, name="campaignmember_edit"),
    path("campaign-members/<int:pk>/delete/", views.campaignmember_delete, name="campaignmember_delete"),
    path("campaign-members/<int:member_pk>/remove/", views.campaignmember_remove, name="campaignmember_remove"),

    # Email templates (1.3 Email Marketing)
    path("email-templates/", views.emailtemplate_list, name="emailtemplate_list"),
    path("email-templates/add/", views.emailtemplate_create, name="emailtemplate_create"),
    path("email-templates/<int:pk>/", views.emailtemplate_detail, name="emailtemplate_detail"),
    path("email-templates/<int:pk>/edit/", views.emailtemplate_edit, name="emailtemplate_edit"),
    path("email-templates/<int:pk>/delete/", views.emailtemplate_delete, name="emailtemplate_delete"),

    # Email campaigns / blasts (1.3 Email Marketing — drip + A/B + tracking)
    path("email-campaigns/", views.emailcampaign_list, name="emailcampaign_list"),
    path("email-campaigns/add/", views.emailcampaign_create, name="emailcampaign_create"),
    path("email-campaigns/<int:pk>/", views.emailcampaign_detail, name="emailcampaign_detail"),
    path("email-campaigns/<int:pk>/edit/", views.emailcampaign_edit, name="emailcampaign_edit"),
    path("email-campaigns/<int:pk>/delete/", views.emailcampaign_delete, name="emailcampaign_delete"),
    path("email-campaigns/<int:pk>/send/", views.emailcampaign_send, name="emailcampaign_send"),

    # Landing pages (1.3 Landing Pages & Forms)
    path("landing-pages/", views.landingpage_list, name="landingpage_list"),
    path("landing-pages/add/", views.landingpage_create, name="landingpage_create"),
    path("landing-pages/<int:pk>/", views.landingpage_detail, name="landingpage_detail"),
    path("landing-pages/<int:pk>/edit/", views.landingpage_edit, name="landingpage_edit"),
    path("landing-pages/<int:pk>/delete/", views.landingpage_delete, name="landingpage_delete"),
    path("landing-pages/<int:pk>/publish/", views.landingpage_publish, name="landingpage_publish"),
    path("p/<str:token>/", views.landing_public, name="landing_public"),  # public web-to-lead

    # Form submissions (1.3 — web-to-lead captures, read-mostly)
    path("form-submissions/", views.formsubmission_list, name="formsubmission_list"),
    path("form-submissions/<int:pk>/", views.formsubmission_detail, name="formsubmission_detail"),
    path("form-submissions/<int:pk>/delete/", views.formsubmission_delete, name="formsubmission_delete"),
    path("form-submissions/<int:pk>/convert/", views.formsubmission_convert, name="formsubmission_convert"),

    # Cases / Tickets (1.4 Case / Ticket Management)
    path("cases/", views.case_list, name="case_list"),
    path("cases/add/", views.case_create, name="case_create"),
    path("cases/track/<str:token>/", views.case_public, name="case_public"),  # public status page
    path("cases/<int:pk>/", views.case_detail, name="case_detail"),
    path("cases/<int:pk>/edit/", views.case_edit, name="case_edit"),
    path("cases/<int:pk>/delete/", views.case_delete, name="case_delete"),
    path("cases/<int:pk>/add-comment/", views.case_comment_add, name="case_comment_add"),

    # SLA policies (1.4)
    path("sla-policies/", views.slapolicy_list, name="slapolicy_list"),
    path("sla-policies/add/", views.slapolicy_create, name="slapolicy_create"),
    path("sla-policies/<int:pk>/", views.slapolicy_detail, name="slapolicy_detail"),
    path("sla-policies/<int:pk>/edit/", views.slapolicy_edit, name="slapolicy_edit"),
    path("sla-policies/<int:pk>/delete/", views.slapolicy_delete, name="slapolicy_delete"),

    # Knowledge base / Solutions (1.4)
    path("knowledge/", views.knowledgearticle_list, name="knowledgearticle_list"),
    path("knowledge/add/", views.knowledgearticle_create, name="knowledgearticle_create"),
    path("knowledge/<int:pk>/", views.knowledgearticle_detail, name="knowledgearticle_detail"),
    path("knowledge/<int:pk>/edit/", views.knowledgearticle_edit, name="knowledgearticle_edit"),
    path("knowledge/<int:pk>/delete/", views.knowledgearticle_delete, name="knowledgearticle_delete"),
    path("kb/<str:token>/", views.kb_public, name="kb_public"),                # public article page
    path("kb/<str:token>/helpful/", views.kb_helpful, name="kb_helpful"),      # public vote

    # KB categories (1.4)
    path("kb-categories/", views.kbcategory_list, name="kbcategory_list"),
    path("kb-categories/add/", views.kbcategory_create, name="kbcategory_create"),
    path("kb-categories/<int:pk>/", views.kbcategory_detail, name="kbcategory_detail"),
    path("kb-categories/<int:pk>/edit/", views.kbcategory_edit, name="kbcategory_edit"),
    path("kb-categories/<int:pk>/delete/", views.kbcategory_delete, name="kbcategory_delete"),

    # Customer portal access — admin mapping (1.4)
    path("portal-access/", views.customerportalaccess_list, name="customerportalaccess_list"),
    path("portal-access/add/", views.customerportalaccess_create, name="customerportalaccess_create"),
    path("portal-access/<int:pk>/", views.customerportalaccess_detail, name="customerportalaccess_detail"),
    path("portal-access/<int:pk>/edit/", views.customerportalaccess_edit, name="customerportalaccess_edit"),
    path("portal-access/<int:pk>/delete/", views.customerportalaccess_delete, name="customerportalaccess_delete"),

    # Customer self-service portal — customer-facing (1.4)
    path("portal/cases/", views.portal_case_list, name="portal_case_list"),
    path("portal/cases/new/", views.portal_case_create, name="portal_case_create"),
    path("portal/cases/<int:pk>/", views.portal_case_detail, name="portal_case_detail"),

    # Tasks (1.5 Task Management — to-dos + recurring tasks)
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/add/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),

    # Calendar events (1.5 Calendar Integration — meetings, invite links, ICS)
    path("calendar/", views.calendarevent_list, name="calendarevent_list"),
    path("calendar/add/", views.calendarevent_create, name="calendarevent_create"),
    path("calendar/<int:pk>/", views.calendarevent_detail, name="calendarevent_detail"),
    path("calendar/<int:pk>/edit/", views.calendarevent_edit, name="calendarevent_edit"),
    path("calendar/<int:pk>/delete/", views.calendarevent_delete, name="calendarevent_delete"),
    path("calendar/<int:event_pk>/add-attendee/", views.event_attendee_add, name="event_attendee_add"),
    path("calendar/attendees/<int:pk>/delete/", views.event_attendee_delete, name="event_attendee_delete"),
    path("invite/<str:token>/", views.event_invite, name="event_invite"),     # public RSVP page
    path("invite/<str:token>/ics/", views.event_ics, name="event_ics"),       # public .ics download

    # Communication logs (1.5 Email & Call Integration — calls + email/BCC sync)
    path("comms/", views.communicationlog_list, name="communicationlog_list"),
    path("comms/add/", views.communicationlog_create, name="communicationlog_create"),
    path("comms/<int:pk>/", views.communicationlog_detail, name="communicationlog_detail"),
    path("comms/<int:pk>/edit/", views.communicationlog_edit, name="communicationlog_edit"),
    path("comms/<int:pk>/delete/", views.communicationlog_delete, name="communicationlog_delete"),

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

    # ===== Module 1 Extension — Sub-modules 1.7–1.12 =========================

    # Expenses (1.7)
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/add/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/", views.expense_detail, name="expense_detail"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("expenses/<int:pk>/submit/", views.expense_submit, name="expense_submit"),
    path("expenses/<int:pk>/approve/", views.expense_approve, name="expense_approve"),
    path("expenses/<int:pk>/reject/", views.expense_reject, name="expense_reject"),

    # Invoicing (1.7) — DealInvoice wrappers over the accounting ledger + quote→invoice conversion
    path("deal-invoices/", views.dealinvoice_list, name="dealinvoice_list"),
    path("deal-invoices/add/", views.dealinvoice_create, name="dealinvoice_create"),
    path("deal-invoices/from-quote/<int:quote_pk>/", views.dealinvoice_from_quote, name="dealinvoice_from_quote"),
    path("deal-invoices/<int:pk>/", views.dealinvoice_detail, name="dealinvoice_detail"),
    path("deal-invoices/<int:pk>/edit/", views.dealinvoice_edit, name="dealinvoice_edit"),
    path("deal-invoices/<int:pk>/delete/", views.dealinvoice_delete, name="dealinvoice_delete"),

    # Payment Tracking (1.7) — receipts over ledger payments, with a printable receipt
    path("payment-receipts/", views.paymentreceipt_list, name="paymentreceipt_list"),
    path("payment-receipts/add/", views.paymentreceipt_create, name="paymentreceipt_create"),
    path("payment-receipts/<int:pk>/", views.paymentreceipt_detail, name="paymentreceipt_detail"),
    path("payment-receipts/<int:pk>/edit/", views.paymentreceipt_edit, name="paymentreceipt_edit"),
    path("payment-receipts/<int:pk>/delete/", views.paymentreceipt_delete, name="paymentreceipt_delete"),
    path("payment-receipts/<int:pk>/print/", views.paymentreceipt_print, name="paymentreceipt_print"),

    # Projects (1.8)
    path("projects/", views.crmproject_list, name="crmproject_list"),
    path("projects/add/", views.crmproject_create, name="crmproject_create"),
    path("projects/<int:pk>/", views.crmproject_detail, name="crmproject_detail"),
    path("projects/<int:pk>/edit/", views.crmproject_edit, name="crmproject_edit"),
    path("projects/<int:pk>/delete/", views.crmproject_delete, name="crmproject_delete"),
    path("opportunities/<int:pk>/to-project/", views.opportunity_to_project, name="opportunity_to_project"),

    # Milestones (1.8)
    path("milestones/", views.crmmilestone_list, name="crmmilestone_list"),
    path("milestones/add/", views.crmmilestone_create, name="crmmilestone_create"),
    path("milestones/<int:pk>/", views.crmmilestone_detail, name="crmmilestone_detail"),
    path("milestones/<int:pk>/edit/", views.crmmilestone_edit, name="crmmilestone_edit"),
    path("milestones/<int:pk>/delete/", views.crmmilestone_delete, name="crmmilestone_delete"),

    # Timesheets (1.8)
    path("timesheets/", views.timesheet_list, name="timesheet_list"),
    path("timesheets/add/", views.timesheet_create, name="timesheet_create"),
    path("timesheets/<int:pk>/", views.timesheet_detail, name="timesheet_detail"),
    path("timesheets/<int:pk>/edit/", views.timesheet_edit, name="timesheet_edit"),
    path("timesheets/<int:pk>/delete/", views.timesheet_delete, name="timesheet_delete"),
    path("timesheets/<int:pk>/submit/", views.timesheet_submit, name="timesheet_submit"),
    path("timesheets/<int:pk>/approve/", views.timesheet_approve, name="timesheet_approve"),
    path("timesheets/<int:pk>/reject/", views.timesheet_reject, name="timesheet_reject"),

    # Resource Allocation (1.8) — capacity bookings + workload board + Kanban
    path("resource-allocations/", views.resourceallocation_list, name="resourceallocation_list"),
    path("resource-allocations/add/", views.resourceallocation_create, name="resourceallocation_create"),
    path("resource-allocations/<int:pk>/", views.resourceallocation_detail, name="resourceallocation_detail"),
    path("resource-allocations/<int:pk>/edit/", views.resourceallocation_edit, name="resourceallocation_edit"),
    path("resource-allocations/<int:pk>/delete/", views.resourceallocation_delete, name="resourceallocation_delete"),
    path("workload/", views.resource_workload, name="resource_workload"),
    path("projects/board/", views.crmproject_board, name="crmproject_board"),
    path("milestones/<int:pk>/move/", views.crmmilestone_move, name="crmmilestone_move"),

    # Document templates (1.9)
    path("doc-templates/", views.doctemplate_list, name="doctemplate_list"),
    path("doc-templates/add/", views.doctemplate_create, name="doctemplate_create"),
    path("doc-templates/<int:pk>/", views.doctemplate_detail, name="doctemplate_detail"),
    path("doc-templates/<int:pk>/edit/", views.doctemplate_edit, name="doctemplate_edit"),
    path("doc-templates/<int:pk>/delete/", views.doctemplate_delete, name="doctemplate_delete"),

    # Contract documents + e-signature (1.9)
    path("contracts/", views.contractdocument_list, name="contractdocument_list"),
    path("contracts/add/", views.contractdocument_create, name="contractdocument_create"),
    path("contracts/<int:pk>/", views.contractdocument_detail, name="contractdocument_detail"),
    path("contracts/<int:pk>/edit/", views.contractdocument_edit, name="contractdocument_edit"),
    path("contracts/<int:pk>/delete/", views.contractdocument_delete, name="contractdocument_delete"),
    path("contracts/<int:pk>/add-signer/", views.contractdocument_add_signer, name="contractdocument_add_signer"),
    path("contracts/<int:pk>/remove-signer/<int:signer_pk>/", views.contractdocument_remove_signer, name="contractdocument_remove_signer"),
    path("sign/<str:token>/", views.sign_document, name="sign_document"),  # public

    # Workflow rules (1.10)
    path("workflows/", views.workflowrule_list, name="workflowrule_list"),
    path("workflows/add/", views.workflowrule_create, name="workflowrule_create"),
    path("workflows/<int:pk>/", views.workflowrule_detail, name="workflowrule_detail"),
    path("workflows/<int:pk>/edit/", views.workflowrule_edit, name="workflowrule_edit"),
    path("workflows/<int:pk>/delete/", views.workflowrule_delete, name="workflowrule_delete"),

    # Workflow logs (1.10, read-only)
    path("workflow-logs/", views.workflowlog_list, name="workflowlog_list"),
    path("workflow-logs/<int:pk>/", views.workflowlog_detail, name="workflowlog_detail"),

    # Approval requests (1.10)
    path("approvals/", views.approvalrequest_list, name="approvalrequest_list"),
    path("approvals/add/", views.approvalrequest_create, name="approvalrequest_create"),
    path("approvals/<int:pk>/", views.approvalrequest_detail, name="approvalrequest_detail"),
    path("approvals/<int:pk>/edit/", views.approvalrequest_edit, name="approvalrequest_edit"),
    path("approvals/<int:pk>/delete/", views.approvalrequest_delete, name="approvalrequest_delete"),
    path("approvals/<int:pk>/approve/", views.approvalrequest_approve, name="approvalrequest_approve"),
    path("approvals/<int:pk>/reject/", views.approvalrequest_reject, name="approvalrequest_reject"),

    # Onboarding plans + steps (1.11)
    path("onboarding/", views.onboardingplan_list, name="onboardingplan_list"),
    path("onboarding/add/", views.onboardingplan_create, name="onboardingplan_create"),
    path("onboarding/<int:pk>/", views.onboardingplan_detail, name="onboardingplan_detail"),
    path("onboarding/<int:pk>/edit/", views.onboardingplan_edit, name="onboardingplan_edit"),
    path("onboarding/<int:pk>/delete/", views.onboardingplan_delete, name="onboardingplan_delete"),
    path("onboarding/<int:pk>/add-step/", views.onboardingstep_add, name="onboardingstep_add"),
    path("onboarding/steps/<int:step_pk>/complete/", views.onboardingstep_complete, name="onboardingstep_complete"),
    path("onboarding/steps/<int:step_pk>/delete/", views.onboardingstep_delete, name="onboardingstep_delete"),

    # Health scores (1.11)
    path("health-scores/", views.healthscore_list, name="healthscore_list"),
    path("health-scores/add/", views.healthscore_create, name="healthscore_create"),
    path("health-scores/config/", views.health_config_edit, name="health_config_edit"),
    path("health-scores/<int:pk>/", views.healthscore_detail, name="healthscore_detail"),
    path("health-scores/<int:pk>/edit/", views.healthscore_edit, name="healthscore_edit"),
    path("health-scores/<int:pk>/delete/", views.healthscore_delete, name="healthscore_delete"),
    path("health-scores/<int:pk>/recompute/", views.recompute_health_score, name="recompute_health_score"),

    # Surveys (1.11)
    path("surveys/", views.survey_list, name="survey_list"),
    path("surveys/add/", views.survey_create, name="survey_create"),
    path("surveys/<int:pk>/", views.survey_detail, name="survey_detail"),
    path("surveys/<int:pk>/edit/", views.survey_edit, name="survey_edit"),
    path("surveys/<int:pk>/delete/", views.survey_delete, name="survey_delete"),
    path("surveys/<str:token>/respond/", views.survey_respond, name="survey_respond"),  # public

    # Product stock (1.12)
    path("stock/", views.productstock_list, name="productstock_list"),
    path("stock/add/", views.productstock_create, name="productstock_create"),
    path("stock/<int:pk>/", views.productstock_detail, name="productstock_detail"),
    path("stock/<int:pk>/edit/", views.productstock_edit, name="productstock_edit"),
    path("stock/<int:pk>/delete/", views.productstock_delete, name="productstock_delete"),

    # Purchase orders (1.12)
    path("purchase-orders/", views.crm_po_list, name="crm_po_list"),
    path("purchase-orders/add/", views.crm_po_create, name="crm_po_create"),
    path("purchase-orders/<int:pk>/", views.crm_po_detail, name="crm_po_detail"),
    path("purchase-orders/<int:pk>/edit/", views.crm_po_edit, name="crm_po_edit"),
    path("purchase-orders/<int:pk>/delete/", views.crm_po_delete, name="crm_po_delete"),
    path("purchase-orders/<int:pk>/add-line/", views.crm_po_add_line, name="crm_po_add_line"),
    path("purchase-orders/<int:pk>/remove-line/<int:line_pk>/", views.crm_po_remove_line, name="crm_po_remove_line"),
    path("purchase-orders/<int:pk>/receive/", views.crm_po_receive, name="crm_po_receive"),

    # Partner portal access — admin (1.12)
    path("partner-portal/", views.partnerportalaccess_list, name="partnerportalaccess_list"),
    path("partner-portal/add/", views.partnerportalaccess_create, name="partnerportalaccess_create"),
    path("partner-portal/<int:pk>/", views.partnerportalaccess_detail, name="partnerportalaccess_detail"),
    path("partner-portal/<int:pk>/edit/", views.partnerportalaccess_edit, name="partnerportalaccess_edit"),
    path("partner-portal/<int:pk>/delete/", views.partnerportalaccess_delete, name="partnerportalaccess_delete"),

    # Partner portal — partner-facing (1.12)
    path("portal/", views.portal_dashboard, name="portal_dashboard"),
    path("portal/orders/", views.portal_po_list, name="portal_po_list"),
    path("portal/stock/", views.portal_stock, name="portal_stock"),

    # ===== 1.6 Analytics & Reporting =====================================
    # Dashboards (saved per-user) + their live widgets
    path("dashboards/", views.dashboard_list, name="dashboard_list"),
    path("dashboards/add/", views.dashboard_create, name="dashboard_create"),
    path("dashboards/<int:pk>/", views.dashboard_detail, name="dashboard_detail"),
    path("dashboards/<int:pk>/edit/", views.dashboard_edit, name="dashboard_edit"),
    path("dashboards/<int:pk>/delete/", views.dashboard_delete, name="dashboard_delete"),
    path("dashboards/<int:dash_pk>/widgets/add/", views.widget_create, name="widget_create"),
    path("widgets/<int:pk>/edit/", views.widget_edit, name="widget_edit"),
    path("widgets/<int:pk>/delete/", views.widget_delete, name="widget_delete"),
    path("widgets/<int:pk>/move/<str:direction>/", views.widget_move, name="widget_move"),

    # Standard reports + point-in-time snapshots
    path("reports/", views.report_list, name="report_list"),
    path("reports/add/", views.report_create, name="report_create"),
    path("reports/<int:pk>/", views.report_detail, name="report_detail"),
    path("reports/<int:pk>/edit/", views.report_edit, name="report_edit"),
    path("reports/<int:pk>/delete/", views.report_delete, name="report_delete"),
    path("reports/<int:pk>/favorite/", views.report_favorite, name="report_favorite"),
    path("reports/<int:pk>/snapshot/", views.report_snapshot, name="report_snapshot"),
    path("snapshots/<int:pk>/", views.snapshot_detail, name="snapshot_detail"),
    path("snapshots/<int:pk>/delete/", views.snapshot_delete, name="snapshot_delete"),
]
