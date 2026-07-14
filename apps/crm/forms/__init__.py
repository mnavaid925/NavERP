"""CRM forms package — split from the former monolithic apps/crm/forms.py.

One sub-package per CRM sub-module (1.1-1.12), one module per entity (mirrors apps/crm/views/ and
apps/crm/models/). This __init__ re-exports every form, so ``from apps.crm.forms import LeadForm``
keeps working unchanged.
"""
# Re-export the shared toolkit so the package namespace matches the pre-split forms.py, which
# incidentally exposed everything it imported — ``apps/crm/tests/test_ext_security.py`` relies on
# ``from apps.crm.forms import MAX_UPLOAD_BYTES``.
from ._common import *  # noqa: F401,F403

# 1.1 Core Data Management
from .CoreData.Leads import (
    LeadForm,
)
from .CoreData.Accounts import (
    AccountForm,
)
from .CoreData.Contacts import (
    ContactForm,
)

# 1.2 Sales Force Automation
from .SalesForceAutomation.Opportunities import (
    OpportunityForm,
    OpportunitySplitForm,
)
from .SalesForceAutomation.Territories import (
    TerritoryForm,
)
from .SalesForceAutomation.Products import (
    ProductForm,
)
from .SalesForceAutomation.PriceBooks import (
    PriceBookForm,
)
from .SalesForceAutomation.Quotes import (
    QuoteForm,
    QuoteLineForm,
)
from .SalesForceAutomation.SalesQuotas import (
    SalesQuotaForm,
)

# 1.3 Marketing Automation
from .MarketingAutomation.Campaigns import (
    CampaignForm,
    CampaignMemberForm,
)
from .MarketingAutomation.EmailTemplates import (
    EmailTemplateForm,
)
from .MarketingAutomation.EmailCampaigns import (
    EmailCampaignForm,
)
from .MarketingAutomation.LandingPages import (
    LandingPageForm,
    PublicLeadForm,
)

# 1.4 Customer Service & Support
from .CustomerService.Cases import (
    CaseForm,
    CaseCommentForm,
)
from .CustomerService.KnowledgeBase import (
    KnowledgeArticleForm,
)
from .CustomerService.SlaPolicies import (
    SlaPolicyForm,
)
from .CustomerService.KbCategories import (
    KbCategoryForm,
)
from .CustomerService.CustomerPortalAccess import (
    CustomerPortalAccessForm,
)
from .CustomerService.PublicPages import (
    PublicSatisfactionForm,
    PublicCommentForm,
)

# 1.5 Activity & Communication Management
from .ActivityManagement.Tasks import (
    CrmTaskForm,
)
from .ActivityManagement.CalendarEvents import (
    CalendarEventForm,
    EventAttendeeForm,
    PublicRsvpForm,
)
from .ActivityManagement.CommunicationLogs import (
    CommunicationLogForm,
)

# 1.6 Analytics & Reporting
from .AnalyticsReporting.Dashboards import (
    AnalyticsDashboardForm,
)
from .AnalyticsReporting.Widgets import (
    DashboardWidgetForm,
)
from .AnalyticsReporting.Reports import (
    AnalyticsReportForm,
)

# 1.7 Finance & Billing Management
from .FinanceBilling.Expenses import (
    ExpenseForm,
)
from .FinanceBilling.DealInvoices import (
    DealInvoiceForm,
)
from .FinanceBilling.PaymentReceipts import (
    PaymentReceiptForm,
)

# 1.8 Project & Delivery Management
from .ProjectDelivery.Projects import (
    CrmProjectForm,
)
from .ProjectDelivery.Milestones import (
    CrmMilestoneForm,
)
from .ProjectDelivery.Timesheets import (
    TimesheetForm,
)
from .ProjectDelivery.ResourceAllocation import (
    ResourceAllocationForm,
)

# 1.9 Document & Contract Management
from .DocumentContract.DocTemplates import (
    DocTemplateForm,
)
from .DocumentContract.Contracts import (
    ContractDocumentForm,
    SignerRecordForm,
)
from .DocumentContract.DocumentVersions import (
    DocumentVersionForm,
)

# 1.10 Automation & Workflow Engine
from .AutomationWorkflow.WorkflowRules import (
    WorkflowRuleForm,
)
from .AutomationWorkflow.Webhooks import (
    WebhookForm,
)
from .AutomationWorkflow.Approvals import (
    ApprovalRequestForm,
)

# 1.11 Customer Success & Retention
from .CustomerSuccess.OnboardingPlans import (
    OnboardingPlanForm,
    OnboardingStepForm,
)
from .CustomerSuccess.OnboardingTemplates import (
    OnboardingTemplateForm,
    OnboardingTemplateStepForm,
)
from .CustomerSuccess.HealthScores import (
    HealthScoreForm,
    HealthScoreConfigForm,
)
from .CustomerSuccess.Surveys import (
    SurveyForm,
)

# 1.12 Inventory & Vendor Management
from .InventoryVendor.ProductStock import (
    ProductStockForm,
)
from .InventoryVendor.PurchaseOrders import (
    PurchaseOrderForm,
    PurchaseOrderLineForm,
)
from .InventoryVendor.PartnerPortalAccess import (
    PartnerPortalAccessForm,
)
